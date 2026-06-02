"""Shared active-markets registry for the dynamic portfolio (v7.0).

The dynamic universe selector writes the current set of "promising" markets
here; the WebSocket feed and the TradingEngine both read from it. A monotonic
version counter lets the WS client detect changes and re-subscribe.
"""
from __future__ import annotations

from threading import RLock
from typing import List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ActiveMarketRegistry:
    """Thread-safe holder for the currently active market list."""

    def __init__(self, initial: Optional[List[str]] = None):
        self._lock = RLock()
        self._markets: List[str] = list(initial or [])
        self._version: int = 0

    def get(self) -> List[str]:
        with self._lock:
            return list(self._markets)

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def set(self, markets: List[str]) -> bool:
        """Replace the active market list.

        Returns True if the set of markets actually changed (and bumps the
        version counter), False otherwise.
        """
        cleaned = [m for m in dict.fromkeys(markets) if m]  # de-dupe, keep order
        with self._lock:
            if cleaned == self._markets:
                return False
            old = self._markets
            self._markets = cleaned
            self._version += 1
            logger.info("active markets updated v%d: %s -> %s", self._version, old, cleaned)
            return True


_REGISTRY: Optional[ActiveMarketRegistry] = None


def get_active_market_registry() -> ActiveMarketRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        s = get_settings()
        _REGISTRY = ActiveMarketRegistry(list(s.tracked_markets))
    return _REGISTRY


def get_active_markets() -> List[str]:
    """Active markets, falling back to settings.tracked_markets when empty."""
    markets = get_active_market_registry().get()
    if markets:
        return markets
    return list(get_settings().tracked_markets)
