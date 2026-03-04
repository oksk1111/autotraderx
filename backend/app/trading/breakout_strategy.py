from typing import Tuple, Dict, Optional
import pandas as pd
from app.core.logging import get_logger

logger = get_logger(__name__)

class BreakoutTradingStrategy:
    """
    돌파(Breakout) 및 추세 추종(Trend Following) 전략 v6.0 보수적 자본 보존
    
    v6.0 변경사항:
    1. 거래량 배수 상향 (2.5 → 3.0): 확실한 수급만 포착
    2. RSI 범위 축소 (50-80 → 55-72): 과열 진입 방지
    3. 기본 신뢰도 하향 (0.7 → 0.65): 더 높은 확신 필요
    4. 매도 조건 강화: 더 빠른 손절
    """

    def __init__(self):
        # v6.0: 보수적 파라미터
        self.vol_multiplier = 3.0  # 평균 거래량 대비 3배 이상 (2.5 → 3.0)
        self.ma_short = 5
        self.ma_long = 20
        self.rsi_min = 55   # (50 → 55: 확실한 상승 모멘텀)
        self.rsi_max = 72   # (80 → 72: 과열 진입 방지)
        
        # 트레일링 스탑 파라미터
        self.trailing_stop_pct = 0.012  # 고점 대비 1.2% 하락 시 청산 (2% → 1.2%)
        self.position_high_prices: dict = {}  # {market: high_price}
        
    def analyze(self, market: str, df: pd.DataFrame) -> Tuple[str, float, str]:
        """
        돌파 매매 분석
        Returns: (Action, Confidence, Rationale)
        """
        if df is None or len(df) < 50:
            return "HOLD", 0.0, "데이터 부족"

        # 1. 기술적 지표 준비
        df = df.copy()
        df['ma5'] = df['close'].rolling(window=self.ma_short).mean()
        df['ma20'] = df['close'].rolling(window=self.ma_long).mean()
        df['vol_ma20'] = df['volume'].rolling(window=20).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 현재 캔들 (Last) 및 직전 캔들 (Prev)
        current = df.iloc[-1]
        
        # 2. 거래량 급증 체크
        vol_surge = current['volume'] > (current['vol_ma20'] * self.vol_multiplier)
        
        # 3. 가격 돌파 체크 (현재가가 MA20 위에 있고, 양봉이며, 상승 추세)
        price_breakout = (current['close'] > current['ma20']) and (current['close'] > current['open'])
        trend_up = current['ma5'] > current['ma20'] # 정배열
        
        # 4. RSI 조건
        rsi_condition = (current['rsi'] >= self.rsi_min) and (current['rsi'] <= self.rsi_max)
        
        # --- 매수 로직 (Strict Breakout Buy) ---
        # 조건: 거래량 급증 AND 정배열 AND RSI 조건 만족 (필수)
        if vol_surge and rsi_condition and trend_up and price_breakout:
            # 추가 확인: 직전 전고점 돌파 여부
            recent_high = df['high'].iloc[-22:-2].max() if len(df) >= 22 else df['high'].max()
            
            msg = []
            confidence = 0.65  # v6.0: 기본 신뢰도 하향 (0.7 → 0.65, 더 확실한 조건 필요)
            
            if current['close'] > recent_high:
                confidence += 0.1
                msg.append("전고점 돌파")
            
            # v6.0: 거래량 4배 이상일 때만 보너스
            if current['volume'] > (current['vol_ma20'] * 4.0):
                confidence += 0.1
                msg.append("거래량 4배+")
                
            msg.append(f"거래량 {self.vol_multiplier}배, 정배열, 추세확인")
            
            # v6.0: RSI 70 이상이면 신뢰도 감소 (75 → 70)
            if current['rsi'] > 70:
                 confidence -= 0.15
                 msg.append("RSI 과열 주의")

            return "BUY", min(confidence, 1.0), ", ".join(msg)

        # --- 매도 로직 (Trend Broken) v5.0 ---
        # 개선: 트레일링 스탑 + 피크 감지 추가
        
        # 0. RSI 기반 피크 감지 (v5.0 신규) - 최우선
        # RSI가 80 이상이었다가 75 아래로 떨어지면 피크 신호
        if len(df) >= 3:
            prev_rsi = df.iloc[-2].get('rsi', 50)
            if prev_rsi >= 80 and current['rsi'] < 78:
                return "SELL", 0.85, f"🔔 피크 감지 (RSI {prev_rsi:.0f} → {current['rsi']:.0f})"
        
        # 1. v6.0: RSI 과열 임계값 하향 (88 → 82)
        if current['rsi'] > 82:
             return "SELL", 0.80, f"RSI 과열 ({current['rsi']:.0f})"
        
        # 2. Dead Cross Check (MA5가 MA20 하향 돌파) - 강력한 매도 신호
        if current['ma5'] < current['ma20']:
             return "SELL", 0.8, "추세 이탈 (Dead Cross)"
             
        # 3. 가격 이탈 Check (단순 MA20 터치가 아닌 -0.5% 여유폭 둠)
        if current['close'] < (current['ma20'] * 0.995):
            return "SELL", 0.7, "추세 이탈 (MA20 -0.5% 하회)"
        
        # 4. 급락 감지 v6.0: 직전 캔들 대비 1.0% 이상 하락 (1.5% → 1.0%)
        if len(df) >= 2:
            prev_close = df.iloc[-2]['close']
            drop_pct = (current['close'] - prev_close) / prev_close * 100
            if drop_pct <= -1.0:
                return "SELL", 0.80, f"급락 감지 ({drop_pct:.1f}%)"

        return "HOLD", 0.0, "조건 미충족"
