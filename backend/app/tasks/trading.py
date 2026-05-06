from __future__ import annotations

import asyncio
import datetime
from datetime import timedelta, timezone
from typing import Any, cast
import pyupbit
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.ml.feature_builder import build_features_from_market_data
from app.services.data_pipeline import HistoricalDataService
from app.services.trading.emergency_trader import EmergencyTrader
from app.services.notifications import Notifier
from app.trading.engine import TradeExecutor, TradingEngine
from app.models.trading import AutoTradingConfig, TradePosition
from app.trading.market_selector import MarketSelector

logger = get_logger(__name__)
settings = get_settings()

# 전역 인스턴스
market_selector = MarketSelector(top_k=5, min_volume=50_000_000_000)  # v6.0: Top 5 대형주만

# v6.0: 일일 손실/거래 횟수 추적 (자본 보존 안전장치)
_daily_pnl_krw: float = 0.0  # 일일 손익 (KRW)
_daily_trade_count: int = 0  # 일일 거래 횟수
_last_loss_time: float = 0.0  # 마지막 손절 시각 (timestamp)
_daily_reset_date: str = ""  # 일일 리셋 날짜
_initial_daily_balance: float = 0.0  # 당일 시작 잔고


def _reset_daily_counters_if_needed(current_balance: float = 0.0) -> None:
    """일일 카운터 리셋 (날짜 변경 시)"""
    global _daily_pnl_krw, _daily_trade_count, _daily_reset_date, _initial_daily_balance
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if _daily_reset_date != today:
        _daily_pnl_krw = 0.0
        _daily_trade_count = 0
        _daily_reset_date = today
        _initial_daily_balance = current_balance
        logger.info(f"📅 Daily counters reset. Starting balance: {current_balance:,.0f} KRW")


def _is_trading_allowed() -> tuple[bool, str]:
    """
    v6.0: 자본 보존 안전장치 체크
    - 일일 최대 손실 한도 초과 시 매매 중단
    - 손절 후 쿨다운 시간 미경과 시 매수 중단 (매도는 허용)
    - 일일 최대 거래 횟수 초과 시 매매 중단
    """
    import time
    global _daily_pnl_krw, _daily_trade_count, _last_loss_time, _initial_daily_balance
    
    # 1. 일일 최대 손실 한도
    if _initial_daily_balance > 0:
        daily_loss_pct = (_daily_pnl_krw / _initial_daily_balance) * 100
        if daily_loss_pct <= -settings.daily_max_loss_percent:
            return False, f"🚨 일일 최대 손실 한도 초과 ({daily_loss_pct:.1f}% <= -{settings.daily_max_loss_percent}%) - 매매 중단"
    
    # 2. 손절 후 쿨다운
    if _last_loss_time > 0:
        elapsed = time.time() - _last_loss_time
        cooldown = settings.cooldown_after_loss_minutes * 60
        if elapsed < cooldown:
            remaining = int((cooldown - elapsed) / 60)
            return False, f"⏳ 손절 후 쿨다운 중 ({remaining}분 남음) - 매수 중단 (매도는 허용)"
    
    # 3. 일일 최대 거래 횟수
    if _daily_trade_count >= settings.max_daily_trades:
        return False, f"🚫 일일 최대 거래 횟수 초과 ({_daily_trade_count}/{settings.max_daily_trades}) - 매매 중단"
    
    return True, "OK"


def _record_trade_result(pnl_krw: float) -> None:
    """거래 결과 기록"""
    import time
    global _daily_pnl_krw, _daily_trade_count, _last_loss_time
    _daily_pnl_krw += pnl_krw
    _daily_trade_count += 1
    if pnl_krw < 0:
        _last_loss_time = time.time()
        logger.warning(f"📉 손실 기록: {pnl_krw:,.0f} KRW (일일 누적: {_daily_pnl_krw:,.0f} KRW, 거래 {_daily_trade_count}회)")
    else:
        logger.info(f"📈 수익 기록: +{pnl_krw:,.0f} KRW (일일 누적: {_daily_pnl_krw:,.0f} KRW, 거래 {_daily_trade_count}회)")


