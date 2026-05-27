# AutoTraderX v5.0 — Capital First Rebuild

> **WARNING — 본 프로젝트는 실거래 자금 손실을 일으킬 수 있습니다.**
> v4.x 운영에서 실제 -91.23% 손실이 발생했고, 그 사후 분석을 바탕으로 v5.0이 다시 쓰여졌습니다.
> v5.0은 수익 극대화가 아니라 **자본 보존**을 1순위 목표로 합니다.

상세 기획: [docs/가상화폐 자동 매매 기획 5.md](docs/가상화폐%20자동%20매매%20기획%205.md)

---

## v5.0 핵심 변경

| 항목 | v4 (폐기) | v5 |
|---|---|---|
| 엔진 개수 | 8개 (충돌, 디버깅 불가) | **1개** (`app/engine/trading_engine.py`) |
| 시세 수신 | REST 폴링 (1~5분) | **Upbit WebSocket** (ticker/trade/orderbook) |
| 의사결정 | ML 단기가격예측 + LLM 검증 | **결정론적 규칙 + Regime Switching** |
| 전략 | 6+ 동시 실행 | **Trend-Following** ↔ **Mean Reversion** (regime별 1개) |
| 포지션 사이징 | 신뢰도 ×고정 비율 | **ATR 기반 1% Risk Sizing** |
| 기본 모드 | 라이브 자동매매 | **Live Trading (LIVE_TRADING_ENABLED=true)** |
| Kill switch | 부분 작동 | **API 1초 내 정지** |
| 백테스트 | 없음 | **이벤트드리븐 백테스터 + 메트릭** |
| ML/LLM | 의사결정자 | **보조 필터 / 뉴스 차단용으로만** |

---

## 빠른 시작

### 1. 환경 변수 (`.env`)

```env
POSTGRES_HOST=postgres
POSTGRES_PASSWORD=...
REDIS_HOST=redis

UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=

# 실전 매매 플래그 — 기본 true
LIVE_TRADING_ENABLED=true

TRACKED_MARKETS=KRW-BTC,KRW-ETH

RISK_PER_TRADE=0.01
MAX_OPEN_POSITIONS=1
MAX_POSITION_RATIO=0.25
DAILY_LOSS_LIMIT=0.03
MAX_DAILY_TRADES=6
COOLDOWN_AFTER_LOSS_MIN=30

STRATEGY_MODE=auto
```

### 2. 백엔드

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

WebSocket 클라이언트는 FastAPI lifespan 에서 자동 기동됩니다.

### 3. Celery (헬스/뉴스 등 부수 작업)

```bash
celery -A app.celery_app.celery_app worker --loglevel=info
celery -A app.celery_app.celery_app beat --loglevel=info
```

### 4. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

### 5. 백테스트

```bash
cd backend
python -m app.backtest.backtester --markets KRW-BTC,KRW-ETH --days 90 --strategy auto
```

---

## 운영 절차

1. **Live 운영**: `LIVE_TRADING_ENABLED=true`. Upbit API 키가 있고 사용 가능 KRW가 최소 주문 금액 이상이면 LiveBroker 가 실거래 주문을 발행한다.
   - 시스템은 비교용 Paper 기록도 함께 남긴다. `live_ok=false` 이면 `/api/dashboard/logs` 의 `live_err` 와 `/api/risk/events` 를 먼저 확인한다.
2. **운영 체크**:
   - Upbit API 키의 조회/거래 권한과 IP 허용 목록 확인
   - 사용 가능 KRW가 최소 주문 금액 + 수수료 이상인지 확인
   - Kill switch 1초 내 동작 확인
3. **비상정지**:
   ```bash
   curl -X POST http://158.180.71.84:8000/api/risk/kill-switch \
        -H "Content-Type: application/json" \
        -d '{"enable":true,"close_positions":true}'
   ```

---

## 트러블슈팅 — "거래가 한 건도 안 됩니다"

운영 중 `daily_trade_count == 0` 상태가 지속될 때 점검 순서:

1. **`GET /api/strategy/status`** 호출 — `live_trading_enabled` / `regime` 확인.
2. **`GET /api/strategy/signals?limit=50`** — 신호 행이 누적되는지, rationale 이 어떤가?
   - `regime=NEUTRAL no regime match` 가 반복되면 → Regime classifier 사각지대 (v5.0 ↔ v5.1 에서 수정됨).
   - `breakout=False trend_up=False vol_ok=False` 가 계속이면 → 시장이 정말 횡보 중이고 Trend 조건 미충족.
3. **`GET /api/dashboard/logs`** — BUY 로그의 `live_err` 확인.
   - `insufficient live KRW` → 실전 주문 가능 KRW 부족.
   - `order rejected: None` → Upbit 권한/IP/잔고 문제 가능성이 높음.
4. **`GET /api/risk/events?limit=50`** — BUY 가 어느 가드에서 막히는가?
   - `Liquidity 24h volume X < Y` → 임계가 너무 높은지 (기획서 §5.3 = 50억 원 = `5_000_000_000`) 확인.
   - `position already open for market` → 이전 OPEN PaperPosition 이 청산 대기 중. 정상 동작 (관리 로직이 SL/TP/시간/regime change 청산을 자동 수행).
4. **`GET /api/health/`** — WebSocket / DB / Redis 정상 여부.

### v5.0 → v5.1 핫픽스 요약 (2026-05-26)

| 항목 | v5.0 (버그) | v5.1 (수정) |
|---|---|---|
| `LiquidityGuard.min_24h_quote` | `50_000_000_000` (500억, 단위 오타 — KRW-ETH 도 상시 BLOCK) | `5_000_000_000` (기획서 §5.3 = 50억) |
| Regime classifier | ADX 18~25 가 NEUTRAL 사각지대 → 모든 전략 비활성 | ADX < 25 = RANGE 로 단순화 (Mean-Reversion 내부에서 RSI/BB 재검증) |
| 기획서 §4.1 / §5.3 | 위 두 항목 명시 누락 | 본 README + 기획서에 명시 |

---

## 폴더 구조

```
backend/app/
├── marketdata/      # Upbit WebSocket + 캔들 빌더 + 인메모리 저장소
├── strategy/        # Regime Classifier + Trend/Range 전략 + 지표
├── risk/            # 일일 손실 가드 / 포지션 사이저 / Kill Switch
├── broker/          # Paper / Live 브로커
├── engine/          # 유일한 TradingEngine + Shadow Runner
├── backtest/        # 이벤트 드리븐 백테스터 + 메트릭
├── api/             # FastAPI 라우트
├── tasks/           # Celery (헬스체크/뉴스)
└── models/          # SQLAlchemy 모델
frontend/src/        # React + Vite 대시보드
docs/                # 기획서 (v5 = 현행)
```

---

## 폐기 (v4 잔재 — 삭제됨)

- `app/trading/*` (8개 엔진)
- `app/services/trading/emergency_trader.py`
- `app/ml/rl_agent.py`, `app/ml/trading_env.py`
- 프론트 `AutonomyBoard`, `PersonaPanel`

---

## 솔직한 면책

- 학습/연구용 프로젝트입니다.
- 어떤 알고리즘도 가상화폐 시장에서 지속적 수익을 보장하지 않습니다.
- v5.0 목표는 "최악 시나리오에서도 MDD -10% 이내, 일일 평균 거래 ≤ 4".
- 본 코드 사용으로 인한 손실에 대해 작성자는 책임지지 않습니다.
