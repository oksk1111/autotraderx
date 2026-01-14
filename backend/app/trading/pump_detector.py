from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

import pyupbit
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PumpDetector:
    """
    실시간 급등(Pump) 감지기
    
    Candle 데이터가 아닌 현재가(Ticker)를 직접 폴링하여
    설정된 시간(lookback_seconds) 내에 설정된 비율(threshold_percent) 이상
    상승하는 경우를 포착합니다.
    """
    
    def __init__(self):
        self.price_cache: Dict[str, Dict[str, float]] = {}  # {market: {'price': 100, 'timestamp': 1234567890}}
        self.last_check_time = 0
        
    def update_price(self, market: str, price: float):
        """현재 가격 업데이트 및 캐시 관리"""
        now = time.time()
        
        if market not in self.price_cache:
            self.price_cache[market] = {
                'start_price': price,
                'start_time': now,
                'current_price': price,
                'last_update': now
            }
            return
            
        cache = self.price_cache[market]
        cache['current_price'] = price
        cache['last_update'] = now
        
        # Lookback 기간이 지났으면 기준 가격(start_price) 리셋
        if now - cache['start_time'] > settings.pump_lookback_seconds:
            cache['start_price'] = price
            cache['start_time'] = now

    def check_pump(self, market: str, current_price: float, current_volume_24h: Optional[float] = None) -> Tuple[bool, float]:
        """
        급등 여부 확인
        
        Args:
            current_volume_24h: 24시간 누적 거래대금 (선택사항, 스캠 필터링용)
            
        Returns:
            (is_pump, change_percent)
        """
        # 1. 스캠 필터링: 거래대금 체크 (300억 미만 제외)
        if current_volume_24h is not None and current_volume_24h < 30_000_000_000:
            return False, 0.0

        self.update_price(market, current_price)
        
        cache = self.price_cache[market]
        start_price = cache['start_price']
        
        if start_price == 0:
            return False, 0.0
            
        change_percent = ((current_price - start_price) / start_price) * 100
        
        # 급등 조건: 상승률 > 임계값
        if change_percent >= settings.pump_threshold_percent:
            logger.info(f"🚀 PUMP DETECTED: {market} +{change_percent:.2f}% in {time.time() - cache['start_time']:.1f}s")
            
            # 감지 후 기준 가격 리셋 (중복 감지 방지)
            cache['start_price'] = current_price
            cache['start_time'] = time.time()
            
            return True, change_percent
            
        return False, change_percent

    def get_market_prices(self, markets: list[str]) -> Dict[str, float]:
        """여러 마켓의 현재가 조회"""
        try:
            prices = pyupbit.get_current_price(markets)
            if isinstance(prices, float) or isinstance(prices, int):
                return {markets[0]: float(prices)}
            return {k: float(v) for k, v in prices.items()} if prices else {}
        except Exception as e:
            logger.error(f"Failed to fetch prices: {e}")
            return {}
