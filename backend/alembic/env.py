"""Alembic 환경 설정"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
import os

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Alembic Config 객체
config = context.config

# Python logging 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 환경 변수에서 DB URL 주입 (alembic.ini 설정 덮어쓰기)
from app.core.config import get_settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.resolved_database_url)

# SQLAlchemy Base 메타데이터 가져오기
from app.db.base import Base
from app.models import trading  # 기존 trading 모델
from app.models import user  # 새로운 user 관련 모델들

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """오프라인 모드로 마이그레이션 실행 (SQL 스크립트 생성)"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드로 마이그레이션 실행 (DB에 직접 적용)"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
