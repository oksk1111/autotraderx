from typing import List, Dict, Tuple
import pyupbit
import time
from app.core.logging import get_logger

logger = get_logger(__name__)

class MarketSelector:
    """
    동적 마켓 선정기 (Dynamic Market Selector)
    거래대금 상위 코인을 자동으로 선정하여 트레이딩 대상에 포함시킵니다.
    """

    def __init__(self, top_k: int = 10, min_volume: float = 30_000_000_000): # 300억
        self.top_k = top_k
        self.min_volume = min_volume
        self.cached_markets = []
        self.last_update = 0
        self.update_interval = 300  # 5분(300초)마다 목록 갱신

    def get_top_volume_coins(self) -> List[str]:
        """
        자산 규모(시가총액) 상위 10개 코인 반환 (Blue Chip Strategy)
        사용자 요청에 따라 시총 상위 우량주 위주로만 거래.
        (BTC, ETH, XRP, SOL, DOGE, ADA, TRX, SHIB, AVAX, LINK - 2025 기준)
        """
        # Blue Chip List (Fixed by Strategy)
        blue_chips = [
            "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE", 
            "KRW-ADA", "KRW-TRX", "KRW-SHIB", "KRW-AVAX", "KRW-LINK"
        ]
        
        # 실제 Upbit에 존재하는지 검증
        try:
            available_tickers = set(pyupbit.get_tickers(fiat="KRW"))
        except:
            available_tickers = set(blue_chips) # Failover
            
        selected_markets = [m for m in blue_chips if m in available_tickers]
        
        self.cached_markets = selected_markets
        return self.cached_markets
            self.last_update = now
            
            logger.info(f"✅ Market Selector Updated: {selected_markets} (Min Volume: {self.min_volume/100000000:.0f}억, Caution Filtered)")
            return selected_markets
            
        except Exception as e:
            logger.error(f"Failed to update market list: {e}")
            # 실패시 기존 캐시가 있으면 반환, 없으면 기본값
            if self.cached_markets:
                return self.cached_markets
            return ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"] # Fallback

