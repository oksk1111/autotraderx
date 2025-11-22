from __future__ import annotations

from fastapi import FastAPI

from app.core.logging import get_logger
from app.db.base import init_models

logger = get_logger(__name__)


def register_events(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_event() -> None:  # pylint: disable=unused-variable
        logger.info("Starting AutoTrader-LXA backend")
        init_models()

    @app.on_event("shutdown")
    async def shutdown_event() -> None:  # pylint: disable=unused-variable
        logger.info("Shutting down AutoTrader-LXA backend")
