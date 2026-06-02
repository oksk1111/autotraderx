from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.routes.account import get_account_balance
from app.api.routes.strategy import strategy_status
from app.broker import PaperBroker, UpbitLiveBroker
from app.core.config import get_settings
from app.db.session import get_db, SessionLocal
from app.engine import get_engine
from app.marketdata import get_active_markets
from app.models import (
    MLDecisionLog, PaperPosition, StrategySignal, TradeLog, TradePosition, RiskEvent, ShadowCompare, AutoTradingConfig
)
from app.schemas.trading import MLDecisionLogSchema, TradeLogSchema, AutoTradingConfigSchema

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
        "tracked_markets": get_active_markets(),
        "strategy_mode": s.strategy_mode,
        "live_trading_enabled": s.live_trading_enabled,
        "paper_equity": paper.get_equity(),
        "daily_pnl_krw": engine.state.daily_realized_pnl_krw,
        "daily_trade_count": engine.state.daily_trade_count,
        "max_daily_trades": s.max_daily_trades,
        "regime_per_market": engine.state.last_regime,
    }


@router.websocket("/ws")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            try:
                with SessionLocal() as db_session:
                    # Metrics & Snapshot
                    s = get_settings()
                    paper = PaperBroker()
                    live = UpbitLiveBroker()
                    engine = get_engine()
                    trade_count = db_session.query(TradeLog).count()
                    paper_open = db_session.query(PaperPosition).filter(PaperPosition.status == "OPEN").count()
                    live_open = db_session.query(TradePosition).filter(TradePosition.status == "OPEN").count()
                    latest_signal = db_session.query(StrategySignal).order_by(StrategySignal.created_at.desc()).first()
                    
                    metrics_data = {
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

                    snapshot_data = {
                        "tracked_markets": get_active_markets(),
                        "strategy_mode": s.strategy_mode,
                        "live_trading_enabled": s.live_trading_enabled,
                        "paper_equity": paper.get_equity(),
                        "daily_pnl_krw": engine.state.daily_realized_pnl_krw,
                        "daily_trade_count": engine.state.daily_trade_count,
                        "max_daily_trades": s.max_daily_trades,
                        "regime_per_market": engine.state.last_regime,
                    }

                    # Trade Logs
                    logs_raw = db_session.query(TradeLog).order_by(TradeLog.created_at.desc()).limit(100).all()
                    trades_data = [TradeLogSchema.model_validate(log).model_dump(mode="json") for log in logs_raw]

                    # Decisions List
                    decisions_raw = db_session.query(MLDecisionLog).order_by(MLDecisionLog.created_at.desc()).limit(50).all()
                    decisions_data = [MLDecisionLogSchema.model_validate(dec).model_dump(mode="json") for dec in decisions_raw]

                    # Config
                    config_obj = db_session.query(AutoTradingConfig).order_by(AutoTradingConfig.id.desc()).first()
                    if not config_obj:
                        config_obj = AutoTradingConfig()
                        db_session.add(config_obj)
                        db_session.commit()
                        db_session.refresh(config_obj)
                    config_data = AutoTradingConfigSchema.model_validate(config_obj).model_dump(mode="json")

                    # Risk State
                    from app.risk import get_kill_switch
                    ks = get_kill_switch()
                    risk_state_data = {
                        "kill_switch": ks.is_enabled(),
                        "live_trading_enabled": s.live_trading_enabled,
                        "daily_loss_limit": s.daily_loss_limit,
                        "daily_realized_pnl_krw": engine.state.daily_realized_pnl_krw,
                        "daily_start_equity": engine.state.daily_start_equity,
                        "daily_trade_count": engine.state.daily_trade_count,
                        "max_daily_trades": s.max_daily_trades,
                        "max_open_positions": s.max_open_positions,
                        "max_position_ratio": s.max_position_ratio,
                        "risk_per_trade": s.risk_per_trade,
                        "cooldown_after_loss_minutes": s.cooldown_after_loss_minutes,
                        "last_loss_unix": engine.state.last_loss_unix,
                        "current_equity_paper": paper.get_equity(),
                        "fee_rate": s.fee_rate,
                        "slippage_est": s.slippage_est,
                    }

                    # Risk Events
                    events_raw = db_session.query(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(20).all()
                    risk_events_data = [
                        {
                            "id": r.id,
                            "created_at": r.created_at.isoformat() if r.created_at else None,
                            "market": r.market,
                            "guard": r.guard,
                            "severity": r.severity,
                            "message": r.message,
                        }
                        for r in events_raw
                    ]

                    # Shadow Compare
                    cutoff = dt.datetime.utcnow() - dt.timedelta(days=7)
                    shadow_raw = (
                        db_session.query(ShadowCompare)
                        .filter(ShadowCompare.created_at >= cutoff)
                        .order_by(ShadowCompare.created_at.asc())
                        .limit(500)
                        .all()
                    )
                    shadow_compare_data = {
                        "count": len(shadow_raw),
                        "series": [
                            {
                                "ts": r.created_at.isoformat() if r.created_at else None,
                                "paper_equity": r.paper_equity,
                                "live_equity": r.live_equity,
                                "paper_open": r.paper_open_positions,
                                "live_open": r.live_open_positions,
                                "daily_pnl_pct": r.daily_pnl_pct,
                            }
                            for r in shadow_raw
                        ],
                    }

                # Executed outside session and handles connection errors
                account_data = await run_in_threadpool(get_account_balance)
                strategy_status_data = await run_in_threadpool(strategy_status)

                # Send payload
                payload = {
                    "metrics": metrics_data,
                    "snapshot": snapshot_data,
                    "trades": trades_data,
                    "decisions": decisions_data,
                    "config": config_data,
                    "risk-state": risk_state_data,
                    "risk-events": risk_events_data,
                    "account": account_data,
                    "strategy-status": strategy_status_data,
                    "shadow-compare": shadow_compare_data,
                }
                await websocket.send_json(payload)
            except Exception as inner_e:
                # Log interior exceptions and retry
                pass
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
