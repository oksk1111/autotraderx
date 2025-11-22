# 긴급 거래 시스템 가이드

## 📋 개요

LLM 분석과 별도로 **실시간 틱 데이터**를 모니터링하여 급락/급등을 감지하고 즉시 매수/매도를 실행하는 시스템입니다.

## 🎯 핵심 기능

### 1. 급락 감지 및 긴급 매도
- **1분 급락**: -2.5% 이상 하락 시 즉시 전량 매도
- **3분 급락**: -4.0% 이상 하락 시 즉시 전량 매도  
- **5분 급락**: -6.0% 이상 하락 시 즉시 전량 매도
- **변동성 급증**: 평균 변동성의 2배 + 하락 시 매도

### 2. 급등 감지 및 긴급 매수
- **1분 급등**: +3.0% 이상 상승 + 거래량 3배 → 매수
- **3분 급등**: +5.0% 이상 상승 + 거래량 3배 → 매수
- **신뢰도 필터**: 0.7 이상 신뢰도에서만 매수 실행

### 3. 실행 주기
- **10초마다** 자동 체크 (기존 5분 자동매매와 별도)
- 보유 포지션 + 관심 마켓 모니터링
- 중복 거래 방지: 5분 쿨다운

## 🏗️ 시스템 구조

```
Celery Beat (10초 간격)
    ↓
emergency_trading_check (Task)
    ↓
EmergencyTrader.detect_emergency_signal()
    ↓
TradingEngine.execute_trade()
    ↓
Upbit API (실제 주문)
```

## 📊 모니터링 대상

1. **보유 포지션 마켓**: 급락 매도용
2. **설정된 관심 마켓**: 급등 매수용
3. 현재 설정: KRW-BTC, KRW-ETH, KRW-SOL, KRW-0G

## 📈 실시간 로그 예시

```
Emergency check: 4 markets (positions: 0, watch: 4)
KRW-SOL 긴급 체크 - 1분:0.05%, 3분:0.14%, 5분:0.23%, 거래량:4.38x, 변동성:0.07%
KRW-ETH 긴급 체크 - 1분:0.02%, 3분:0.12%, 5분:0.23%, 거래량:0.7x, 변동성:0.1%
```

### 긴급 매도 트리거 예시
```
🚨 KRW-BTC 긴급 신호 감지: emergency_sell - 1분 급락 감지 (-3.2%)
💥 KRW-BTC 긴급 매도 실행! (사유: 1분 급락 감지)
```

### 긴급 매수 트리거 예시
```
🚨 KRW-ETH 긴급 신호 감지: emergency_buy - 거래량 동반 급등 (+3.5%, 4.2x)
🚀 KRW-ETH 긴급 매수 실행! (사유: 거래량 동반 급등)
```

## ⚙️ 설정 커스터마이징

### 임계값 조정

`backend/app/services/trading/emergency_trader.py`:

```python
self.thresholds = {
    # 급락 기준 (더 민감하게: 값을 작게)
    'crash_1min': -2.5,   # 기본: -2.5%
    'crash_3min': -4.0,   # 기본: -4.0%
    'crash_5min': -6.0,   # 기본: -6.0%
    
    # 급등 기준 (더 민감하게: 값을 작게)
    'surge_1min': 3.0,    # 기본: +3.0%
    'surge_3min': 5.0,    # 기본: +5.0%
    
    # 거래량 기준 (더 엄격하게: 값을 크게)
    'volume_spike': 3.0,  # 기본: 3배
    
    # 변동성 기준
    'volatility_spike': 2.0,  # 기본: 2배
}
```

### 쿨다운 시간 조정

```python
self.cooldown_minutes = 5  # 기본: 5분
```

### 체크 주기 변경

`backend/app/celery_app.py`:

```python
"emergency-trading-check": {
    "task": "app.tasks.emergency_trading_check",
    "schedule": 10.0,  # 기본: 10초 (더 빠르게: 5.0)
},
```

## 🛡️ 안전 장치

### 1. 쿨다운 메커니즘
- 동일 종목에 대해 5분 내 1회만 긴급 거래
- 과도한 거래 방지

### 2. 신뢰도 필터 (매수)
- 급등 매수는 신뢰도 0.7 이상에서만 실행
- False positive 최소화

### 3. 포지션 확인
- 급락 매도: 보유 중일 때만 실행
- 급등 매수: 보유 중이 아닐 때만 실행

### 4. 에러 핸들링
- 각 마켓별 독립 실행 (한 마켓 에러가 전체 영향 안 줌)
- 상세 로그 기록

## 📱 명령어

### 로그 모니터링
```bash
# 긴급 거래 로그만 보기
docker logs autotraderx_celery --follow | grep -E "긴급|emergency|🚨|💥|🚀"

# 전체 긴급 체크 로그
docker logs autotraderx_celery --follow | grep "Emergency check"
```

