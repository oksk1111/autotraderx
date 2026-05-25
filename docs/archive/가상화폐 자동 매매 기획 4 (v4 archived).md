# 가상화폐 자동 매매 기획 v4.2

---

# 📊 업비트 오픈 API 기반 3-Layer 통합 자동 매매 시스템

## 1. 개정 이력

| 버전 | 날짜 | 주요 변경사항 |
|------|------|--------------|
| v1.0 | 2024-11 | 초기 기획 - ML 단독 전략 |
| v2.0 | 2024-12-03 | 긴급 거래 모드 추가 |
| v3.0 | 2024-12-05 | 신호 필터링 v3.0, 자동 재훈련 시스템 |
| v4.0 | 2024-12-06 | 3-Layer 통합 전략으로 전면 개편 |
| v4.1 | 2025-01-10 | Breakout Strategy 추가, 펌핑 감지 시스템, 동적 마켓 선정 |
| **v4.2** | **2026-01-20** | **GitHub CI/CD 자동 배포, 로그 원격 접근, 기획서 현행화** |

---

## 2. 시스템 개요

### 2.1 개정 배경

#### ❌ 기존 시스템 문제점 (v3.0)
```
문제 1: 데이터 주기 불일치
- 기획: 1-5초 Tick 데이터 분석 (워뇨띠 스타일)
- 현실: 5분마다 1시간봉 분석
- 결과: 60-300배 느린 반응 → 단타 불가능

문제 2: ML 모델 한계
- 훈련 정확도: 85%
- 실전 신뢰도: 1-33% (평균 10%)
- 현상: 50% 미만 신뢰도 = 거래 안 함 → 21시간 거래 중단

문제 3: 수익률 저조
- 12월 5일: -7.3% 손실
- 원인: 모델 노후화 (2주) + 느린 반응 속도
```

#### ✅ v4.0 해결 방안
```
해결 1: 3-Layer 통합 전략
- Layer 1: 기술적 지표 (1초 반응)
- Layer 2: 멀티 타임프레임 (트렌드 확인)
- Layer 3: 강화학습 (선택적, 최적화)

해결 2: 거래 주기 단축
- 기존: 5분 → 개선: 1분
- 효과: 5배 더 많은 거래 기회

해결 3: 자동 재훈련 시스템
- 매일 새벽 3시 자동 모델 업데이트
- 최신 데이터로 지속 학습
```

---

## 3. 3-Layer 통합 전략

### 3.1 전략 구조

```
┌─────────────────────────────────────────────────┐
│          통합 트레이딩 엔진                        │
│         (Ensemble Decision Making)              │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   ┌────▼─────┐  ┌───▼────┐  ┌────▼──────┐
   │ Layer 1  │  │Layer 2 │  │ Layer 3   │
   │ Hybrid   │  │MultiTF │  │ RL Agent  │
   │ (빠름)    │  │(안정)   │  │(최적화)    │
   └──────────┘  └────────┘  └───────────┘
        │             │             │
   ┌────▼─────┐  ┌───▼────┐  ┌────▼──────┐
   │ RSI      │  │ 1h 트렌드│  │DQN/PPO   │
   │ MACD     │  │15m 모멘텀│  │학습 에이전트│
   │ Volume   │  │ 5m 진입 │  │수익 최대화 │
   │Bollinger │  │         │  │           │
   └──────────┘  └────────┘  └───────────┘

        가중치 투표 (Weighted Voting)
    Layer 1: 30% | Layer 2: 30% | Layer 3: 40%
```

### 3.2 Layer 1: 하이브리드 전략 (Hybrid Engine)

#### 📌 목적
- **즉각 반응**: 1초 이내 매매 판단
- **워뇨띠 스타일**: 단기 패턴 포착