async def _run_capital_preservation_cycle(
    db: Session,
    executor: TradeExecutor,
    markets: list[str],
    multi_tf_data_dict: dict,
    account_info: dict,
) -> None:
    """Deprecated path retained for backward compatibility. No-op."""
    logger.info("Capital preservation strategy path is deprecated; using LLM auto path.")
    return


async def _run_llm_autotrading_cycle(
    db: Session,
    engine: TradingEngine,
    executor: TradeExecutor,
    markets: list[str],
    multi_tf_data_dict: dict,
    account_info: dict,
) -> None:
    """Single-path LLM-driven auto trading cycle."""
    from app.trading.engine import TradeDecisionResult

    for market in markets:
        try:
            market_tf_data = multi_tf_data_dict.get(market, {})
            market_data = market_tf_data.get("minute60", [])
            if len(market_data) < 150:
                logger.warning("Insufficient data for %s: %s rows", market, len(market_data))
                continue

            features = build_features_from_market_data(market_data, market)
            decision = await engine.decide(db, market, features, account_info)

            if decision.action == "BUY":
                trading_ok, reason = _is_trading_allowed()
                if not trading_ok:
                    logger.warning("⛔ %s BUY blocked: %s", market, reason)
                    continue
                if account_info["open_positions"] >= settings.max_open_positions:
                    logger.info(
                        "⏸️ %s BUY skipped: max positions reached (%s/%s)",
                        market,
                        account_info["open_positions"],
                        settings.max_open_positions,
                    )
                    continue
                if decision.confidence < settings.min_confidence_for_trade:
                    logger.info(
                        "⏸️ %s BUY skipped: confidence %.1f%% < %.1f%%",
                        market,
                        decision.confidence * 100,
                        settings.min_confidence_for_trade * 100,
                    )
                    continue

            if decision.action == "HOLD":
                logger.info("⏸️ %s: HOLD - %s", market, decision.rationale[:120])
                continue

            if decision.action == "BUY":
                decision = TradeDecisionResult(
                    approved=True,
                    action="BUY",
                    market=decision.market,
                    confidence=decision.confidence,
                    rationale=f"LLM Auto: {decision.rationale}",
                    emergency=decision.emergency,
                    investment_ratio=min(decision.investment_ratio, settings.max_investment_ratio),
                    max_loss_acceptable=decision.max_loss_acceptable,
                    take_profit_target=decision.take_profit_target,
                )
            else:
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=decision.market,
                    confidence=decision.confidence,
                    rationale=f"LLM Auto: {decision.rationale}",
                    emergency=decision.emergency,
                    investment_ratio=1.0,
                    max_loss_acceptable=decision.max_loss_acceptable,
                    take_profit_target=decision.take_profit_target,
                )

            executor.execute(db, decision, account_info["available_balance"])
            logger.info(
                "🤖 LLM Auto %s %s (conf %.1f%%, ratio %.1f%%)",
                market,
                decision.action,
                decision.confidence * 100,
                decision.investment_ratio * 100,
            )

        except Exception as e:
            logger.error("LLM auto cycle error for %s: %s", market, e, exc_info=True)
            continue


