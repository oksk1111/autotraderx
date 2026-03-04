from __future__ import annotations

import asyncio
import json
import datetime
from datetime import timedelta, timezone
import websockets
import pyupbit
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis_client
from app.db.session import SessionLocal
from app.ml.feature_builder import build_features_from_market_data, calculate_technical_indicators
from app.services.data_pipeline import HistoricalDataService
from app.services.trading.emergency_trader import EmergencyTrader
from app.trading.engine import TradeExecutor, TradingEngine
from app.trading.enhanced_engine import get_enhanced_engine
from app.models.trading import AutoTradingConfig, TradePosition
from app.trading.market_selector import MarketSelector
from app.trading.breakout_strategy import BreakoutTradingStrategy
from app.trading.personas import PersonaManager

logger = get_logger(__name__)
settings = get_settings()

# 전역 인스턴스
market_selector = MarketSelector(top_k=5, min_volume=50_000_000_000)  # v6.0: Top 5 대형주만
breakout_strategy = BreakoutTradingStrategy()

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
        
        current_prices = pyupbit.get_current_price(markets)
        if isinstance(current_prices, (float, int)):
            current_prices = {markets[0]: current_prices}
        elif current_prices is None:
            logger.error("Failed to fetch current prices for position check")
            return
            
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
        db: Session = SessionLocal()
        
        # 현재가 조회 (보유 코인 가치 계산 및 포지션 동기화용)
        if held_tickers:
            current_prices = pyupbit.get_current_price(held_tickers)
            if isinstance(current_prices, (float, int)):
                current_prices = {held_tickers[0]: current_prices}
            elif current_prices is None:
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
        if 'db' in locals(): db.close()
        return

    engine = TradingEngine(settings)
    executor = TradeExecutor(settings)
    
    # Enhanced Engine (Hybrid + MultiTF) 사용
    enhanced_engine = get_enhanced_engine()

    db: Session = SessionLocal()
    try:
        # 1. 기존 포지션 관리 (Stop Loss / Take Profit)
        await check_and_manage_positions(db, executor)
        
        for market in markets:
            try:
                # 시장 데이터를 ML 입력 특징으로 변환
                market_tf_data = multi_tf_data_dict.get(market, {})
                market_data = market_tf_data.get('minute60', [])
                
                if len(market_data) < 150:
                    logger.warning(f"Insufficient data for {market}: {len(market_data)} rows (need 150+)")
                    continue
                
                # Enhanced Engine 사용 가능 여부 확인
                if enhanced_engine.is_available():
                    # market_data를 DataFrame으로 변환
                    import pandas as pd
                    df = pd.DataFrame(market_data)
                    
                    # 'index' 컬럼 제거 (pyupbit reset_index()에서 추가된 불필요한 컬럼)
                    if 'index' in df.columns:
                        df = df.drop(columns=['index'])
                        logger.debug(f"Removed 'index' column from {market} market data")
                    
                    # 기술적 지표 추가 (CRITICAL FIX for RL Agent & Hybrid Engine)
                    try:
                        df = calculate_technical_indicators(df)
                        # NaN 값 처리 (앞부분 데이터 부족으로 인한 NaN은 제거하거나 채움)
                        df = df.bfill().ffill().fillna(0)
                    except Exception as e:
                        logger.error(f"Failed to calculate indicators for {market}: {e}")
                        continue

                    # Multi-timeframe 데이터 준비
                    multi_tf_dfs = {}
                    for interval, data in market_tf_data.items():
                        if data:
                            tf_df = pd.DataFrame(data)
                            if 'index' in tf_df.columns:
                                tf_df = tf_df.drop(columns=['index'])
                            multi_tf_dfs[interval] = tf_df

                    # Enhanced Engine으로 거래 신호 생성 (Hybrid + MultiTF)
                    action, confidence, details = enhanced_engine.get_enhanced_signal(market, df, multi_tf_data=multi_tf_dfs)
                    
                    # [Persona Strategy Integration] v6.0: 매도 거부권만 유지, 매수 오버라이드 제거
                    try:
                        persona_mgr = PersonaManager()
                        p_decisions = persona_mgr.evaluate_all(market, df)
                        
                        # [Dashboard Update] Save Persona Analysis to Redis
                        try:
                            rd = get_redis_client()
                            if rd:
                                rd.hset("persona_status", market, json.dumps(p_decisions))
                        except Exception as re:
                            logger.error(f"Redis save failed: {re}")
                        
                        best_sell = max([d for d in p_decisions if d['action'] == 'SELL'], key=lambda x: x['confidence'], default=None)
                        
                        # v6.0: 페르소나 매수 오버라이드 완전 제거 (FOMO 방지)
                        # HOLD는 HOLD로 유지. 엔진이 확신할 때만 매수.
                        
                        if action == "HOLD" and best_sell and best_sell['confidence'] >= 0.7:
                            # 매도 신호가 있으면 HOLD를 SELL로 전환 (리스크 관리만)
                            action = "SELL"
                            confidence = best_sell['confidence']
                            details['rationale'] = f"Persona Risk Exit ({best_sell['persona']}): {best_sell['reason']}"
                            logger.info(f"🎭 Persona Risk Exit: {market} by {best_sell['persona']}")
                                
                        elif action == "BUY":
                            # v6.0: 매수 신호가 떴을 때 페르소나 매도 거부권 강화 (0.85→0.70)
                            if best_sell and best_sell['confidence'] >= 0.70:
                                action = "HOLD"
                                details['rationale'] = f"Persona Veto ({best_sell['persona']}): {best_sell['reason']}"
                                logger.warning(f"🎭 Persona Veto: Blocking BUY for {market} due to {best_sell['persona']}")
                                
                    except Exception as pe:
                        logger.error(f"Persona evaluation failed for {market}: {pe}")

                    # [Trend Review] v6.0: 손실 -1.5%에서 즉시 청산 (기존 -3%)
                    current_pos = db.query(TradePosition).filter(
                        TradePosition.market == market,
                        TradePosition.status == "OPEN"
                    ).first()

                    if current_pos and (action == "HOLD" or (action == "BUY" and confidence < 0.75)):
                        try:
                            current_price = df.iloc[-1]['close']
                            entry_price = current_pos.entry_price
                            if entry_price > 0:
                                pnl_pct = (current_price - entry_price) / entry_price
                                
                                # v6.0: -1.5% 이상 손실 + 강한 상승 추세 아님 → 즉시 청산
                                if pnl_pct < -0.015:
                                    logger.info(f"📉 Trend Review: {market} PnL {pnl_pct:.2%} & Signal is {action}({confidence:.2f}). Cutting Loss.")
                                    action = "SELL"
                                    confidence = 0.95
                                    details['rationale'] = f"v6.0 Trend Review: Loss ({pnl_pct:.1%}) without strong uptrend."
                        except Exception as e:
                            logger.error(f"Error reviewing trend for {market}: {e}")

                    if action != "HOLD":
                        # v6.0: 자본 보존 안전장치 체크 (매수만 차단, 매도는 항상 허용)
                        if action == "BUY":
                            trading_ok, reason = _is_trading_allowed()
                            if not trading_ok:
                                logger.warning(f"⛔ {market} BUY blocked: {reason}")
                                action = "HOLD"
                            
                            # v6.0: 최소 신뢰도 체크 (75% 이상만 매수)
                            elif confidence < settings.min_confidence_for_trade:
                                logger.info(f"⏸️ {market} BUY skipped: confidence {confidence:.1%} < {settings.min_confidence_for_trade:.1%}")
                                action = "HOLD"
                            
                            # v6.0: 최대 포지션 수 체크
                            elif account_info["open_positions"] >= settings.max_open_positions:
                                logger.info(f"⏸️ {market} BUY skipped: max positions reached ({account_info['open_positions']}/{settings.max_open_positions})")
                                action = "HOLD"
                        
                    if action != "HOLD":
                        # v6.0: 보수적 투자 비율 (기존의 절반 이하)
                        if confidence >= 0.90:
                            investment_ratio = 0.25  # 최고: 25% (기존 40%)
                        elif confidence >= 0.85:
                            investment_ratio = 0.20  # 높음: 20% (기존 30%)
                        elif confidence >= 0.80:
                            investment_ratio = 0.15  # 양호: 15% (기존 25%)
                        elif confidence >= 0.75:
                            investment_ratio = 0.10  # 최소: 10% (기존 15%)
                        else:
                            investment_ratio = 0.07  # 관망: 7%
                        
                        # 절대 상한 적용
                        investment_ratio = min(investment_ratio, settings.max_investment_ratio)
                        
                        # SELL은 전량 매도
                        if action == "SELL":
                            investment_ratio = 1.0
                        
                        # v6.0: SL/TP 고정 (ATR 과신 방지, 확실한 손익비 1:2)
                        stop_loss_pct = 0.015   # -1.5% 고정
                        take_profit_pct = 0.03  # +3.0% 고정
                        
                        # ATR 기반 미세 조정 (SL은 더 좁힐 수는 있지만 넓힐 수 없음)
                        atr = df.iloc[-1].get('atr', 0)
                        current_price = df.iloc[-1].get('close', 0)
                        if atr > 0 and current_price > 0:
                            atr_based_sl = min((atr * 1.0 / current_price), 0.015)  # ATR 1배, 최대 1.5%
                            atr_based_tp = min((atr * 2.5 / current_price), 0.05)    # ATR 2.5배, 최대 5%
                            stop_loss_pct = max(atr_based_sl, 0.008)  # 최소 0.8%
                            take_profit_pct = max(atr_based_tp, 0.025)  # 최소 2.5%
                            
                            # v6.0: 손익비 최소 1:1.5 보장
                            if take_profit_pct / stop_loss_pct < 1.5:
                                take_profit_pct = stop_loss_pct * 2.0
                        
                        # TradeDecisionResult 생성
                        from app.trading.engine import TradeDecisionResult
                        decision = TradeDecisionResult(
                            approved=True,
                            action=action,
                            market=market,
                            confidence=confidence,
                            rationale=f"Enhanced Engine: {details.get('rationale', 'Multi-layer signal')}",
                            emergency=False,
                            investment_ratio=investment_ratio,
                            max_loss_acceptable=stop_loss_pct,
                            take_profit_target=take_profit_pct,
                        )
                        
                        logger.info(f"🚀 Enhanced: {market} {action} ({confidence:.1%}) SL:{stop_loss_pct:.1%}/TP:{take_profit_pct:.1%} - {details.get('rationale', '')[:60]}")
                    else:
                        # HOLD 신호
                        from app.trading.engine import TradeDecisionResult
                        decision = TradeDecisionResult(
                            approved=False,
                            action="HOLD",
                            market=market,
                            confidence=confidence,
                            rationale=details.get('rationale', 'Enhanced Engine: No strong signal'),
                            emergency=False,
                            investment_ratio=0.0,
                            max_loss_acceptable=0.015,
                            take_profit_target=0.03,
                        )
                        logger.debug(f"⏸️ Enhanced: {market} HOLD ({confidence:.1%})")
                else:
                    # Enhanced Engine 사용 불가 시 기존 ML 방식 사용
                    # 특징 생성
                    features = build_features_from_market_data(market_data, market)
                    
                    # 거래 결정
                    decision = await engine.decide(db, market, features, account_info)
                    
                    # 결정 로깅
                    if decision.approved:
                        logger.info(f"📝 {market}: {decision.action} (투자비율: {decision.investment_ratio*100:.0f}%) - {decision.rationale[:100]}")
                    else:
                        logger.info(f"⏸️ {market}: HOLD - {decision.rationale[:100]}")
                
                # 거래 실행
                executor.execute(db, decision, account_info["available_balance"])
                
            except Exception as e:
                logger.error(f"Error processing {market}: {e}", exc_info=True)
                continue
    finally:
        db.close()


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
    if not settings.aggressive_trading_mode:
        logger.debug("⛔ Tick trading disabled (v6.0: aggressive_trading_mode=False)")
        return
    
    logger.debug("🚀 Starting tick trading cycle")
    
    db: Session = SessionLocal()
    try:
        # 자동매매 활성화 여부 확인
        config = db.query(AutoTradingConfig).order_by(AutoTradingConfig.id.desc()).first()
        if not config or not config.is_active:
            logger.debug("Auto trading is not active, skipping tick cycle")
            return
        
        # Upbit 계정 정보 가져오기
        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        krw_balance = float(upbit.get_balance("KRW") or 0)  # type: ignore
        
        # 현재 포지션 수 확인
        open_positions = len([b for b in balances if b['currency'] != 'KRW'])
        
        # 최대 포지션 수 제한 체크
        if open_positions >= settings.tick_max_positions:
            logger.debug(f"Max positions reached ({open_positions}/{settings.tick_max_positions}), skipping tick cycle")
            return
        
        # 원금과 현재 자산 계산
        total_value = krw_balance
        for balance in balances:
            if balance['currency'] != 'KRW':
                ticker = f"KRW-{balance['currency']}"
                current_price = pyupbit.get_current_price(ticker)
                if current_price and isinstance(current_price, (int, float)):
                    total_value += float(balance['balance']) * float(current_price)
        
        account_info = {
            "principal": total_value,
            "available_balance": krw_balance,
            "open_positions": open_positions,
            "avg_return": 0.0,
            "consecutive_losses": 0,
        }
        
        markets = settings.tracked_markets
        data_service = HistoricalDataService(markets)
        
        # 최근 데이터 가져오기 (짧은 시퀀스 사용)
        market_data_dict = await data_service.fetch_recent()
        
        engine = TradingEngine(settings)
        executor = TradeExecutor(settings)
        
        for market in markets:
            try:
                market_data = market_data_dict.get(market, [])
                
                if len(market_data) < 150:
                    logger.debug(f"Insufficient data for {market}: {len(market_data)} rows")
                    continue
                
                # 특징 생성
                features = build_features_from_market_data(market_data, market)
                
                # ML 신호만 사용 (LLM 검증 없이)
                ml_signal = engine.predictor.infer({"market": market, **features})
                
                # 최소 신뢰도 체크
                confidence = max(ml_signal.buy_probability, ml_signal.sell_probability)
                if confidence < settings.tick_min_confidence:
                    logger.debug(f"{market} tick skip: confidence {confidence:.1%} < {settings.tick_min_confidence:.1%}")
                    continue
                
                # 신뢰도 기반 투자 비율 (더 공격적)
                if confidence >= 0.85:
                    investment_ratio = 0.5  # 매우 높은 신뢰도: 50%
                elif confidence >= 0.75:
                    investment_ratio = 0.3  # 높은 신뢰도: 30%
                else:
                    investment_ratio = 0.15  # 중간 신뢰도: 15%
                
                # SELL 신호는 항상 전량 매도
                if ml_signal.action == "SELL":
                    investment_ratio = 1.0
                
                # 거래 결정 생성 (LLM 승인 없이)
                from app.trading.engine import TradeDecisionResult
                decision = TradeDecisionResult(
                    approved=(ml_signal.action != "HOLD"),
                    action=ml_signal.action,
                    market=market,
                    confidence=confidence,
                    rationale=f"🚀 Tick trading: ML {confidence:.1%} confidence (no LLM)",
                    emergency=False,
                    investment_ratio=investment_ratio,
                    max_loss_acceptable=0.02,  # 더 타이트한 손절
                    take_profit_target=0.03,  # 더 빠른 익절
                )
                
                # 거래 실행
                if decision.approved:
                    executor.execute(db, decision, account_info["available_balance"])
                    logger.info(f"⚡ Tick trade: {market} {ml_signal.action} at {confidence:.1%} confidence, {investment_ratio*100:.0f}% position")
                
            except Exception as e:
                logger.error(f"Error in tick trading for {market}: {e}", exc_info=True)
                continue
                
    except Exception as e:
        logger.error(f"Error in tick trading cycle: {e}", exc_info=True)
    finally:
        db.close()


