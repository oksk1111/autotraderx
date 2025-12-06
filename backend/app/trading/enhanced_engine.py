"""
Enhanced Trading Engine
기존 TradingEngine을 확장하여 하이브리드 전략 추가
"""
import logging
from typing import Dict, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class EnhancedTradingEngine:
    """
    기존 ML 기반 엔진에 하이브리드 및 멀티 타임프레임 전략 추가
    
    동작 방식:
    1. 하이브리드 엔진으로 빠른 판단 (기술적 지표)
    2. 멀티 타임프레임으로 트렌드 확인
    3. 두 신호가 일치하면 높은 신뢰도로 거래
    """
    
    def __init__(self):
        # Hybrid engine (Layer 1)
        try:
            from app.trading.hybrid_engine import HybridTradingEngine
            from app.ml.predictor import Predictor
            
            ml_predictor = Predictor()
            self.hybrid_engine = HybridTradingEngine(ml_predictor=ml_predictor)
            self.has_hybrid = True
            logger.info("✅ Hybrid engine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Hybrid engine not available: {e}")
            self.hybrid_engine = None
            self.has_hybrid = False
        
        # Multi-timeframe engine (Layer 2)
        try:
            from app.trading.multi_timeframe_engine import MultiTimeframeEngine
            self.multi_tf_engine = MultiTimeframeEngine()
            self.has_multi_tf = True
            logger.info("✅ Multi-timeframe engine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Multi-timeframe engine not available: {e}")
            self.multi_tf_engine = None
            self.has_multi_tf = False
    
    def get_enhanced_signal(self, market: str, df: pd.DataFrame) -> Tuple[str, float, Dict]:
        """
        향상된 거래 신호 생성
        
        Args:
            market: 마켓 코드 (KRW-BTC)
            df: OHLCV + 기술적 지표 데이터프레임
        
        Returns:
            (action, confidence, details)
            - action: BUY, SELL, HOLD
            - confidence: 0.0 ~ 1.0 (enhanced)
            - details: 각 엔진의 판단 내용
        """
        if not self.has_hybrid and not self.has_multi_tf:
            # 향상된 엔진 없음 - 기본 신호
            return "HOLD", 0.3, {'error': 'no_enhanced_engines'}
        
        details = {}
        
        # Layer 1: Hybrid (기술적 지표)
        hybrid_action = "HOLD"
        hybrid_conf = 0.3
        
        if self.has_hybrid and df is not None and len(df) > 20:
            try:
                hybrid_action, hybrid_conf, hybrid_details = self.hybrid_engine.analyze(market, df)
                details['hybrid'] = {
                    'action': hybrid_action,
                    'confidence': hybrid_conf,
                    'details': hybrid_details
                }
                logger.info(f"[Hybrid] {market}: {hybrid_action} @ {hybrid_conf:.1%}")
            except Exception as e:
                logger.error(f"[Hybrid] Error: {e}")
        
        # Layer 2: Multi-timeframe (트렌드)
        multi_tf_action = "HOLD"
        multi_tf_conf = 0.3
        
        if self.has_multi_tf:
            try:
                multi_tf_action, multi_tf_conf, multi_tf_details = self.multi_tf_engine.analyze(market)
                details['multi_tf'] = {
                    'action': multi_tf_action,
                    'confidence': multi_tf_conf,
                    'details': multi_tf_details
                }
                logger.info(f"[MultiTF] {market}: {multi_tf_action} @ {multi_tf_conf:.1%}")
            except Exception as e:
                logger.error(f"[MultiTF] Error: {e}")
        
        # 신호 조합
        final_action, final_conf, reason = self._combine_signals(
            hybrid_action, hybrid_conf,
            multi_tf_action, multi_tf_conf
        )
        
        details['final'] = {
            'action': final_action,
            'confidence': final_conf,
            'reason': reason
        }
        
        logger.info(f"[Enhanced] {market}: {final_action} @ {final_conf:.1%} - {reason}")
        
        return final_action, final_conf, details
    
    def _combine_signals(
        self,
        hybrid_action: str,
        hybrid_conf: float,
        multi_tf_action: str,
        multi_tf_conf: float
    ) -> Tuple[str, float, str]:
        """
        두 레이어의 신호 조합
        
        Returns:
            (action, confidence, reason)
        """
        # 두 신호가 모두 HOLD인 경우
        if hybrid_action == "HOLD" and multi_tf_action == "HOLD":
            return "HOLD", 0.3, "두 엔진 모두 관망"
        
        # 두 신호가 일치하는 경우 (강한 신호)
        if hybrid_action == multi_tf_action and hybrid_action != "HOLD":
            # 신뢰도 부스트 (두 엔진 동의)
            combined_conf = min(0.95, (hybrid_conf + multi_tf_conf) / 2 * 1.2)
            return hybrid_action, combined_conf, f"두 엔진 일치 ({hybrid_action})"
        
        # 한쪽만 거래 신호인 경우
        if hybrid_action != "HOLD" and multi_tf_action == "HOLD":
            # Hybrid만 신호 → 신뢰도 약간 감소
            adjusted_conf = hybrid_conf * 0.9
            return hybrid_action, adjusted_conf, "Hybrid 신호만 감지"
        
        if hybrid_action == "HOLD" and multi_tf_action != "HOLD":
            # Multi-TF만 신호 → 신뢰도 약간 감소
            adjusted_conf = multi_tf_conf * 0.9
            return multi_tf_action, adjusted_conf, "트렌드 신호만 감지"
        
        # 두 신호가 충돌하는 경우 (BUY vs SELL)
        if hybrid_action != multi_tf_action and hybrid_action != "HOLD" and multi_tf_action != "HOLD":
            # 더 높은 신뢰도를 가진 신호 선택, 단 신뢰도 크게 감소
            if hybrid_conf > multi_tf_conf:
                return hybrid_action, hybrid_conf * 0.6, "신호 충돌 (Hybrid 우선)"
            else:
                return multi_tf_action, multi_tf_conf * 0.6, "신호 충돌 (트렌드 우선)"
        
        # 기본값 (도달하지 않아야 함)
        return "HOLD", 0.2, "알 수 없는 조합"
    
    def is_available(self) -> bool:
        """향상된 엔진 사용 가능 여부"""
        return self.has_hybrid or self.has_multi_tf
    
    def get_status(self) -> Dict:
        """엔진 상태 정보"""
        return {
            'hybrid_available': self.has_hybrid,
            'multi_tf_available': self.has_multi_tf,
            'overall_status': 'ready' if self.is_available() else 'unavailable'
        }


# 전역 인스턴스 (싱글톤)
_enhanced_engine = None


def get_enhanced_engine() -> EnhancedTradingEngine:
    """
    Enhanced engine 싱글톤 인스턴스 반환
    
    Usage:
        from app.trading.enhanced_engine import get_enhanced_engine
        
        engine = get_enhanced_engine()
        if engine.is_available():
            action, conf, details = engine.get_enhanced_signal(market, df)
    """
    global _enhanced_engine
    if _enhanced_engine is None:
        _enhanced_engine = EnhancedTradingEngine()
    return _enhanced_engine
