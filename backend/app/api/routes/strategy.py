"""Strategy status + signal log API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.engine import get_engine
from app.marketdata import get_store, get_active_markets
from app.models import StrategySignal
from app.strategy.regime import RegimeClassifier

router = APIRouter()


@router.get("/status")
def strategy_status() -> dict:
    s = get_settings()
    store = get_store()
    engine = get_engine()
    classifier = RegimeClassifier()
    active_markets = get_active_markets()
    markets = []
    for m in active_markets:
        candles_1m = store.get_candles(m, "1m")
        reading = classifier.classify(candles_1m) if candles_1m else None
        t = store.get_ticker(m)
        markets.append({
            "market": m,
            "price": t.trade_price if t else None,
            "candles_1m": len(candles_1m),
            "stale_sec": round(store.staleness_sec(m), 1) if t else None,
            "regime": reading.as_dict() if reading else None,
        })
    return {
        "mode": s.strategy_mode,
        "live_trading_enabled": s.live_trading_enabled,
        "dynamic_universe_enabled": s.dynamic_universe_enabled,
        "universe_size": s.universe_size,
        "tracked_markets": active_markets,
        "active_markets": active_markets,
        "daily_trade_count": engine.state.daily_trade_count,
        "daily_realized_pnl_krw": engine.state.daily_realized_pnl_krw,
        "daily_start_equity": engine.state.daily_start_equity,
        "markets": markets,
    }


@router.get("/signals")
def strategy_signals(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(StrategySignal)
          .order_by(StrategySignal.created_at.desc())
          .limit(min(max(1, limit), 500))
          .all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "market": r.market,
            "regime": r.regime,
            "strategy": r.strategy,
            "action": r.action,
            "price": r.price,
            "atr": r.atr,
            "stop_price": r.stop_price,
            "target_price": r.target_price,
            "rationale": r.rationale,
        }
        for r in rows
    ]
