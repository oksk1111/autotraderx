from __future__ import annotations

import pyupbit
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.ml.feature_builder import build_features_from_market_data
from app.services.data_pipeline import HistoricalDataService
from app.services.trading.emergency_trader import EmergencyTrader
from app.trading.engine import TradeExecutor, TradingEngine
from app.trading.enhanced_engine import get_enhanced_engine
from app.models.trading import AutoTradingConfig

logger = get_logger(__name__)
settings = get_settings()


async def run_cycle() -> None:
    logger.info("Starting trading cycle")
    markets = settings.tracked_markets
    data_service = HistoricalDataService(markets)
    
    # 시장별 최근 데이터 가져오기 (최소 150개, 권장 200개)
    market_data_dict = await data_service.fetch_recent()

    # Upbit 계정 정보 가져오기
    try:
        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        krw_balance = float(upbit.get_balance("KRW") or 0)
        
        # 원금과 현재 자산 계산
        total_value = krw_balance
        for balance in balances:
            if balance['currency'] != 'KRW':
                ticker = f"KRW-{balance['currency']}"
                current_price = pyupbit.get_current_price(ticker)
                if current_price and isinstance(current_price, (int, float)):
                    total_value += float(balance['balance']) * float(current_price)
        
        account_info = {
            "principal": total_value,  # 총 자산을 원금으로 사용
            "available_balance": krw_balance,  # 가용 KRW
            "open_positions": len([b for b in balances if b['currency'] != 'KRW']),
            "avg_return": 0.0,  # 계산 필요
            "consecutive_losses": 0,  # 계산 필요
        }
        logger.info(f"Account Info: Total={total_value:,.0f} KRW, Available={krw_balance:,.0f} KRW, Positions={account_info['open_positions']}")
        
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        return

    engine = TradingEngine(settings)
    executor = TradeExecutor(settings)
    
    # Enhanced Engine (Hybrid + MultiTF) 사용
    enhanced_engine = get_enhanced_engine()

    db: Session = SessionLocal()
    try:
        for market in markets:
            try:
                # 시장 데이터를 ML 입력 특징으로 변환
                market_data = market_data_dict.get(market, [])
                
                if len(market_data) < 150:
                    logger.warning(f"Insufficient data for {market}: {len(market_data)} rows (need 150+)")
                    continue
                
                # Enhanced Engine 사용 가능 여부 확인
                if enhanced_engine.is_available():
                    # market_data를 DataFrame으로 변환
                    import pandas as pd
                    df = pd.DataFrame(market_data)
                    
                    # Enhanced Engine으로 거래 신호 생성 (Hybrid + MultiTF)
                    action, confidence, details = enhanced_engine.get_enhanced_signal(market, df)
                    
                    if action != "HOLD":
                        # 신뢰도 기반 투자 비율 설정
                        if confidence >= 0.85:
                            investment_ratio = 0.5
                        elif confidence >= 0.75:
                            investment_ratio = 0.3
                        elif confidence >= 0.65:
                            investment_ratio = 0.2
                        else:
                            investment_ratio = 0.1
                        
                        # SELL은 전량 매도
                        if action == "SELL":
                            investment_ratio = 1.0
                        
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
                            max_loss_acceptable=0.03,
                            take_profit_target=0.05,
                        )
                        
                        logger.info(f"🚀 Enhanced: {market} {action} ({confidence:.1%}) - {details.get('rationale', '')[:80]}")
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
