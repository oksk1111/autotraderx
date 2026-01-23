"""
신호 필터링 서비스

연속적인 동일 신호를 필터링하고, 신호가 반전될 때만 거래를 허용합니다.
Redis를 사용하여 각 코인의 마지막 신호를 추적합니다.
"""
from __future__ import annotations

import redis
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SignalFilter:
    """신호 필터 - 연속 신호 방지 및 반전 신호만 허용"""
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        redis_url = self.settings.redis_url or "redis://localhost:6379/0"
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.ttl = 86400  # 24시간 후 자동 만료
        
    def _get_key(self, market: str) -> str:
        """Redis 키 생성"""
        return f"signal:last:{market}"
    
    def _get_confidence_key(self, market: str) -> str:
        """신뢰도 Redis 키 생성"""
        return f"signal:confidence:{market}"
    
    def get_last_signal(self, market: str) -> Optional[str]:
        """
        마지막 신호 조회
        
        Args:
            market: 시장 코드 (예: KRW-BTC)
            
        Returns:
            마지막 신호 ("BUY" 또는 "SELL") 또는 None (처음 신호)
        """
        try:
            key = self._get_key(market)
            last_signal = self.redis_client.get(key)
            return last_signal
        except Exception as e:
            logger.error(f"Redis 조회 실패 ({market}): {e}")
            return None
    
    def get_last_confidence(self, market: str) -> float:
        """
        마지막 거래의 신뢰도 조회
        
        Args:
            market: 시장 코드 (예: KRW-BTC)
            
        Returns:
            마지막 신뢰도 (0.0 ~ 1.0) 또는 0.0 (기록 없음)
        """
        try:
            key = self._get_confidence_key(market)
            confidence_str = self.redis_client.get(key)
            return float(confidence_str) if confidence_str else 0.0
        except Exception as e:
            logger.error(f"Redis 신뢰도 조회 실패 ({market}): {e}")
            return 0.0
    
    def set_last_signal(self, market: str, signal: str, confidence: float = 0.0) -> None:
        """
        마지막 신호 및 신뢰도 저장
        
        Args:
            market: 시장 코드 (예: KRW-BTC)
            signal: 신호 ("BUY" 또는 "SELL")
            confidence: 신호 신뢰도 (0.0 ~ 1.0)
        """
        try:
            key = self._get_key(market)
            conf_key = self._get_confidence_key(market)
            self.redis_client.setex(key, self.ttl, signal)
            self.redis_client.setex(conf_key, self.ttl, str(confidence))
            logger.debug(f"신호 저장: {market} -> {signal} (신뢰도: {confidence:.1%})")
        except Exception as e:
            logger.error(f"Redis 저장 실패 ({market}): {e}")
    
    def should_allow_trade(self, market: str, current_signal: str, confidence: float = 0.0) -> tuple[bool, str]:
        """
        거래 허용 여부 판단 (v5.0 완화)
        
        v5.0 변경사항:
        - 연속 신호 허용 임계값 80% → 70%로 완화
        - 급등장에서 더 많은 기회 포착
        - BUY 연속 신호는 더 관대하게 처리
        
        규칙:
        1. 신호 반전 (BUY ↔ SELL): 항상 허용
        2. 연속 BUY + 신뢰도 ≥ 70%: 허용 (급등장 대응)
        3. 연속 SELL + 신뢰도 ≥ 75%: 허용
        4. 이미 90% 이상으로 거래했다면: 차단 (최고점 매수 방지)
        
        Args:
            market: 시장 코드 (예: KRW-BTC)
            current_signal: 현재 신호 ("BUY", "SELL", "HOLD")
            confidence: 신호 신뢰도 (0.0 ~ 1.0)
            
        Returns:
            (허용 여부, 사유) 튜플
        """
        # HOLD 신호는 항상 거래 없음
        if current_signal == "HOLD":
            return False, "HOLD 신호"
        
        last_signal = self.get_last_signal(market)
        
        # 처음 신호 (이전 기록 없음) - 허용
        if last_signal is None:
            logger.info(f"🟢 {market}: 첫 신호 {current_signal} - 거래 허용")
            return True, f"첫 {current_signal} 신호"
        
        # 신호 반전 (BUY ↔ SELL) - 항상 허용
        if last_signal != current_signal:
            logger.info(f"🟢 {market}: 신호 반전 {last_signal} → {current_signal} - 거래 허용")
            return True, f"신호 반전: {last_signal} → {current_signal}"
        
        # 여기서부터는 연속 동일 신호 처리
        last_confidence = self.get_last_confidence(market)
        
        # v5.0: 이미 매우 고신뢰도(≥90%)로 거래했다면 차단 (최고점 매수 방지)
        if last_confidence >= 0.90:
            logger.info(f"🔴 {market}: 연속 {current_signal} 신호 차단 (이전 거래 이미 최고신뢰도: {last_confidence:.1%})")
            return False, f"최고신뢰도 거래 후 연속 신호 (이전: {last_confidence:.1%})"
        
        # v5.0: BUY 연속 신호는 더 관대하게 처리 (급등장 대응)
        if current_signal == "BUY":
            if confidence >= 0.70:  # 80% → 70%로 완화
                logger.info(f"🟡 {market}: 연속 BUY 신호 허용 (급등장 대응, 신뢰도: {confidence:.1%})")
                return True, f"급등장 연속 BUY (신뢰도: {confidence:.1%})"
        
        # SELL 연속 신호는 75% 이상이면 허용
        if current_signal == "SELL":
            if confidence >= 0.75:
                logger.info(f"🟡 {market}: 연속 SELL 신호 허용 (하락 방어, 신뢰도: {confidence:.1%})")
                return True, f"하락 방어 연속 SELL (신뢰도: {confidence:.1%})"
        
        # 연속 신호 + 낮은 신뢰도 - 차단
        logger.info(f"🔴 {market}: 연속 {current_signal} 신호 차단 (현재 신뢰도: {confidence:.1%} < 필요 70%)")
        return False, f"연속 {current_signal} 신호 (신뢰도 부족)"
    
    def reset_signal(self, market: str) -> None:
        """
        특정 시장의 신호 기록 초기화
        
        Args:
            market: 시장 코드 (예: KRW-BTC)
        """
        try:
            key = self._get_key(market)
            self.redis_client.delete(key)
            logger.info(f"신호 초기화: {market}")
        except Exception as e:
            logger.error(f"Redis 삭제 실패 ({market}): {e}")
    
    def reset_all_signals(self) -> None:
        """모든 시장의 신호 기록 초기화"""
        try:
            pattern = self._get_key("*")
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"모든 신호 초기화: {len(keys)}개 삭제")
        except Exception as e:
            logger.error(f"Redis 전체 삭제 실패: {e}")
