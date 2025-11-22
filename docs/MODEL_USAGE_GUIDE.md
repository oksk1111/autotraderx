# 모델 통합 시스템 사용 가이드

## 빠른 시작

### 1. 시스템 재시작 (코드 업데이트 반영)
```bash
cd /home/mingky/workspace/autotraderx
docker compose restart backend worker scheduler
```

### 2. 모델 로딩 확인
```bash
docker compose logs backend | grep "Models loaded"
```

예상 출력:
```
Models loaded successfully from /app/models on cpu
MultiCoinModelManager initialized with device: cpu
Loaded 4/4 models
```

### 3. 예측 테스트
```bash
docker compose exec backend python3 /app/test_model_integration.py
```

## 코드 사용법

### Python에서 모델 사용하기

#### 방법 1: HybridPredictor (단순)
```python
from app.ml.predictor import HybridPredictor
from app.ml.feature_builder import build_features_from_market_data
import pyupbit

# 시장 데이터 수집 (최소 150개 권장)
market_data = pyupbit.get_ohlcv("KRW-BTC", "minute60", 200)
market_data = market_data.reset_index().to_dict('records')

# 특징 생성
features = build_features_from_market_data(market_data, "KRW-BTC")

# 예측
predictor = HybridPredictor()
signal = predictor.infer(features)

print(f"Action: {signal.action}")
print(f"Buy Probability: {signal.buy_probability:.3f}")
print(f"Sell Probability: {signal.sell_probability:.3f}")
print(f"Confidence: {signal.confidence:.3f}")
```

#### 방법 2: MultiCoinModelManager (다중 코인)
```python
from app.ml.model_manager import MultiCoinModelManager
from app.ml.feature_builder import build_features_from_market_data
import pyupbit

# 모델 매니저 초기화
manager = MultiCoinModelManager()
manager.load_all_models()

# 여러 코인 예측
for market in ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]:
    # 데이터 수집
    market_data = pyupbit.get_ohlcv(market, "minute60", 200)
    market_data = market_data.reset_index().to_dict('records')
    
    # 특징 생성
    features = build_features_from_market_data(market_data, market)
    sequence = features['sequence']
    
    # 예측
    signal = manager.predict(market, sequence)
    if signal:
        print(f"{market}: {signal.action} (confidence: {signal.confidence:.3f})")
```

### Trading Engine에서 사용하기

Trading engine은 자동으로 통합된 모델을 사용합니다:

```python
from app.trading.engine import TradingEngine
from app.ml.feature_builder import build_features_from_market_data

engine = TradingEngine()

# 시장 데이터 준비
market_data = pyupbit.get_ohlcv("KRW-BTC", "minute60", 200)
market_data = market_data.reset_index().to_dict('records')
features = build_features_from_market_data(market_data, "KRW-BTC")

# 계정 정보
account_info = {
    "principal": 1000000.0,
    "available_balance": 500000.0,
    "open_positions": 2,
    "avg_return": 0.05,
    "consecutive_losses": 0
}

# 거래 결정
decision = await engine.decide(db, "KRW-BTC", features, account_info)

print(f"Approved: {decision.approved}")
print(f"Action: {decision.action}")
print(f"Investment Ratio: {decision.investment_ratio * 100}%")
```

## 모델 출력 해석

### MLSignal 객체
```python
@dataclass
class MLSignal:
    market: str              # 마켓 코드 (예: "KRW-BTC")
    buy_probability: float   # 매수 확률 (0.0-1.0)
    sell_probability: float  # 매도 확률 (0.0-1.0)
    emergency_score: float   # 긴급 매도 점수 (0.0-1.0)
    confidence: float        # 예측 신뢰도 (0.0-1.0)
    
    @property
    def action(self) -> str:
        # "BUY", "SELL", "HOLD" 중 하나
```