async def run_pump_detection_loop() -> None:
    """
    실시간 모니터링 루프 (WebSocket 기반, 1분간 지속 실행) v5.0
    v6.0: 비활성화 - pump_detection_enabled=False
    급등 매수(FOMO)가 대규모 손실의 핵심 원인이었음
    """
    if not settings.pump_detection_enabled:
        logger.debug("⛔ Pump detection disabled (v6.0: pump_detection_enabled=False)")
        return

    import time
    from app.trading.pump_predictor import PumpPredictor  # v5.0: 신규 예측기
    from app.trading.pump_detector import PumpDetector  # 레거시 호환
    from app.trading.reversal_strategy import ReversalTradingStrategy
    from app.trading.engine import TradeDecisionResult
    from app.models.trading import AutoTradingConfig
    
    # breakout_strategy는 전역 변수 사용

    db = SessionLocal()
    
    # 0. 전략 모드 확인
    try:
        config_obj = db.query(AutoTradingConfig).order_by(AutoTradingConfig.id.desc()).first()
        # 기본값: breakout_strategy
        strategy_mode = getattr(config_obj, "strategy_option", "breakout_strategy")
        if not strategy_mode or strategy_mode == "reversal_strategy": 
            # 사용자 요청으로 Reversal -> Breakout 강제 전환 (또는 Config가 없을 때)
            strategy_mode = "breakout_strategy"
            
    except Exception as e:
        logger.error(f"Failed to load strategy config: {e}")
        strategy_mode = "breakout_strategy"

    logger.info(f"🚀 Starting Real-time Monitoring Loop v5.0: Mode={strategy_mode} (55s)")
    
    # v5.0: PumpPredictor 사용 (급등 조짐 + 피크 감지)
    pump_predictor = PumpPredictor()
    detector = None  # 레거시
    reversal_strategy = None
    
    # 동적 마켓 사용
    markets = market_selector.get_top_volume_coins()
    
    # 전략 초기화
    if strategy_mode == "momentum_strategy":
        detector = PumpDetector()  # 레거시 호환
    elif strategy_mode == "reversal_strategy":
        reversal_strategy = ReversalTradingStrategy(settings)
    # BreakoutStrategy는 전역 인스턴스 사용

    start_time = time.time()
    
    # 전략용 데이터 캐시 (시작 시 1회 로드)
    # Breakout 및 Reversal 모두 과거 데이터 필요
    cached_dfs = {}
    if strategy_mode in ["reversal_strategy", "breakout_strategy"]:
        try:
            logger.info(f"loading historical data for {strategy_mode}...")
            for m in markets:
                # API 호출 속도 제한 고려
                df = pyupbit.get_ohlcv(m, interval="minute1", count=200)
                if df is not None:
                    cached_dfs[m] = df
                time.sleep(0.05) 
        except Exception as e:
            logger.warning(f"Initial data load failed: {e}")

    executor = TradeExecutor(settings)
    
    try:
        # 1. 현재 오픈된 포지션 로드
        open_positions = db.query(TradePosition).filter(TradePosition.status == "OPEN").all()
        monitored_positions = {p.market: p for p in open_positions}
        
        # WebSocket 연결 (Async direct implementation)
        import websockets
        import json
        uri = "wss://api.upbit.com/websocket/v1"
        subscribe_fmt = [{"ticket": "UNIQUE_TICKET"}, {"type": "ticker", "codes": markets, "isOnlyRealtime": True}]
        
        websocket = await websockets.connect(uri)
        await websocket.send(json.dumps(subscribe_fmt))
        
        while time.time() - start_time < 55:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                data = json.loads(msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"WS Recv Error: {e}")
                break
                
            market = data.get('code')
            if not market: continue
            price = float(data.get('trade_price'))
            volume = float(data.get('acc_trade_price_24h'))
            
            # --- [A] v5.0 개선: 실시간 트레일링 스탑 + SL/TP ---
            if market in monitored_positions:
                pos = monitored_positions[market]
                
                # 1. 기존 Stop Loss
                if price <= pos.stop_loss:
                    logger.warning(f"🛑 Real-time Stop Loss: {market} {price}")
                    decision = TradeDecisionResult(True, "SELL", market, 1.0, "Real-time Stop Loss", True, 1.0)
                    executor.execute(db, decision)
                    pump_predictor.clear_position(market)  # v5.0: 포지션 추적 초기화
                    del monitored_positions[market]
                    continue
                    
                # 2. 기존 Take Profit
                elif price >= pos.take_profit:
                    logger.info(f"💰 Real-time Take Profit: {market} {price}")
                    decision = TradeDecisionResult(True, "SELL", market, 1.0, "Real-time Take Profit", False, 1.0)
                    executor.execute(db, decision)
                    pump_predictor.clear_position(market)  # v5.0: 포지션 추적 초기화
                    del monitored_positions[market]
                    continue
                
                # 3. v5.0 신규: 트레일링 스탑 + 피크 감지
                df = cached_dfs.get(market)
                peak_signal = pump_predictor.detect_peak(
                    market, price, pos.entry_price, volume,
                    rsi=df.iloc[-1].get('rsi', 50) if df is not None and len(df) > 0 else None
                )
                if peak_signal and peak_signal.action == "SELL":
                    logger.info(f"🔔 Peak Detected: {market} - {peak_signal.reason}")
                    decision = TradeDecisionResult(
                        True, "SELL", market, peak_signal.confidence,
                        f"Peak Sell: {peak_signal.reason}", False, 1.0
                    )
                    executor.execute(db, decision)
                    pump_predictor.clear_position(market)
                    del monitored_positions[market]
                    continue

            # --- [B] 전략별 진입/청산 로직 ---
            
            # Option 1: Momentum (Pump) - v5.0 개선
            if strategy_mode == "momentum_strategy":
                df = cached_dfs.get(market)
                if df is None:
                    continue
                
                # v5.0: PumpPredictor로 급등 조짐 사전 감지
                has_position = market in monitored_positions
                entry_price = monitored_positions[market].entry_price if has_position else 0
                
                signal = pump_predictor.analyze(
                    market, df, price, volume,
                    has_position=has_position,
                    entry_price=entry_price
                )
                
                if signal.action == "BUY" and signal.signal_type == "PRE_PUMP":
                    if market not in monitored_positions:
                        logger.warning(f"🚀 PRE-PUMP 감지: {market} - {signal.reason}")
                        
                        existing = db.query(TradePosition).filter(
                            TradePosition.market==market, 
                            TradePosition.status=="OPEN"
                        ).first()
                        if existing:
                            monitored_positions[market] = existing
                            continue
                        
                        decision = TradeDecisionResult(
                            True, "BUY", market, signal.confidence, 
                            f"Pre-Pump: {signal.reason}", False, 
                            settings.pump_investment_ratio,
                            max_loss_acceptable=0.02,  # 타이트한 SL
                            take_profit_target=0.08    # 8% 목표 (급등 기대)
                        )
                        executor.execute(db, decision, None)
                        
                elif signal.action == "SELL" and signal.signal_type == "PEAK":
                    if market in monitored_positions:
                        logger.info(f"🔔 PEAK 매도: {market} - {signal.reason}")
                        decision = TradeDecisionResult(
                            True, "SELL", market, signal.confidence, 
                            f"Peak Detected: {signal.reason}", False, 1.0
                        )
                        executor.execute(db, decision)
                        pump_predictor.clear_position(market)
                        del monitored_positions[market]

            # Option 2: Reversal (Peak Sell, Dip Buy)
            elif strategy_mode == "reversal_strategy" and reversal_strategy:
                df = cached_dfs.get(market)
                if df is None: continue
                
                action, conf, reason = reversal_strategy.analyze(market, price, df)
                
                if action == "SELL":
                    if market in monitored_positions:
                        logger.info(f"📉 PEAK SELL Signal for {market}: {reason}")
                        decision = TradeDecisionResult(
                            True, "SELL", market, conf, 
                            f"Reversal Peak Sell: {reason}", False, 1.0
                        )
                        executor.execute(db, decision)
                        del monitored_positions[market]
                        
                elif action == "BUY":
                    if market not in monitored_positions:
                        existing = db.query(TradePosition).filter(TradePosition.market==market, TradePosition.status=="OPEN").first()
                        if existing:
                            monitored_positions[market] = existing
                            continue

                        decision = TradeDecisionResult(
                            True, "BUY", market, conf, 
                            f"Reversal Dip Buy: {reason}", False, 
                            settings.pump_investment_ratio, 
                            max_loss_acceptable=0.03, 
                            take_profit_target=0.03
                        )
                        executor.execute(db, decision, None)

            # Option 3: Breakout Strategy (Trend Following) - NEW
            elif strategy_mode == "breakout_strategy":
                df = cached_dfs.get(market)
                # 데이터 갱신 (마지막 row의 close price 정도만 업데이트 해주는게 좋지만, 여기선 근사치 사용)
                # 더 정확하게 하려면 DataFrame의 마지막 Row를 현재가/거래량으로 업데이트 해야함.
                if df is None: continue
                
                # Real-time data injection (Update last candle temporarily)
                # 간단하게 현재가 반영을 위해 copy 후 수정
                # (빈번한 copy는 성능 이슈가 있지만 5분주기+WS조합이므로 1초에 수십건 아니면 괜찮음)
                # 하지만 Python DataFrame copy는 꽤 무거움. 
                # 전략이 '종가' 기준이 많으므로 현재가가 종가라고 가정하고 분석 Execute.
                
                # BreakoutStrategy.analyze는 DataFrame 전체를 보므로, 
                # 마지막 캔들의 Close를 현재가로 덮어쓰거나, 새로운 캔들을 임시로 추가해야 함.
                # 편의상 '현재 캔들'이 아직 완성되지 않았지만 현재가로 형성중이라고 가정.
                
                # df.iloc[-1, df.columns.get_loc('close')] = price (SettingWithCopyWarning 주의)
                # 여기서는 원본 df 손상 방지를 위해 복사본 없이 analyze 내에서 처리하거나,
                # 그냥 직전 확정 캔들 + 현재가 별도 전달이 나음.
                # 하지만 BreakoutStrategy.analyze 인터페이스는 market, df 임.
                # BreakoutStrategy 내부에서 df.iloc[-1]을 참조하므로,
                # 여기서 df의 마지막 row를 업데이트해서 넘겨줘야 실시간 반영됨.
                pass 
                # (TODO: Optimize DataFrame update)
                
                # 일단 단순하게, df는 1분 전 데이터이므로 실시간 급등 반영이 늦을 수 있음.
                # 따라서 BreakoutStrategy를 'Current Price'를 인자로 받도록 수정하거나
                # 여기서 약간의 트릭 사용.
                
                # -> BreakoutStrategy를 수정하지 않고, 여기서 df를 살짝 수정해서 넘김
                # (Warning ignore)
                last_idx = df.index[-1]
                df.at[last_idx, 'close'] = price
                # 거래량은 누적이므로 API가 주는 누적거래량이 24h라 캔들 볼륨과 다름.
                # 캔들 볼륨 추정 불가하므로 이전 볼륨 그대로 사용하되, 가격 돌파 위주로 봄.
                
                bo_action, bo_conf, bo_reason = breakout_strategy.analyze(market, df)
                
                if bo_action == "BUY":
                    if market not in monitored_positions:
                        logger.info(f"🚀 BREAKOUT BUY: {market} {bo_conf:.1%} - {bo_reason}")
                        
                        existing = db.query(TradePosition).filter(TradePosition.market==market, TradePosition.status=="OPEN").first()
                        if existing:
                            monitored_positions[market] = existing
                            continue
                            
                        decision = TradeDecisionResult(
                            True, "BUY", market, bo_conf, 
                            f"Trend Breakout: {bo_reason}", False, 
                            0.2, # 20% investment
                            max_loss_acceptable=0.02, # -2% SL (Trend following usually tight SL)
                            take_profit_target=0.05   # +5% TP (Let profits run)
                        )
                        executor.execute(db, decision, None)
                
                elif bo_action == "SELL":
                     if market in monitored_positions:
                        logger.info(f"📉 TREND BROKEN: {market} - {bo_reason}")
                        decision = TradeDecisionResult(
                            True, "SELL", market, bo_conf, 
                            f"Trend Broken: {bo_reason}", False, 1.0
                        )
                        executor.execute(db, decision)
                        del monitored_positions[market]
                        
        await websocket.close()
            
    except Exception as e:
        logger.error(f"Error in monitoring loop: {e}")
    finally:
        db.close()

