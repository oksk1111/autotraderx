# AutoTrader-LXA v3

Hybrid ML + dual LLM autonomous cryptocurrency trading stack rebuilt from the v3 planning document.

## Features

- FastAPI backend orchestrating ML inference, dual LLM verification (Groq + Ollama), and emergency safeguards.
- Celery worker/beat for continuous trading cycles and scheduling.
- React + Vite dashboard showing metrics, decisions, and trade history.
- PostgreSQL for persistence, Redis for task queue, Ollama container for local LLMs.

## Getting Started

1. Duplicate `.env.example` into `.env` and fill all secrets (Upbit, Groq, Telegram, etc.).
2. Configure trading parameters (optional):
   - `TRADING_CYCLE_SECONDS`: 매매 주기 (초단위, 기본값: 300 = 5분)
     - 60: 1분 (매우 공격적, 수수료 주의)
     - 180: 3분 (빠른 대응)
     - 300: 5분 (권장, LLM 처리 시간 고려)
     - 600: 10분 (보수적)
   - `DEFAULT_TRADE_AMOUNT`: 거래당 투자 금액 (기본값: 50000원)
   - `MAX_OPEN_POSITIONS`: 최대 동시 보유 포지션 (기본값: 3)
   - `STOP_LOSS_PERCENT`: 손절 비율 (기본값: 3%)
   - `TAKE_PROFIT_PERCENT`: 익절 비율 (기본값: 5%)
3. Build and start the stack:

```bash
docker compose up --build
```

This launches PostgreSQL, Redis, backend, Celery worker/beat, frontend, and Ollama.

Backend runs at `http://localhost:8000/api`, frontend dashboard at `http://localhost:4173`.

## Development

- Backend dependencies: `pip install -r backend/requirements.txt`
- Run API locally: `uvicorn app.main:app --reload`
- Frontend dev server: `npm install && npm run dev` inside `frontend`.
- Celery worker: `celery -A app.celery_app.celery_app worker --loglevel=info`

## Next Strategy Rollout (Cloud, systemd)

For non-docker cloud deployments, use the rollout helper:

```bash
chmod +x deploy/run_next_strategy.sh
PROJECT_DIR=/home/ubuntu/autotraderx ./deploy/run_next_strategy.sh
```

It performs:
- `git fetch/pull`
- service restart (`autotrader-backend`, `autotrader-worker`, `autotrader-scheduler`, `autotrader-frontend`)
- health checks via `systemctl is-active`
- surge alert smoke task trigger via Celery

Validate surge alert settings and notification readiness:

```bash
cd backend
source venv/bin/activate
python scripts/test_surge_alert_config.py
```

### Utility Scripts

- **Position Sync**: Sync Upbit account balance with local database.
  ```bash
  docker compose exec backend python /app/scripts/sync_positions.py
  ```
- **Health Check**: Run manual system health check.
  ```bash
  docker compose exec backend python /app/scripts/daily_health_check.py
  ```

## Tests

Run backend unit tests:

```bash
cd backend && pytest
```

## Folder Structure

```
backend/    FastAPI app, ML/LLM services, Celery tasks
frontend/   React dashboard (Vite)
docs/       Planning docs (source of truth)
```
