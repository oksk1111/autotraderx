"""Add strategy option column

Revision ID: 002
Revises: 001
Create Date: 2026-01-06

"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('auto_trading_config', sa.Column('strategy_option', sa.String(length=32), nullable=True, server_default='reversal_strategy'))

def downgrade() -> None:
    op.drop_column('auto_trading_config', 'strategy_option')
