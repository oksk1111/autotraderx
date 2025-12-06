"""
통합 트레이딩 엔진
3가지 전략 레이어를 모두 활용하는 앙상블 접근법

Layer 1: 기술적 지표 기반 (빠른 반응)
Layer 2: 멀티 타임프레임 (트렌드 확인)
Layer 3: 강화학습 (최종 판단) - Optional
"""

from __future__ import annotations

import numpy as np
from typing import Dict, Tuple, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class IntegratedTradingEngine:
    """
    3-Layer 통합 트레이딩 엔진
    
    각 레이어의 장점을 결합하여 더 안정적이고 수익성 높은 거래 결정
    """
    
    def __init__(
        self,
        use_technical: bool = True,
        use_multi_tf: bool = True,
        use_rl: bool = False,  # RL은 선택적
    ):
        self.use_technical = use_technical
        self.use_multi_tf = use_multi_tf
        self.use_rl = use_rl
        
        # Layer 1: 기술적 지표 엔진
        self.technical_engine = None
        if use_technical:
            try:
                from app.trading.hybrid_engine import HybridTradingEngine
                from app.ml.predictor import Predictor
                ml_predictor = Predictor()
                self.technical_engine = HybridTradingEngine(ml_predictor=ml_predictor)
            except Exception as e:
                logger.warning(f"Failed to load HybridTradingEngine: {e}")
                self.use_technical = False
        
        # Layer 2: 멀티 타임프레임 분석
        self.timeframe_analyzer = None
        if use_multi_tf:
            try:
                from app.trading.multi_timeframe_engine import MultiTimeframeEngine
                self.timeframe_analyzer = MultiTimeframeEngine()
            except Exception as e:
                logger.warning(f"Failed to load MultiTimeframeEngine: {e}")
                self.use_multi_tf = False
        
        # Layer 3: 강화학습 에이전트 (선택적)
        self.rl_agent = None
        if use_rl:
            try:
                from app.ml.rl_agent import RLTradingAgent
                self.rl_agent = RLTradingAgent()
            except Exception as e:
                logger.warning(f"RL agent not available: {e}")
                self.use_rl = False
        
        # 가중치 설정 (조정 가능)
        self.weights = self._calculate_weights()
        
        logger.info(
            f"Integrated engine initialized: "
            f"Technical={use_technical}, MultiTF={use_multi_tf}, RL={use_rl}"
        )
    
    def _calculate_weights(self) -> Dict[str, float]:
        """각 레이어의 가중치 계산"""
        weights = {}
        total = 0
        
        if self.use_technical:
            weights['technical'] = 0.3
            total += 0.3
        
        if self.use_multi_tf:
            weights['multi_tf'] = 0.3
            total += 0.3
        
        if self.use_rl:
            weights['rl'] = 0.4
            total += 0.4
        
        # 정규화 (합이 1.0이 되도록)
        if total > 0:
            for key in weights:
                weights[key] = weights[key] / total
        
        return weights
    
    def analyze(self, market: str) -> Tuple[str, float, Dict]:
        """
        통합 분석
        
        Args:
            market: 마켓 코드 (예: KRW-BTC)
        
        Returns:
            (action, confidence, details)
            - action: BUY, SELL, HOLD
            - confidence: 0.0 ~ 1.0
            - details: 각 레이어의 판단 상세
        """
        details = {}
        
        # === Layer 1: 기술적 지표 ===
        if self.use_technical and self.technical_engine:
            # HybridTradingEngine needs DataFrame, so we fetch latest data
            from app.services.data_pipeline import DataPipeline
            pipeline = DataPipeline()
            df = pipeline.get_latest_features(market)
            
            if df is not None and len(df) > 0:
                tech_signal, tech_conf, tech_details = self.technical_engine.analyze(market, df)
                details['technical'] = {
                    'signal': tech_signal,
                    'confidence': tech_conf,
                    'weight': self.weights.get('technical', 0),
                    'details': tech_details
                }
                logger.debug(f"Layer 1 (Technical): {tech_signal} @ {tech_conf:.1%}")
            else:
                tech_signal, tech_conf = "HOLD", 0.3
        else:
            tech_signal, tech_conf = "HOLD", 0.3
        
        # === Layer 2: 멀티 타임프레임 ===
        if self.use_multi_tf and self.timeframe_analyzer:
            trend_signal, trend_conf, trend_details = self.timeframe_analyzer.analyze(market)
            details['multi_tf'] = {
                'signal': trend_signal,
                'confidence': trend_conf,
                'weight': self.weights.get('multi_tf', 0),
                'details': trend_details
            }
            logger.debug(f"Layer 2 (MultiTF): {trend_signal} @ {trend_conf:.1%}")
        else:
            trend_signal, trend_conf = tech_signal, tech_conf
        
        # === Layer 3: 강화학습 (선택적) ===
        if self.use_rl:
            state = self._build_state(market, tech_signal, trend_signal)
            rl_action, rl_conf = self.rl_agent.predict(state)
            details['rl'] = {
                'signal': rl_action,
                'confidence': rl_conf,
                'weight': self.weights.get('rl', 0)
            }
            logger.debug(f"Layer 3 (RL): {rl_action} @ {rl_conf:.1%}")
        else:
            rl_action, rl_conf = None, None
        
        # === 최종 판단 조합 ===
        final_action, final_conf = self._combine_signals(
            tech_signal, tech_conf,
            trend_signal, trend_conf,
            rl_action, rl_conf
        )
        
        details['final'] = {
            'signal': final_action,
            'confidence': final_conf
        }
        
        logger.info(
            f"🎯 {market} Integrated: {final_action} "
            f"(Confidence: {final_conf:.1%})"
        )
        
        return final_action, final_conf, details
    
    def _combine_signals(
        self,
        tech_signal: str, tech_conf: float,
        trend_signal: str, trend_conf: float,
        rl_action: Optional[str], rl_conf: Optional[float]
    ) -> Tuple[str, float]:
        """
        여러 레이어의 신호를 조합하여 최종 판단
        
        전략:
        1. 모두 일치 → 매우 강한 신호
        2. 2개 일치 → 강한 신호
        3. 불일치 → 신중 (RL 있으면 RL 따름, 없으면 HOLD)
        """
        
        # === 케이스 1: RL 없음 (Layer 1 + 2만) ===
        if not self.use_rl:
            if tech_signal == trend_signal:
                # 기술적 + 트렌드 일치 → 강한 신호
                final_action = tech_signal
                final_conf = (
                    tech_conf * self.weights['technical'] +
                    trend_conf * self.weights['multi_tf']
                )
            else:
                # 불일치 → HOLD
                final_action = "HOLD"
                final_conf = 0.3
            
            return final_action, final_conf
        
        # === 케이스 2: RL 있음 (Layer 1 + 2 + 3) ===
        signals = [tech_signal, trend_signal, rl_action]
        
        # 투표 방식: 가장 많이 나온 신호
        vote_counts = {}
        for signal in signals:
            if signal:
                vote_counts[signal] = vote_counts.get(signal, 0) + 1
        
        if not vote_counts:
            return "HOLD", 0.3
        
        # 최다 득표 신호
        winning_signal = max(vote_counts, key=vote_counts.get)
        vote_ratio = vote_counts[winning_signal] / len([s for s in signals if s])
        
        # 신뢰도 계산 (가중 평균)
        total_conf = 0.0
        total_weight = 0.0
        
        if tech_signal == winning_signal:
            total_conf += tech_conf * self.weights['technical']
            total_weight += self.weights['technical']
        
        if trend_signal == winning_signal:
            total_conf += trend_conf * self.weights['multi_tf']
            total_weight += self.weights['multi_tf']
        
        if rl_action == winning_signal:
            total_conf += rl_conf * self.weights['rl']
            total_weight += self.weights['rl']
        
        if total_weight > 0:
            final_conf = total_conf / total_weight
        else:
            final_conf = 0.3
        
        # 투표 비율에 따른 신뢰도 조정
        if vote_ratio == 1.0:
            # 만장일치 → 신뢰도 그대로
            pass
        elif vote_ratio >= 0.67:
            # 2/3 일치 → 신뢰도 80%
            final_conf *= 0.8
        else:
            # 의견 분분 → 신뢰도 60%
            final_conf *= 0.6
        
        return winning_signal, final_conf
    
    def _build_state(
        self,
        market: str,
        tech_signal: str,
        trend_signal: str
    ) -> np.ndarray:
        """
        RL 에이전트를 위한 상태 벡터 구성
        
        Returns:
            numpy array: [features, tech_signal_onehot, trend_signal_onehot]
        """
        # 기본 features (기존 ML 모델에서 사용하는 것)
        from app.ml.predictor import predict_signal
        features = self._get_market_features(market)  # shape: (46,)
        
        # 원-핫 인코딩: BUY, SELL, HOLD
        tech_vector = self._encode_signal(tech_signal)    # shape: (3,)
        trend_vector = self._encode_signal(trend_signal)  # shape: (3,)
        
        # 결합
        state = np.concatenate([
            features,
            tech_vector,
            trend_vector
        ])  # shape: (52,)
        
        return state
    
    def _encode_signal(self, signal: str) -> np.ndarray:
        """신호를 원-핫 벡터로 인코딩"""
        if signal == "BUY":
            return np.array([1, 0, 0])
        elif signal == "SELL":
            return np.array([0, 1, 0])
        else:  # HOLD
            return np.array([0, 0, 1])
    
    def _get_market_features(self, market: str) -> np.ndarray:
        """시장 데이터를 features로 변환"""
        # TODO: 실제 구현 필요
        # 임시로 랜덤 features 반환
        return np.random.rand(46)


# === Phase 1 구현: Layer 1 + Layer 2만 사용 ===
class SimpleIntegratedEngine(IntegratedTradingEngine):
    """
    간단한 통합 엔진 (RL 없이)
    
    기술적 지표 + 멀티 타임프레임만 사용
    가장 빠르게 구현하고 효과를 볼 수 있음
    """
    
    def __init__(self):
        super().__init__(
            use_technical=True,
            use_multi_tf=True,
            use_rl=False  # RL 없음
        )
        logger.info("Simple Integrated Engine (Phase 1) initialized")


# === Phase 2 구현: 모든 레이어 사용 ===
class FullIntegratedEngine(IntegratedTradingEngine):
    """
    전체 통합 엔진 (RL 포함)
    
    모든 레이어를 활용하여 최고 성능 추구
    """
    
    def __init__(self):
        super().__init__(
            use_technical=True,
            use_multi_tf=True,
            use_rl=True  # RL 포함
        )
        logger.info("Full Integrated Engine (Phase 2) initialized")
