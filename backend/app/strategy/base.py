"""Common types for the strategy layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol


@dataclass
class Signal:
    market: str
    action: str          # "BUY" | "SELL" | "HOLD"
    price: float
    atr: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0
    strategy: str = ""
    regime: str = ""
    rationale: str = ""
    confidence: float = 0.5
    # diagnostic metrics for logging
    metrics: dict = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.action in ("BUY", "SELL")


class Strategy(Protocol):
    name: str
    def evaluate(self, market: str, candles_1m: List, candles_5m: List, candles_15m: List) -> Signal: ...
