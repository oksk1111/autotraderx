# 🔧 버그 수정 보고서 (2026-02-25)

## 문제 현상
- 대시보드(http://158.180.71.84:4173/dashboard)에서 **거래가 장기간 중단**된 상태
- Celery Worker가 태스크 실행 시 모듈 import 실패로 **모든 거래 사이클이 침묵 실패**

## 발견된 문제 및 수정 내역

### 🔴 Critical (시스템 중단 원인) — 3건

#### 1. `market_selector.py` — 도달 불가능한 코드 (SyntaxError)
- **원인**: `return self.cached_markets` 뒤에 `self.last_update = now` 등 도달 불가능한 코드 존재
- **영향**: `MarketSelector` import 실패 → Celery 태스크 전체 중단
- **수정**: 불필요한 데드 코드 제거, `self.last_update = time.time()` 올바른 위치로 이동

#### 2. `hybrid_engine.py` — 중복 else 블록 (SyntaxError)  
- **원인**: if/elif/else 분기 후 두 번째 `else:` 블록 존재 (구문 오류)
- **영향**: `HybridTradingEngine` import 실패 → Enhanced Engine Layer 1 작동 불가
- **수정**: 중복 else를 제거하고 ML fallback 로직을 첫 번째 else 블록 내부로 통합

#### 3. `breakout_strategy.py` — 도달 불가능한 코드 (SyntaxError)
- **원인**: BUY 반환 후 `return "HOLD", 0.0, ""` 와 추가 매도 로직이 dead code로 존재
- **영향**: `BreakoutTradingStrategy` import 실패 → 전역 인스턴스 생성 실패
- **수정**: dead code 제거, 매도 로직(RSI 피크 감지, Dead Cross, 급락 감지)이 정상 실행되도록 복원

### 🔴 Critical — async/await 오류 — 1건

#### 4. `tasks/trading.py` — 비동기 함수 선언 누락
- **원인**: `check_and_manage_positions()` 함수가 `def`로 선언되었으나 내부에서 `await asyncio.sleep()` 사용
- **영향**: 런타임에 `SyntaxError: 'await' outside async function` 발생 → 포지션 관리 실패
- **수정**: 
  - `def` → `async def` 변경
  - 호출부에서 `await check_and_manage_positions(db, executor)` 사용

### 🟠 High — 안정성 문제 — 2건

#### 5. `tasks/trading.py` — `balances` 변수 미정의 위험
- **원인**: 첫 번째 try 블록에서 `balances = upbit.get_balances()` 실패 시, 이후 코드에서 `balances` 참조 시 `NameError`
- **수정**: try 블록 진입 전 `balances = []`, `held_tickers = []` 초기화, except에서도 재초기화

#### 6. `data_pipeline.py` — WebSocket JSON 파싱 오류
- **원인**: `msg.json(loads=None)` 호출은 aiohttp WSMessage에서 잘못된 사용법
- **영향**: Upbit 실시간 스트림 수신 불가
- **수정**: `msg.type` 체크 후 TEXT/BINARY 분기 처리, `{"format": "DEFAULT"}` 추가

### 🟡 Medium — 로직 개선 — 2건

#### 7. `engine.py` — SELL 주문 결과 미검증
- **원인**: BUY 주문은 `uuid` 존재 여부로 성공 확인했으나, SELL은 무조건 성공 처리
- **수정**: SELL 주문에도 `uuid` 체크 추가, 실패 시 경고 로그

#### 8. `multi_timeframe_engine.py` — Division by Zero 위험
- **원인**: 거래량 비율 계산 시 초기 5캔들 평균 거래량이 0일 경우 무한대 발생
- **수정**: 0으로 나눔 방지 (fallback: 1.0)

## 수정된 파일 목록 (7개)

| 파일 | 수정 유형 |
|------|-----------|
| `backend/app/trading/market_selector.py` | SyntaxError 수정 |
| `backend/app/trading/hybrid_engine.py` | SyntaxError 수정 |
| `backend/app/trading/breakout_strategy.py` | SyntaxError 수정 |
| `backend/app/tasks/trading.py` | async/await + 변수 안전성 |
| `backend/app/services/data_pipeline.py` | WebSocket 파싱 수정 |
| `backend/app/trading/engine.py` | SELL 검증 추가 |
| `backend/app/trading/multi_timeframe_engine.py` | Division by Zero 방지 |

## 거래 중단의 근본 원인 분석

```
SyntaxError in market_selector.py / hybrid_engine.py / breakout_strategy.py
    ↓
Celery Worker가 app.tasks.trading 모듈 import 시 실패
    ↓
beat 스케줄러가 태스크를 등록하지만 Worker가 실행 불가
    ↓
모든 거래 사이클 (trading-cycle, emergency-check, pump-detection) 침묵 실패
    ↓
거래 완전 중단
```

## 배포 후 확인 사항

1. Celery Worker 재시작 후 `run_trading_cycle` 태스크 정상 실행 확인
2. DB에서 `auto_trading_configs` 테이블의 `is_active = true` 확인
3. `.env` 파일의 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` 유효성 확인
4. Redis 연결 정상 확인
