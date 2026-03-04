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
# Beat 스케줄 동적 생성 (v6.0: 보수적 주기)
beat_schedule = {
    'trading-cycle-scalping': {
        'task': 'app.celery_app.run_trading_cycle',
        'schedule': float(settings.trading_cycle_seconds),  # v6.0: 180초 (3분)
    },
    'emergency-trading-check': {
        'task': 'app.celery_app.run_emergency_check',
        'schedule': 120.0,  # v6.0: 120초(2분)마다 긴급 체크 (60→120, API 부하 감소)
    },
    'system-health-check': {
        'task': 'app.celery_app.run_health_check',
        'schedule': 7200.0,  # 2시간(7200초)마다 시스템 헬스 체크
    },
    'auto-model-retrain': {
        'task': 'app.celery_app.run_auto_retrain',
        'schedule': crontab(hour='3', minute='0'),  # 매일 새벽 3시에 실행
    },
}

# 펌핑 감지 모드 활성화 시 스케줄 추가
if settings.pump_detection_enabled:
    beat_schedule['pump-detection-loop'] = {
        'task': 'app.celery_app.run_pump_detection',
        'schedule': 60.0,  # 1분마다 실행 (내부적으로 55초 루프)
    }
    logger.info(f"🚀 Pump detection enabled: {settings.pump_threshold_percent}% threshold, {settings.pump_check_interval}s interval")

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
def run_pump_detection() -> str:
    from app.tasks.trading import run_pump_detection_loop  # pylint: disable=import-outside-toplevel

    logger.info("Triggering pump detection loop")
    asyncio.run(run_pump_detection_loop())
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


@celery_app.task
def run_health_check() -> str:
    """
    시스템 헬스 체크 태스크
    2시간마다 실행되어 시스템 상태를 점검하고 Groq LLM으로 분석합니다.
    """
    import subprocess
    from pathlib import Path
    
    logger.info("🏥 Starting system health check...")
    
    try:
        scripts_dir = Path(__file__).parent.parent / "scripts"
        result = subprocess.run(
            ["python", str(scripts_dir / "daily_health_check.py")],
            capture_output=True,
            text=True,
            timeout=300  # 5분 타임아웃
        )
        
        if result.returncode == 0:
            logger.info("✅ System health check completed")
            # 결과의 주요 부분만 로그에 출력
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if '🏥' in line or '✅' in line or '⚠️' in line or '❌' in line:
                    logger.info(line)
            return "success"
        else:
            logger.error(f"❌ Health check failed: {result.stderr}")
            return "failed"
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Health check timeout (5 minutes)")
        return "timeout"
    except Exception as e:
        logger.error(f"❌ Health check error: {e}")
        return "error"
