"""TradingEngine — the single source of trading truth in v5.0.

Responsibilities:
  1. For each market, read candles from MarketDataStore.
  2. Classify regime → pick strategy → produce a Signal.
  3. Manage existing positions (stops, targets, time, regime change).
  4. For BUY signals: run RiskGuardChain → size position → fire orders on
     both Paper and Live brokers (Live is no-op if disabled).
  5. Persist StrategySignal, RiskEvent, ShadowCompare rows.

Concurrency model:
  Designed to be called from a single asyncio loop (FastAPI lifespan) or from
  the Celery polling task as a fallback. Heavy work (DB / HTTP / pyupbit) is
  synchronous; the engine itself is not threadsafe.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from app.broker import Broker, PaperBroker, UpbitLiveBroker
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.marketdata import get_store, get_active_markets
from app.models import (
    PaperAccount, PaperPosition, RiskEvent, ShadowCompare, StrategySignal,
    TradeLog, TradePosition,
)
from app.risk import (
    RiskContext, RiskGuardChain, compute_position_size, get_kill_switch,
)
from app.risk.sizing import MIN_UPBIT_ORDER_KRW
from app.strategy import (
    MeanReversionStrategy, Regime, RegimeClassifier, Signal, TrendFollowingStrategy,
    HybridStrategy, AggressiveMomentumStrategy, DipBuyingStrategy,
)

logger = get_logger(__name__)


@dataclass
class EngineState:
    """In-memory engine state. Daily counters reset on UTC date boundary."""
    daily_realized_pnl_krw: float = 0.0
    daily_trade_count: int = 0
    last_loss_unix: float = 0.0
    daily_start_equity: float = 0.0
    daily_date: str = ""
    news_blackout_until_unix: float = 0.0
    last_regime: dict[str, str] = field(default_factory=dict)


class TradingEngine:
    def __init__(self):
        self.s = get_settings()
        self.store = get_store()
        self.classifier = RegimeClassifier()
        self.trend = TrendFollowingStrategy()
        self.range = MeanReversionStrategy()
        self.hybrid = HybridStrategy()  # v8.0: LLM + Mechanical hybrid
        self.momentum = AggressiveMomentumStrategy()  # v8.0: Momentum strategy
        self.dip = DipBuyingStrategy()  # v8.0: Dip buying strategy
        self.guards = RiskGuardChain()
        self.paper = PaperBroker()
        self.live = UpbitLiveBroker()
        self.state = EngineState()
        self._reset_daily_if_needed()

    # ====================================================================== entry
    def evaluate_all(self) -> None:
        """One full sweep across all active (dynamic) markets."""
        self._reset_daily_if_needed()
        if get_kill_switch().is_enabled():
            logger.warning("Kill switch ON — engine evaluate_all skipped")
            return
        for market in get_active_markets():
            try:
                self.evaluate_market(market)
            except Exception as e:
                logger.exception("evaluate_market(%s) error: %s", market, e)
        self._snapshot_shadow()

    # =================================================================== per-market
    def evaluate_market(self, market: str) -> Optional[Signal]:
        if self.store.staleness_sec(market) > 120:
            logger.debug("market %s stale=%ss → skip", market, self.store.staleness_sec(market))
            return None

        candles_1m = self.store.get_candles(market, "1m")
        candles_5m = self.store.get_candles(market, "5m")
        candles_15m = self.store.get_candles(market, "15m")

        # 1) Regime
        reading = self.classifier.classify(candles_1m)
        self.state.last_regime[market] = reading.regime.value

        # 2) Manage existing positions for both brokers
        self._manage_positions(market, reading.regime)

        # 3) Strategy selection
        strategy_mode = self.s.strategy_mode.lower()
        if strategy_mode == "off":
            return None
        chosen = None
        if strategy_mode == "trend":
            chosen = self.trend
        elif strategy_mode == "range":
            chosen = self.range
        elif strategy_mode == "hybrid":
            # v8.0: Use hybrid LLM + mechanical strategy
            chosen = self.hybrid
        elif strategy_mode == "momentum":
            chosen = self.momentum
        elif strategy_mode == "dip":
            chosen = self.dip
        else:  # auto - default to hybrid in v8.0
            # Hybrid strategy handles regime internally and uses LLM
            chosen = self.hybrid
            # Fallback to regime-based if hybrid not suitable
            if reading.regime == Regime.CHAOS:
                self._log_signal(market, reading.regime.value, "-", "HOLD",
                                 price=candles_1m[-1].close if candles_1m else 0.0,
                                 rationale=f"regime=CHAOS — too volatile, staying out")
                return None

        signal = chosen.evaluate(market, candles_1m, candles_5m, candles_15m)
        signal.regime = reading.regime.value

        # 4) Persist signal row
        self._log_signal(market, signal.regime, signal.strategy, signal.action,
                         signal.price, signal.atr, signal.stop_price,
                         signal.target_price, signal.rationale)

        if signal.action != "BUY":
            return signal

        # 5) Risk guards
        if self.paper.get_position(market) is not None or self.live.get_position(market) is not None:
            self._log_risk(market, "ConcurrencyGuard", "WARN", "position already open for market")
            return signal
        ctx = self._build_risk_context(market)
        allowed, results = self.guards.evaluate(ctx, signal)
        for r in results:
            if not r.allowed:
                self._log_risk(market, r.name, "BLOCK", r.reason)
                logger.info("[%s] BUY blocked by %s: %s", market, r.name, r.reason)
                return signal
        # 6) Sizing
        equity_for_sizing = self.paper.get_equity()
        available_live_krw: float | None = None
        if self.s.live_trading_enabled:
            live_equity = self.live.get_equity()
            if live_equity > 0:
                equity_for_sizing = live_equity
            else:
                self._log_risk(
                    market,
                    "LiveEquity",
                    "WARN",
                    "live equity unavailable; sizing from paper equity",
                )
            available_live_krw = self.live.get_available_krw()
            if available_live_krw < MIN_UPBIT_ORDER_KRW * (1.0 + self.s.fee_rate):
                self._log_risk(
                    market,
                    "LiveFunds",
                    "WARN",
                    f"live order skipped: available KRW {available_live_krw:.0f} below minimum order",
                )
        sz = compute_position_size(equity_for_sizing, signal.price, signal.stop_price)
        if sz.notional_krw <= 0:
            self._log_risk(market, "Sizing", "BLOCK", sz.reason)
            return signal
        # Portfolio-level exposure cap: total open notional must stay within
        # max_portfolio_exposure × equity so the dynamic basket cannot over-leverage.
        budget = equity_for_sizing * self.s.max_portfolio_exposure
        open_notional = self._current_open_notional()
        remaining = budget - open_notional
        if remaining < MIN_UPBIT_ORDER_KRW:
            self._log_risk(market, "PortfolioExposure", "BLOCK",
                           f"exposure {open_notional:.0f}/{budget:.0f} — no room")
            return signal
        if sz.notional_krw > remaining:
            sz.notional_krw = remaining
            sz.qty = sz.notional_krw / signal.price
        live_skip_reason = ""
        if available_live_krw is not None and available_live_krw < MIN_UPBIT_ORDER_KRW * (1.0 + self.s.fee_rate):
            live_skip_reason = f"insufficient live KRW: available={available_live_krw:.0f}"
        elif available_live_krw is not None:
            max_live_notional = available_live_krw / (1.0 + self.s.fee_rate)
            if sz.notional_krw > max_live_notional:
                if max_live_notional < MIN_UPBIT_ORDER_KRW:
                    self._log_risk(
                        market,
                        "LiveFunds",
                        "WARN",
                        f"live order skipped: sized order {sz.notional_krw:.0f} exceeds available KRW {available_live_krw:.0f}",
                    )
                    live_skip_reason = f"insufficient live KRW: available={available_live_krw:.0f}, required={sz.notional_krw:.0f}"
                else:
                    self._log_risk(
                        market,
                        "LiveFunds",
                        "WARN",
                        f"capped order from {sz.notional_krw:.0f} to {max_live_notional:.0f} by available KRW",
                    )
                    sz.notional_krw = max_live_notional
                    sz.qty = sz.notional_krw / signal.price

        # 7) Fire both brokers
        po = self.paper.submit_market_buy(
            market, sz.notional_krw,
            stop_loss=signal.stop_price, take_profit=signal.target_price,
            strategy=signal.strategy,
        )
        lo = None
        if self.s.live_trading_enabled and not live_skip_reason:
            lo = self.live.submit_market_buy(
                market, sz.notional_krw,
                stop_loss=signal.stop_price, take_profit=signal.target_price,
                strategy=signal.strategy,
            )
        elif not self.s.live_trading_enabled:
            live_skip_reason = "live disabled"
        self.state.daily_trade_count += 1
        self._log_trade(market, "BUY", sz.notional_krw,
                        rationale=f"{signal.strategy}/{signal.regime} {signal.rationale}",
                        paper_ok=po.success,
                        live_ok=bool(lo and lo.success),
                        live_err=(lo.error if lo else live_skip_reason))
        return signal

    # ==================================================== existing-position management
    def _manage_positions(self, market: str, regime: Regime) -> None:
        ticker = self.store.get_ticker(market)
        if ticker is None:
            return
        price = ticker.trade_price

        # Paper positions
        with SessionLocal() as db:
            paper_open = db.query(PaperPosition).filter(
                PaperPosition.market == market, PaperPosition.status == "OPEN"
            ).all()
            for p in paper_open:
                self._maybe_close_paper(db, p, price, regime)

        # Live positions
        with SessionLocal() as db:
            live_open = db.query(TradePosition).filter(
                TradePosition.market == market, TradePosition.status == "OPEN"
            ).all()
            for p in live_open:
                self._maybe_close_live(p, price, regime)

    def _maybe_close_paper(self, db: Session, p: PaperPosition, price: float, regime: Regime) -> None:
        reason = self._exit_reason(p.strategy, p.entry_price, p.stop_loss,
                                   p.take_profit, price, regime,
                                   created_at=p.created_at)
        if not reason:
            return
        order = self.paper.submit_market_sell(p.market, p.size)
        if order.success:
            pnl = (order.filled_price - p.entry_price) * order.filled_qty
            self.state.daily_realized_pnl_krw += pnl
            if pnl < 0:
                self.state.last_loss_unix = time.time()
            self._log_trade(p.market, "SELL", order.filled_notional_krw,
                            rationale=f"exit/{reason} pnl={pnl:.0f}",
                            paper_ok=True, live_ok=False, live_err="")

    def _maybe_close_live(self, p: TradePosition, price: float, regime: Regime) -> None:
        reason = self._exit_reason("", p.entry_price, p.stop_loss, p.take_profit,
                                   price, regime, created_at=p.created_at)
        if not reason:
            return
        order = self.live.submit_market_sell(p.market, p.size)
        # Note: live pnl tracking is approximate without per-trade fill detail
        if order.success:
            pnl = (order.filled_price - p.entry_price) * order.filled_qty
            self.state.daily_realized_pnl_krw += pnl
            if pnl < 0:
                self.state.last_loss_unix = time.time()
            self._log_trade(p.market, "SELL", order.filled_notional_krw,
                            rationale=f"live exit/{reason} pnl={pnl:.0f}",
                            paper_ok=False, live_ok=True, live_err="")

    def _exit_reason(self, strategy: str, entry: float, stop: float, target: float,
                     price: float, regime: Regime, created_at: dt.datetime) -> str:
        if entry <= 0:
            return ""
        # 1) hard stop
        if stop and price <= stop:
            return f"stop@{stop:.2f}"
        # 2) target
        if target and price >= target:
            return f"target@{target:.2f}"
        # 3) time-based by strategy
        now = dt.datetime.now(dt.timezone.utc)
        ca = created_at if created_at.tzinfo else created_at.replace(tzinfo=dt.timezone.utc)
        elapsed_min = (now - ca).total_seconds() / 60.0
        if strategy == "trend_following" and elapsed_min > 240:
            return "time>240m"
        if strategy == "mean_reversion" and elapsed_min > 90:
            return "time>90m"
        if strategy == "hybrid_v8" and elapsed_min > 180:
            return "time>180m"
        if strategy == "aggressive_momentum" and elapsed_min > 60:
            return "time>60m"
        if strategy == "dip_buying" and elapsed_min > 240:
            return "time>240m"
        if not strategy and elapsed_min > 240:
            return "time>240m"
        # 4) regime change — exit if market becomes chaotic
        if regime == Regime.CHAOS:
            return f"regime→CHAOS"
        if strategy == "trend_following" and regime not in (Regime.TREND,):
            return f"regime→{regime.value}"
        if strategy == "mean_reversion" and regime not in (Regime.RANGE,):
            return f"regime→{regime.value}"
        return ""

    # ============================================================== risk context
    def _current_open_notional(self) -> float:
        """Sum of open paper-position notional (canonical exposure basis)."""
        try:
            with SessionLocal() as db:
                rows = db.query(PaperPosition).filter(PaperPosition.status == "OPEN").all()
                return float(sum((p.size or 0.0) * (p.entry_price or 0.0) for p in rows))
        except Exception as e:  # noqa
            logger.warning("current_open_notional failed: %s", e)
            return 0.0

    def _build_risk_context(self, market: str) -> RiskContext:
        equity = self.paper.get_equity()  # use paper as canonical equity
        if self.state.daily_start_equity == 0:
            self.state.daily_start_equity = equity
        if equity > 0 and self.state.daily_start_equity > 0:
            pnl_pct = (equity - self.state.daily_start_equity) / self.state.daily_start_equity
        else:
            pnl_pct = 0.0
        # open positions across both
        open_count = 0
        with SessionLocal() as db:
            open_count = (
                db.query(PaperPosition).filter(PaperPosition.status == "OPEN").count()
                + db.query(TradePosition).filter(TradePosition.status == "OPEN").count()
            )
        ob = self.store.get_orderbook(market)
        t = self.store.get_ticker(market)
        return RiskContext(
            equity_krw=equity,
            open_positions=open_count,
            daily_realized_pnl_pct=pnl_pct,
            daily_trade_count=self.state.daily_trade_count,
            last_loss_unix=self.state.last_loss_unix,
            spread_pct=ob.spread_pct if ob else 1.0,
            acc_trade_price_24h=t.acc_trade_price_24h if t else 0.0,
            news_blackout_until_unix=self.state.news_blackout_until_unix,
        )

    # =================================================================== persistence
    def _log_signal(self, market: str, regime: str, strategy: str, action: str,
                    price: float, atr: float = 0.0, stop_price: float = 0.0,
                    target_price: float = 0.0, rationale: str = "") -> None:
        try:
            with SessionLocal() as db:
                row = StrategySignal(
                    market=market, regime=regime, strategy=strategy, action=action,
                    price=price, atr=atr, stop_price=stop_price, target_price=target_price,
                    rationale=rationale,
                )
                db.add(row); db.commit()
        except Exception as e:
            logger.warning("log_signal failed: %s", e)

    def _log_risk(self, market: str | None, guard: str, severity: str, message: str) -> None:
        try:
            with SessionLocal() as db:
                db.add(RiskEvent(market=market, guard=guard, severity=severity, message=message))
                db.commit()
        except Exception as e:
            logger.warning("log_risk failed: %s", e)

    def _log_trade(self, market: str, side: str, amount: float, rationale: str,
                   *, paper_ok: bool, live_ok: bool, live_err: str) -> None:
        try:
            with SessionLocal() as db:
                ctx = {"paper_ok": paper_ok, "live_ok": live_ok}
                if live_err:
                    ctx["live_err"] = live_err
                db.add(TradeLog(market=market, side=side, amount=amount,
                                reason=rationale[:120], context=ctx))
                db.commit()
        except Exception as e:
            logger.warning("log_trade failed: %s", e)

    def _snapshot_shadow(self) -> None:
        try:
            paper_eq = self.paper.get_equity()
            live_eq = self.live.get_equity() if self.s.live_trading_enabled else 0.0
            with SessionLocal() as db:
                paper_open = db.query(PaperPosition).filter(PaperPosition.status == "OPEN").count()
                live_open = db.query(TradePosition).filter(TradePosition.status == "OPEN").count()
                pnl_pct = 0.0
                if self.state.daily_start_equity > 0:
                    pnl_pct = (paper_eq - self.state.daily_start_equity) / self.state.daily_start_equity
                db.add(ShadowCompare(
                    paper_equity=paper_eq, live_equity=live_eq,
                    paper_open_positions=paper_open, live_open_positions=live_open,
                    daily_pnl_pct=pnl_pct,
                ))
                db.commit()
        except Exception as e:
            logger.warning("snapshot_shadow failed: %s", e)

    # ===================================================================== daily reset
    def _reset_daily_if_needed(self) -> None:
        today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        if self.state.daily_date != today:
            self.state.daily_date = today
            self.state.daily_trade_count = 0
            self.state.daily_realized_pnl_krw = 0.0
            self.state.last_loss_unix = 0.0
            self.state.daily_start_equity = self.paper.get_equity()
            logger.info("Daily counters reset. start_equity=%.0f", self.state.daily_start_equity)


_ENGINE: Optional[TradingEngine] = None


def get_engine() -> TradingEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = TradingEngine()
    return _ENGINE
