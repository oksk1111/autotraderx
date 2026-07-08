"""v9.0 — Add earn system tables

Revision ID: 005
Revises: 004
Create Date: 2026-07-08

Adds:
  - earn_opportunities
  - earn_logs
  - earn_phase_state
"""
from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "earn_opportunities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("estimated_value_krw", sa.Float, default=0.0),
        sa.Column("action_url", sa.String(512), default=""),
        sa.Column("action_type", sa.String(32), default="notification"),
        sa.Column("status", sa.String(32), default="discovered", index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, default=dict),
    )

    op.create_table(
        "earn_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, index=True),
        sa.Column("amount_krw", sa.Float, default=0.0),
        sa.Column("currency", sa.String(16), default="KRW"),
        sa.Column("raw_amount", sa.Float, default=0.0),
        sa.Column("tx_hash", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text, default=""),
    )

    op.create_table(
        "earn_phase_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_phase", sa.Integer, default=1),
        sa.Column("total_earned_krw", sa.Float, default=0.0),
        sa.Column("phase2_activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phase3_activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opportunities_found", sa.Integer, default=0),
        sa.Column("opportunities_claimed", sa.Integer, default=0),
    )


def downgrade() -> None:
    op.drop_table("earn_phase_state")
    op.drop_table("earn_logs")
    op.drop_table("earn_opportunities")