#### 🔧 구현
```python
# backend/app/trading/hybrid_engine.py

class HybridTradingEngine:
    """기술적 지표 중심, ML은 보조"""
    
    def analyze(self, market, df):
        # 1. 빠른 기술적 지표 분석
        signals = 0
        
        if rsi < 30:              # 과매도
            signals += 1
        if macd_cross == 'golden': # 골든크로스
            signals += 1
        if volume > 2x_average:    # 거래량 급등
            signals += 1
        if bb_position < 0.2:      # 볼린저 하단
            signals += 1
        
        # 2. 신호 강도에 따른 신뢰도
        if signals >= 3:
            return "BUY", 0.85  # 매우 강한 신호
        elif signals >= 2:
            return "BUY", 0.65  # 중간 신호
        
        # 3. ML 보조 검증
        ml_signal, ml_conf = ml_predictor.predict(market)
        if ml_signal == "SELL" and ml_conf > 0.7:
            confidence *= 0.6  # ML 반대 의견
        
        return action, confidence
```

#### 📊 성능 예상
```
반응 속도: 1초
정확도: 70-80%
예상 수익률: +5-10% (주간)
```

---

### 3.3 Layer 2: 멀티 타임프레임 전략 (Multi-Timeframe)

#### 📌 목적
- **트렌드 확인**: 큰 흐름 속에서 진입
- **리스크 감소**: 역추세 거래 방지

#### 🔧 구현
```python
# backend/app/trading/multi_timeframe_engine.py

class MultiTimeframeEngine:
    """장기 트렌드 + 단기 타이밍"""
    
    def analyze(self, market):
        # 1시간봉: 전체 트렌드
        trend_1h = analyze_trend(df_1h)  # UP/DOWN/SIDEWAYS
        
        # 15분봉: 모멘텀 강도
        momentum_15m = analyze_momentum(df_15m)  # STRONG/WEAK
        
        # 5분봉: 진입 타이밍
        entry_5m = analyze_entry(df_5m)  # BUY/SELL/HOLD
        
        # 조합 로직
        if trend_1h == "UP":
            if momentum_15m == "STRONG" and entry_5m == "BUY":
                return "BUY", 0.90  # 완벽한 타이밍
            elif entry_5m == "BUY":
                return "BUY", 0.70  # 괜찮은 타이밍
        
        elif trend_1h == "DOWN":
            return "HOLD", 0.20  # 하락장 거래 자제
        
        return "HOLD", 0.35
```

#### 📊 성능 예상
```
반응 속도: 1-5분
정확도: 80-90%
예상 수익률: +10-15% (주간)
리스크 감소: -50%
```

---

### 3.4 Layer 3: 강화학습 전략 (Reinforcement Learning) - 선택적

#### 📌 목적
- **수익 최대화**: 직접 학습으로 최적 전략 탐색
- **실시간 적응**: 시장 변화에 동적 대응

#### 🔧 구현 (향후)
```python
# backend/app/ml/rl_agent.py

class RLTradingAgent:
    """DQN/PPO 기반 강화학습"""
    
    def train(self):
        # 환경: 실제 시장 시뮬레이션
        # 상태: 가격, 지표, 보유량
        # 행동: BUY, SELL, HOLD
        # 보상: 수익 - 비용 - 리스크
        
        for episode in range(10000):
            state = env.reset()
            while not done:
                action = agent.select_action(state)
                next_state, reward, done = env.step(action)
                agent.learn(state, action, reward, next_state)
    
    def predict(self, state):
        # 학습된 정책으로 최적 행동 선택
        action = agent.act(state)
        return action, confidence
```

#### 📊 성능 예상
```
반응 속도: 실시간
정확도: 90%+
예상 수익률: +15-20% (주간)
단점: 구현 복잡도 높음 (1-2주 소요)
```

---

## 4. 통합 엔진 (Ensemble Decision Making)

### 4.1 가중치 투표 시스템

