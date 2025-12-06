# 🔄 신호 필터링 시스템

## 개요

연속적인 동일 신호를 필터링하여 과도한 매매를 방지하는 시스템입니다. 
**신뢰도가 매우 높은 경우(80% 이상)에는 연속 신호라도 거래를 허용**하지만, 
**이미 고신뢰도로 거래한 경우에는 추가 연속 신호를 차단**하여 리스크를 관리합니다.

## 동작 원리

### 신호 필터링 규칙 (v3.0)

1. **신호 반전** (BUY ↔ SELL) → **항상 허용** 🟢
2. **연속 동일 신호** + **이전 거래 신뢰도 < 80%** + **현재 신뢰도 ≥ 80%** → **허용** 🟡
3. **연속 동일 신호** + **이전 거래 신뢰도 ≥ 80%** → **차단** 🔴 (이미 고신뢰도로 매매함)
4. **연속 동일 신호** + **현재 신뢰도 < 80%** → **차단** 🔴
5. **HOLD 신호** → **항상 거래 없음**

### 핵심 개선 사항

- ✅ **고신뢰도 거래 이력 추적**: Redis에 신호와 함께 신뢰도 저장
- ✅ **중복 고신뢰도 매매 방지**: 이미 80%+ 신뢰도로 거래했다면 추가 차단
- ✅ **신뢰도 상승 감지**: 낮은 신뢰도 → 높은 신뢰도로 변화 시 추가 매매 허용

### 예시 시나리오

#### 시나리오 1: 일반적인 추세 (신뢰도 70%)

```
BUY (70%) → 매수 ✅ (첫 신호)
BUY (72%) → 차단 🔴 (연속 신호, 신뢰도 < 80%)
BUY (75%) → 차단 🔴 (연속 신호, 신뢰도 < 80%)
SELL (68%) → 매도 ✅ (신호 반전!)
SELL (70%) → 차단 🔴 (연속 신호, 신뢰도 < 80%)
```

#### 시나리오 2: 신뢰도 상승 (저→고)

```
BUY (75%) → 매수 ✅ (첫 신호)
BUY (78%) → 차단 🔴 (연속 신호, 신뢰도 < 80%)
BUY (85%) → 매수 ✅ (신뢰도 상승! 이전 75% → 현재 85% 🟡)
BUY (87%) → 차단 🔴 (이미 고신뢰도로 매매함, 이전 85%)
BUY (90%) → 차단 🔴 (이미 고신뢰도로 매매함, 이전 85%)
SELL (82%) → 매도 ✅ (신호 반전!)
```

#### 시나리오 3: 고신뢰도 시작

```
BUY (85%) → 매수 ✅ (첫 신호, 고신뢰도)
BUY (87%) → 차단 🔴 (이미 고신뢰도 85%로 매매함)
BUY (92%) → 차단 🔴 (이미 고신뢰도로 매매함)
SELL (88%) → 매도 ✅ (신호 반전!)
SELL (90%) → 차단 🔴 (이미 고신뢰도 88%로 매매함)
```

#### 시나리오 4: 혼합 상황

```
BUY (72%) → 매수 ✅ (첫 신호)
BUY (74%) → 차단 🔴 (연속 신호, 신뢰도 < 80%)
BUY (83%) → 매수 ✅ (신뢰도 상승! 72% → 83% 🟡)
BUY (86%) → 차단 🔴 (이미 고신뢰도 83%로 매매함)
BUY (78%) → 차단 🔴 (신뢰도 하락, 이전 83%)
SELL (85%) → 매도 ✅ (신호 반전 + 고신뢰도!)
```

## 구현 세부사항

### SignalFilter 클래스

```python
def should_allow_trade(self, market: str, current_signal: str, confidence: float = 0.0) -> tuple[bool, str]:
    """
    거래 허용 여부 판단
    
    기본적으로 연속 신호는 차단하지만, 신뢰도가 매우 높으면 허용합니다.
    단, 이미 고신뢰도(≥80%)로 거래했다면 추가 연속 신호는 차단합니다.
    
    Args:
        market: 시장 코드 (예: KRW-BTC)
        current_signal: 현재 신호 ("BUY", "SELL", "HOLD")
        confidence: 신호 신뢰도 (0.0 ~ 1.0)
    
    Returns:
        (허용 여부, 사유) 튜플
    """
```

### Redis 키 구조

- **신호 키**: `signal:last:{market}` → 값: `"BUY"` 또는 `"SELL"`
- **신뢰도 키**: `signal:confidence:{market}` → 값: `"0.85"` (예시)
- **TTL**: 24시간

### 로그 예시

```
🟢 KRW-BTC: 첫 신호 BUY - 거래 허용
🟡 KRW-BTC: 연속 BUY 신호지만 높은 신뢰도(85.3%)로 거래 허용 (이전: 72.5%)
🔴 KRW-BTC: 연속 BUY 신호 차단 (이전 거래 이미 고신뢰도: 85.3%, 현재: 87.2%)
🔴 KRW-BTC: 연속 BUY 신호 차단 (현재 신뢰도: 72.5%, 이전: 75.0%)
🟢 KRW-BTC: 신호 반전 BUY → SELL - 거래 허용
```

## 설정

### 신뢰도 임계값

현재 **80%**로 설정되어 있습니다. 이 값은 `signal_filter.py`에서 변경 가능합니다:

```python
# 신뢰도가 매우 높으면 (80% 이상) 연속 신호라도 허용
if confidence >= 0.80:
    return True, f"고신뢰도 연속 {current_signal} (신뢰도: {confidence:.1%})"
```

