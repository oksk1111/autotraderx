from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
 
from app.db.session import get_db
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