async def check_and_manage_positions(db: Session, executor: TradeExecutor) -> None:
    """
    오픈 포지션의 Stop Loss / Take Profit 체크 및 실행
    
    v6.0 전략 전면 개정 (Conservative Capital Preservation):
    - 즉시 손절: -1.5% 이상 손실 시 무조건 청산
    - Hard Stop: -2.5% 절대 마지노선
    - Trailing Stop 3단계: +1% 본전 보존, +2% 수익 추적, +3% 타이트 추적
    - Rule No.1: 돈을 잃지 마라
    """
    from app.trading.engine import TradeDecisionResult
    
    positions = db.query(TradePosition).filter(TradePosition.status == "OPEN").all()
    if not positions:
        return

    logger.info(f"Checking {len(positions)} open positions for Stop Loss/Take Profit")
    
    markets = list(set([p.market for p in positions]))
    
    try:
        await asyncio.sleep(0.5) 
        
        current_prices_raw = pyupbit.get_current_price(cast(Any, markets))
        if isinstance(current_prices_raw, (float, int)):
            current_prices = {markets[0]: float(current_prices_raw)}
        elif isinstance(current_prices_raw, dict):
            current_prices = {k: float(v) for k, v in current_prices_raw.items()}
        elif current_prices_raw is None:
            logger.error("Failed to fetch current prices for position check")
            return
        else:
            current_prices = {}
            
        for pos in positions:
            market = pos.market
            current_price = current_prices.get(market)
            
            if not current_price:
                continue
            
            current_price = float(current_price)
            
            # PnL 계산
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price
            
            # --- [Rule No.1: 돈을 잃지 마라] v6.0 ---
            # 1. 즉시 손절: -1.5% (기존 -3% → -1.5%)
            if pnl_pct <= -0.015:
                logger.warning(f"🚨 LOSS CUT for {pos.market}: PnL {pnl_pct:.2%} <= -1.5%")
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=pos.market,
                    confidence=1.0,
                    rationale=f"v6.0 Rule No.1: Loss Cut at {pnl_pct:.1%} (limit: -1.5%)",
                    emergency=True,
                    investment_ratio=1.0
                )
                executor.execute(db, decision)
                pnl_krw = (current_price - pos.entry_price) * pos.size
                _record_trade_result(pnl_krw)
                await asyncio.sleep(1.0)
                continue
            
            # 2. Hard Stop: -2.5% 절대 마지노선 (기존 -4% → -2.5%)
            hard_stop_limit = -0.025
            if pnl_pct <= hard_stop_limit:
                logger.warning(f"🚨 HARD STOP for {pos.market}: PnL {pnl_pct:.2%} <= {hard_stop_limit:.2%}")
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=pos.market,
                    confidence=1.0,
                    rationale=f"Hard Stop Limit (PnL {pnl_pct:.1%})",
                    emergency=True,
                    investment_ratio=1.0
                )
                executor.execute(db, decision)
                pnl_krw = (current_price - pos.entry_price) * pos.size
                _record_trade_result(pnl_krw)
                await asyncio.sleep(1.0)
                continue
            
            # 3. v6.0 Improved Trailing Stop (3단계)
            # 단계1: +1% 이상 수익 → 본전(수수료 포함) 보존
            if current_price > pos.entry_price * 1.01:
                breakeven_stop = pos.entry_price * 1.003  # 본전 + 수수료
                if breakeven_stop > pos.stop_loss:
                    old_sl = pos.stop_loss
                    pos.stop_loss = breakeven_stop
                    db.commit()
                    logger.info(f"🟢 본전 보존: {pos.market} SL {old_sl:,.0f} → {pos.stop_loss:,.0f}")
            
            # 단계2: +2% 이상 수익 → 수익 추적 (고점 대비 -1.2%)
            if current_price > pos.entry_price * 1.02:
                trailing_stop_price = max(current_price * 0.988, pos.entry_price * 1.01)
                if trailing_stop_price > pos.stop_loss:
                    old_sl = pos.stop_loss
                    pos.stop_loss = trailing_stop_price
                    db.commit()
                    logger.info(f"📈 Trailing Stop: {pos.market} SL {old_sl:,.0f} → {pos.stop_loss:,.0f} (Price: {current_price:,.0f})")
            
            # 단계3: +3% 이상 수익 → 타이트 추적 (고점 대비 -0.8%)
            if current_price > pos.entry_price * 1.03:
                tight_trail = max(current_price * 0.992, pos.entry_price * 1.02)
                if tight_trail > pos.stop_loss:
                    old_sl = pos.stop_loss
                    pos.stop_loss = tight_trail
                    db.commit()
                    logger.info(f"💰 Tight Trail: {pos.market} SL {old_sl:,.0f} → {pos.stop_loss:,.0f}")

            # Stop Loss 체크
            if current_price <= pos.stop_loss:
                pnl_krw = (current_price - pos.entry_price) * pos.size
                logger.warning(f"🛑 Stop Loss: {pos.market} Current {current_price:,.0f} <= Stop {pos.stop_loss:,.0f}")
                
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=pos.market,
                    confidence=1.0,
                    rationale=f"Stop Loss Triggered (Entry: {pos.entry_price:,.0f}, Current: {current_price:,.0f})",
                    emergency=True,
                    investment_ratio=1.0
                )
                executor.execute(db, decision)
                _record_trade_result(pnl_krw)
                
            # Take Profit 체크
            elif current_price >= pos.take_profit:
                pnl_krw = (current_price - pos.entry_price) * pos.size
                logger.info(f"💰 Take Profit: {pos.market} Current {current_price:,.0f} >= Target {pos.take_profit:,.0f}")
                
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=pos.market,
                    confidence=1.0,
                    rationale=f"Take Profit (Entry: {pos.entry_price:,.0f}, Current: {current_price:,.0f}, +{pnl_pct:.1%})",
                    emergency=False,
                    investment_ratio=1.0
                )
                executor.execute(db, decision)
                _record_trade_result(pnl_krw)

            # Time Limit 체크
            elif settings.max_position_hold_minutes > 0:
                now = datetime.datetime.now(datetime.timezone.utc)
                entry_time = pos.created_at
                
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=datetime.timezone.utc)
                
                elapsed = now - entry_time
                limit = datetime.timedelta(minutes=settings.max_position_hold_minutes)
                
                if elapsed > limit:
                    logger.info(f"⏰ Time Limit Triggered for {pos.market}: Held for {elapsed} (> {settings.max_position_hold_minutes}m)")
                    
                    decision = TradeDecisionResult(
                        approved=True,
                        action="SELL",
                        market=pos.market,
                        confidence=1.0,
                        rationale=f"Time Limit Exceeded (>{settings.max_position_hold_minutes}m)",
                        emergency=False, 
                        investment_ratio=1.0
                    )
                    executor.execute(db, decision)
                
    except Exception as e:
        logger.error(f"Error managing positions: {e}", exc_info=True)


