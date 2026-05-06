"""Drop legacy strategy_option column

Revision ID: 003
Revises: 002
Create Date: 2026-05-07

"""
from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("auto_trading_config", "strategy_option")


def downgrade() -> None:
    op.add_column(
        "auto_trading_config",
        sa.Column("strategy_option", sa.String(length=32), nullable=True, server_default="deprecated"),
    )
