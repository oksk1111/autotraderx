from typing import Dict, Tuple, Optional
import time
import pandas as pd
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)

class ReversalTradingStrategy:
    """
    급등 후 하락(Peak Sell), 급락 후 반등(Dip Buy)을 노리는 역추세(Mean Reversion) 매매 전략
    User Request: "최고점에서 매도, 낙폭이 큰 하락시점에서 매수"
    """

    def __init__(self, settings):
        self.settings = settings
        # 급등/급락 기준 (예: 1분간 2% 변동)
        self.volatility_threshold = 2.0 
        # RSI 기준
        self.rsi_sell_threshold = 75  # 과매수 구간 (매도 타점)
        self.rsi_buy_threshold = 25   # 과매도 구간 (매수 타점)
        
        # 캐시
        self.last_prices = {}

    def analyze(self, market: str, current_price: float, df: pd.DataFrame) -> Tuple[str, float, str]:
        """
        단기 급등락 및 기술적 지표를 분석하여 역추세 매매 신호 생성
        Returns: (Action, Confidence, Rationale)
        """
        if df is None or len(df) < 15:
            return "HOLD", 0.0, "데이터 부족"

        # 1. 기술적 지표 계산 (RSI, Bollinger Bands)
        rsi = self._calculate_rsi(df['close'], 14).iloc[-1]
        
        # 볼린저 밴드
        sma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        upper_band = sma20 + (std20 * 2)
        lower_band = sma20 - (std20 * 2)
        
        bb_upper = upper_band.iloc[-1]
        bb_lower = lower_band.iloc[-1]
        
        # 2. 급등락 감지 (현재가가 직전 종가 대비 얼마나 변했는지)
        prev_close = df['close'].iloc[-1]
        price_change_pct = ((current_price - prev_close) / prev_close) * 100
        
        action = "HOLD"
        confidence = 0.0
        rationale = ""

        # --- 매도 로직 (Sell the Peak) ---
        # 조건: 가격이 볼린저 상단을 뚫고 급등했으며, RSI가 과매수 구간일 때
        if current_price > bb_upper and rsi > self.rsi_sell_threshold:
            # 추가 조건: 급격한 상승 (Momentum Exhaustion 가능성)
            if price_change_pct > self.volatility_threshold:
                action = "SELL"
                confidence = 0.85 + (min(rsi, 90) - 70) / 100  # RSI가 높을수록 신뢰도 증가
                rationale = f"🎢 Peak Detected: RSI({rsi:.1f}) > {self.rsi_sell_threshold} + Price({current_price:,.0f}) > BB_Upper + Surge({price_change_pct:.2f}%)"

        # --- 매수 로직 (Buy the Dip) ---
        # 조건: 가격이 볼린저 하단을 뚫고 급락했으며, RSI가 과매도 구간일 때
        elif current_price < bb_lower and rsi < self.rsi_buy_threshold:
            # 추가 조건: 급격한 하락 (Panic Selling)
            if price_change_pct < -self.volatility_threshold:
                action = "BUY"
                confidence = 0.85 + (30 - max(rsi, 10)) / 100 # RSI가 낮을수록 신뢰도 증가
                rationale = f"📉 Dip Detected: RSI({rsi:.1f}) < {self.rsi_buy_threshold} + Price({current_price:,.0f}) < BB_Lower + Drop({price_change_pct:.2f}%)"
        
        return action, confidence, rationale

    def _calculate_rsi(self, series: pd.Series, period: int = 14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
