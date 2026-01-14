from __future__ import annotations

import datetime as dt
from typing import List

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


class AutoTradingConfig(Base, TimestampMixin):
    __tablename__ = "auto_trading_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_markets: Mapped[List[str]] = mapped_column(JSON, default=list)
    use_ai: Mapped[bool] = mapped_column(Boolean, default=True)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    stop_loss_percent: Mapped[float] = mapped_column(Float, default=3.0)
    take_profit_percent: Mapped[float] = mapped_column(Float, default=5.0)
    max_positions: Mapped[int] = mapped_column(Integer, default=3)
    default_trade_amount: Mapped[float] = mapped_column(Float, default=50_000.0)
    trading_cycle_seconds: Mapped[int] = mapped_column(Integer, default=60)
    strategy_option: Mapped[str] = mapped_column(String(32), default="breakout_strategy")  # momentum, reversal, or breakout


class TradePosition(Base, TimestampMixin):
    __tablename__ = "trade_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    size: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")


class TradeLog(Base, TimestampMixin):
    __tablename__ = "trade_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(8))
    amount: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(128))
    context: Mapped[dict | None] = mapped_column(JSON, default=dict)


class MLDecisionLog(Base, TimestampMixin):
    __tablename__ = "ml_decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16))
    predicted_move: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[float] = mapped_column(Float)
    groq_alignment: Mapped[bool] = mapped_column(Boolean, default=False)
    ollama_alignment: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str] = mapped_column(Text)