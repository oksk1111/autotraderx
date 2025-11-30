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

    db: Session = SessionLocal()
    try:
        for market in markets:
            try:
                # 시장 데이터를 ML 입력 특징으로 변환
                market_data = market_data_dict.get(market, [])
                
                if len(market_data) < 150:
                    logger.warning(f"Insufficient data for {market}: {len(market_data)} rows (need 150+)")
                    continue
                
                # 특징 생성
                features = build_features_from_market_data(market_data, market)
                
                # 거래 결정
                decision = await engine.decide(db, market, features, account_info)
                
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
