"""UniverseRunner — periodically refreshes the dynamic trading universe (v7.0).

Every ``universe_refresh_sec`` it asks the :class:`UniverseSelector` for the
current best markets, bootstraps candle history for any *new* markets, then
publishes the list to the shared :class:`ActiveMarketRegistry`. The WS feed
re-subscribes automatically and the TradingEngine picks up the new markets on
its next sweep.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.marketdata import get_active_market_registry
from app.marketdata.active import ActiveMarketRegistry
from app.marketdata.candles import CandleBuilder
from app.strategy import UniverseSelector

logger = get_logger(__name__)


class UniverseRunner:
    def __init__(
        self,
        registry: Optional[ActiveMarketRegistry] = None,
        builder: Optional[CandleBuilder] = None,
        selector: Optional[UniverseSelector] = None,
    ):
        self.s = get_settings()
        self.registry = registry or get_active_market_registry()
        self.builder = builder
        self.selector = selector or UniverseSelector(settings=self.s)
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def refresh_once(self) -> None:
        if not self.s.dynamic_universe_enabled:
            return
        try:
            selected = await asyncio.to_thread(self.selector.select)
        except Exception as exc:  # noqa
            logger.exception("universe select failed: %s", exc)
            return
        if not selected:
            return

        current = set(self.registry.get())
        new_markets = [m for m in selected if m not in current]
        # Warm up candle history for new markets before they go live.
        if new_markets and self.builder is not None:
            try:
                await self.builder.bootstrap_markets(new_markets, count_per_tf=200)
            except Exception as exc:  # noqa
                logger.warning("bootstrap new markets failed: %s", exc)

        self.registry.set(selected)

    async def run(self) -> None:
        if not self.s.dynamic_universe_enabled:
            logger.info("dynamic universe disabled — UniverseRunner idle")
            return
        # Run once immediately so the universe is fresh at startup.
        await self.refresh_once()
        interval = max(int(self.s.universe_refresh_sec), 60)
        logger.info("UniverseRunner started, interval=%ss size=%s", interval, self.s.universe_size)
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set():
                break
            await self.refresh_once()
        logger.info("UniverseRunner stopped")
