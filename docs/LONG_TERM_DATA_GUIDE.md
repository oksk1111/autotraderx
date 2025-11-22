# 장기 데이터 수집 가이드

## 현재 상황
- **수집된 데이터**: 80일 (2.7개월, 1,919시간)
- **문제점**: 암호화폐의 긴 주기(2-3년) 패턴을 학습하지 못함
- **영향**: Hold 클래스 정확도 낮음 (65-86% vs Sell/Buy 84-93%)

## 데이터 기간에 따른 기대 효과

### 📊 옵션 1: 6개월 (180일, 4,380시간)
```bash
docker compose exec backend python3 /app/collect_long_term_data.py 180
```

**장점**:
- 수집 시간: 약 8-10분 (22번 API 호출)
- 단기 트렌드 학습 가능
- 최근 시장 상황 반영

**단점**:
- 여전히 긴 주기 누락
- 계절성 패턴 부족

**기대 정확도 향상**: +2-3% (84-89%)

---

### 📊 옵션 2: 1년 (365일, 8,760시간)
```bash
docker compose exec backend python3 /app/collect_long_term_data.py 365
```

**장점**:
- 수집 시간: 약 18-20분 (44번 API 호출)
- 4개 분기 데이터 커버
- 중기 사이클 학습 가능
- Hold 클래스 성능 개선 기대

**단점**:
- 2-3년 주기는 여전히 부족
- 데이터 크기 증가 (학습 시간 증가)

**기대 정확도 향상**: +3-5% (85-91%)

---

### 📊 옵션 3: 2년 (730일, 17,520시간) ⭐ 권장
```bash
docker compose exec backend python3 /app/collect_long_term_data.py 730
```

**장점**:
- 수집 시간: 약 35-40분 (88번 API 호출)
- 완전한 불장/약장 사이클 커버
- 장기 패턴 학습 가능
- Hold 판단 정확도 크게 개선
- 과적합(overfitting) 위험 감소

**단점**:
- 수집 시간 소요
- 학습 시간 증가 (CPU: 15-20분/코인)
- 저장 공간 증가 (~2MB/코인)

**기대 정확도 향상**: +5-8% (87-94%)

---

## 데이터 기간별 비교

| 기간 | 행 수 | API 호출 | 수집 시간 | 학습 시간 | 기대 정확도 | 추천도 |
|------|-------|----------|-----------|-----------|-------------|--------|
| 80일 (현재) | 1,919 | 10 | 2분 | 5-10분 | 81-87% | ❌ |
| 6개월 | 4,380 | 22 | 8-10분 | 8-12분 | 84-89% | ⚠️ |
| 1년 | 8,760 | 44 | 18-20분 | 12-18분 | 85-91% | ✅ |
| 2년 | 17,520 | 88 | 35-40분 | 15-25분 | 87-94% | ⭐ |
| 3년 | 26,280 | 132 | 50-60분 | 20-35분 | 88-95% | ⭐⭐ |

## 실행 방법

### 1단계: 데이터 수집 (2년 권장)
```bash
# 2년 데이터 수집 (약 40분 소요)
docker compose exec backend python3 /app/collect_long_term_data.py 730

# 진행 상황 모니터링
docker compose logs -f backend
```

### 2단계: 특징 엔지니어링
```bash
# 기술적 지표 계산 (약 1-2분)
docker compose exec backend python3 /app/prepare_features.py
```

### 3단계: 모델 재학습
```bash
# 4개 코인 순차 학습 (각 15-25분, 총 60-100분)
docker compose exec backend python3 /app/train_gpu.py KRW-BTC
docker compose exec backend python3 /app/train_gpu.py KRW-ETH
docker compose exec backend python3 /app/train_gpu.py KRW-XRP
docker compose exec backend python3 /app/train_gpu.py KRW-SOL

# 모델 백업
docker cp autotraderx-backend-1:/app/models /home/mingky/workspace/autotraderx/backend/models_2years
```

## 기대 효과

### 현재 문제점 (80일 데이터)
```
Hold 클래스 정확도:
- BTC: 86.13% (양호)
- ETH: 75.45% (낮음)
- XRP: 78.10% (낮음)
- SOL: 65.06% (매우 낮음)

문제: 시장 불확실성 판단 어려움
```

### 2년 데이터 학습 후 기대
```
Hold 클래스 정확도 예상:
- BTC: 90-92% (+4-6%)
- ETH: 82-85% (+7-10%)
- XRP: 84-87% (+6-9%)
- SOL: 78-82% (+13-17%)

개선 이유:
1. 다양한 시장 국면 학습
2. 장기 패턴 인식 능력 향상
3. False positive/negative 감소
4. 횡보장 판단 정확도 향상
```

## 주의사항

### 1. 메모리 관리
- 17,520행 × 46 특징 = 약 800K 데이터포인트
- LSTM 시퀀스: (17,496, 24, 46) = 약 19M 엘리먼트
- 예상 메모리: ~2-3GB (현재 1GB에서 증가)

### 2. 학습 시간
- CPU 기준: 15-25분/코인
- GPU 사용 시: 5-8분/코인 (3-4배 빠름)
- 전체 학습: 60-100분 (CPU) 또는 20-35분 (GPU)

### 3. 과적합 위험
- 데이터가 많을수록 과적합 위험 감소
- Early stopping으로 자동 방지
- Validation set으로 일반화 성능 확인

### 4. API 제한
- pyupbit: 초당 10회 제한
- 스크립트는 0.12초 간격으로 호출
- 안정적인 수집 보장

## 추천 진행 순서

### 즉시 실행 (1시간 이내)
1. ⭐ **1년 데이터 수집**: 중간 옵션, 빠른 개선
2. 특징 엔지니어링
3. BTC 1개 코인만 재학습 (테스트)
4. 정확도 비교

### 주말/야간 실행 (2-3시간)
1. ⭐⭐ **2년 데이터 수집**: 최적 옵션
2. 특징 엔지니어링
3. 4개 코인 전체 재학습
4. 통합 테스트 및 배포

### 선택사항 (3-4시간)
1. **3년 데이터 수집**: 최대 성능
2. GPU 환경 설정 (학습 가속)
3. 앙상블 모델 실험

## 빠른 시작

```bash
# 권장: 2년 데이터로 바로 시작
cd /home/mingky/workspace/autotraderx

# 1. 데이터 수집 (40분)
docker compose exec backend python3 /app/collect_long_term_data.py 730

# 2. 특징 생성 (2분)
docker compose exec backend python3 /app/prepare_features.py

# 3. 한 개 코인 테스트 (20분)
docker compose exec backend python3 /app/train_gpu.py KRW-BTC

# 4. 정확도 확인
# 예상: 86.67% → 90-92%
```

## 결론

**2년 데이터 수집을 강력히 권장합니다:**
- 투자 시간: 40분 (수집) + 60-100분 (학습) = 약 2시간
- 기대 효과: 정확도 +5-8%, Hold 클래스 +10-15%
- 장기 사용 가치: 더 신뢰할 수 있는 거래 시스템

암호화폐 시장의 2-3년 주기를 제대로 학습하려면 최소 1-2년의 데이터가 필수적입니다.
