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
market_selector = MarketSelector(top_k=10, min_volume=30_000_000_000)
breakout_strategy = BreakoutTradingStrategy()


async def check_and_manage_positions(db: Session, executor: TradeExecutor) -> None:
    """
    오픈 포지션의 Stop Loss / Take Profit 체크 및 실행
    
    v5.1 업그레이드:
    - 즉시 손절: -3% 이상 손실 시 무조건 청산 (추세 무관)
    - Hard Stop: -4% 절대 마지노선 유지
    - Rule No.1: 돈을 잃지 마라
    """
    from app.trading.engine import TradeDecisionResult
    
    # OPEN 상태인 포지션 조회
    positions = db.query(TradePosition).filter(TradePosition.status == "OPEN").all()
    if not positions:
        return

    logger.info(f"Checking {len(positions)} open positions for Stop Loss/Take Profit")
    
    # 마켓 목록 추출
    markets = list(set([p.market for p in positions]))
    
    try:
        # [Rate Limit Prevention] API 호출 전 딜레이
        await asyncio.sleep(0.5) 
        
        # 현재가 일괄 조회
        current_prices = pyupbit.get_current_price(markets)
        # 단일 마켓일 경우 float 반환, 다수일 경우 dict 반환
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
            
            # [v5.1 핵심] PnL 계산
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price
            
            # --- [Rule No.1: 돈을 잃지 마라] ---
            # 1. 즉시 손절: -3.0% (Blue Chip은 변동성이 적으므로 3%면 큰 하락)
            if pnl_pct <= -0.03:
                logger.warning(f"🚨 URGENT LOSS CUT for {pos.market}: PnL {pnl_pct:.2%} <= -3.0%")
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=pos.market,
                    confidence=1.0,
                    rationale=f"Rule No.1: Immediate Loss Cut at {pnl_pct:.1%}",
                    emergency=True,
                    investment_ratio=1.0
                )
                executor.execute(db, decision)
                await asyncio.sleep(1.0) # [Rate Limit] 매도 후 대기
                continue
            
            # 2. Hard Stop Limit: -4.0% 절대 마지노선
            hard_stop_limit = -0.04
            
            if pnl_pct <= hard_stop_limit:
                logger.warning(f"🚨 CRITICAL Hard Stop Limit Triggered for {pos.market}: PnL {pnl_pct:.2%} <= Limit {hard_stop_limit:.2%}")
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=pos.market,
                    confidence=1.0,
                    rationale=f"Hard Stop Limit Triggered (PnL {pnl_pct:.1%})",
                    emergency=True,
                    investment_ratio=1.0
                )
                executor.execute(db, decision)
                await asyncio.sleep(1.0) # [Rate Limit]
                continue
            
            # 3. Trailing Stop (꺾이면 판다)
            # 급등 후 하락세 전환 시 빠르게 매도
            # 최고가 대비 일정 비율 하락 시 매도하는 로직이 필요하지만, 여기선 간이로 구현
            # 이익 구간(+2% 이상)에서 현재가가 평단가보다 낮아지거나, 수익률이 급감하면 매도
            
            # 본전 보존 로직
            break_even_price = pos.entry_price * 1.002 # 수수료 포함 본전
            if current_price > pos.entry_price * 1.02: 
                # 2% 이상 수익나면 본전+0.5%를 Stop Loss로 설정
                trailing_stop_price = max(current_price * 0.97, pos.entry_price * 1.005)
                
                if trailing_stop_price > pos.stop_loss:
                    old_sl = pos.stop_loss
                    pos.stop_loss = trailing_stop_price
                    db.commit()
                    logger.info(f"📈 Trailing Stop Updated for {pos.market}: {old_sl:,.0f} -> {pos.stop_loss:,.0f} (Price: {current_price:,.0f})")

            # Stop Loss 체크
            if current_price <= pos.stop_loss:
                # ... existing logic ...

                logger.warning(f"🛑 Stop Loss Triggered for {pos.market}: Current {current_price:,.0f} <= Stop {pos.stop_loss:,.0f}")
                
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
                
            # Take Profit 체크
            elif current_price >= pos.take_profit:
                logger.info(f"💰 Take Profit Triggered for {pos.market}: Current {current_price:,.0f} >= Target {pos.take_profit:,.0f}")
                
                decision = TradeDecisionResult(
                    approved=True,
                    action="SELL",
                    market=pos.market,
                    confidence=1.0,
                    rationale=f"Take Profit Triggered (Entry: {pos.entry_price:,.0f}, Current: {current_price:,.0f})",
                    emergency=False,
                    investment_ratio=1.0
                )
                executor.execute(db, decision)

            # Time Limit 체크
            elif settings.max_position_hold_minutes > 0:
                # 포지션 보유 시간 계산
                now = datetime.datetime.now(datetime.timezone.utc)
                entry_time = pos.created_at
                
                # DB에서 가져온 시간이 Naive할 경우 UTC로 간주
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
    Main Trading Cycle
    
    [Philosophy v5.0] Wonyyotti x Buffett
    1. Market Selection: Only High Volume & Healthy assets (No Scams/Caution items).
    2. Continuous Review: All held positions are re-evaluated every cycle.
    3. Strict Risk Management:
       - Hard Stop at -4% (No questions asked).
       - Soft Stop at -2% (Trailing).
       - Trend Exit: If held asset is losing >3% and not a Strong Buy, EXIT.
    """
    logger.info("Starting trading cycle")
    # 동적 마켓 선정 (Top 10 거래대금, Caution 제외)
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
                    
                    # [Persona Strategy Integration]
                    # 페르소나 전략을 통한 신호 보정 (v3.5)
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
                        
                        best_buy = max([d for d in p_decisions if d['action'] == 'BUY'], key=lambda x: x['confidence'], default=None)
                        best_sell = max([d for d in p_decisions if d['action'] == 'SELL'], key=lambda x: x['confidence'], default=None)
                        
                        if action == "HOLD":
                            # 강력한 페르소나 매수 신호가 있으면 HOLD를 BUY로 전환
                            if best_buy and best_buy['confidence'] >= 0.8:
                                action = "BUY"
                                confidence = best_buy['confidence']
                                details['rationale'] = f"Persona Override ({best_buy['persona']}): {best_buy['reason']}"
                                logger.info(f"🎭 Persona Override: Switching HOLD to BUY for {market} by {best_buy['persona']}")
                            
                            # 페르소나 매도 신호가 있으면 HOLD를 SELL로 전환 (리스크 관리)
                            elif best_sell and best_sell['confidence'] >= 0.7:
                                action = "SELL"
                                confidence = best_sell['confidence']
                                details['rationale'] = f"Persona Override ({best_sell['persona']}): {best_sell['reason']}"
                                logger.info(f"🎭 Persona Override: Switching HOLD to SELL for {market} by {best_sell['persona']}")
                                
                        elif action == "BUY":
                            # 매수 신호가 떴지만, 페르소나가 강력 매도를 외치면 취소
                            if best_sell and best_sell['confidence'] >= 0.85:
                                action = "HOLD"
                                details['rationale'] = f"Persona Veto ({best_sell['persona']}): {best_sell['reason']}"
                                logger.warning(f"🎭 Persona Veto: Blocking BUY for {market} due to {best_sell['persona']}")
                                
                    except Exception as pe:
                        logger.error(f"Persona evaluation failed for {market}: {pe}")

                    # [Trend Review] 보유 종목에 대한 추세 재점검
                    # 만약 보유 중인데 손실이 크고(-3% 이상), 추세가 강력한 상승(BUY + High Confidence)이 아니라면 매도 검토
                    current_pos = db.query(TradePosition).filter(
                        TradePosition.market == market,
                        TradePosition.status == "OPEN"
                    ).first()

                    # HOLD 상태거나, BUY 신호라도 신뢰도가 낮다면(0.7 미만) 손실 관리 모드 작동
                    if current_pos and (action == "HOLD" or (action == "BUY" and confidence < 0.7)):
                        try:
                            current_price = df.iloc[-1]['close']
                            entry_price = current_pos.entry_price
                            if entry_price > 0:
                                pnl_pct = (current_price - entry_price) / entry_price
                                
                                # 3% 이상 손실 중인데 확실한 상승 추세가 아니라면 매도하여 리스크 관리
                                if pnl_pct < -0.03:
                                    logger.info(f"📉 Trend Review: {market} PnL {pnl_pct:.2%} & Signal is {action}({confidence:.2f}). Forcing Exit.")
                                    action = "SELL"
                                    confidence = 0.95  # 강제 매도 실행을 위해 높은 신뢰도 부여
                                    details['rationale'] = f"Trend Review: Deep Loss ({pnl_pct:.1%}) without strong uptrend. Cutting Loss."
                        except Exception as e:
                            logger.error(f"Error reviewing trend for held position {market}: {e}")

                    if action != "HOLD":
                        # v5.0: 신뢰도 기반 투자 비율 상향 (더 공격적)
                        if confidence >= 0.90:
                            investment_ratio = 0.40  # 최고 신뢰도: 40%
                        elif confidence >= 0.85:
                            investment_ratio = 0.30  # 기존 0.20 -> 0.30
                        elif confidence >= 0.75:
                            investment_ratio = 0.25  # 기존 0.15 -> 0.25
                        elif confidence >= 0.65:
                            investment_ratio = 0.15  # 기존 0.10 -> 0.15
                        else:
                            investment_ratio = 0.10  # 기존 0.05 -> 0.10
                        
                        # SELL은 전량 매도
                        if action == "SELL":
                            investment_ratio = 1.0
                        
                        # ATR 기반 동적 SL/TP 설정 (v4.2 개선)
                        # ATR(Average True Range)을 활용하여 변동성에 맞는 손절/익절 설정
                        atr = df.iloc[-1].get('atr', 0)
                        atr_ratio = df.iloc[-1].get('atr_ratio', 0.02)  # 기본값 2%
                        current_price = df.iloc[-1].get('close', 0)
                        
                        if atr > 0 and current_price > 0:
                            # v5.0: ATR 배수 기반 SL/TP (변동성 적응형)
                            # SL: 1.5 ATR, TP: 3.0 ATR (손익비 1:2)
                            atr_sl_multiplier = 1.5
                            atr_tp_multiplier = 3.0  # 기존 2.5 -> 3.0 (급등 대응)
                            
                            # 고신뢰도일수록 더 넓은 TP 허용 (v5.0 강화)
                            if confidence >= 0.9:
                                atr_tp_multiplier = 4.0  # 손익비 1:3 (급등장 최대화)
                                atr_sl_multiplier = 1.0  # 타이트한 SL
                            elif confidence >= 0.8:
                                atr_tp_multiplier = 3.5  # 손익비 1:2.5
                                atr_sl_multiplier = 1.2  # 타이트한 SL
                            
                            # ATR 기반 퍼센티지
                            stop_loss_pct = min((atr * atr_sl_multiplier / current_price), 0.04)  # 최대 4% (기존 5%)
                            take_profit_pct = min((atr * atr_tp_multiplier / current_price), 0.15)  # 최대 15% (기존 10%)
                            
                            # 최소값 보장 (v5.0 조정)
                            stop_loss_pct = max(stop_loss_pct, 0.012)  # 최소 1.2% (기존 1.5%)
                            take_profit_pct = max(take_profit_pct, 0.03)  # 최소 3% (기존 2.5%)
                        else:
                            # ATR 없을 경우 신뢰도 기반 동적 기본값 (v5.0)
                            if confidence >= 0.9:
                                stop_loss_pct = 0.015
                                take_profit_pct = 0.08  # 8% TP
                            elif confidence >= 0.8:
                                stop_loss_pct = 0.02
                                take_profit_pct = 0.06  # 6% TP
                            elif confidence >= 0.7:
                                stop_loss_pct = 0.02
                                take_profit_pct = 0.05  # 5% TP
                            else:
                                stop_loss_pct = 0.025
                                take_profit_pct = 0.04  # 4% TP
                        
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
                            max_loss_acceptable=0.03,
                            take_profit_target=0.05,
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
    긴급 거래 체크 (10초마다 실행)
    - 급락/급등 실시간 감지
    - 정규 매매 주기와 독립적으로 동작
    """
    logger.debug("Starting emergency trading check")
    
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
        
        # 관심 마켓 (설정에서 가져오기)
        watch_markets = config.selected_markets if config.selected_markets else settings.tracked_markets
        
        # 긴급 거래 체크
        trader = EmergencyTrader()
        result = trader.check_all_markets(positions, watch_markets)
        
        # 긴급 거래 실행
        for action_item in result.get('emergency_actions', []):
            market = action_item['market']
            action = action_item['action']
            reason = action_item['reason']
            
            # 실제 거래 실행
            trade_result = trader.execute_emergency_trade(market, action, reason)
            
            if trade_result.get('success'):
                logger.warning(f"✅ {market} 긴급 거래 실행됨: {action} - {reason}")
            else:
                logger.error(f"❌ {market} 긴급 거래 실패: {trade_result.get('error')}")
        
        if result['markets_checked'] > 0:
            logger.info(f"Emergency check completed: {result['markets_checked']} markets, {len(result.get('emergency_actions', []))} actions triggered")
            
    except Exception as e:
        logger.error(f"Error in emergency trading check: {e}", exc_info=True)
    finally:
        db.close()


async def run_tick_cycle() -> None:
    """
    Tick 단위 공격적 매매 (1분 단위)
    - ML 신호만으로 빠른 매매 실행
    - LLM 검증 없이 신뢰도 기반 즉시 진입/청산
    - 최소 신뢰도 이상일 때만 거래
    """
    if not settings.aggressive_trading_mode:
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
    
    v5.0 업그레이드:
    - PumpPredictor: 급등 조짐 사전 감지 + 피크 매도
    - 트레일링 스탑: 수익 극대화
    
    Mode 1: Momentum Strategy (Pump buy) -> PumpPredictor 사용
    Mode 2: Reversal Strategy (Peak sell, Dip buy)
    Mode 3: Breakout Strategy (Trend Following) - **DEFAULT**
    """
    if not settings.pump_detection_enabled:
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

