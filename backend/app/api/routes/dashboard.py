from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.broker import PaperBroker, UpbitLiveBroker
from app.core.config import get_settings
from app.db.session import get_db
from app.engine import get_engine
from app.models import (
    MLDecisionLog, PaperPosition, StrategySignal, TradeLog, TradePosition,
)
from app.schemas.trading import MLDecisionLogSchema, TradeLogSchema

router = APIRouter()


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    s = get_settings()
    paper = PaperBroker()
    live = UpbitLiveBroker()
    engine = get_engine()
    trade_count = db.query(TradeLog).count()
    paper_open = db.query(PaperPosition).filter(PaperPosition.status == "OPEN").count()
    live_open = db.query(TradePosition).filter(TradePosition.status == "OPEN").count()
    latest_signal = db.query(StrategySignal).order_by(StrategySignal.created_at.desc()).first()
    return {
        "trade_count": trade_count,
        "paper_equity": paper.get_equity(),
        "live_equity": live.get_equity() if s.live_trading_enabled else 0.0,
        "paper_open_positions": paper_open,
        "live_open_positions": live_open,
        "daily_realized_pnl_krw": engine.state.daily_realized_pnl_krw,
        "daily_start_equity": engine.state.daily_start_equity,
        "daily_trade_count": engine.state.daily_trade_count,
        "live_trading_enabled": s.live_trading_enabled,
        "strategy_mode": s.strategy_mode,
        "last_signal": {
            "market": latest_signal.market,
            "regime": latest_signal.regime,
            "strategy": latest_signal.strategy,
            "action": latest_signal.action,
            "price": latest_signal.price,
            "created_at": latest_signal.created_at.isoformat() if latest_signal.created_at else None,
        } if latest_signal else None,
    }


@router.get("/logs", response_model=list[TradeLogSchema])
def get_trade_logs(db: Session = Depends(get_db)) -> list[TradeLog]:
    return db.query(TradeLog).order_by(TradeLog.created_at.desc()).limit(100).all()


@router.get("/decisions", response_model=list[MLDecisionLogSchema])
def get_decision_logs(db: Session = Depends(get_db)) -> list[MLDecisionLog]:
    return db.query(MLDecisionLog).order_by(MLDecisionLog.created_at.desc()).limit(50).all()


@router.get("/snapshot")
def get_snapshot() -> dict:
    s = get_settings()
    engine = get_engine()
    paper = PaperBroker()
    return {
        "tracked_markets": s.tracked_markets,
        "strategy_mode": s.strategy_mode,
        "live_trading_enabled": s.live_trading_enabled,
        "paper_equity": paper.get_equity(),
        "daily_pnl_krw": engine.state.daily_realized_pnl_krw,
        "daily_trade_count": engine.state.daily_trade_count,
        "max_daily_trades": s.max_daily_trades,
        "regime_per_market": engine.state.last_regime,
    }
