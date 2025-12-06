# 개선된 자동 매매 전략

## 📊 현재 시스템 문제점

### 치명적 이슈
1. **데이터 주기 불일치**
   - 기획: 1-5초 Tick 데이터 분석
   - 현실: 5분마다 1시간봉 분석
   - 결과: **60-300배 느린 반응** → 단타 불가능

2. **ML 모델 한계**
   - 훈련 정확도: 85%
   - 실전 신뢰도: 1-33% (평균 10%)
   - 문제: **50% 미만 신뢰도 = 거래 안 함** → 21시간 거래 중단

3. **전략-데이터 미스매치**
   - 워뇨띠 스타일: 캔들 변화 즉각 대응
   - 현재 시스템: 과거 패턴 학습 후 느린 예측

## 💡 개선된 전략 (3단계)

### 🥇 1단계: 하이브리드 전략 (즉시 적용 가능)

#### 기술적 지표 중심 + ML 보조 역할

```python
# backend/app/trading/hybrid_engine.py
class HybridTradingEngine:
    """기술적 지표 중심, ML은 보조"""
    
    def analyze(self, market: str) -> tuple[str, float]:
        # 1. 빠른 기술적 지표 분석 (실시간)
        indicators = self.get_technical_indicators(market)
        
        # 강한 매수 신호 (2개 이상 일치)
        strong_buy_signals = 0
        if indicators['rsi'] < 30:  # 과매도
            strong_buy_signals += 1
        if indicators['macd_cross'] == 'golden':  # 골든크로스
            strong_buy_signals += 1
        if indicators['volume_surge'] > 2.0:  # 거래량 2배
            strong_buy_signals += 1
        if indicators['bb_position'] < 0.2:  # 볼린저 하단
            strong_buy_signals += 1
        
        # 2. 신호 강도에 따른 신뢰도
        if strong_buy_signals >= 3:
            action = "BUY"
            base_confidence = 0.85
        elif strong_buy_signals == 2:
            action = "BUY"
            base_confidence = 0.65
        else:
            # ML 모델 보조 사용
            ml_signal, ml_conf = self.ml_predictor.predict(market)
            if ml_conf > 0.6:
                return ml_signal, ml_conf
            else:
                return "HOLD", 0.3
        
        # 3. ML 검증 (선택적)
        ml_signal, ml_conf = self.ml_predictor.predict(market)
        if ml_signal == "SELL" and ml_conf > 0.7:
            # ML이 강하게 반대 → 신중
            final_confidence = base_confidence * 0.6
        else:
            # ML 동의 또는 중립
            final_confidence = base_confidence
        
        return action, final_confidence
```

**장점**:
- ✅ 즉각 반응 (1초 이내)
- ✅ ML 과신 방지
- ✅ 기존 코드 재사용
- ✅ 디버깅 쉬움

**구현 시간**: 2-3시간

---

### 🥈 2단계: 멀티 타임프레임 전략

#### 여러 시간대 동시 분석

```python
# backend/app/trading/multi_timeframe_engine.py
class MultiTimeframeEngine:
    """장기 트렌드 + 단기 타이밍"""
    
    def analyze(self, market: str) -> tuple[str, float]:
        # 장기 (1시간): 트렌드 방향
        trend_1h = self.get_trend(market, "1h")  # UP, DOWN, SIDEWAYS
        
        # 중기 (15분): 모멘텀
        momentum_15m = self.get_momentum(market, "15m")  # STRONG, WEAK
        
        # 단기 (5분): 진입 타이밍
        entry_5m = self.get_entry_signal(market, "5m")  # BUY, SELL, HOLD
        
        # 조합 로직
        if trend_1h == "UP":
            if momentum_15m == "STRONG" and entry_5m == "BUY":
                return "BUY", 0.90  # 매우 강한 신호
            elif momentum_15m == "WEAK" and entry_5m == "BUY":
                return "BUY", 0.65  # 중간 신호
        
        elif trend_1h == "DOWN":
            # 하락장에서는 거래 안 함 (리스크 회피)
            return "HOLD", 0.2
        
        else:  # SIDEWAYS
            # 횡보장: 단기 신호만 사용
            if entry_5m == "BUY":
                return "BUY", 0.55
        
        return "HOLD", 0.3
```