```python
# backend/app/trading/integrated_engine.py

class IntegratedTradingEngine:
    """3가지 레이어를 모두 활용하는 앙상블"""
    
    def analyze(self, market):
        # Layer 1: Hybrid
        tech_signal, tech_conf = hybrid_engine.analyze(market, df)
        
        # Layer 2: Multi-TF
        trend_signal, trend_conf = multi_tf_engine.analyze(market)
        
        # Layer 3: RL (선택적)
        if use_rl:
            rl_action, rl_conf = rl_agent.predict(state)
        
        # 가중치 투표
        final_action, final_conf = combine_signals(
            tech_signal, tech_conf, weight=0.3,
            trend_signal, trend_conf, weight=0.3,
            rl_action, rl_conf, weight=0.4
        )
        
        return final_action, final_conf
```

### 4.2 신호 조합 규칙

| 상황 | Layer 1 | Layer 2 | Layer 3 | 최종 판단 | 신뢰도 |
|------|---------|---------|---------|-----------|--------|
| 완벽한 일치 | BUY | BUY | BUY | **BUY** | **95%** |
| 2/3 일치 | BUY | BUY | HOLD | **BUY** | **80%** |
| 강한 신호 1개 | BUY (85%) | HOLD | HOLD | **BUY** | **65%** |
| 신호 충돌 | BUY | SELL | - | **HOLD** | **40%** |
| 하락 트렌드 | - | DOWN | - | **HOLD** | **20%** |

---

## 5. 데이터 수집 전략

### 5.1 멀티 타임프레임 데이터

```python
# backend/scripts/collect_data.py

timeframes = [
    ("minute5", 288 * 7),    # 5분봉: 7일치
    ("minute15", 96 * 14),   # 15분봉: 14일치
    ("minute60", 24 * 90),   # 1시간봉: 90일치
    ("day", 365),            # 일봉: 1년치
]

for market in ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]:
    for interval, count in timeframes:
        data = collect_ohlcv(market, interval, count)
        save_data(f"{market}_{interval}.csv", data)
```

### 5.2 저장 구조

```
backend/data/raw/
├── KRW_BTC_minute5.csv      # 5분봉 (7일)
├── KRW_BTC_minute15.csv     # 15분봉 (14일)
├── KRW_BTC_minute60.csv     # 1시간봉 (90일)
├── KRW_BTC_day.csv          # 일봉 (1년)
├── KRW_ETH_minute5.csv
├── ... (동일 구조)
```

---

## 6. 시스템 구성도 (v4.0)

```
[사용자 브라우저]
      │
      ▼
[웹앱 (Frontend: React)]
      │
      ▼
[API 서버 (FastAPI)]
      │
      ├── [Enhanced Trading Engine] ★NEW
      │       ├─ Layer 1: Hybrid Engine
      │       ├─ Layer 2: Multi-Timeframe
      │       └─ Layer 3: RL Agent (Optional)
      │
      ├── [기존 ML Predictor] (보조)
      │       ├─ LSTM + LightGBM
      │       └─ 자동 재훈련 (매일 3AM)
      │
      ├── [신호 필터링 v3.0]
      │       ├─ 연속 신호 차단
      │       └─ 고신뢰도 신호만 통과
      │
      ├── [Emergency Guard]
      │       └─ 급락 감지 즉시 매도
      │
      └── [업비트 API 통신]
              ├─ 1분 주기 거래 (기존 5분)
              └─ 실시간 시세 조회
```

---

## 7. 거래 파라미터 (v4.0)

### 7.1 워뇨띠 스타일 적용

| 파라미터 | v3.0 (기존) | v4.0 (개선) | 변경 사유 |
|----------|-------------|-------------|-----------|
| 거래 주기 | 5분 | **1분** | 5배 더 많은 기회 |
| 손절 라인 | -3% | **-2%** | 빠른 손절 |
| 익절 라인 | +5% | **+2%** | 소액 다회 |
| 투자 비율 | 10% | **5-15%** | 신뢰도 기반 |
| 최대 보유 | 무제한 | **30분** | 장기 보유 금지 |

### 7.2 신뢰도별 투자 비율

```python
if confidence >= 0.80:
    investment_ratio = 0.15  # 15% (매우 높음)
elif confidence >= 0.70:
    investment_ratio = 0.10  # 10% (높음)
elif confidence >= 0.60:
    investment_ratio = 0.07  # 7% (보통)
else:
    investment_ratio = 0.05  # 5% (낮음)
```

