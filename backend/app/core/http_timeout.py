from __future__ import annotations

from typing import Any

import requests


_PATCHED_ATTR = "_autotraderx_timeout_patched"


def install_default_requests_timeout(timeout_seconds: float = 5.0) -> None:
    """Apply a default timeout to requests-based libraries such as pyupbit."""
    original = requests.sessions.Session.request
    if getattr(original, _PATCHED_ATTR, False):
        return

    def request_with_timeout(self: requests.Session, method: str, url: str, **kwargs: Any):
        kwargs.setdefault("timeout", timeout_seconds)
        return original(self, method, url, **kwargs)

    setattr(request_with_timeout, _PATCHED_ATTR, True)
    requests.sessions.Session.request = request_with_timeout