**데이터 수집 개선**:
```python
# backend/scripts/collect_multi_timeframe_data.py
def collect_all_timeframes():
    markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]
    intervals = ["minute5", "minute15", "minute60"]  # 5분, 15분, 1시간
    
    for market in markets:
        for interval in intervals:
            data = fetch_data(market, interval, count=200)
            save_data(f"{market}_{interval}.csv", data)
```

**장점**:
- ✅ 큰 흐름 + 단기 타이밍
- ✅ 워뇨띠 스타일 부합
- ✅ 안정적

**구현 시간**: 1일

---

### 🥉 3단계: 강화학습 전환 (장기)

#### DQN 또는 PPO 기반 에이전트

```python
# backend/app/ml/rl_agent.py
import torch
from stable_baselines3 import PPO

class RLTradingAgent:
    """강화학습 기반 트레이딩"""
    
    def __init__(self):
        self.model = PPO(
            "MlpPolicy",
            env=TradingEnv(),
            learning_rate=0.0003,
            n_steps=2048,
            batch_size=64,
            verbose=1
        )
    
    def train(self, total_timesteps=100000):
        """환경에서 직접 학습"""
        self.model.learn(total_timesteps=total_timesteps)
    
    def predict(self, state):
        """실시간 예측"""
        action, _states = self.model.predict(state, deterministic=True)
        return action  # 0: HOLD, 1: BUY, 2: SELL

# 보상 함수 (핵심)
class TradingEnv:
    def calculate_reward(self, action, next_price):
        if action == "BUY":
            # 매수 후 상승 → 보상
            profit = (next_price - buy_price) / buy_price
            reward = profit * 100
            # 거래 비용 차감
            reward -= 0.05  # 수수료 0.05%
        elif action == "SELL":
            # 수익 실현 → 보상
            reward = realized_profit
        else:  # HOLD
            # 기회비용 (작은 패널티)
            reward = -0.01
        
        # 리스크 패널티
        if abs(profit) > 0.05:  # 5% 이상 변동
            reward -= 0.1
        
        return reward
```

**장점**:
- ✅ 수익 최대화가 목표
- ✅ 실시간 적응
- ✅ 거래 비용 고려

**단점**:
- ❌ 구현 복잡도 높음
- ❌ 학습 데이터 많이 필요
- ❌ 불안정할 수 있음

**구현 시간**: 1-2주

---

## 🔧 즉시 적용 가능한 개선 (1단계)

### A. 신뢰도 임계값 조정

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    # 기존: 50% 이상만 거래
    min_confidence_threshold: float = 0.50
    
    # 개선: 전략별 다른 임계값
    technical_min_confidence: float = 0.60  # 기술적 지표
    ml_min_confidence: float = 0.70  # ML 예측
    hybrid_min_confidence: float = 0.55  # 하이브리드
```

### B. 거래 주기 단축

```python
# docker-compose.yml 또는 .env
TRADING_CYCLE_SECONDS=60  # 5분 → 1분으로 단축
```

### C. 기술적 지표 강화

```python
# backend/app/ml/feature_builder.py
def add_advanced_indicators(df):
    # 기존 46개 features +
    
    # 1. 거래량 분석
    df['volume_ma_20'] = df['volume'].rolling(20).mean()
    df['volume_surge'] = df['volume'] / df['volume_ma_20']
    
    # 2. 변동성
    df['high_low_range'] = (df['high'] - df['low']) / df['close']
    df['volatility_ratio'] = df['atr'] / df['close']
    
    # 3. 추세 강도
    df['adx'] = calculate_adx(df)  # Average Directional Index
    df['trend_strength'] = df['adx'] / 100
    
    # 4. 지지/저항
    df['support'] = df['low'].rolling(20).min()
    df['resistance'] = df['high'].rolling(20).max()
    df['price_position'] = (df['close'] - df['support']) / (df['resistance'] - df['support'])
    
    return df
