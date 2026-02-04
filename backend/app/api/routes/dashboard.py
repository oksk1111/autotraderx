from __future__ import annotations
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
 
from app.db.session import get_db
from app.core.redis_client import get_redis_client
from app.models import MLDecisionLog, TradeLog
from app.schemas.trading import MLDecisionLogSchema, TradeLogSchema
from app.services.state import SystemSnapshotService

router = APIRouter()


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)) -> dict[str, float | int]:
    trade_count = db.query(TradeLog).count()
    latest_trade = db.query(TradeLog).order_by(TradeLog.created_at.desc()).first()
    latest_confidence = db.query(MLDecisionLog).order_by(MLDecisionLog.created_at.desc()).first()
    return {
        "trade_count": trade_count,
        "last_trade_amount": latest_trade.amount if latest_trade else 0,
        "last_confidence": latest_confidence.confidence if latest_confidence else 0,
    }


@router.get("/logs", response_model=list[TradeLogSchema])
def get_trade_logs(db: Session = Depends(get_db)) -> list[TradeLog]:
    return db.query(TradeLog).order_by(TradeLog.created_at.desc()).limit(50).all()


@router.get("/decisions", response_model=list[MLDecisionLogSchema])
def get_decision_logs(db: Session = Depends(get_db)) -> list[MLDecisionLog]:
    return db.query(MLDecisionLog).order_by(MLDecisionLog.created_at.desc()).limit(50).all()


@router.get("/snapshot")
def get_snapshot(service: SystemSnapshotService = Depends(SystemSnapshotService.from_settings)) -> dict:
    return service.snapshot()


@router.get("/personas_status")
def get_personas_status() -> dict:
    result = {}
    rd = get_redis_client()
    if rd:
        raw_data = rd.hgetall("persona_status")
        for market, data_str in raw_data.items():
            try:
                result[market] = json.loads(data_str)
            except:
                pass
    return result
