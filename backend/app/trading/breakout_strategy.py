from typing import Tuple, Dict, Optional
import pandas as pd
from app.core.logging import get_logger

logger = get_logger(__name__)

class BreakoutTradingStrategy:
    """
    돌파(Breakout) 및 추세 추종(Trend Following) 전략
    거래량이 터지면서 전고점이나 이동평균선을 강하게 돌파할 때 매수
    """

    def __init__(self):
        # 전략 파라미터
        self.vol_multiplier = 2.0  # 평균 거래량 대비 배수
        self.ma_short = 5
        self.ma_long = 20
        self.rsi_min = 50   # 추세가 살아있어야 함
        self.rsi_max = 85   # 너무 과열(90이상)은 조심, 하지만 급등주는 80도 감
        
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
        prev = df.iloc[-2]
        
        # 2. 거래량 급증 체크
        vol_surge = current['volume'] > (current['vol_ma20'] * self.vol_multiplier)
        
        # 3. 가격 돌파 체크 (현재가가 MA20 위에 있고, 양봉이며, 상승 추세)
        price_breakout = (current['close'] > current['ma20']) and (current['close'] > current['open'])
        trend_up = current['ma5'] > current['ma20'] # 정배열 초기 or 지속
        
        # 4. RSI 조건
        rsi_condition = (current['rsi'] >= self.rsi_min) and (current['rsi'] <= self.rsi_max)
        
        # --- 매수 로직 (Breakout Buy) ---
        if vol_surge and price_breakout and rsi_condition:
            # 추가 확인: 직전 전고점 돌파 여부 (최근 20개 캔들 중 최고가 갱신 시도)
            recent_high = df['high'].iloc[-22:-2].max() # 현재봉 제외, 직전 20개
            
            # 현재가가 최근 고점 근처이거나 돌파했으면 더 강력
            msg = []
            confidence = 0.6
            
            if current['close'] > recent_high:
                confidence += 0.2
                msg.append("전고점 돌파")
            
            if trend_up:
                confidence += 0.1
                msg.append("이평선 정배열")
                
            if current['volume'] > (current['vol_ma20'] * 3.0):
                confidence += 0.1
                msg.append("거래량 폭발(3배+)")
            
            # 최종 신뢰도 캡
            confidence = min(confidence, 0.95)
            
            rationale = f"🚀 Breakout: Vol({current['volume']:.0f}) > Avg*2 + {', '.join(msg)}"
            return "BUY", confidence, rationale

        # --- 매도 로직 (Trend Broken) ---
        # 추세가 꺾이면 매도 (Dead Cross 발생 시 또는 가격이 MA20을 유의미하게 하회할 때)
        
        # 1. Dead Cross Check (MA5가 MA20 하향 돌파) - 강력한 매도 신호
        if current['ma5'] < current['ma20']:
             return "SELL", 0.8, "추세 이탈 (Dead Cross)"
             
        # 2. 가격 이탈 Check (단순 MA20 터치가 아닌 -0.5% 여유폭 둠)
        # 1분봉상 노이즈로 인한 잦은 손절 방지
        if current['close'] < (current['ma20'] * 0.995):
            return "SELL", 0.7, "추세 이탈 (MA20 -0.5% 하회)"
        
        if current['rsi'] > 90:
             return "SELL", 0.6, "RSI 과열 (90+)"

        return "HOLD", 0.0, "조건 미충족"
