"""Kill switch — global flag readable by both API and engine.

Stored in Redis if available, otherwise in-process. State is sticky across
restarts because Redis persists.
"""
from __future__ import annotations

import os
from typing import Optional

from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)

_KEY = "autotrader:kill_switch"


class KillSwitch:
    def __init__(self):
        self._fallback = False  # used if Redis is down

    def is_enabled(self) -> bool:
        rd = get_redis_client()
        if rd is None:
            return self._fallback
        try:
            v = rd.get(_KEY)
            if v is None:
                return False
            return str(v).lower() in ("1", "true", "on", "yes")
        except Exception as e:
            logger.warning("kill-switch redis read failed, using fallback: %s", e)
            return self._fallback

    def enable(self) -> None:
        rd = get_redis_client()
        if rd is None:
            self._fallback = True
            return
        try:
            rd.set(_KEY, "1")
        except Exception as e:
            logger.error("kill-switch redis write failed: %s", e)
            self._fallback = True

    def disable(self) -> None:
        rd = get_redis_client()
        self._fallback = False
        if rd is None:
            return
        try:
            rd.set(_KEY, "0")
        except Exception as e:
            logger.error("kill-switch redis disable failed: %s", e)


_INSTANCE: Optional[KillSwitch] = None


def get_kill_switch() -> KillSwitch:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = KillSwitch()
        # init from env on first construction (idempotent)
        if os.environ.get("KILL_SWITCH", "false").lower() in ("1", "true", "on", "yes"):
            _INSTANCE.enable()
    return _INSTANCE