### 신뢰도 계산
```python
# 최대 확률 - 두번째 확률
confidence = max_probability - second_max_probability

# 예시:
# Buy: 0.7, Sell: 0.2, Hold: 0.1
# -> confidence = 0.7 - 0.2 = 0.5 (높은 신뢰도)

# Buy: 0.4, Sell: 0.35, Hold: 0.25
# -> confidence = 0.4 - 0.35 = 0.05 (낮은 신뢰도)
```

### Emergency Score
```python
# Sell 확률 × 신뢰도
emergency_score = sell_probability * confidence

# 0.7 이상이면 긴급 매도 트리거
if emergency_score > 0.7:
    # 전량 매도 (investment_ratio = 1.0)
```

## 트러블슈팅

### 문제: "Models not loaded"
**원인**: 모델 파일이 없거나 경로가 잘못됨
**해결**:
```bash
# 모델 파일 확인
docker compose exec backend ls -la /app/models/

# 예상 출력:
# lstm_best.pth
# lightgbm_model.txt
# scaler.pkl
# model_metadata.json
```

### 문제: "Invalid sequence data"
**원인**: 입력 데이터가 (24, 46) 형태가 아님
**해결**:
```python
# 데이터 최소 150개 이상 수집
market_data = pyupbit.get_ohlcv(market, "minute60", 200)

# feature_builder 사용
features = build_features_from_market_data(market_data, market)
print(features['sequence'].shape)  # (24, 46) 확인
```

### 문제: 예측이 너무 보수적 (항상 HOLD)
**원인**: 신뢰도가 낮거나 threshold가 높음
**해결**:
```python
# predictor.py에서 threshold 조정
@property
def action(self) -> str:
    # 기존: 0.55 threshold
    if self.buy_probability > self.sell_probability and self.buy_probability > 0.55:
        return "BUY"
    
    # 더 공격적: 0.45 threshold
    if self.buy_probability > self.sell_probability and self.buy_probability > 0.45:
        return "BUY"
```

### 문제: 메모리 부족
**원인**: 여러 모델을 동시에 로드
**해결**:
```python
# lazy loading 사용 (기본값)
predictor = HybridPredictor()  # 필요할 때만 모델 로드

# 또는 특정 마켓만 로드
manager = MultiCoinModelManager()
manager.load_model_for_market("KRW-BTC")  # 한 개만 로드
```

## 성능 최적화

### 1. 모델 캐싱
```python
# 전역 변수로 모델 재사용
_predictor_cache = None

def get_predictor():
    global _predictor_cache
    if _predictor_cache is None:
        _predictor_cache = HybridPredictor()
    return _predictor_cache
```

### 2. 배치 예측
```python
# 여러 시퀀스를 한번에 예측
sequences = [seq1, seq2, seq3]  # 각각 (24, 46)
batch = np.stack(sequences)  # (3, 24, 46)

with torch.no_grad():
    batch_tensor = torch.FloatTensor(batch).to(device)
    features = lstm_model(batch_tensor)  # (3, 32)
```

### 3. GPU 사용 (옵션)
```bash
# docker-compose.yml 수정
services:
  backend:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

## 모니터링

### 로그 확인
```bash
# 실시간 로그
docker compose logs -f backend

# 예측 로그만 필터
docker compose logs backend | grep "ML prediction"

# 에러 로그
docker compose logs backend | grep ERROR
```

### 성능 메트릭
```python
# 예측 시간 측정
import time

start = time.time()
signal = predictor.infer(features)
elapsed = time.time() - start

print(f"Prediction took {elapsed:.3f} seconds")
# 목표: < 0.5초
```

## 추가 리소스
- 모델 학습 가이드: `docs/AI_SETUP_GUIDE.md`
- 긴급 매매 가이드: `docs/EMERGENCY_TRADING_GUIDE.md`
- 통합 보고서: `docs/MODEL_INTEGRATION_REPORT.md`
- 학습 스크립트: `backend/scripts/train_gpu.py`
- 특징 준비: `backend/scripts/prepare_features.py`
