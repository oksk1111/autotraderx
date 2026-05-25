from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import init_models
from app.engine import get_engine
from app.engine.shadow_runner import ShadowRunner
from app.marketdata import run_upbit_ws_loop

logger = get_logger(__name__)

_ws_task: Optional[asyncio.Task] = None
_runner_task: Optional[asyncio.Task] = None
_shadow: Optional[ShadowRunner] = None


def register_events(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_event() -> None:  # pylint: disable=unused-variable
        logger.info("Starting AutoTraderX v5.0 backend")
        init_models()
        get_engine()  # warm singleton + daily reset

        s = get_settings()
        markets = list(s.tracked_markets)
        if not markets:
            logger.warning("No tracked_markets configured — skipping WS startup")
            return

        global _ws_task, _runner_task, _shadow
        _ws_task = asyncio.create_task(run_upbit_ws_loop(markets), name="upbit-ws")
        _shadow = ShadowRunner(interval_sec=30)
        _runner_task = asyncio.create_task(_shadow.run(), name="shadow-runner")
        logger.info("v5 background tasks launched: upbit-ws, shadow-runner (markets=%s)", markets)

    @app.on_event("shutdown")
    async def shutdown_event() -> None:  # pylint: disable=unused-variable
        logger.info("Shutting down AutoTraderX v5.0 backend")
        global _ws_task, _runner_task, _shadow
        if _shadow is not None:
            _shadow.stop()
        for task in (_runner_task, _ws_task):
            if task is None:
                continue
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=3)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa
                pass
