"""Paper vs Live PnL comparison API."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ShadowCompare

router = APIRouter()


@router.get("/compare")
def shadow_compare(days: int = 7, limit: int = 500, db: Session = Depends(get_db)) -> dict:
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=max(1, days))
    rows = (
        db.query(ShadowCompare)
          .filter(ShadowCompare.created_at >= cutoff)
          .order_by(ShadowCompare.created_at.asc())
          .limit(min(max(1, limit), 5000))
          .all()
    )
    return {
        "count": len(rows),
        "series": [
            {
                "ts": r.created_at.isoformat() if r.created_at else None,
                "paper_equity": r.paper_equity,
                "live_equity": r.live_equity,
                "paper_open": r.paper_open_positions,
                "live_open": r.live_open_positions,
                "daily_pnl_pct": r.daily_pnl_pct,
            }
            for r in rows
        ],
    }