---

## 8. 성능 비교

### 8.1 시스템 버전별 성능

| 버전 | 전략 | 반응속도 | 수익률 (주간) | 상태 |
|------|------|----------|--------------|------|
| v1.0 | ML 단독 | 5분 | -5% ~ +3% | ❌ 폐기 |
| v2.0 | ML + Emergency | 5분 | -2% ~ +5% | ❌ 개선 필요 |
| v3.0 | ML + Filter | 5분 | -7.3% (실측) | ❌ 실패 |
| **v4.0** | **3-Layer 통합** | **1분** | **+10-15% (예상)** | ✅ **현재** |

### 8.2 레이어별 성능 (예상)

| 구성 | 사용 레이어 | 예상 수익률 | 구현 시간 |
|------|-------------|------------|----------|
| Phase 1 | Layer 1 + 2 | **+10-15%** | **3시간** ✅ |
| Phase 2 | Layer 1 + 2 + 3 | **+15-20%** | 1-2주 |

---

## 9. 구현 로드맵

### 9.1 Phase 1: 즉시 적용 (완료)

#### ✅ 2024-12-06 구현 완료
```bash
# Layer 1: Hybrid Engine
backend/app/trading/hybrid_engine.py ✅

# Layer 2: Multi-Timeframe Engine
backend/app/trading/multi_timeframe_engine.py ✅

# Enhanced Engine (통합)
backend/app/trading/enhanced_engine.py ✅

# 데이터 수집 개선
backend/scripts/collect_data.py ✅

# 거래 주기 단축
.env: TRADING_CYCLE_SECONDS=60 ✅
```

#### 🔄 배포 절차 (진행 중)
```bash
# 1. 멀티 타임프레임 데이터 수집
docker compose exec backend python /app/scripts/collect_data.py

# 2. 서비스 재시작
docker compose restart worker scheduler

# 3. 로그 모니터링
docker compose logs -f worker | grep "Enhanced"
```

---

### 9.2 Phase 2: 강화학습 추가 (향후)

#### Week 1-2: RL 환경 구축
```python
# backend/app/ml/rl_agent.py
- DQN 또는 PPO 에이전트 구현
- 거래 환경 정의 (OpenAI Gym)
- 보상 함수 설계
```

#### Week 3-4: 학습 및 검증
```bash
# 과거 데이터로 학습
python scripts/train_rl_agent.py --episodes 10000

# 백테스트
python scripts/backtest_rl.py --period 90d

# 실전 배포
# FullIntegratedEngine 활성화
```

---

## 10. 모니터링 지표

### 10.1 일일 체크리스트

```
□ 자동 재훈련 실행 (매일 3AM)
  - docker compose logs scheduler | grep "auto-model-retrain"

□ Enhanced Engine 신호 확인
  - docker compose logs worker | grep "Enhanced"

□ 거래 횟수
  - 기대: 5-15회/일 (1분 주기)
  - 기존: 1-2회/주 (5분 주기)

□ 평균 신뢰도
  - 목표: 60% 이상
  - 기존: 10-30%

□ 일일 수익률
  - 목표: +1-3%
  - 기존: -1% ~ +0.5%
```

### 10.2 주간 리포트

```
일주일 누적 지표:
- 총 거래 횟수: __회
- 승률: __%
- 누적 수익률: __%
- 최대 낙폭: __%
- Sharpe Ratio: __
```

---

## 11. 리스크 관리 (v4.0 강화)

### 11.1 다층 방어 시스템

```
1단계: 신호 필터링 v3.0
- 연속 신호 차단
- 신뢰도 임계값 (60%)

2단계: Enhanced Engine
- 3개 레이어 교차 검증
- 신호 충돌 시 HOLD

3단계: Emergency Guard
- 급락 5% 즉시 매도
- 변동성 필터

4단계: 손절/익절
- 손절: -2%
- 익절: +2%
- 최대 보유: 30분
```

