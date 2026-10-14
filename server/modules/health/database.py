"""SQLite engine for Health Scale Hub measurements + profile."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from server.config import get_settings

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    pass


def _db_path() -> Path:
    settings = get_settings()
    data_dir = Path(settings.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "health.db"


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = f"sqlite:///{_db_path()}"
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory():
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    from server.modules.health import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def get_db():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine_for_tests() -> None:
    """Drop cached engine (tests / settings reload)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