### 자동매매 상태 확인
```bash
curl http://localhost:8000/api/v1/trading/auto/status
```

### 긴급 거래 비활성화
자동매매를 끄면 긴급 거래도 자동으로 중지됩니다:
```bash
curl -X POST http://localhost:8000/api/v1/trading/auto/stop
```

### 서비스 재시작 (설정 변경 시)
```bash
docker-compose restart celery_worker celery_beat
```

## 🔬 백테스팅 (향후 구현)

현재는 **규칙 기반** 시스템입니다. 추후 과거 데이터로 임계값을 최적화할 수 있습니다:

```python
# scripts/backtest_emergency.py (예정)

# 과거 3개월 데이터로 최적 임계값 찾기
optimal_thresholds = optimize_emergency_thresholds(
    historical_data=candles_3months,
    test_ranges={
        'crash_1min': [-1.5, -2.0, -2.5, -3.0],
        'surge_1min': [2.0, 2.5, 3.0, 3.5],
        'volume_spike': [2.0, 3.0, 4.0, 5.0]
    },
    target_metric='sharpe_ratio'
)
```

## 🤖 머신러닝 업그레이드 (Phase 2)

### 데이터 수집
```python
# scripts/collect_training_data.py
python scripts/collect_training_data.py --markets KRW-BTC,KRW-ETH --days 90
```

### 모델 학습
```python
# scripts/train_crash_predictor.py
python scripts/train_crash_predictor.py --model lstm --epochs 50
```

### 예측 통합
```python
from app.services.ai.crash_predictor import crash_predictor

# 긴급 거래 시 ML 예측 추가
ml_prediction = crash_predictor.predict_crash_probability(market)
if ml_prediction['crash_prob'] > 0.8:
    # 긴급 매도
```

## 📊 성과 지표

### 추적 중인 메트릭
- `markets_checked`: 체크한 마켓 수
- `emergency_actions`: 긴급 거래 실행 건수
- `results`: 각 거래의 성공/실패 결과

### 로그 분석
```bash
# 하루 긴급 거래 횟수
docker logs autotraderx_celery --since 24h | grep "긴급 거래 실행됨" | wc -l

# 성공률 분석
docker logs autotraderx_celery --since 24h | grep "'result': 'success'" | wc -l
```

## ⚠️ 주의사항

1. **변동성이 큰 시장에서는 False Positive 가능**
   - 임계값 조정 필요
   - 백테스팅으로 최적화 권장

2. **슬리피지 고려**
   - 급락/급등 시 실제 체결가는 다를 수 있음
   - 시장가 주문 특성상 불리한 가격에 체결 가능

3. **리스크 관리**
   - 전체 자산의 일부만 자동매매에 할당
   - 정기적인 모니터링 필수

4. **API 제한**
   - Upbit API Rate Limit: 초당 5-10회
   - 10초 주기 + 4개 마켓 = 문제없음
   - 마켓 수 증가 시 주기 조정 필요

## 🚀 다음 단계

1. ✅ **규칙 기반 시스템 구현** (완료)
2. ⏳ 백테스팅으로 임계값 최적화
3. ⏳ 과거 데이터 수집 및 라벨링
4. ⏳ LSTM 모델 학습
5. ⏳ ML 예측 통합
6. ⏳ A/B 테스팅 (규칙 vs ML)

## 📞 문제 해결

### 긴급 거래가 실행되지 않음
```bash
# 1. Celery Beat 확인
docker logs autotraderx_celery_beat | grep emergency

# 2. 자동매매 활성화 확인
curl http://localhost:8000/api/v1/trading/auto/status

# 3. 관심 마켓 설정 확인
curl http://localhost:8000/api/v1/trading/auto/status | jq '.selected_markets'
```

### 과도한 거래 발생
```python
# 임계값을 더 보수적으로 조정
'crash_1min': -3.5,  # -2.5에서 -3.5로 (덜 민감)
'surge_1min': 4.0,   # 3.0에서 4.0으로 (덜 민감)
```

### 에러 발생
```bash
# 상세 로그 확인
docker logs autotraderx_celery --tail 100 | grep ERROR

# 서비스 재시작
docker-compose restart celery_worker celery_beat
```

## 📚 관련 파일

- `backend/app/services/trading/emergency_trader.py`: 긴급 거래 로직
- `backend/app/tasks.py`: emergency_trading_check 태스크
- `backend/app/celery_app.py`: 스케줄 설정
- `docs/EMERGENCY_TRADING_GUIDE.md`: 이 문서

---

**업데이트**: 2025년 11월 14일  
**버전**: 1.0 (규칙 기반)  
**상태**: ✅ 운영 중