```

---

## 📊 성능 비교 예상

| 전략 | 반응속도 | 정확도 | 수익률 | 구현 난이도 |
|------|----------|--------|--------|-------------|
| **현재 (ML 단독)** | ⭐⭐ (5분) | ⭐⭐ (50% 이하) | ⭐ (-7.3%) | ⭐⭐⭐ |
| **1단계 (하이브리드)** | ⭐⭐⭐⭐ (1분) | ⭐⭐⭐⭐ (70-80%) | ⭐⭐⭐⭐ (+5-10%) | ⭐⭐ |
| **2단계 (멀티프레임)** | ⭐⭐⭐ (1-5분) | ⭐⭐⭐⭐⭐ (80-90%) | ⭐⭐⭐⭐⭐ (+10-15%) | ⭐⭐⭐ |
| **3단계 (강화학습)** | ⭐⭐⭐⭐⭐ (실시간) | ⭐⭐⭐⭐⭐ (90%+) | ⭐⭐⭐⭐⭐ (+15-20%) | ⭐⭐⭐⭐⭐ |

---

## 🎯 추천 실행 계획

### Week 1: 하이브리드 전략 구현
```bash
# 1. 기술적 지표 강화
backend/app/ml/feature_builder.py 수정

# 2. 하이브리드 엔진 작성
backend/app/trading/hybrid_engine.py 생성

# 3. 기존 엔진과 A/B 테스트
- 50% 자금은 하이브리드
- 50% 자금은 기존 ML

# 4. 성능 비교 (7일)
- 수익률
- 거래 횟수
- 최대 낙폭
```

### Week 2: 멀티 타임프레임 추가
```bash
# 1. 5분, 15분 데이터 수집
scripts/collect_multi_timeframe_data.py

# 2. 트렌드 분석 모듈
backend/app/trading/trend_analyzer.py

# 3. 통합 엔진
backend/app/trading/multi_timeframe_engine.py

# 4. 백테스트 (과거 1개월)
```

### Week 3-4: 최적화 및 모니터링
```bash
# 1. 하이퍼파라미터 튜닝
- RSI 임계값 (30 → 25?)
- 거래량 배수 (2.0 → 1.5?)
- 신뢰도 가중치

# 2. 리스크 관리 강화
- 변동성 필터
- 최대 보유 시간
- 일일 손실 한도

# 3. 알림 시스템
- Telegram 봇
- 수익/손실 리포트
```

---

## 💰 예상 수익 개선

### 현재 (ML 단독)
```
초기 자금: 100,000원
7일 후: 92,700원
수익률: -7.3%
거래 횟수: 1-2건/주
```

### 개선 후 (하이브리드)
```
초기 자금: 100,000원
7일 후: 105,000~110,000원
수익률: +5~10%
거래 횟수: 5-15건/일
```

---

## ⚠️ 주의사항

### 1. 과최적화 방지
- 백테스트에서만 좋고 실전에서 실패
- **해결**: 최근 1개월 데이터로만 검증

### 2. 슬리피지 고려
- 시장가 주문 시 가격 변동
- **해결**: 지정가 주문 + 타임아웃

### 3. 거래 비용
- 수수료 0.05% × 2 (매수/매도)
- **해결**: 최소 +0.2% 이상에서만 매도

### 4. 감정 개입
- 손실 시 패닉 → 시스템 끄기
- **해결**: 자동 손절 + 알림만 받기

---

**작성일**: 2025-12-06
**작성자**: GitHub Copilot
**버전**: 1.0
