"""
하이브리드 트레이딩 엔진 (Layer 1)
기술적 지표 중심 + ML 보조 역할

빠른 반응(1초)으로 워뇨띠 스타일 단타 지원
"""
import logging
from typing import Dict, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class HybridTradingEngine:
    """
    기술적 지표 기반 빠른 매매 판단
    ML 모델은 보조 검증 역할만 수행
    """
    
    def __init__(self, ml_predictor=None):
        """
        Args:
            ml_predictor: 선택적 ML 예측기 (검증용)
        """
        self.ml_predictor = ml_predictor
        
        # 기술적 지표 임계값 (v5.2 조정: 안정적 우량주 패턴 매매)
        # 잦은 매매 방지 및 가짜 반등 필터링
        self.thresholds = {
            'rsi_oversold': 30,      # RSI 과매도 (40 -> 30: 확실한 저점만 진입)
            'rsi_overbought': 70,    # RSI 과매수 (60 -> 70: 추세 충분히 반영)
            'volume_surge': 1.5,     # 거래량 급등 (1.3 -> 1.5: 확실한 수급만)
            'bb_lower': 0.1,         # 볼린저 하단 (0.25 -> 0.1: 하단 터치 확실할 때)
            'bb_upper': 0.9,         # 볼린저 상단 (0.75 -> 0.9: 상단 돌파 확실할 때)
            'macd_threshold': 0.0,   # MACD 골든크로스
        }
        
        # 신호 가중치
        self.weights = {
            'rsi': 0.3,    # RSI 비중 확대
            'macd': 0.3,   # 추세 비중 확대
            'volume': 0.2,
            'bollinger': 0.2,
        }
    
    def analyze(self, market: str, df: pd.DataFrame) -> Tuple[str, float, Dict]:
        """
        시장 분석 및 매매 신호 생성
        
        Args:
            market: 마켓 코드 (예: KRW-BTC)
            df: OHLCV + 기술적 지표 데이터프레임
        
        Returns:
            (action, confidence, details)
            - action: "BUY", "SELL", "HOLD"
            - confidence: 0.0 ~ 1.0
            - details: 분석 상세 정보
        """
        try:
            # 최신 데이터
            latest = df.iloc[-1]
            
            # 1. 기술적 지표 분석
            buy_signals, sell_signals = self._analyze_technical_indicators(latest)
            
            # 2. 신호 강도 계산
            buy_strength = sum(buy_signals.values())
            sell_strength = sum(sell_signals.values())
            
            # 3. 기본 판단 (v5.2: 보수적 진입 / 빠른 청산)
            if buy_strength >= 3:
                # 강한 매수 신호 (3개 이상 시에만 진입)
                action = "BUY"
                base_confidence = 0.85
                reason = f"강한 매수 신호 {buy_strength}개 감지"
            elif sell_strength >= 2:
                # 매도 신호는 2개만 떠도 기민하게 반응 (이익 보전)
                action = "SELL"
                base_confidence = 0.80
                reason = f"매도 신호 {sell_strength}개 감지"
            else:
                action = "HOLD"
                base_confidence = 0.5
                reason = "신호 부족 (관망)"
            else:
                # 신호 부족 → ML 보조 사용
                if self.ml_predictor:
                    # DataFrame에서 최근 24개 시퀀스 생성
                    sequence = self._create_sequence_from_df(df, market)
                    logger.info(f"[Hybrid] {market} ML fallback - sequence shape: {sequence.shape if sequence is not None else 'None'}")
                    ml_signal = self.ml_predictor.infer({'market': market, 'sequence': sequence})
                    ml_conf = max(ml_signal.buy_probability, ml_signal.sell_probability)
                    if ml_conf > 0.6:
                        return ml_signal.action, ml_conf, {
                            'source': 'ml_fallback',
                            'buy_signals': buy_signals,
                            'sell_signals': sell_signals,
                            'ml_details': {'buy_prob': ml_signal.buy_probability, 'sell_prob': ml_signal.sell_probability},
                        }
                
                # ML도 없거나 신뢰도 낮음
                return "HOLD", 0.3, {
                    'source': 'insufficient_signals',
                    'buy_signals': buy_signals,
                    'sell_signals': sell_signals,
                    'reason': '충분한 신호 없음',
                }
            
            # 4. ML 검증 (선택적)
            final_confidence = base_confidence
            ml_adjustment = "none"
            
            if self.ml_predictor:
                # DataFrame에서 최근 24개 시퀀스 생성
                sequence = self._create_sequence_from_df(df, market)
                ml_signal = self.ml_predictor.infer({'market': market, 'sequence': sequence})
                ml_action = ml_signal.action
                ml_conf = max(ml_signal.buy_probability, ml_signal.sell_probability)
                
                if ml_action != action and ml_conf > 0.7:
                    # ML이 강하게 반대 → 신중
                    final_confidence *= 0.6
                    ml_adjustment = "reduced"
                    reason += f" (ML 반대 의견으로 신뢰도 감소)"
                elif ml_action == action:
                    # ML이 동의 → 강화
                    final_confidence = min(0.95, final_confidence * 1.1)
                    ml_adjustment = "enhanced"
                    reason += f" (ML 동의로 신뢰도 증가)"
            
            # 5. 상세 정보
            details = {
                'source': 'hybrid',
                'action': action,
                'base_confidence': base_confidence,
                'final_confidence': final_confidence,
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'buy_strength': buy_strength,
                'sell_strength': sell_strength,
                'ml_adjustment': ml_adjustment,
                'reason': reason,
                'latest_indicators': {
                    'rsi': float(latest.get('rsi', 0)),
                    'macd': float(latest.get('macd', 0)),
                    'volume': float(latest.get('volume', 0)),
                    'close': float(latest.get('close', 0)),
                }
            }
            
            logger.info(
                f"[HybridEngine] {market} - {action} ({final_confidence:.1%}): {reason}"
            )
            
            return action, final_confidence, details
            
        except Exception as e:
            logger.error(f"[HybridEngine] 분석 실패 ({market}): {e}")
            return "HOLD", 0.0, {'error': str(e)}
    
    def _analyze_technical_indicators(self, row: pd.Series) -> Tuple[Dict, Dict]:
        """
        기술적 지표 분석
        
        Returns:
            (buy_signals, sell_signals)
            각각 {'indicator': 1 or 0} 형태
        """
        buy_signals = {}
        sell_signals = {}
        
        # 1. RSI (Relative Strength Index)
        rsi = row.get('rsi', 50)
        if rsi < self.thresholds['rsi_oversold']:
            buy_signals['rsi'] = 1  # 과매도 → 매수
        elif rsi > self.thresholds['rsi_overbought']:
            sell_signals['rsi'] = 1  # 과매수 → 매도
        else:
            buy_signals['rsi'] = 0
            sell_signals['rsi'] = 0
        
        # 2. MACD (Moving Average Convergence Divergence)
        macd = row.get('macd', 0)
        macd_signal = row.get('macd_signal', 0)
        macd_diff = macd - macd_signal
        
        if macd_diff > self.thresholds['macd_threshold'] and macd_diff > 0:
            buy_signals['macd'] = 1  # 골든크로스 → 매수
        elif macd_diff < -self.thresholds['macd_threshold'] and macd_diff < 0:
            sell_signals['macd'] = 1  # 데드크로스 → 매도
        else:
            buy_signals['macd'] = 0
            sell_signals['macd'] = 0
        
        # 3. Volume Surge (거래량 급등)
        volume = row.get('volume', 0)
        volume_ma = row.get('volume_ma_20', 1)
        
        if volume_ma > 0:
            volume_ratio = volume / volume_ma
            if volume_ratio > self.thresholds['volume_surge']:
                # 거래량 급등 → 추세 시작 가능성
                # RSI와 조합해서 방향 결정
                if rsi < 50:
                    buy_signals['volume'] = 1  # 저점 + 거래량 → 매수
                elif rsi > 50:
                    sell_signals['volume'] = 1  # 고점 + 거래량 → 매도
                else:
                    buy_signals['volume'] = 0
                    sell_signals['volume'] = 0
            else:
                buy_signals['volume'] = 0
                sell_signals['volume'] = 0
        else:
            buy_signals['volume'] = 0
            sell_signals['volume'] = 0
        
        # 4. Bollinger Bands (볼린저 밴드)
        bb_position = row.get('bb_position', 0.5)  # 0~1 (하단~상단)
        
        if bb_position < self.thresholds['bb_lower']:
            buy_signals['bollinger'] = 1  # 하단 터치 → 매수
        elif bb_position > self.thresholds['bb_upper']:
            sell_signals['bollinger'] = 1  # 상단 터치 → 매도
        else:
            buy_signals['bollinger'] = 0
            sell_signals['bollinger'] = 0
            
        # 5. Trend Filter (EMA 50)
        # 추세 추종: 상승 추세에서는 매수 신호 강화, 하락 추세에서는 매도 신호 강화
        close = row.get('close', 0)
        ema_50 = row.get('ema_50', 0)
        
        if ema_50 > 0:
            if close > ema_50:
                buy_signals['trend'] = 1   # 상승 추세 → 매수 유리
                sell_signals['trend'] = 0
            else:
                buy_signals['trend'] = 0
                sell_signals['trend'] = 1  # 하락 추세 → 매도 유리
        
        return buy_signals, sell_signals
    
    def get_signal_summary(self, market: str, df: pd.DataFrame) -> str:
        """
        사람이 읽기 쉬운 신호 요약
        
        Returns:
            요약 문자열
        """
        action, confidence, details = self.analyze(market, df)
        
        buy_signals = details.get('buy_signals', {})
        sell_signals = details.get('sell_signals', {})
        
        buy_count = sum(buy_signals.values())
        sell_count = sum(sell_signals.values())
        
        active_buy = [k for k, v in buy_signals.items() if v == 1]
        active_sell = [k for k, v in sell_signals.items() if v == 1]
        
        summary = f"""
=== {market} 하이브리드 분석 ===
행동: {action}
신뢰도: {confidence:.1%}

매수 신호 ({buy_count}개): {', '.join(active_buy) if active_buy else '없음'}
매도 신호 ({sell_count}개): {', '.join(active_sell) if active_sell else '없음'}

판단: {details.get('reason', '-')}
        """.strip()
        
        return summary
    
    def _create_sequence_from_df(self, df: pd.DataFrame, market: str) -> np.ndarray:
        """
        DataFrame에서 최근 24시간 시퀀스 생성
        
        Args:
            df: OHLCV 데이터프레임 (기술적 지표 포함)
            market: 마켓 이름
        
        Returns:
            (24, 46) 형태의 시퀀스 또는 None
        """
        try:
            if len(df) < 24:
                logger.warning(f"{market}: 시퀀스 생성 실패 - 데이터 부족 ({len(df)} < 24)")
                return None
            
            # 특성 컬럼 선택 (기본 OHLCV + 기술적 지표)
            feature_cols = ['open', 'high', 'low', 'close', 'volume']
            
            # RSI, MACD 등 있으면 추가
            for col in ['rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_middle', 'bb_lower', 
                       'volume_ma', 'price_ma_5', 'price_ma_20', 'atr']:
                if col in df.columns:
                    feature_cols.append(col)
            
            # 최근 24개 선택
            recent = df[feature_cols].tail(24).values
            
            # 46개 특성으로 패딩 (부족하면 0으로)
            if recent.shape[1] < 46:
                padding = np.zeros((24, 46 - recent.shape[1]))
                sequence = np.hstack([recent, padding])
            else:
                sequence = recent[:, :46]
            
            return sequence.astype(np.float32)
            
        except Exception as e:
            logger.error(f"{market}: 시퀀스 생성 오류 - {e}")
            return None


# 편의 함수
def create_hybrid_engine(ml_predictor=None):
    """
    하이브리드 엔진 생성
    
    Usage:
        from app.ml.predictor import Predictor
        ml = Predictor()
        engine = create_hybrid_engine(ml)
        action, conf, details = engine.analyze("KRW-BTC", df)
    """
    return HybridTradingEngine(ml_predictor=ml_predictor)
