from __future__ import annotations

from app.db.session import engine
from app.models import Base


def init_models() -> None:
    Base.metadata.create_all(bind=engine)
