import jwt
import hashlib
import uuid
from urllib.parse import urlencode, unquote
import requests
from typing import Dict, List, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class UpbitClient:
    """업비트 API 클라이언트"""
    
    def __init__(self):
        self.access_key = settings.UPBIT_ACCESS_KEY
        self.secret_key = settings.UPBIT_SECRET_KEY
        self.base_url = settings.UPBIT_API_URL
    
    def _get_headers(self, query: Optional[Dict] = None) -> Dict[str, str]:
        """JWT 토큰을 포함한 헤더 생성"""
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }
        
        if query:
            query_string = unquote(urlencode(query, doseq=True)).encode("utf-8")
            m = hashlib.sha512()
            m.update(query_string)
            query_hash = m.hexdigest()
            payload['query_hash'] = query_hash
            payload['query_hash_alg'] = 'SHA512'
        
        jwt_token = jwt.encode(payload, self.secret_key)
        return {'Authorization': f'Bearer {jwt_token}'}
    
    # Market Data APIs (Public)
    
    def get_markets(self) -> List[Dict]:
        """마켓 코드 조회"""
        url = f"{self.base_url}/market/all"
        params = {"isDetails": "true"}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get markets: {e}")
            return []
    
    def get_ticker(self, markets: List[str]) -> List[Dict]:
        """현재가 정보 조회"""
        url = f"{self.base_url}/ticker"
        params = {"markets": ",".join(markets)}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get ticker: {e}")
            return []
    
    def get_orderbook(self, markets: List[str]) -> List[Dict]:
        """호가 정보 조회"""
        url = f"{self.base_url}/orderbook"
        params = {"markets": ",".join(markets)}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get orderbook: {e}")
            return []
    
    def get_candles(
        self,
        market: str,
        unit: str = "minutes",
        count: int = 200,
        to: Optional[str] = None
    ) -> List[Dict]:
        """캔들 데이터 조회
        
        Args:
            market: 마켓 코드 (e.g., KRW-BTC)
            unit: 시간 단위 (minutes/1, minutes/3, minutes/5, minutes/15, minutes/30, 
                             minutes/60, minutes/240, days, weeks, months)
            count: 캔들 개수 (최대 200)
            to: 마지막 캔들 시각 (ISO 8601 format)
        """
        if unit.startswith("minutes"):
            minute = unit.split("/")[1] if "/" in unit else "1"
            url = f"{self.base_url}/candles/minutes/{minute}"
        else:
            url = f"{self.base_url}/candles/{unit}"
        
        params = {"market": market, "count": count}
        if to:
            params["to"] = to
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get candles: {e}")
            return []
    
    # Account APIs (Private)
    
    def get_accounts(self) -> List[Dict]:
        """전체 계좌 조회"""
        url = f"{self.base_url}/accounts"
        headers = self._get_headers()
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return []
    
    # Order APIs (Private)
    
    def place_order(
        self,
        market: str,
        side: str,
        volume: Optional[float] = None,
        price: Optional[float] = None,
        ord_type: str = "limit"
    ) -> Dict:
        """주문하기
        
        Args:
            market: 마켓 코드 (e.g., KRW-BTC)
            side: 주문 종류 (bid: 매수, ask: 매도)
            volume: 주문량
            price: 주문 가격 (지정가 주문 시)
            ord_type: 주문 타입 (limit: 지정가, price: 시장가 매수, market: 시장가 매도)
        """
        url = f"{self.base_url}/orders"
        
        data = {
            "market": market,
            "side": side,
            "ord_type": ord_type
        }
        
        if volume:
            data["volume"] = str(volume)
        if price:
            data["price"] = str(price)
        
        headers = self._get_headers(data)
        
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {"error": str(e)}
    
    def cancel_order(self, uuid: str) -> Dict:
        """주문 취소"""
        url = f"{self.base_url}/order"
        data = {"uuid": uuid}
        headers = self._get_headers(data)
        
        try:
            response = requests.delete(url, params=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {"error": str(e)}
    
    def get_order(self, uuid: str) -> Dict:
        """개별 주문 조회"""
        url = f"{self.base_url}/order"
        data = {"uuid": uuid}
        headers = self._get_headers(data)
        
        try:
            response = requests.get(url, params=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get order: {e}")
            return {"error": str(e)}
    
    def get_orders(
        self,
        market: Optional[str] = None,
        state: str = "wait",
        page: int = 1,
        limit: int = 100
    ) -> List[Dict]:
        """주문 리스트 조회
        
        Args:
            market: 마켓 코드
            state: 주문 상태 (wait: 체결 대기, done: 전체 체결 완료, cancel: 주문 취소)
            page: 페이지
            limit: 요청 개수 (최대 100)
        """
        url = f"{self.base_url}/orders"
        data = {"state": state, "page": page, "limit": limit}
        
        if market:
            data["market"] = market
        
        headers = self._get_headers(data)
        
        try:
            response = requests.get(url, params=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []


# Singleton instance
upbit_client = UpbitClient()
