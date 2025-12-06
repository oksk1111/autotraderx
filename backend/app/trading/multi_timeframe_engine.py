"""
멀티 타임프레임 분석 엔진 (Layer 2)
장기 트렌드 + 중기 모멘텀 + 단기 타이밍

워뇨띠 스타일: 큰 흐름 속에서 진입 타이밍 포착
"""
import logging
from typing import Dict, Tuple
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class MultiTimeframeEngine:
    """
    여러 시간대 동시 분석으로 안정적 매매
    
    - 1시간봉: 전체 트렌드 (UP/DOWN/SIDEWAYS)
    - 15분봉: 모멘텀 강도 (STRONG/WEAK)
    - 5분봉: 진입 타이밍 (BUY/SELL/HOLD)
    """
    
    def __init__(self, data_dir: str = "/app/data/raw"):
        """
        Args:
            data_dir: 멀티 타임프레임 데이터 디렉토리
        """
        self.data_dir = Path(data_dir)
        
        # 트렌드 판단 임계값
        self.trend_thresholds = {
            'strong_up': 0.015,      # 1.5% 이상 상승
            'strong_down': -0.015,   # 1.5% 이상 하락
            'momentum_strong': 0.01,  # 1% 이상 변동
        }
    
    def analyze(self, market: str) -> Tuple[str, float, Dict]:
        """
        멀티 타임프레임 분석
        
        Args:
            market: 마켓 코드 (예: KRW-BTC)
        
        Returns:
            (action, confidence, details)
        """
        try:
            # 1. 각 타임프레임 데이터 로드
            df_1h = self._load_timeframe_data(market, "minute60")
            df_15m = self._load_timeframe_data(market, "minute15")
            df_5m = self._load_timeframe_data(market, "minute5")
            
            if df_1h is None or df_15m is None or df_5m is None:
                logger.warning(f"[MultiTF] {market} 데이터 부족")
                return "HOLD", 0.2, {'error': 'insufficient_data'}
            
            # 2. 각 타임프레임 분석
            trend_1h = self._analyze_trend(df_1h, "1h")
            momentum_15m = self._analyze_momentum(df_15m, "15m")
            entry_5m = self._analyze_entry(df_5m, "5m")
            
            # 3. 신호 조합
            action, confidence, reason = self._combine_signals(
                trend_1h, momentum_15m, entry_5m
            )
            
            # 4. 상세 정보
            details = {
                'source': 'multi_timeframe',
                'trend_1h': trend_1h,
                'momentum_15m': momentum_15m,
                'entry_5m': entry_5m,
                'action': action,
                'confidence': confidence,
                'reason': reason,
                'latest_prices': {
                    '1h': float(df_1h.iloc[-1]['close']),
                    '15m': float(df_15m.iloc[-1]['close']),
                    '5m': float(df_5m.iloc[-1]['close']),
                }
            }
            
            logger.info(
                f"[MultiTF] {market} - {action} ({confidence:.1%}): "
                f"트렌드={trend_1h['direction']}, "
                f"모멘텀={momentum_15m['strength']}, "
                f"진입={entry_5m['signal']}"
            )
            
            return action, confidence, details
            
        except Exception as e:
            logger.error(f"[MultiTF] 분석 실패 ({market}): {e}")
            return "HOLD", 0.0, {'error': str(e)}
    
    def _load_timeframe_data(self, market: str, interval: str) -> pd.DataFrame:
        """
        타임프레임 데이터 로드
        
        Args:
            market: KRW-BTC
            interval: minute5, minute15, minute60
        
        Returns:
            DataFrame 또는 None
        """
        file_path = self.data_dir / f"{market}_{interval}.csv"
        
        if not file_path.exists():
            logger.warning(f"[MultiTF] 파일 없음: {file_path}")
            return None
        
        try:
            df = pd.read_csv(file_path)
            if len(df) < 20:  # 최소 20개 필요
                return None
            return df
        except Exception as e:
            logger.error(f"[MultiTF] 데이터 로드 실패: {e}")
            return None
    
    def _analyze_trend(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """
        장기 트렌드 분석 (1시간봉)
        
        Returns:
            {
                'direction': 'UP' | 'DOWN' | 'SIDEWAYS',
                'strength': float (0~1),
                'details': {...}
            }
        """
        # 최근 20개 캔들의 가격 변화
        latest = df.iloc[-1]
        past = df.iloc[-20]
        
        price_change = (latest['close'] - past['close']) / past['close']
        
        # 이동평균선 기울기
        ma_20 = df['close'].rolling(20).mean()
        ma_slope = (ma_20.iloc[-1] - ma_20.iloc[-5]) / ma_20.iloc[-5]
        
        # 방향 판단
        if price_change > self.trend_thresholds['strong_up']:
            direction = "UP"
            strength = min(1.0, abs(price_change) / 0.05)  # 5% = 100%
        elif price_change < self.trend_thresholds['strong_down']:
            direction = "DOWN"
            strength = min(1.0, abs(price_change) / 0.05)
        else:
            direction = "SIDEWAYS"
            strength = 0.3  # 횡보는 낮은 강도
        
        return {
            'direction': direction,
            'strength': strength,
            'price_change': price_change,
            'ma_slope': ma_slope,
            'timeframe': timeframe,
        }
    
    def _analyze_momentum(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """
        중기 모멘텀 분석 (15분봉)
        
        Returns:
            {
                'strength': 'STRONG' | 'WEAK',
                'direction': 'UP' | 'DOWN',
                'value': float
            }
        """
        # 최근 10개 캔들
        recent = df.iloc[-10:]
        
        # 가격 변동률
        price_change = (recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
        
        # 거래량 변화
        volume_ratio = recent['volume'].iloc[-5:].mean() / recent['volume'].iloc[:5].mean()
        
        # 모멘텀 판단
        momentum_value = abs(price_change) * volume_ratio
        
        if momentum_value > self.trend_thresholds['momentum_strong']:
            strength = "STRONG"
        else:
            strength = "WEAK"
        
        direction = "UP" if price_change > 0 else "DOWN"
        
        return {
            'strength': strength,
            'direction': direction,
            'value': momentum_value,
            'price_change': price_change,
            'volume_ratio': volume_ratio,
            'timeframe': timeframe,
        }
    
    def _analyze_entry(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """
        단기 진입 타이밍 분석 (5분봉)
        
        Returns:
            {
                'signal': 'BUY' | 'SELL' | 'HOLD',
                'confidence': float (0~1)
            }
        """
        latest = df.iloc[-1]
        
        # RSI
        rsi = latest.get('rsi', 50)
        
        # MACD
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)
        
        # 볼린저 밴드
        bb_position = latest.get('bb_position', 0.5)
        
        # 신호 카운트
        buy_score = 0
        sell_score = 0
        
        if rsi < 35:
            buy_score += 1
        elif rsi > 65:
            sell_score += 1
        
        if macd > macd_signal:
            buy_score += 1
        elif macd < macd_signal:
            sell_score += 1
        
        if bb_position < 0.3:
            buy_score += 1
        elif bb_position > 0.7:
            sell_score += 1
        
        # 최종 신호
        if buy_score >= 2:
            signal = "BUY"
            confidence = 0.6 + (buy_score - 2) * 0.15
        elif sell_score >= 2:
            signal = "SELL"
            confidence = 0.6 + (sell_score - 2) * 0.15
        else:
            signal = "HOLD"
            confidence = 0.3
        
        return {
            'signal': signal,
            'confidence': confidence,
            'buy_score': buy_score,
            'sell_score': sell_score,
            'rsi': rsi,
            'timeframe': timeframe,
        }
    
    def _combine_signals(
        self,
        trend_1h: Dict,
        momentum_15m: Dict,
        entry_5m: Dict
    ) -> Tuple[str, float, str]:
        """
        3개 시간대 신호 조합
        
        Returns:
            (action, confidence, reason)
        """
        trend = trend_1h['direction']
        momentum = momentum_15m['strength']
        entry = entry_5m['signal']
        
        # === 상승 추세 ===
        if trend == "UP":
            if momentum == "STRONG" and entry == "BUY":
                # 완벽한 매수 타이밍
                return "BUY", 0.90, "상승 트렌드 + 강한 모멘텀 + 매수 타이밍"
            
            elif momentum == "WEAK" and entry == "BUY":
                # 괜찮은 매수 타이밍
                return "BUY", 0.70, "상승 트렌드 + 약한 모멘텀 + 매수 타이밍"
            
            elif entry == "SELL":
                # 추세는 상승인데 단기 매도 신호 → 조심
                return "HOLD", 0.40, "상승 트렌드지만 단기 매도 신호"
            
            else:
                # 추세는 좋은데 진입 타이밍 아님
                return "HOLD", 0.50, "상승 트렌드지만 진입 타이밍 아님"
        
        # === 하락 추세 ===
        elif trend == "DOWN":
            if momentum == "STRONG" and entry == "SELL":
                # 명확한 매도 신호 (보유 중이라면)
                return "SELL", 0.85, "하락 트렌드 + 강한 하락 모멘텀"
            
            else:
                # 하락장에서는 거래 안 함 (리스크 회피)
                return "HOLD", 0.20, "하락 트렌드 - 거래 자제"
        
        # === 횡보 ===
        else:  # SIDEWAYS
            if momentum == "STRONG" and entry == "BUY":
                # 횡보 돌파 가능성
                return "BUY", 0.65, "횡보 중 강한 매수 신호"
            
            elif entry == "BUY":
                # 약한 매수 신호
                return "BUY", 0.50, "횡보 중 매수 타이밍"
            
            elif entry == "SELL":
                # 약한 매도 신호
                return "SELL", 0.50, "횡보 중 매도 타이밍"
            
            else:
                # 횡보 중 관망
                return "HOLD", 0.35, "횡보 - 명확한 신호 대기"
    
    def get_analysis_summary(self, market: str) -> str:
        """
        사람이 읽기 쉬운 분석 요약
        """
        action, confidence, details = self.analyze(market)
        
        trend = details['trend_1h']
        momentum = details['momentum_15m']
        entry = details['entry_5m']
        
        summary = f"""
=== {market} 멀티 타임프레임 분석 ===
최종 판단: {action} (신뢰도 {confidence:.1%})

[1시간봉] 트렌드: {trend['direction']} (강도: {trend['strength']:.1%})
  - 가격 변화: {trend['price_change']:.2%}

[15분봉] 모멘텀: {momentum['strength']} {momentum['direction']}
  - 변동: {momentum['value']:.2%}

[5분봉] 진입: {entry['signal']} (RSI: {entry['rsi']:.1f})
  - 매수 점수: {entry['buy_score']}, 매도 점수: {entry['sell_score']}

이유: {details['reason']}
        """.strip()
        
        return summary


# 편의 함수
def create_multi_timeframe_engine(data_dir: str = "/app/data/raw"):
    """
    멀티 타임프레임 엔진 생성
    
    Usage:
        engine = create_multi_timeframe_engine()
        action, conf, details = engine.analyze("KRW-BTC")
    """
    return MultiTimeframeEngine(data_dir=data_dir)
