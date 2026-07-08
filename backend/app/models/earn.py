"""SQLAlchemy models for the Earn subsystem."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .trading import Base, TimestampMixin


class EarnOpportunity(Base, TimestampMixin):
    """Discovered earning opportunities (events, airdrops, faucets)."""

    __tablename__ = "earn_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_value_krw: Mapped[float] = mapped_column(Float, default=0.0)
    action_url: Mapped[str] = mapped_column(String(512), default="")
    action_type: Mapped[str] = mapped_column(String(32), default="notification")
    status: Mapped[str] = mapped_column(String(32), default="discovered", index=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)


class EarnLog(Base, TimestampMixin):
    """Realized earnings (claimed amounts)."""

    __tablename__ = "earn_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    amount_krw: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(16), default="KRW")
    raw_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class EarnPhaseState(Base, TimestampMixin):
    """Tracks current earn system phase and cumulative statistics."""

    __tablename__ = "earn_phase_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_phase: Mapped[int] = mapped_column(Integer, default=1)
    total_earned_krw: Mapped[float] = mapped_column(Float, default=0.0)
    phase2_activated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    phase3_activated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scan_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opportunities_found: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_claimed: Mapped[int] = mapped_column(Integer, default=0)