async def run_cycle() -> None:
    """
    Main Trading Cycle v6.0 - Conservative Capital Preservation
    
    [Philosophy v6.0] 자본 보존 최우선
    1. 일일 손실 한도/거래 횟수 체크
    2. 손절 후 쿨다운 (30분)
    3. 높은 신뢰도(75%+)에서만 진입
    4. 손익비 최소 1:2 (SL -1.5%, TP +3%)
    5. 최대 투자비율 25% (단일 거래)
    6. 페르소나: 매수 오버라이드 제거, 매도 거부권만 유지
    """
    logger.info("Starting trading cycle v6.0")
    # v6.0: 동적 마켓 선정 (Top 5 대형주만)
    markets = market_selector.get_top_volume_coins()
    
    # [Improvement] 보유 중인 코인도 분석 대상에 포함
    balances = []
    held_tickers = []
    db: Session | None = None
    try:
        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        if not balances:
            balances = []
        
        for b in balances:
            if b['currency'] == 'KRW': continue
            ticker = f"KRW-{b['currency']}"
            held_tickers.append(ticker)
            
            if ticker not in markets:
                markets.append(ticker)
                logger.info(f"➕ Adding held coin to analysis target: {ticker}")
                
    except Exception as e:
        logger.error(f"Failed to fetch balances for market Sync: {e}")
        balances = []
        held_tickers = []
        # 계속 진행 (기본 markets 만으로)

    logger.info(f"Selected Markets (including holdings): {markets}")
    
    data_service = HistoricalDataService(markets)
    
    # 시장별 멀티 타임프레임 데이터 가져오기 (1h, 15m, 5m)
    multi_tf_data_dict = await data_service.fetch_multi_timeframe()

    # Upbit 계정 정보 및 자산 계산
    try:
        # balances는 위에서 이미 가져왔으나, KRW 잔고 등 정확한 계산을 위해 재사용
        krw_balance = 0.0
        for b in balances:
            if b['currency'] == 'KRW':
                krw_balance = float(b['balance'])
                break
        
        # 원금과 현재 자산 계산
        total_value = krw_balance
        
        # DB 세션 미리 생성
        db = SessionLocal()
        
        # 현재가 조회 (보유 코인 가치 계산 및 포지션 동기화용)
        if held_tickers:
            current_prices_raw = pyupbit.get_current_price(cast(Any, held_tickers))
            if isinstance(current_prices_raw, (float, int)):
                current_prices = {held_tickers[0]: float(current_prices_raw)}
            elif isinstance(current_prices_raw, dict):
                current_prices = {k: float(v) for k, v in current_prices_raw.items()}
            elif current_prices_raw is None:
                current_prices = {}
            else:
                current_prices = {}
        else:
            current_prices = {}

        for b in balances:
            if b['currency'] != 'KRW':
                ticker = f"KRW-{b['currency']}"
                price = float(current_prices.get(ticker, 0))
                balance_val = float(b['balance']) * price
                total_value += balance_val
                
                # [Sync] DB에 없는 포지션이면 생성 (수동 매수 등)
                # 평가금액 5000원 이상만
                if balance_val > 5000:
                    existing_pos = db.query(TradePosition).filter(
                        TradePosition.market == ticker, 
                        TradePosition.status == "OPEN"
                    ).first()
                    
                    if not existing_pos:
                        avg_buy_price = float(b['avg_buy_price'])
                        pnl_pct = (price - avg_buy_price) / avg_buy_price if avg_buy_price > 0 else 0
                        
                        # [v5.1 개선] 손실 포지션 Sync 시 더 엄격한 Stop Loss 설정
                        # Rule No.1: 돈을 잃지 마라 - 이미 손실 중이면 더 이상 방치하지 않음
                        
                        if pnl_pct <= -0.025:  # 이미 2.5% 이상 손실 중 (기존 3% -> 2.5%)
                            # 즉시 청산 대상으로 마킹 (stop_loss를 현재가 위로 설정)
                            stop_loss = price * 1.001  # 현재가 바로 위 = 다음 체크에서 즉시 청산
                            logger.warning(f"🚨 CRITICAL: {ticker} already at {pnl_pct:.1%} loss! Marking for immediate sale")
                        elif pnl_pct <= -0.015:  # 1.5% ~ 2.5% 손실 중
                            stop_loss = price * 0.995  # 현재가 -0.5%로 매우 타이트하게
                            logger.warning(f"⚠️ Moderate loss detected for {ticker} ({pnl_pct:.1%}). Tight SL at current -0.5%")
                        elif pnl_pct < 0:  # 0% ~ 1.5% 손실 중
                            stop_loss = avg_buy_price * 0.98  # 평단가 -2%
                            logger.info(f"⚠️ Small loss for {ticker} ({pnl_pct:.1%}). SL at avg -2%")
                        else:  # 수익 중
                            # 수익 중이면 최소한 본전은 지키도록
                            stop_loss = max(avg_buy_price * 0.99, avg_buy_price * (1 - settings.stop_loss_percent / 100))
                            logger.info(f"✅ Profit position {ticker} ({pnl_pct:.1%}). Protecting gains")

                        take_profit = avg_buy_price * (1 + settings.take_profit_percent / 100)
                        
                        new_pos = TradePosition(
                            market=ticker,
                            size=float(b['balance']),
                            entry_price=avg_buy_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            status="OPEN"
                        )
                        db.add(new_pos)
                        db.commit()
                        logger.info(f"🔄 Synced external position to DB: {ticker} (Avg: {avg_buy_price:,.0f})")
        
        # 임시 세션 종료
        db.close()

        account_info = {
            "principal": total_value,  
            "available_balance": krw_balance,  
            "open_positions": len(held_tickers),
            "avg_return": 0.0, 
            "consecutive_losses": 0, 
        }
        logger.info(f"Account Info: Total={total_value:,.0f} KRW, Available={krw_balance:,.0f} KRW, Positions={account_info['open_positions']}")
        
        # v6.0: 일일 카운터 리셋 및 안전장치 체크
        _reset_daily_counters_if_needed(total_value)
        
    except Exception as e:
        logger.error(f"Failed to process account info: {e}")
        # db 세션 닫기
        if db is not None:
            db.close()
        return

    engine = TradingEngine(settings)
    executor = TradeExecutor(settings)
    
    db = SessionLocal()
    try:
        # 1. 기존 포지션 관리 (Stop Loss / Take Profit)
        await check_and_manage_positions(db, executor)

        if settings.llm_autotrading_enabled:
            await _run_llm_autotrading_cycle(
                db=db,
                engine=engine,
                executor=executor,
                markets=markets,
                multi_tf_data_dict=multi_tf_data_dict,
                account_info=account_info,
            )
            return

        # Fallback branch: keep single decision engine even if llm_autotrading_enabled is disabled.
        for market in markets:
            try:
                market_tf_data = multi_tf_data_dict.get(market, {})
                market_data = market_tf_data.get('minute60', [])
                if len(market_data) < 150:
                    continue

                features = build_features_from_market_data(market_data, market)
                decision = await engine.decide(db, market, features, account_info)
                if decision.approved:
                    executor.execute(db, decision, account_info["available_balance"])
            except Exception as e:
                logger.error("Error processing %s: %s", market, e, exc_info=True)
                continue
    finally:
        db.close()


