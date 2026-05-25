"""Broker protocol and shared types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    side: OrderSide
    market: str
    requested_notional_krw: float = 0.0
    requested_qty: float = 0.0
    filled_qty: float = 0.0
    filled_price: float = 0.0
    filled_notional_krw: float = 0.0
    success: bool = False
    error: str = ""
    broker: str = ""


@dataclass
class Position:
    market: str
    qty: float
    entry_price: float
    stop_loss: float = 0.0
    take_profit: float = 0.0
    strategy: str = ""


class Broker(Protocol):
    name: str
    def get_equity(self) -> float: ...
    def get_position(self, market: str) -> Optional[Position]: ...
    def list_positions(self) -> list[Position]: ...
    def submit_market_buy(self, market: str, notional_krw: float, *,
                          stop_loss: float = 0.0, take_profit: float = 0.0,
                          strategy: str = "") -> Order: ...
    def submit_market_sell(self, market: str, qty: float) -> Order: ...