### 11.2 일일 손실 한도

```python
# backend/app/core/config.py

class Settings:
    max_daily_loss: float = 0.05  # 5%
    max_loss_per_trade: float = 0.02  # 2%
    max_open_positions: int = 3
    max_holding_minutes: int = 30
```

---

## 12. 기대 효과

### 12.1 정량적 개선

| 지표 | v3.0 (기존) | v4.0 (예상) | 개선율 |
|------|-------------|-------------|--------|
| 주간 수익률 | -7.3% | **+10-15%** | **+240%** |
| 거래 횟수/주 | 1-2회 | **35-105회** | **+50배** |
| 평균 신뢰도 | 10-30% | **60-80%** | **+200%** |
| 반응 속도 | 5분 | **1분** | **5배** |
| 승률 | 40% | **65-75%** | **+60%** |

### 12.2 정성적 개선

```
✅ 워뇨띠 스타일 부합
- 1분 주기 빠른 반응
- 소액 분산 다회 거래
- 빠른 손절/익절

✅ 감정 배제
- 기계적 판단
- 일관된 전략 적용

✅ 24시간 자동 운영
- 인간 불가능한 속도
- 밤낮 없는 감시

✅ 지속적 학습
- 매일 3AM 자동 재훈련
- 최신 패턴 반영
```

---

## 13. 결론

### 13.1 v4.0의 핵심 혁신

```
🎯 문제 해결:
- 데이터 주기 불일치 → 1분 주기 + 멀티 타임프레임
- ML 과신 → 3-Layer 앙상블
- 느린 반응 → 기술적 지표 (1초)

🚀 성능 목표:
- 주간 수익률: +10-15%
- 승률: 65-75%
- 거래 횟수: 35-105회/주

⚡ 즉시 적용:
- Phase 1 완료 (2024-12-06)
- 배포 대기 중
```

### 13.2 다음 단계

```
단기 (1주):
□ Phase 1 실전 검증
□ 성능 모니터링
□ 파라미터 튜닝

중기 (1개월):
□ A/B 테스트 (v3 vs v4)
□ 데이터 분석 리포트
□ 전략 최적화

장기 (3개월):
□ Phase 2 (RL) 도입
□ 자동 하이퍼파라미터 튜닝
□ 멀티 마켓 확장
```

---

**작성일**: 2024-12-06  
**버전**: 4.0  
**작성자**: GitHub Copilot  
**상태**: 구현 완료, 배포 대기

**다음 리뷰**: 2024-12-13 (실전 1주 결과 분석)

---

## 14. 알림 및 경보 시스템 (Notification System)

### 14.1 개요
사용자가 별도의 앱 설치 없이 무료로 쉽게 알림을 받을 수 있도록 **Telegram**과 **Email**을 지원합니다. 또한 불필요한 알림 공해를 방지하기 위해 **알림 수위(Alert Level)**를 설정하여 중요한 문제 발생 시에만 알림을 받을 수 있도록 합니다.

### 14.2 지원 채널
1.  **Telegram (권장)**
    *   **장점**: 무료, 즉시성, 별도 앱 개발 불필요 (Telegram 메신저 사용).
    *   **설정**: BotFather를 통해 봇 생성 후 Token 및 Chat ID 입력.
2.  **Email (SMTP)**
    *   **장점**: 무료 (Gmail 등 사용), 기록 보관 용이.
    *   **설정**: SMTP 서버 정보 (Host, Port, User, Password) 입력.
    *   **수신자**: DB에 저장된 사용자 계정(`users` 테이블)의 이메일로 개별 발송.

### 14.3 알림 수위 (Alert Level)
알림의 중요도에 따라 발송 여부를 결정합니다. 기본값은 **WARNING**입니다.

