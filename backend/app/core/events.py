from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import init_models
from app.engine import get_engine
from app.engine.universe_runner import UniverseRunner
from app.marketdata import get_active_market_registry, run_upbit_ws_loop
from app.marketdata.candles import CandleBuilder
from app.marketdata.store import get_store
from app.marketdata.upbit_ws import run_dynamic_upbit_ws_loop

logger = get_logger(__name__)

_ws_task: Optional[asyncio.Task] = None
_universe_task: Optional[asyncio.Task] = None
_earn_task: Optional[asyncio.Task] = None
_universe: Optional[UniverseRunner] = None


def register_events(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_event() -> None:  # pylint: disable=unused-variable
        init_models()
        get_engine()  # warm singleton + daily reset

        s = get_settings()
        seed_markets = list(s.tracked_markets)

        global _ws_task, _universe_task, _earn_task, _universe

        if s.dynamic_universe_enabled:
            registry = get_active_market_registry()
            builder = CandleBuilder(markets=list(registry.get()), store=get_store())
            _universe = UniverseRunner(registry=registry, builder=builder)
            await _universe.refresh_once()
            _ws_task = asyncio.create_task(
                run_dynamic_upbit_ws_loop(registry=registry, builder=builder),
                name="upbit-ws",
            )
            _universe_task = asyncio.create_task(_universe.run(), name="universe-runner")
        else:
            if not seed_markets:
                return
            _ws_task = asyncio.create_task(run_upbit_ws_loop(seed_markets), name="upbit-ws")

        # Start Earn system (zero-capital bootstrap)
        if s.earn_system_enabled:
            from app.earn import get_earn_manager
            earn_mgr = get_earn_manager()
            _earn_task = asyncio.create_task(earn_mgr.run(), name="earn-manager")
            logger.info("EarnManager task scheduled")

    @app.on_event("shutdown")
    async def shutdown_event() -> None:  # pylint: disable=unused-variable
        global _ws_task, _universe_task, _earn_task, _universe

        # Stop earn manager
        if _earn_task is not None:
            from app.earn import get_earn_manager
            get_earn_manager().stop()

        if _universe is not None:
            _universe.stop()
        for task in (_universe_task, _ws_task, _earn_task):
            if task is None:
                continue
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=3)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa
                pass