async def run_surge_alert_loop() -> None:
    """Alert-only websocket loop for sudden surges. No auto-buy execution."""
    if not settings.surge_alert_enabled:
        logger.debug("surge alert disabled")
        return

    import time
    from app.services.data_pipeline import UpbitStream

    markets = market_selector.get_top_volume_coins()
    if not markets:
        markets = settings.tracked_markets

    stream = UpbitStream(markets)
    notifier = Notifier(settings)
    baseline: dict[str, tuple[float, float]] = {}
    last_alert: dict[str, float] = {}
    end_time = time.time() + 55

    logger.info(
        "Starting surge alert websocket loop: threshold=%.2f%%, window=%ss",
        settings.surge_alert_threshold_percent,
        settings.surge_alert_window_seconds,
    )

    try:
        async for tick in stream.ticker_stream():
            now = time.time()
            if now >= end_time:
                break

            base_price, base_ts = baseline.get(tick.market, (tick.price, now))
            if now - base_ts > settings.surge_alert_window_seconds:
                baseline[tick.market] = (tick.price, now)
                continue

            if base_price <= 0:
                baseline[tick.market] = (tick.price, now)
                continue

            change_pct = ((tick.price - base_price) / base_price) * 100
            if change_pct < settings.surge_alert_threshold_percent:
                continue

            # Liquidity filter: 24h accumulated trade value on ticker stream.
            if tick.volume < settings.surge_alert_min_volume_24h:
                continue

            prev = last_alert.get(tick.market, 0.0)
            if now - prev < settings.surge_alert_cooldown_seconds:
                continue

            msg = (
                f"{tick.market} surge {change_pct:.2f}% in ~{int(now - base_ts)}s\n"
                f"price={tick.price:,.0f}, 24h volume={tick.volume:,.0f}\n"
                "action policy: alert-only (no FOMO auto-buy)"
            )
            await notifier.send("SURGE ALERT", msg, level="WARNING")
            logger.warning("SURGE ALERT: %s", msg.replace("\n", " | "))

            last_alert[tick.market] = now
            baseline[tick.market] = (tick.price, now)

    except Exception as e:
        logger.error("surge alert loop error: %s", e, exc_info=True)


