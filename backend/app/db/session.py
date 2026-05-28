from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

database_url = settings.resolved_database_url

connect_args = {}
if database_url.startswith("postgresql"):
    connect_args["connect_timeout"] = 3

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_timeout=5,
    connect_args=connect_args,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
