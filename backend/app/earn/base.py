"""Base protocol and data structures for the Earn subsystem.

Each earner implements BaseEarner: scan for opportunities and optionally claim them.
"""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class EarnSource(str, Enum):
    UPBIT_EVENT = "upbit_event"
    AIRDROP = "airdrop"
    FAUCET = "faucet"
    DEFI = "defi"


class ActionType(str, Enum):
    AUTO_CLAIM = "auto_claim"       # Can be claimed automatically
    MANUAL = "manual"               # Requires user action (quiz answer, etc.)
    NOTIFICATION = "notification"   # Alert-only (new listing, etc.)


class EventStatus(str, Enum):
    DISCOVERED = "discovered"
    CLAIMED = "claimed"
    PENDING = "pending"
    FAILED = "failed"
    EXPIRED = "expired"
    NOTIFIED = "notified"


@dataclass
class EarnEvent:
    """A discovered earning opportunity."""

    source: EarnSource
    title: str
    description: str
    estimated_value_krw: float = 0.0
    action_url: str = ""
    action_type: ActionType = ActionType.NOTIFICATION
    status: EventStatus = EventStatus.DISCOVERED
    expires_at: Optional[dt.datetime] = None
    metadata: Dict = field(default_factory=dict)
    discovered_at: dt.datetime = field(default_factory=dt.datetime.utcnow)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return dt.datetime.utcnow() > self.expires_at

    @property
    def is_claimable(self) -> bool:
        return (
            self.action_type == ActionType.AUTO_CLAIM
            and self.status == EventStatus.DISCOVERED
            and not self.is_expired
        )


class BaseEarner(ABC):
    """Protocol for all earning strategy implementations."""

    name: str = "base"

    @abstractmethod
    async def scan(self) -> List[EarnEvent]:
        """Scan for new earning opportunities. Returns newly discovered events."""
        ...

    async def claim(self, event: EarnEvent) -> bool:
        """Attempt to claim an opportunity. Returns True on success."""
        return False

    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether this earner is currently active."""
        ...
