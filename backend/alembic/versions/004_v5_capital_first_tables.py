"""v5.0 — Add capital-first tables

Revision ID: 004
Revises: 003
Create Date: 2026-05-25

Adds:
  - strategy_signals
  - risk_events
  - shadow_compare
  - paper_positions
  - paper_account
"""
from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.String(16), nullable=False, index=True),
        sa.Column("regime", sa.String(16), nullable=False),
        sa.Column("strategy", sa.String(32), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("atr", sa.Float, server_default="0"),
        sa.Column("stop_price", sa.Float, server_default="0"),
        sa.Column("target_price", sa.Float, server_default="0"),
        sa.Column("rationale", sa.Text, server_default=""),
        sa.Column("executed", sa.Boolean, server_default=sa.false()),
    )
    op.create_index("ix_strategy_signals_market", "strategy_signals", ["market"])

    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.String(16), nullable=True),
        sa.Column("guard", sa.String(48), nullable=False),
        sa.Column("severity", sa.String(16), server_default="INFO"),
        sa.Column("message", sa.Text, nullable=False),
    )

    op.create_table(
        "shadow_compare",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paper_equity", sa.Float, nullable=False),
        sa.Column("live_equity", sa.Float, server_default="0"),
        sa.Column("paper_open_positions", sa.Integer, server_default="0"),
        sa.Column("live_open_positions", sa.Integer, server_default="0"),
        sa.Column("daily_pnl_pct", sa.Float, server_default="0"),
        sa.Column("notes", sa.Text, server_default=""),
    )

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.String(16), nullable=False, index=True),
        sa.Column("size", sa.Float, nullable=False),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("stop_loss", sa.Float, nullable=False),
        sa.Column("take_profit", sa.Float, nullable=False),
        sa.Column("strategy", sa.String(32), server_default=""),
        sa.Column("status", sa.String(16), server_default="OPEN"),
        sa.Column("closed_price", sa.Float, server_default="0"),
        sa.Column("closed_pnl_krw", sa.Float, server_default="0"),
    )
    op.create_index("ix_paper_positions_market", "paper_positions", ["market"])

    op.create_table(
        "paper_account",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cash_krw", sa.Float, server_default="300000"),
        sa.Column("realized_pnl_krw", sa.Float, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("paper_account")
    op.drop_index("ix_paper_positions_market", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_table("shadow_compare")
    op.drop_table("risk_events")
    op.drop_index("ix_strategy_signals_market", table_name="strategy_signals")
    op.drop_table("strategy_signals")
