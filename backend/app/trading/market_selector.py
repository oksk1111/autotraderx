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
        거래대금 상위 Top K 코인을 반환합니다.
        (BTC, ETH는 항상 포함)
        """
        now = time.time()
        
        # 캐시 유효하면 반환
        if self.cached_markets and (now - self.last_update < self.update_interval):
            return self.cached_markets

        try:
            # 1. 마켓 메타데이터 조회 (유의 종목 확인용)
            # isDetails=true 파라미터를 통해 유의종목(CAUTION) 여부 확인 가능
            import requests
            market_url = "https://api.upbit.com/v1/market/all"
            market_res = requests.get(market_url, params={"isDetails": "true"})
            market_warnings = {}
            if market_res.status_code == 200:
                for m in market_res.json():
                    # market_warning: 'NONE', 'CAUTION'
                    market_warnings[m['market']] = m.get('market_warning', 'NONE')
            
            # 모든 KRW 마켓 가져오기 (pyupbit 이용)
            krw_tickers = pyupbit.get_tickers(fiat="KRW")
            
            # 2. Ticker 정보 조회 (거래대금 확인용)
            ticker_url = "https://api.upbit.com/v1/ticker"
            
            # 100개씩 나눠서 요청 (최대 100개 가능할수도)
            chunks = [krw_tickers[i:i + 100] for i in range(0, len(krw_tickers), 100)]
            
            all_tickers_data = []
            for chunk in chunks:
                params = {"markets": ",".join(chunk)}
                res = requests.get(ticker_url, params=params)
                if res.status_code == 200:
                    all_tickers_data.extend(res.json())
                time.sleep(0.1)
                
            # 거래대금(acc_trade_price_24h) 기준 정렬
            # acc_trade_price_24h: 24시간 누적 거래대금
            sorted_tickers = sorted(
                all_tickers_data, 
                key=lambda x: x['acc_trade_price_24h'], 
                reverse=True
            )
            
            # 3. 필터링 및 선정 (Scam Filter + Trend Filter)
            selected_markets = []
            
            # 고정 포함 (BTC, ETH) - 안전자산, 단 유의종목 지정 시 제외됨
            safe_havens = {'KRW-BTC', 'KRW-ETH'}
            
            for item in sorted_tickers:
                market = item['market']
                volume = item['acc_trade_price_24h']
                warning = market_warnings.get(market, 'NONE')
                
                # [Filter 1] 유의 종목 절대 배제 (Scam Prevention)
                if warning == 'CAUTION':
                    logger.info(f"🚫 Filtering {market}: Marked as CAUTION (Investment Warning)")
                    continue

                # [Filter 2] 최소 거래대금 미달 배제 (Liquidity Check)
                if volume < self.min_volume:
                    continue

                # [Selection] 안전자산 우선 포함
                if market in safe_havens:
                    if market not in selected_markets:
                        selected_markets.append(market)
                    continue
                
                # [Selection] Top K 채우기
                if len(selected_markets) < self.top_k:
                    if market not in selected_markets:
                        selected_markets.append(market)
                    
            self.cached_markets = selected_markets
            self.last_update = now
            
            logger.info(f"✅ Market Selector Updated: {selected_markets} (Min Volume: {self.min_volume/100000000:.0f}억, Caution Filtered)")
            return selected_markets
            
        except Exception as e:
            logger.error(f"Failed to update market list: {e}")
            # 실패시 기존 캐시가 있으면 반환, 없으면 기본값
            if self.cached_markets:
                return self.cached_markets
            return ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"] # Fallback

