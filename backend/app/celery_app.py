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
# Beat 스케줄 동적 생성
beat_schedule = {
    'trading-cycle-scalping': {
        'task': 'app.celery_app.run_trading_cycle',
        'schedule': float(settings.trading_cycle_seconds),  # 환경변수로 설정 가능 (기본값: 1분, v4.0)
    },
    'emergency-trading-check': {
        'task': 'app.celery_app.run_emergency_check',
        'schedule': 10.0,  # 10초마다 긴급 체크
    },
    'auto-model-retrain': {
        'task': 'app.celery_app.run_auto_retrain',
        'schedule': crontab(hour='3', minute='0'),  # 매일 새벽 3시에 실행
    },
}

# 공격적 매매 모드가 활성화되면 tick 매매 스케줄 추가
if settings.aggressive_trading_mode:
    beat_schedule['tick-trading-cycle'] = {
        'task': 'app.celery_app.run_tick_trading',
        'schedule': float(settings.tick_interval_seconds),  # tick 주기 (기본값: 1분)
    }
    logger.info(f"🚀 Aggressive trading mode enabled: {settings.tick_interval_seconds}s interval, min confidence {settings.tick_min_confidence:.0%}")

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
    beat_schedule=beat_schedule,
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


@celery_app.task
def run_tick_trading() -> str:
    from app.tasks.trading import run_tick_cycle  # pylint: disable=import-outside-toplevel

    logger.debug("Triggering tick trading cycle")
    asyncio.run(run_tick_cycle())
    return "ok"


@celery_app.task
def run_auto_retrain() -> str:
    """
    자동 모델 재훈련 태스크
    매일 새벽 3시에 실행되어 최신 데이터로 ML 모델을 재훈련합니다.
    """
    import subprocess
    from pathlib import Path
    
    logger.info("🤖 Starting automatic model retraining...")
    
    try:
        scripts_dir = Path(__file__).parent.parent / "scripts"
        result = subprocess.run(
            ["python", str(scripts_dir / "auto_retrain.py")],
            capture_output=True,
            text=True,
            timeout=3600  # 1시간 타임아웃
        )
        
        if result.returncode == 0:
            logger.info("✅ Automatic model retraining completed successfully")
            logger.info(result.stdout[-500:] if result.stdout else "")
            return "success"
        else:
            logger.error(f"❌ Model retraining failed: {result.stderr}")
            return "failed"
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Model retraining timeout (1 hour)")
        return "timeout"
    except Exception as e:
        logger.error(f"❌ Model retraining error: {e}")
        return "error"
