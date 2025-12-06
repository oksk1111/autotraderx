from __future__ import annotations

import datetime as dt
from typing import List

from pydantic import BaseModel, Field


class TradeDecision(BaseModel):
    market: str
    action: str  # BUY / SELL / HOLD
    confidence: float = Field(ge=0, le=1)
    rationale: str
    emergency: bool = False


class AutoTradingConfigSchema(BaseModel):
    is_active: bool = False
    selected_markets: List[str] = Field(default_factory=lambda: ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"])
    use_ai: bool = True
    min_confidence: float = 0.6
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 5.0
    max_positions: int = 3
    default_trade_amount: float = 50_000
    trading_cycle_seconds: int = 60


class TradeLogSchema(BaseModel):
    id: int
    created_at: dt.datetime
    market: str
    side: str
    amount: float
    reason: str
    context: dict | None = None

    class Config:
        from_attributes = True


class MLDecisionLogSchema(BaseModel):
    id: int
    created_at: dt.datetime
    market: str
    predicted_move: str
    confidence: float
    groq_alignment: bool
    ollama_alignment: bool
    emergency_triggered: bool
    rationale: str

    class Config:
        from_attributes = True
