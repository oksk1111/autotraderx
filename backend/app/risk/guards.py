"""Risk guards. Each guard inspects RiskContext and either allows or blocks a BUY.

All guards are pure functions; state lives in `RiskContext`. The TradingEngine
builds the context once per evaluation tick.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

from app.core.config import get_settings
from app.core.logging import get_logger
from app.strategy.base import Signal
from .kill_switch import get_kill_switch

logger = get_logger(__name__)


@dataclass
class RiskContext:
    equity_krw: float
    open_positions: int
    daily_realized_pnl_pct: float        # negative = loss
    daily_trade_count: int
    last_loss_unix: float                # 0 if no loss today
    spread_pct: float                    # market spread
    acc_trade_price_24h: float           # liquidity proxy
    news_blackout_until_unix: float = 0.0
    now_unix: float = field(default_factory=time.time)


@dataclass
class GuardResult:
    allowed: bool
    name: str
    reason: str = ""


# -- individual guards --------------------------------------------------------

class KillSwitchGuard:
    name = "KillSwitch"
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        ks = get_kill_switch()
        if ks.is_enabled():
            return GuardResult(False, self.name, "kill switch is ON")
        return GuardResult(True, self.name)


class DailyLossGuard:
    name = "DailyLoss"
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        s = get_settings()
        if ctx.daily_realized_pnl_pct <= -abs(s.daily_loss_limit):
            return GuardResult(False, self.name,
                               f"daily PnL {ctx.daily_realized_pnl_pct:.2%} <= -{s.daily_loss_limit:.0%}")
        return GuardResult(True, self.name)


class MaxDailyTradesGuard:
    name = "MaxDailyTrades"
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        s = get_settings()
        if ctx.daily_trade_count >= s.max_daily_trades:
            return GuardResult(False, self.name,
                               f"daily trades {ctx.daily_trade_count}/{s.max_daily_trades}")
        return GuardResult(True, self.name)


class ConcurrencyGuard:
    name = "Concurrency"
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        s = get_settings()
        if ctx.open_positions >= s.max_open_positions:
            return GuardResult(False, self.name,
                               f"open positions {ctx.open_positions}/{s.max_open_positions}")
        return GuardResult(True, self.name)


class CooldownGuard:
    name = "Cooldown"
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        s = get_settings()
        if ctx.last_loss_unix <= 0:
            return GuardResult(True, self.name)
        cd = s.cooldown_after_loss_minutes * 60
        elapsed = ctx.now_unix - ctx.last_loss_unix
        if elapsed < cd:
            return GuardResult(False, self.name,
                               f"cooldown {int((cd - elapsed)/60)}m remaining")
        return GuardResult(True, self.name)


class FeeViabilityGuard:
    name = "FeeViability"
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        s = get_settings()
        if signal.price <= 0 or signal.target_price <= 0:
            return GuardResult(True, self.name)  # nothing to check for non-tp signals
        expected_tp_pct = (signal.target_price - signal.price) / signal.price
        cost = (s.fee_rate * 2.0) + s.slippage_est
        if expected_tp_pct < cost * 1.5:
            return GuardResult(False, self.name,
                               f"target {expected_tp_pct:.3%} < 1.5×cost {cost*1.5:.3%}")
        return GuardResult(True, self.name)


class LiquidityGuard:
    name = "Liquidity"
    def __init__(self, min_24h_quote: float = 50_000_000_000.0, max_spread_pct: float = 0.003):
        self.min_24h_quote = min_24h_quote
        self.max_spread_pct = max_spread_pct
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        if ctx.acc_trade_price_24h < self.min_24h_quote:
            return GuardResult(False, self.name,
                               f"24h volume {ctx.acc_trade_price_24h:,.0f} < {self.min_24h_quote:,.0f}")
        if ctx.spread_pct > self.max_spread_pct:
            return GuardResult(False, self.name,
                               f"spread {ctx.spread_pct:.3%} > {self.max_spread_pct:.3%}")
        return GuardResult(True, self.name)


class NewsBlackoutGuard:
    name = "NewsBlackout"
    def check(self, ctx: RiskContext, signal: Signal) -> GuardResult:
        if ctx.news_blackout_until_unix > ctx.now_unix:
            remaining = int(ctx.news_blackout_until_unix - ctx.now_unix)
            return GuardResult(False, self.name, f"news blackout {remaining}s remain")
        return GuardResult(True, self.name)


# -- chain --------------------------------------------------------------------

class RiskGuardChain:
    """Runs all guards in order. Returns first blocker (if any)."""

    def __init__(self, guards: Optional[Iterable] = None):
        self.guards = list(guards) if guards else [
            KillSwitchGuard(),
            DailyLossGuard(),
            MaxDailyTradesGuard(),
            ConcurrencyGuard(),
            CooldownGuard(),
            LiquidityGuard(),
            FeeViabilityGuard(),
            NewsBlackoutGuard(),
        ]

    def evaluate(self, ctx: RiskContext, signal: Signal) -> Tuple[bool, List[GuardResult]]:
        results: List[GuardResult] = []
        for g in self.guards:
            r = g.check(ctx, signal)
            results.append(r)
            if not r.allowed:
                return False, results
        return True, results
