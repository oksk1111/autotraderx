"""Earn subsystem — zero-capital bootstrap via airdrops, events, and faucets."""
from __future__ import annotations

from functools import lru_cache

from .base import ActionType, BaseEarner, EarnEvent, EarnSource, EventStatus
from .manager import EarnManager


@lru_cache(maxsize=1)
def get_earn_manager() -> EarnManager:
    """Singleton EarnManager instance."""
    return EarnManager()


__all__ = [
    "ActionType",
    "BaseEarner",
    "EarnEvent",
    "EarnManager",
    "EarnSource",
    "EventStatus",
    "get_earn_manager",
]