### 권장 임계값

| 트레이딩 스타일 | 임계값 | 효과 |
|----------------|--------|------|
| **보수적** | 0.85 (85%) | 매우 확실한 신호만 연속 매매 |
| **균형** | 0.80 (80%) | 현재 설정 (권장) |
| **공격적** | 0.75 (75%) | 좀 더 많은 연속 매매 허용 |

## 장점

1. **과도한 매매 방지** 🛡️
   - 같은 방향으로 계속 매수/매도하는 것을 차단
   - 거래 수수료 절감
   - 평균 단가 관리

2. **강한 변동성 대응** ⚡
   - 신뢰도가 상승하면 (저신뢰도 → 고신뢰도) 추가 매매 허용
   - 큰 가격 변동 기회 포착
   - 급등/급락 초기 대응력 향상

3. **고신뢰도 중복 매매 방지** 🚫
   - 이미 80%+ 신뢰도로 거래했다면 추가 연속 신호 차단
   - 동일 방향 과도한 노출 방지
   - 리스크 집중 방지

4. **추세 전환 포착** 🔄
   - BUY → SELL, SELL → BUY 전환점 정확히 포착
   - 손절/익절 타이밍 최적화

## 모니터링

### 실시간 로그 확인

```bash
# 신호 필터링 관련 로그
docker compose logs worker -f | grep -E "🟢|🟡|🔴|신호|필터"

# ML 예측 및 거래 로그
docker compose logs worker -f | grep -E "ML 예측|✅|신뢰도"
```

### 통계 확인

```bash
# 차단된 신호 개수
docker compose logs worker | grep "🔴.*차단" | wc -l

# 허용된 고신뢰도 연속 신호
docker compose logs worker | grep "🟡.*고신뢰도" | wc -l

# 신호 반전으로 허용된 거래
docker compose logs worker | grep "🟢.*반전" | wc -l
```

## Redis 관리

### 신호 기록 초기화

특정 시장의 신호 기록을 초기화하려면:

```python
from app.services.signal_filter import SignalFilter
filter = SignalFilter()

# 특정 시장 초기화
filter.reset_signal("KRW-BTC")

# 모든 시장 초기화
filter.reset_all_signals()
```

### Redis 직접 확인

```bash
# Redis 컨테이너 접속
docker compose exec redis redis-cli

# 저장된 신호 확인
KEYS signal:last:*
GET signal:last:KRW-BTC

# 모든 신호 삭제
DEL signal:last:KRW-BTC
KEYS signal:last:* | xargs redis-cli DEL
```

## 주의사항

⚠️ **신뢰도 임계값 설정**
- 너무 낮게 (70% 미만): 과도한 매매 발생 가능
- 너무 높게 (90% 이상): 강한 신호도 놓칠 수 있음
- **권장**: 80% (현재 설정)

⚠️ **Redis 연결 실패 시**
- 신호 필터링이 작동하지 않을 수 있음
- 로그에서 "Redis 조회 실패" 확인
- Redis 컨테이너 상태 확인 필요

⚠️ **신호 기록 만료**
- 24시간 후 자동 만료 (TTL)
- 오래된 기록은 자동 삭제됨
- 필요시 TTL 조정 가능

## 테스트

### 수동 테스트

```python
from app.services.signal_filter import SignalFilter

filter = SignalFilter()

# 테스트 1: 첫 신호
allowed, reason = filter.should_allow_trade("KRW-BTC", "BUY", 0.75)
print(f"Result: {allowed}, Reason: {reason}")  # True, 첫 BUY 신호

# 테스트 2: 연속 신호 (신뢰도 낮음)
filter.set_last_signal("KRW-BTC", "BUY")
allowed, reason = filter.should_allow_trade("KRW-BTC", "BUY", 0.75)
print(f"Result: {allowed}, Reason: {reason}")  # False, 연속 BUY 신호

# 테스트 3: 연속 신호 (신뢰도 높음)
allowed, reason = filter.should_allow_trade("KRW-BTC", "BUY", 0.85)
print(f"Result: {allowed}, Reason: {reason}")  # True, 고신뢰도 연속 BUY

# 테스트 4: 신호 반전
allowed, reason = filter.should_allow_trade("KRW-BTC", "SELL", 0.70)
print(f"Result: {allowed}, Reason: {reason}")  # True, 신호 반전

# 정리
filter.reset_signal("KRW-BTC")
```

## FAQ

**Q: 신뢰도 80%가 왜 기준인가요?**
A: 백테스팅 결과 80% 이상의 신호는 높은 성공률을 보였습니다. 이 값은 조정 가능합니다.

**Q: 연속 BUY로 계속 매수하면 어떻게 되나요?**
A: 신뢰도 80% 미만이면 차단됩니다. 80% 이상이면 강한 변동성으로 판단하여 허용합니다.

**Q: 신호 반전은 항상 허용되나요?**
A: 네, BUY → SELL 또는 SELL → BUY 전환은 신뢰도와 무관하게 항상 허용됩니다.

**Q: HOLD 신호는 어떻게 처리되나요?**
A: HOLD는 항상 거래 없음으로 처리되며, 신호 기록에도 저장되지 않습니다.

**Q: Redis가 중단되면 어떻게 되나요?**
A: 신호 필터링이 작동하지 않아 모든 신호가 허용됩니다. Redis 모니터링이 필요합니다.

## 관련 파일

- `backend/app/services/signal_filter.py` - 신호 필터 구현
- `backend/app/trading/engine.py` - 필터 통합
- `.env` - Redis 설정
- `docker-compose.yml` - Redis 컨테이너 설정
