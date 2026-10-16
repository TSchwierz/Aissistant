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


def _migrate_profile_columns() -> None:
    """create_all does not add columns to an existing SQLite profile table."""
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(profile)").fetchall()
        if not rows:
            return
        cols = {row[1] for row in rows}
        if "activity_level" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE profile ADD COLUMN activity_level VARCHAR(32) DEFAULT 'moderate'"
            )
        if "target_fat_pct" not in cols:
            conn.exec_driver_sql("ALTER TABLE profile ADD COLUMN target_fat_pct FLOAT")
        if "meals_per_day" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE profile ADD COLUMN meals_per_day INTEGER DEFAULT 3"
            )


def init_db() -> None:
    from server.modules.health import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    _migrate_profile_columns()


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