| 레벨 | 설명 | 예시 | 기본 발송 여부 |
| :--- | :--- | :--- | :--- |
| **INFO** | 일반적인 정보 | 매매 체결, 일일 리포트(정상), 시스템 시작 | ❌ (설정 시 가능) |
| **WARNING** | 주의가 필요한 상황 | 손절 매도, API 지연, 데이터 수집 실패 | ✅ |
| **ERROR** | 즉각 조치가 필요한 장애 | 주문 실패, 잔고 부족, 시스템 크래시 | ✅ |

### 14.4 구현 계획
*   **설정 관리**: `.env` 파일에 채널별 설정 및 `ALERT_LEVEL` 추가.
*   **서비스 로직**: `Notifier` 클래스에서 레벨 필터링 및 다중 채널 발송 처리.
*   **수신자 관리**: 기존 단일 수신자 설정 제거, DB의 활성 사용자(`is_active=True`) 이메일 조회 후 발송.
*   **헬스 체크**: 일일 리포트 전송 시 `INFO` 레벨이라도 강제 전송 옵션 지원 (사용자가 원할 경우).

### 14.5 설정 예시 (.env)
```env
# 알림 설정
ALERT_LEVEL=WARNING  # INFO, WARNING, ERROR

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

---

## 15. 2025-12-17 업데이트: 추세 추종 및 동적 리스크 관리

### 15.1 개요
지속적인 마이너스 수익률 문제를 해결하기 위해 **하이브리드 엔진의 진입 로직**과 **리스크 관리 전략**을 대폭 수정했습니다. '떨어지는 칼날'을 잡는 역추세 매매를 지양하고, 확실한 상승 추세에서만 진입하며, 신뢰도에 따라 손익비를 동적으로 조절합니다.

### 15.2 주요 변경 사항

#### ✅ Hybrid Engine: 추세 필터 (Trend Filter) 도입
*   **EMA 50 (50일 지수이동평균) 활용**:
    *   현재 가격 > EMA 50: **상승 추세** (매수 신호 강화)
    *   현재 가격 < EMA 50: **하락 추세** (매수 신호 억제)
*   **진입 장벽 완화**:
    *   기존의 너무 엄격했던 진입 조건(거래량 2배 급등 등)을 현실적으로 완화 (1.5배)하여, 상승 추세에서의 기회를 놓치지 않도록 조정.
    *   RSI 과매도 기준 완화 (30 -> 35), 과매수 기준 완화 (70 -> 65).

#### ✅ Risk Management: 동적 손절/익절 (Dynamic SL/TP)
*   **기존**: 고정된 손절(-3%), 익절(+5%)
*   **변경**: 신뢰도(Confidence)에 따른 동적 대응
    *   **기본 설정**: 손절 **-2.5%**, 익절 **+4.0%** (방어적 운용)
    *   **고신뢰도(80% 이상)**: 손절 **-2.0%**, 익절 **+6.0%**
        *   확신이 있는 진입이므로 손절은 더 짧게(틀리면 바로 탈출), 익절은 더 길게(추세 추종) 가져가 **손익비(Risk/Reward Ratio)** 극대화.

### 15.3 기대 효과
*   하락장에서의 무의미한 저점 매수 시도 감소.
*   상승장에서의 진입 기회 확대.
*   손실은 짧게 끊고 이익은 길게 가져가는 워뇨띠 스타일의 매매 원칙 구현.

---

## 16. v4.2 업데이트: CI/CD 및 운영 개선 (2026-01-20)

### 16.1 GitHub CI/CD 자동 배포

#### 구현 완료
master/main 브랜치에 커밋 시 Oracle Cloud 서버에 자동 배포됩니다.

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [master, main]

# 배포 프로세스:
# 1. SSH로 클라우드 서버 접속
# 2. git pull로 최신 코드 가져오기
# 3. docker compose up -d --build로 서비스 재시작
# 4. 헬스 체크 수행
# 5. 실패 시 Telegram/Slack 알림
```

#### 필요한 GitHub Secrets
| Secret 이름 | 설명 |
|------------|------|
| `SSH_PRIVATE_KEY` | 클라우드 서버 SSH 개인키 |
| `SERVER_HOST` | 서버 IP 주소 (예: 158.180.71.84) |
| `SERVER_USER` | SSH 사용자명 (예: mingky) |
| `TELEGRAM_BOT_TOKEN` | Telegram 봇 토큰 (선택) |
| `TELEGRAM_CHAT_ID` | Telegram 채팅 ID (선택) |

