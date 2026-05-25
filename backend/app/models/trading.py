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


# =============================================================================
# v5.0 신규 테이블
# =============================================================================

class StrategySignal(Base, TimestampMixin):
    """Regime/Strategy 가 발행한 신호 로그."""

    __tablename__ = "strategy_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    regime: Mapped[str] = mapped_column(String(16))          # TREND/RANGE/CHAOS/NEUTRAL
    strategy: Mapped[str] = mapped_column(String(32))        # trend_following / mean_reversion
    action: Mapped[str] = mapped_column(String(8))           # BUY/SELL/HOLD
    price: Mapped[float] = mapped_column(Float)
    atr: Mapped[float] = mapped_column(Float, default=0.0)
    stop_price: Mapped[float] = mapped_column(Float, default=0.0)
    target_price: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    executed: Mapped[bool] = mapped_column(Boolean, default=False)


class RiskEvent(Base, TimestampMixin):
    """RiskGuard 가 차단/경고/발동한 이벤트."""

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str | None] = mapped_column(String(16), nullable=True)
    guard: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16), default="INFO")  # INFO/WARN/BLOCK
    message: Mapped[str] = mapped_column(Text)


class ShadowCompare(Base, TimestampMixin):
    """Paper vs Live PnL 비교 스냅샷. 매 사이클 종료 시 1행 기록."""

    __tablename__ = "shadow_compare"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_equity: Mapped[float] = mapped_column(Float)
    live_equity: Mapped[float] = mapped_column(Float, default=0.0)
    paper_open_positions: Mapped[int] = mapped_column(Integer, default=0)
    live_open_positions: Mapped[int] = mapped_column(Integer, default=0)
    daily_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")


class PaperPosition(Base, TimestampMixin):
    """Paper Broker 의 포지션 (TradePosition 과 별도 관리)."""

    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    size: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    strategy: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    closed_price: Mapped[float] = mapped_column(Float, default=0.0)
    closed_pnl_krw: Mapped[float] = mapped_column(Float, default=0.0)


class PaperAccount(Base, TimestampMixin):
    """Paper Broker 잔고. 싱글톤(id=1)."""

    __tablename__ = "paper_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash_krw: Mapped[float] = mapped_column(Float, default=300_000.0)  # 초기 30만원 (v4 시작값)
    realized_pnl_krw: Mapped[float] = mapped_column(Float, default=0.0)