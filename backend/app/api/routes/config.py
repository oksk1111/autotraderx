from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AutoTradingConfig
from app.schemas.trading import AutoTradingConfigSchema
from app.celery_app import celery_app
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=AutoTradingConfigSchema)
def get_config(db: Session = Depends(get_db)) -> AutoTradingConfig:
    config = db.query(AutoTradingConfig).order_by(AutoTradingConfig.id.desc()).first()
    if not config:
        config = AutoTradingConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.put("/", response_model=AutoTradingConfigSchema)
def update_config(payload: AutoTradingConfigSchema, db: Session = Depends(get_db)) -> AutoTradingConfig:
    config = db.query(AutoTradingConfig).order_by(AutoTradingConfig.id.desc()).first()
    if not config:
        config = AutoTradingConfig()
        db.add(config)
    
    # 매매 주기가 변경되었는지 확인
    old_cycle = getattr(config, 'trading_cycle_seconds', 60)
    new_cycle = payload.trading_cycle_seconds
    cycle_changed = old_cycle != new_cycle
    
    for field, value in payload.model_dump().items():
        setattr(config, field, value)
    db.commit()
    db.refresh(config)
    
    # 매매 주기가 변경되면 Celery Beat 스케줄 업데이트
    if cycle_changed:
        try:
            celery_app.conf.beat_schedule['trading-cycle-scalping']['schedule'] = float(new_cycle)
            logger.info(f"Trading cycle updated: {old_cycle}s -> {new_cycle}s")
        except Exception as e:
            logger.error(f"Failed to update Celery Beat schedule: {e}")
    
    return config
