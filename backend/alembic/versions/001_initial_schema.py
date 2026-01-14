"""Initial schema - users, api_keys, audit_logs

Revision ID: 001
Revises: 
Create Date: 2025-12-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users 테이블
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('oauth_provider', sa.Enum('GOOGLE', 'NAVER', 'KAKAO', name='oauthprovider'), nullable=False, comment='OAuth 제공자'),
        sa.Column('oauth_id', sa.String(length=255), nullable=False, comment='OAuth 사용자 ID'),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('profile_image', sa.String(length=500), nullable=True),
        sa.Column('role', sa.Enum('USER', 'ADMIN', 'DEVELOPER', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='계정 활성화 여부'),
        sa.Column('terms_agreed', sa.Boolean(), nullable=False, comment='이용약관 동의'),
        sa.Column('privacy_agreed', sa.Boolean(), nullable=False, comment='개인정보처리방침 동의'),
        sa.Column('marketing_agreed', sa.Boolean(), nullable=False, comment='마케팅 수신 동의'),
        sa.Column('terms_agreed_at', sa.DateTime(timezone=True), nullable=True, comment='약관 동의 일시'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_oauth_id'), 'users', ['oauth_id'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # api_keys 테이블
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('encrypted_access_key', sa.Text(), nullable=False, comment='암호화된 Access Key'),
        sa.Column('encrypted_secret_key', sa.Text(), nullable=False, comment='암호화된 Secret Key'),
        sa.Column('key_name', sa.String(length=100), nullable=True, comment='키 별칭 (사용자 지정)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='키 활성화 여부'),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True, comment='마지막 검증 시각'),
        sa.Column('permissions', sa.Text(), nullable=True, comment='키 권한 JSON (조회/거래만 허용)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)

    # audit_logs 테이블
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.Enum('LOGIN', 'LOGOUT', 'REGISTER', 'API_KEY_ADD', 'API_KEY_DELETE', 'API_KEY_VALIDATE', 'TRADE_BUY', 'TRADE_SELL', 'SETTINGS_UPDATE', 'PASSWORD_CHANGE', name='auditlogaction'), nullable=False, comment='수행 액션'),
        sa.Column('resource', sa.String(length=100), nullable=True, comment='대상 리소스'),
        sa.Column('resource_id', sa.String(length=100), nullable=True, comment='리소스 ID'),
        sa.Column('details', sa.Text(), nullable=True, comment='액션 상세 (JSON)'),
        sa.Column('ip_address', sa.String(length=45), nullable=True, comment='요청 IP 주소'),
        sa.Column('user_agent', sa.String(length=500), nullable=True, comment='User Agent'),
        sa.Column('success', sa.Boolean(), nullable=False, comment='성공 여부'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='에러 메시지 (실패 시)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)

    # auto_trading_config 테이블
    op.create_table(
        'auto_trading_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=False),
        sa.Column('selected_markets', sa.JSON(), nullable=True),
        sa.Column('use_ai', sa.Boolean(), nullable=True, default=True),
        sa.Column('min_confidence', sa.Float(), nullable=True, default=0.5),
        sa.Column('stop_loss_percent', sa.Float(), nullable=True, default=3.0),
        sa.Column('take_profit_percent', sa.Float(), nullable=True, default=5.0),
        sa.Column('max_positions', sa.Integer(), nullable=True, default=3),
        sa.Column('default_trade_amount', sa.Float(), nullable=True, default=50000.0),
        sa.Column('trading_cycle_seconds', sa.Integer(), nullable=True, default=60),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auto_trading_config_id'), 'auto_trading_config', ['id'], unique=False)

    # trade_positions 테이블
    op.create_table(
        'trade_positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('market', sa.String(length=16), nullable=False),
        sa.Column('size', sa.Float(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('stop_loss', sa.Float(), nullable=False),
        sa.Column('take_profit', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default="OPEN"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trade_positions_market'), 'trade_positions', ['market'], unique=False)

    # trade_logs 테이블
    op.create_table(
        'trade_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('market', sa.String(length=16), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(length=128), nullable=False),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # ml_decision_logs 테이블
    op.create_table(
        'ml_decision_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('market', sa.String(length=16), nullable=False),
        sa.Column('predicted_move', sa.String(length=8), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('groq_alignment', sa.Boolean(), nullable=True, default=False),
        sa.Column('ollama_alignment', sa.Boolean(), nullable=True, default=False),
        sa.Column('emergency_triggered', sa.Boolean(), nullable=True, default=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('ml_decision_logs')
    op.drop_table('trade_logs')
    op.drop_index(op.f('ix_trade_positions_market'), table_name='trade_positions')
    op.drop_table('trade_positions')
    op.drop_index(op.f('ix_auto_trading_config_id'), table_name='auto_trading_config')
    op.drop_table('auto_trading_config')
    
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    
    op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_id'), table_name='api_keys')
    op.drop_table('api_keys')
    
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_oauth_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
    
    op.execute('DROP TYPE IF EXISTS auditlogaction')
    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS oauthprovider')
