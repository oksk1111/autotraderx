"""Risk control API: state inspection + kill switch."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.broker import UpbitLiveBroker
from app.core.config import get_settings
from app.db.session import get_db
from app.engine import get_engine
from app.models import RiskEvent
from app.risk import get_kill_switch

router = APIRouter()


class KillSwitchPayload(BaseModel):
    enable: bool
    close_positions: bool = False


@router.get("/state")
def risk_state() -> dict:
    s = get_settings()
    engine = get_engine()
    ks = get_kill_switch()
    live = UpbitLiveBroker()
    return {
        "kill_switch": ks.is_enabled(),
        "live_trading_enabled": True,
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
        "current_equity": live.get_equity(),
        "fee_rate": s.fee_rate,
        "slippage_est": s.slippage_est,
    }


@router.get("/events")
def risk_events(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(RiskEvent).order_by(RiskEvent.created_at.desc())
          .limit(min(max(1, limit), 500)).all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "market": r.market,
            "guard": r.guard,
            "severity": r.severity,
            "message": r.message,
        }
        for r in rows
    ]


@router.post("/kill-switch")
def toggle_kill_switch(payload: KillSwitchPayload) -> dict:
    ks = get_kill_switch()
    closed: list[str] = []
    errors: list[str] = []
    if payload.enable:
        ks.enable()
        if payload.close_positions:
            live = UpbitLiveBroker()
            for pos in live.list_positions():
                r = live.submit_market_sell(pos.market, pos.qty)
                if r.success:
                    closed.append(f"live:{pos.market}")
                else:
                    errors.append(f"live:{pos.market}:{r.error}")
    else:
        ks.disable()
    return {"enabled": ks.is_enabled(), "closed": closed, "errors": errors}
