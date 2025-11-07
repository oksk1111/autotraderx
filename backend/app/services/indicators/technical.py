import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """RSI (Relative Strength Index) 계산"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        seed = deltas[:period + 1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        if down == 0:
            return 100.0
        
        rs = up / down
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, float]:
        """MACD (Moving Average Convergence Divergence) 계산"""
        if len(prices) < slow:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        
        df = pd.DataFrame(prices, columns=['close'])
        
        # EMA 계산
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        
        # MACD 라인
        macd_line = ema_fast - ema_slow
        
        # 시그널 라인
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # 히스토그램
        histogram = macd_line - signal_line
        
        return {
            "macd": float(macd_line.iloc[-1]),
            "signal": float(signal_line.iloc[-1]),
            "histogram": float(histogram.iloc[-1])
        }
    
    @staticmethod
    def calculate_moving_average(prices: List[float], period: int) -> float:
        """이동평균선 계산"""
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        
        return np.mean(prices[-period:])
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, float]:
        """볼린저 밴드 계산"""
        if len(prices) < period:
            price = prices[-1] if prices else 0.0
            return {"upper": price, "middle": price, "lower": price}
        
        df = pd.DataFrame(prices, columns=['close'])
        
        # 중심선 (이동평균)
        middle = df['close'].rolling(window=period).mean()
        
        # 표준편차
        std = df['close'].rolling(window=period).std()
        
        # 상단/하단 밴드
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        
        return {
            "upper": float(upper.iloc[-1]),
            "middle": float(middle.iloc[-1]),
            "lower": float(lower.iloc[-1])
        }
    
    @staticmethod
    def calculate_mfi(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        period: int = 14
    ) -> float:
        """MFI (Money Flow Index) 계산"""
        if len(closes) < period + 1:
            return 50.0
        
        # Typical Price
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        
        # Money Flow
        money_flows = [tp * v for tp, v in zip(typical_prices, volumes)]
        
        # Positive and Negative Money Flow
        positive_flow = []
        negative_flow = []
        
        for i in range(1, len(typical_prices)):
            if typical_prices[i] > typical_prices[i - 1]:
                positive_flow.append(money_flows[i])
                negative_flow.append(0)
            elif typical_prices[i] < typical_prices[i - 1]:
                positive_flow.append(0)
                negative_flow.append(money_flows[i])
            else:
                positive_flow.append(0)
                negative_flow.append(0)
        
        # Calculate MFI
        positive_mf = sum(positive_flow[-period:])
        negative_mf = sum(negative_flow[-period:])
        
        if negative_mf == 0:
            return 100.0
        
        money_ratio = positive_mf / negative_mf
        mfi = 100 - (100 / (1 + money_ratio))
        
        return mfi
    
    @staticmethod
    def calculate_stochastic(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> Dict[str, float]:
        """스토캐스틱 오실레이터 계산"""
        if len(closes) < period:
            return {"k": 50.0, "d": 50.0}
        
        # %K 계산
        lowest_low = min(lows[-period:])
        highest_high = max(highs[-period:])
        
        if highest_high == lowest_low:
            k = 50.0
        else:
            k = ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100
        
        # %D는 %K의 3일 이동평균 (간단히 현재 K 값 반환)
        d = k
        
        return {"k": k, "d": d}
    
    @staticmethod
    def analyze_trend(prices: List[float], periods: List[int] = [5, 20, 60]) -> str:
        """추세 분석"""
        if len(prices) < max(periods):
            return "neutral"
        
        current_price = prices[-1]
        mas = [TechnicalIndicators.calculate_moving_average(prices, p) for p in periods]
        
        # 모든 이동평균선 위에 있으면 상승 추세
        if all(current_price > ma for ma in mas):
            return "uptrend"
        # 모든 이동평균선 아래에 있으면 하락 추세
        elif all(current_price < ma for ma in mas):
            return "downtrend"
        else:
            return "neutral"
    
    @staticmethod
    def calculate_all_indicators(
        candles: List[Dict],
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9
    ) -> Dict:
        """모든 지표 일괄 계산"""
        if not candles:
            return {}
        
        closes = [c['trade_price'] for c in candles]
        highs = [c['high_price'] for c in candles]
        lows = [c['low_price'] for c in candles]
        volumes = [c['candle_acc_trade_volume'] for c in candles]
        
        indicators = {
            "rsi": TechnicalIndicators.calculate_rsi(closes, rsi_period),
            "macd": TechnicalIndicators.calculate_macd(closes, macd_fast, macd_slow, macd_signal),
            "ma_5": TechnicalIndicators.calculate_moving_average(closes, 5),
            "ma_20": TechnicalIndicators.calculate_moving_average(closes, 20),
            "ma_60": TechnicalIndicators.calculate_moving_average(closes, 60),
            "bollinger": TechnicalIndicators.calculate_bollinger_bands(closes),
            "mfi": TechnicalIndicators.calculate_mfi(highs, lows, closes, volumes),
            "stochastic": TechnicalIndicators.calculate_stochastic(highs, lows, closes),
            "trend": TechnicalIndicators.analyze_trend(closes),
            "current_price": closes[-1]
        }
        
        return indicators


technical_indicators = TechnicalIndicators()
