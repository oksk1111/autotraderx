"""v5.0 Celery — minimal. Engine主 cycle은 FastAPI lifespan(ShadowRunner)에서 돌고,
Celery 는 안전망(주기 점검/헬스/뉴스)만 담당."""
from __future__ import annotations

import asyncio

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

celery_app = Celery(
    "autotraderx",
    broker=settings.resolved_redis_url,
    backend=settings.resolved_redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
    beat_schedule={
        # Safety-net cycle. ShadowRunner in API process는 30s 주기로 이미 호출.
        # Celery는 API가 죽었을 경우 백업으로 5분마다 한번 실행.
        "engine-safety-cycle": {
            "task": "app.celery_app.run_engine_safety_cycle",
            "schedule": 300.0,
        },
        "system-health-check": {
            "task": "app.celery_app.run_health_check",
            "schedule": 7200.0,
        },
    },
)


@celery_app.task
def run_engine_safety_cycle() -> str:
    from app.tasks.trading import run_safety_cycle
    asyncio.run(run_safety_cycle())
    return "ok"


@celery_app.task
def run_health_check() -> str:
    from app.tasks.trading import run_health
    asyncio.run(run_health())
    return "ok"