### 16.2 클라우드 로그 로컬 접근

#### 실시간 로그 확인 방법

```bash
# SSH 접속
ssh mingky@158.180.71.84

# 전체 로그 확인
cd ~/autotraderx
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f worker     # 거래 로직
docker compose logs -f backend    # API 서버
docker compose logs -f beat       # 스케줄러

# 최근 100줄만 확인
docker compose logs --tail=100 worker
```

#### 로컬에서 원격 로그 스트리밍

```bash
# 로컬 터미널에서 실시간 로그 확인
ssh mingky@158.180.71.84 "cd ~/autotraderx && docker compose logs -f worker"

# 특정 패턴만 필터링 (예: 거래 신호)
ssh mingky@158.180.71.84 "cd ~/autotraderx && docker compose logs -f worker | grep -E '(BUY|SELL|Enhanced)'"
```

### 16.3 현재 운영 중인 전략 모드

| 전략 | 설명 | 상태 |
|------|------|------|
| **Breakout Strategy** | 돌파 + 추세 추종, 거래량 급등 시 진입 | ✅ 기본값 |
| Momentum Strategy | 펌핑 감지 후 즉시 매수 | 설정 가능 |
| Reversal Strategy | 저점 매수 / 고점 매도 | 비활성화 권장 |

### 16.4 동적 마켓 선정

기존 고정 마켓 대신 **거래대금 Top 10** 코인을 실시간으로 선정합니다.

```python
# backend/app/trading/market_selector.py
class MarketSelector:
    def get_top_volume_coins(self, top_k=10, min_volume=30_000_000_000):
        # 24시간 거래대금 300억 이상 + 상위 10개
        return filtered_markets
```

### 16.5 시스템 아키텍처 (현행)

```
[Oracle Cloud VM]
├── Docker Compose
│   ├── backend (FastAPI) :8000
│   │   └── 3-Layer Engine
│   │       ├── Hybrid Engine (기술적 지표)
│   │       ├── MultiTF Engine (멀티 타임프레임)
│   │       └── RL Agent (선택적)
│   │
│   ├── worker (Celery)
│   │   ├── 1분 주기 거래 (run_cycle)
│   │   ├── WebSocket 실시간 모니터링 (run_pump_detection_loop)
│   │   └── 포지션 관리 (SL/TP)
│   │
│   ├── beat (Celery Beat)
│   │   └── 스케줄 관리
│   │
│   ├── db (PostgreSQL)
│   ├── redis
│   └── frontend (Vite) :4173
│
└── GitHub Actions
    ├── deploy.yml (자동 배포)
    └── daily-health-check.yml (일일 점검)
```

---

## 17. 부록: 문제 해결 가이드

### 17.1 자주 발생하는 문제

#### 거래가 실행되지 않을 때
```bash
# 1. 자동매매 활성화 여부 확인
# Dashboard에서 "자동매매 ON" 상태인지 확인

# 2. Worker 로그 확인
docker compose logs --tail=50 worker | grep -E "(HOLD|Enhanced)"

# 3. 신뢰도 확인 - 60% 미만이면 거래 안함
docker compose logs worker | grep "confidence"
```

#### 서비스가 응답하지 않을 때
```bash
# 모든 서비스 재시작
docker compose down && docker compose up -d

# 특정 서비스만 재시작
docker compose restart worker
```

### 17.2 성능 모니터링

```bash
# 시스템 리소스 확인
docker stats

# 디스크 사용량
df -h

# PostgreSQL 연결 수
docker compose exec db psql -U autotrader -c "SELECT count(*) FROM pg_stat_activity;"
```

---

**마지막 업데이트**: 2026-01-20  
**버전**: 4.2  
**운영 URL**: http://158.180.71.84:4173/dashboard

