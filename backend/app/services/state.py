from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.config import Settings, get_settings


@dataclass
class SystemSnapshot:
    timestamp: datetime
    active_markets: list[str]
    groq_latency_ms: int
    ollama_latency_ms: int
    emergency_triggers_today: int
    open_positions: int
    pnl_24h: float


class SystemSnapshotService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @classmethod
    def from_settings(cls) -> "SystemSnapshotService":
        return cls(get_settings())

    def snapshot(self) -> dict[str, Any]:
        data = SystemSnapshot(
            timestamp=datetime.utcnow(),
            active_markets=self.settings.tracked_markets,
            groq_latency_ms=random.randint(40, 180),
            ollama_latency_ms=random.randint(180, 400),
            emergency_triggers_today=random.randint(0, 3),
            open_positions=random.randint(0, self.settings.max_open_positions),
            pnl_24h=round(random.uniform(-2.3, 4.7), 2),
        )
        return data.__dict__
