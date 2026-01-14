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
            # 모든 KRW 마켓 가져오기
            krw_tickers = pyupbit.get_tickers(fiat="KRW")
            
            # 티커 조회 (가격, 거래대금 등)
            # get_current_price는 간단하지만 거래대금 정보가 없으므로 get_ohlcv나 get_ticker 대용 함수 필요
            # 보통 pyupbit.get_ohlcv(ticker, count=1) 로 day 캔들 가져와서 거래대금(value) 확인
            
            # 더 효율적인 방법: pyupbit.get_current_price 대신 호가정보나 티커정보 등.. 
            # 하지만 pyupbit에는 bulk ticker 조회 기능이 get_current_price 외에 제한적일 수 있음.
            # 다행히 pyupbit.get_ticker 라는 함수가 있으면 좋은데.. 없으면 loop 돌아야 함. (느림)
            # pyupbit.get_ohlcv는 느릴 수 있음.
            
            # 대안: 주요 코인 리스트업이라 API call 최소화. 하지만 Top K를 뽑으려면 다 봐야함.
            # Quotation API의 'ticker' 엔드포인트를 쓰면 됨. pyupbit.get_current_price는 현재가만 줌.
            # 직접 request 호출하거나 pyupbit 소스 확인 필요하지만, 안전하게 loop 돌되 
            # 주요 30-50개만 봐도 될 수도 있음.
            
            # 개선: pyupbit의 get_ohlcv는 1건씩이므로, get_daily_ohlcv_from_base() 같은 건 없고..
            # 그냥 KRW 마켓 전체에 대해 looping 하기엔 너무 많지만(100개+), 5분에 한번이면 괜찮음.
            
            market_volumes = []
            
            # Batch로 묶어서 처리하거나.. 여기선 일단 상위 인지도 있는거 위주로 하면 좋지만
            # 사용자 요청이 "급등 코인"이므로 전체 스캔이 필요.
            
            # pyupbit.get_ohlcv는 너무 느리므로, Request를 직접 날려서 Ticker 정보(acc_trade_price_24h)를 가져오는게 낫음.
            # 하지만 pyupbit 라이브러리 사용을 선호.
            
            # pyupbit.get_ticker() 같은 함수가 있는지 확인 어렵지만, 
            # pyupbit.get_quotation(tickers) -> 리스트로 반환. 
            # 실제 함수명은 get_ticker가 아니라 get_current_price(..., verbose=True) 일수도?
            # pyupbit 구현상 get_current_price는 'trade_price'만 리턴함 (기본적으로).
            
            # 직접 request 사용이 확실함.
            import requests
            url = "https://api.upbit.com/v1/ticker"
            
            # 100개씩 나눠서 요청 (최대 100개 가능할수도)
            chunks = [krw_tickers[i:i + 100] for i in range(0, len(krw_tickers), 100)]
            
            all_tickers_data = []
            for chunk in chunks:
                params = {"markets": ",".join(chunk)}
                res = requests.get(url, params=params)
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
            
            # 필터링 및 추출
            selected_markets = []
            
            # 고정 포함 (BTC, ETH) - 안전자산
            must_include = {'KRW-BTC', 'KRW-ETH'}
            for m in must_include:
                if m in krw_tickers and m not in selected_markets:
                    selected_markets.append(m)
                    
            for item in sorted_tickers:
                market = item['market']
                volume = item['acc_trade_price_24h']
                
                if market in selected_markets:
                    continue
                    
                if len(selected_markets) >= self.top_k:
                    break
                    
                # 거래대금 필터
                if volume < self.min_volume:
                    continue
                    
                # (Optional) 너무 동전주는 제외하거나.. 일단 사용자 요청대로 급등 가능성 열어둠
                
                selected_markets.append(market)
                
            self.cached_markets = selected_markets
            self.last_update = now
            
            logger.info(f"Market Selector Updated: {selected_markets} (Min Volume: {self.min_volume/100000000:.0f}억)")
            return selected_markets
            
        except Exception as e:
            logger.error(f"Failed to update market list: {e}")
            # 실패시 기존 캐시가 있으면 반환, 없으면 기본값
            if self.cached_markets:
                return self.cached_markets
            return ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"] # Fallback

