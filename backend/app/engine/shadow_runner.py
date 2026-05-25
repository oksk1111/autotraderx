"""Async runner that periodically calls TradingEngine.evaluate_all().

Triggered every N seconds OR on 1m candle close (via CandleBuilder listener).
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from .trading_engine import get_engine

logger = get_logger(__name__)


class ShadowRunner:
    def __init__(self, interval_sec: int = 30):
        self.interval = interval_sec
        self._stop = asyncio.Event()
        self.s = get_settings()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        engine = get_engine()
        # initial delay so WS has time to fill the store
        await asyncio.sleep(10)
        logger.info("ShadowRunner started, interval=%ss live=%s", self.interval, self.s.live_trading_enabled)
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(engine.evaluate_all)
            except Exception as e:
                logger.exception("ShadowRunner evaluate_all error: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
        logger.info("ShadowRunner stopped")
