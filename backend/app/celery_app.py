from __future__ import annotations

import asyncio

from celery import Celery

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
        'trading-cycle-scalping': {
            'task': 'app.celery_app.run_trading_cycle',
            'schedule': float(settings.trading_cycle_seconds),  # 환경변수로 설정 가능 (기본값: 5분)
        },
        'emergency-trading-check': {
            'task': 'app.celery_app.run_emergency_check',
            'schedule': 10.0,  # 10초마다 긴급 체크
        },
    },
)


@celery_app.task
def run_trading_cycle() -> str:
    from app.tasks.trading import run_cycle  # pylint: disable=import-outside-toplevel

    logger.info("Triggering trading cycle")
    asyncio.run(run_cycle())
    return "ok"


@celery_app.task
def run_emergency_check() -> str:
    from app.tasks.trading import run_emergency_check  # pylint: disable=import-outside-toplevel

    logger.debug("Triggering emergency trading check")
    asyncio.run(run_emergency_check())
    return "ok"