async def run_emergency_check() -> None:
    """
    긴급 거래 체크 (60초마다 실행)
    v6.0: 긴급 매도(SELL)만 허용 - 긴급 매수(BUY)는 FOMO 매수이므로 차단
    - 급락 시 보유 포지션 긴급 청산만 수행
    - 급등 시 매수하지 않음 (이것이 가장 큰 손실 원인이었음)
    """
    logger.debug("Starting emergency trading check (v6.0: SELL-only)")
    
    db: Session = SessionLocal()
    try:
        # 자동매매 활성화 여부 확인
        config = db.query(AutoTradingConfig).order_by(AutoTradingConfig.id.desc()).first()
        if not config or not config.is_active:
            logger.debug("Auto trading is not active, skipping emergency check")
            return
        
        # 보유 포지션 조회
        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        
        positions = []
        for balance in balances:
            if balance['currency'] != 'KRW':
                market = f"KRW-{balance['currency']}"
                positions.append({
                    'market': market,
                    'amount': float(balance['balance'])
                })
        
        # v6.0: 보유 포지션이 없으면 긴급 체크 불필요 (매수 안 하므로)
        if not positions:
            logger.debug("No open positions, skipping emergency check (v6.0: no emergency BUY)")
            return
        
        # 관심 마켓 (설정에서 가져오기)
        watch_markets = config.selected_markets if config.selected_markets else settings.tracked_markets
        
        # 긴급 거래 체크
        trader = EmergencyTrader()
        result = trader.check_all_markets(positions, watch_markets)
        
        # v6.0: 긴급 SELL만 실행, BUY는 차단
        sell_count = 0
        buy_blocked = 0
        for action_item in result.get('emergency_actions', []):
            market = action_item['market']
            action = action_item['action']
            reason = action_item['reason']
            
            # v6.0: BUY 차단 (FOMO 매수 방지)
            if action == "BUY":
                logger.warning(f"⛔ {market} 긴급 BUY 차단됨 (v6.0 FOMO 방지): {reason}")
                buy_blocked += 1
                continue
            
            # SELL만 실행
            trade_result = trader.execute_emergency_trade(market, action, reason)
            
            if trade_result.get('success'):
                logger.warning(f"✅ {market} 긴급 매도 실행됨: {reason}")
                # v6.0: 손실 기록
                _record_trade_result(-500)  # 긴급 매도는 보통 손실
                sell_count += 1
            else:
                logger.error(f"❌ {market} 긴급 매도 실패: {trade_result.get('error')}")
        
        if result['markets_checked'] > 0:
            logger.info(f"Emergency check v6.0: {result['markets_checked']} markets, {sell_count} sells, {buy_blocked} buys blocked")
            
    except Exception as e:
        logger.error(f"Error in emergency trading check: {e}", exc_info=True)
    finally:
        db.close()


async def run_tick_cycle() -> None:
    """
    Tick 단위 공격적 매매 (1분 단위)
    v6.0: 비활성화 - aggressive_trading_mode=False
    ML 신호만으로 검증 없이 매매하는 것이 주요 손실 원인이었음
    """
    logger.info("Tick trading legacy path retired. Using LLM auto trading path only.")
    return


async def run_pump_detection_loop() -> None:
    """
    실시간 모니터링 루프 (WebSocket 기반, 1분간 지속 실행) v5.0
    v6.0: 비활성화 - pump_detection_enabled=False
    급등 매수(FOMO)가 대규모 손실의 핵심 원인이었음
    """
    logger.info("Pump/momentum/reversal loop retired. LLM auto trading path is active.")
    return

