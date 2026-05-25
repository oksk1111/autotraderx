"""Slim v5.0 Celery task helpers — safety-net only.

Real engine cycle runs in the FastAPI process (ShadowRunner). These tasks are
fallbacks invoked by Celery beat in case the API process is down.
"""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.engine import get_engine
from app.marketdata import get_store

logger = get_logger(__name__)


async def run_safety_cycle() -> None:
    """Run a single engine sweep. No-op if the WS store hasn't been populated
    (i.e. API process is the only thing with live WS data)."""
    store = get_store()
    if not store.known_markets():
        logger.info("safety-cycle skipped: no market data in this process")
        return
    engine = get_engine()
    await asyncio.to_thread(engine.evaluate_all)


async def run_health() -> None:
    store = get_store()
    markets = store.known_markets()
    stale = {m: round(store.staleness_sec(m), 1) for m in markets}
    logger.info("health: markets=%d stale=%s", len(markets), stale)
