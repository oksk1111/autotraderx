"""
Enhanced Trading Engine
기존 TradingEngine을 확장하여 하이브리드 전략 추가
"""
import logging
from typing import Dict, Tuple, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class EnhancedTradingEngine:
    """
    3-Layer 통합 트레이딩 엔진
    
    동작 방식:
    1. Layer 1: 하이브리드 엔진으로 빠른 판단 (기술적 지표)
    2. Layer 2: 멀티 타임프레임으로 트렌드 확인
    3. Layer 3: RL Agent로 최종 판단 (선택적)
    4. 신호 조합하여 최종 거래 결정
    """
    
    def __init__(self, use_rl: bool = True):
        """
        Args:
            use_rl: RL Agent 사용 여부 (기본값: True)
        """
        self.use_rl = use_rl
        
        # Hybrid engine (Layer 1)
        try:
            from app.trading.hybrid_engine import HybridTradingEngine
            from app.ml.predictor import HybridPredictor
            
            ml_predictor = HybridPredictor()
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
        
        # RL Agent (Layer 3 - Optional)
        self.rl_agent = None
        self.has_rl = False
        
        if use_rl:
            try:
                from app.ml.rl_agent import RLTradingAgent
                self.rl_agent = RLTradingAgent()
                self.has_rl = self.rl_agent.is_available()
                
                if self.has_rl:
                    logger.info("✅ RL Agent loaded and ready")
                else:
                    logger.warning("⚠️ RL Agent not trained yet")
            except Exception as e:
                logger.warning(f"⚠️ RL Agent not available: {e}")
                self.rl_agent = None
                self.has_rl = False
    
    def get_enhanced_signal(self, market: str, df: pd.DataFrame) -> Tuple[str, float, Dict]:
        """
        향상된 거래 신호 생성 (3-Layer 통합)
        
        Args:
            market: 마켓 코드 (KRW-BTC)
            df: OHLCV + 기술적 지표 데이터프레임
        
        Returns:
            (action, confidence, details)
            - action: BUY, SELL, HOLD
            - confidence: 0.0 ~ 1.0 (enhanced)
            - details: 각 엔진의 판단 내용
        """
        if not self.has_hybrid and not self.has_multi_tf and not self.has_rl:
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
        
        # Layer 3: RL Agent (선택적)
        rl_action = None
        rl_conf = None
        
        if self.has_rl and self.rl_agent:
            try:
                # RL 에이전트를 위한 상태 벡터 구성
                state = self._build_rl_state(
                    df,
                    hybrid_action,
                    multi_tf_action
                )
                
                rl_action, rl_conf = self.rl_agent.predict(state)
                details['rl'] = {
                    'action': rl_action,
                    'confidence': rl_conf
                }
                logger.info(f"[RL] {market}: {rl_action} @ {rl_conf:.1%}")
            except Exception as e:
                logger.error(f"[RL] Error: {e}")
                rl_action = None
                rl_conf = None
        
        # 신호 조합
        final_action, final_conf, reason = self._combine_signals(
            hybrid_action, hybrid_conf,
            multi_tf_action, multi_tf_conf,
            rl_action, rl_conf
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
        multi_tf_conf: float,
        rl_action: Optional[str] = None,
        rl_conf: Optional[float] = None
    ) -> Tuple[str, float, str]:
        """
        3개 레이어의 신호 조합
        
        Returns:
            (action, confidence, reason)
        """
        # === RL 없는 경우 (Layer 1 + 2만) ===
        if rl_action is None or not self.has_rl:
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
        
        # === RL 있는 경우 (Layer 1 + 2 + 3) ===
        signals = [hybrid_action, multi_tf_action, rl_action]
        
        # 투표 방식: 가장 많이 나온 신호
        vote_counts = {}
        for signal in signals:
            if signal:
                vote_counts[signal] = vote_counts.get(signal, 0) + 1
        
        if not vote_counts:
            return "HOLD", 0.3, "모든 신호 없음"
        
        # 최다 득표 신호
        winning_signal = max(vote_counts.keys(), key=lambda x: vote_counts[x])
        vote_count = vote_counts[winning_signal]
        
        # 신뢰도 계산 (가중 평균)
        total_conf = 0.0
        total_weight = 0.0
        
        weights = {'hybrid': 0.3, 'multi_tf': 0.3, 'rl': 0.4}
        
        if hybrid_action == winning_signal:
            total_conf += hybrid_conf * weights['hybrid']
            total_weight += weights['hybrid']
        
        if multi_tf_action == winning_signal:
            total_conf += multi_tf_conf * weights['multi_tf']
            total_weight += weights['multi_tf']
        
        if rl_action == winning_signal and rl_conf is not None:
            total_conf += rl_conf * weights['rl']
            total_weight += weights['rl']
        
        if total_weight > 0:
            final_conf = total_conf / total_weight
        else:
            final_conf = 0.3
        
        # 투표 비율에 따른 신뢰도 조정
        if vote_count == 3:
            # 만장일치 → 신뢰도 그대로
            reason = f"3-Layer 만장일치 ({winning_signal})"
        elif vote_count == 2:
            # 2/3 일치 → 신뢰도 80%
            final_conf *= 0.8
            reason = f"2/3 일치 ({winning_signal})"
        else:
            # 의견 분분 → 신뢰도 60%
            final_conf *= 0.6
            reason = f"신호 불일치 ({winning_signal} 선택)"
        
        return winning_signal, final_conf, reason
    
    def _build_rl_state(
        self,
        df: pd.DataFrame,
        tech_signal: str,
        trend_signal: str
    ) -> np.ndarray:
        """
        RL 에이전트를 위한 상태 벡터 구성
        
        Args:
            df: 시장 데이터 (features 포함)
            tech_signal: Layer 1 신호
            trend_signal: Layer 2 신호
        
        Returns:
            52차원 상태 벡터
        """
        # 기본 features (46차원)
        if df is None or len(df) == 0:
            features = np.zeros(46, dtype=np.float32)
        else:
            # 최신 행의 features 추출
            latest_row = df.iloc[-1]
            features = latest_row.values[:46].astype(np.float32)
        
        # 원-핫 인코딩: BUY, SELL, HOLD
        tech_vector = self._encode_signal(tech_signal)
        trend_vector = self._encode_signal(trend_signal)
        
        # 결합
        state = np.concatenate([
            features,
            tech_vector,
            trend_vector
        ])
        
        return state
    
    def _encode_signal(self, signal: str) -> np.ndarray:
        """신호를 원-핫 벡터로 인코딩"""
        if signal == "BUY":
            return np.array([1, 0, 0], dtype=np.float32)
        elif signal == "SELL":
            return np.array([0, 1, 0], dtype=np.float32)
        else:  # HOLD
            return np.array([0, 0, 1], dtype=np.float32)
    
    def is_available(self) -> bool:
        """향상된 엔진 사용 가능 여부"""
        return self.has_hybrid or self.has_multi_tf or self.has_rl
    
    def get_status(self) -> Dict:
        """엔진 상태 정보"""
        return {
            'hybrid_available': self.has_hybrid,
            'multi_tf_available': self.has_multi_tf,
            'rl_available': self.has_rl,
            'overall_status': 'ready' if self.is_available() else 'unavailable'
        }


# 전역 인스턴스 (싱글톤)
_enhanced_engine = None


def get_enhanced_engine(use_rl: bool = False) -> EnhancedTradingEngine:
    """
    Enhanced engine 싱글톤 인스턴스 반환
    
    Args:
        use_rl: RL Agent 사용 여부 (기본값: False)
    
    Usage:
        from app.trading.enhanced_engine import get_enhanced_engine
        
        # Layer 1 + 2만 사용
        engine = get_enhanced_engine()
        
        # Layer 1 + 2 + 3 (RL) 사용
        engine = get_enhanced_engine(use_rl=True)
        
        if engine.is_available():
            action, conf, details = engine.get_enhanced_signal(market, df)
    """
    global _enhanced_engine
    if _enhanced_engine is None:
        _enhanced_engine = EnhancedTradingEngine(use_rl=use_rl)
    return _enhanced_engine
