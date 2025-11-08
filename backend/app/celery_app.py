"""
Celery 애플리케이션 설정
"""
from celery import Celery
from app.core.config import settings

# Celery 인스턴스 생성
celery_app = Celery(
    "autotraderx",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"]
)

# Celery 설정
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30분
    task_soft_time_limit=25 * 60,  # 25분
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# 주기적 작업 스케줄 (Celery Beat)
celery_app.conf.beat_schedule = {
    "update-market-data": {
        "task": "app.tasks.update_market_data",
        "schedule": 60.0,  # 1분마다 실행
    },
    "check-trading-signals": {
        "task": "app.tasks.check_trading_signals",
        "schedule": 30.0,  # 30초마다 실행
    },
}


if __name__ == "__main__":
    celery_app.start()
