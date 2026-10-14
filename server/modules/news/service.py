"""News topic CRUD and digest queries."""

from __future__ import annotations

from server.config import get_settings
from server.modules.news.db import (
    DigestRow,
    TopicRow,
    get_news_db,
    to_iso,
)
from server.modules.news.jobs import run_topic_job
from server.modules.news.providers import configured_providers
from server.modules.news.schemas import (
    DigestOut,
    RunResultOut,
    TopicCreate,
    TopicOut,
    TopicUpdate,
)


def _topic_out(row: TopicRow) -> TopicOut:
    return TopicOut(
        id=row.id,
        label=row.label,
        goal=row.goal,
        feed_urls=list(row.feed_urls),
        schedule_enabled=row.schedule_enabled,
        schedule_hour=row.schedule_hour,
        schedule_minute=row.schedule_minute,
        schedule_days=list(row.schedule_days),
        last_run_at=to_iso(row.last_run_at) if row.last_run_at else None,
        last_run_status=row.last_run_status,
        last_error=row.last_error,
        created_at=to_iso(row.created_at) if row.created_at else None,
        updated_at=to_iso(row.updated_at) if row.updated_at else None,
    )


def _digest_out(row: DigestRow) -> DigestOut:
    return DigestOut(
        id=row.id,
        topic_id=row.topic_id,
        topic_label=row.topic_label,
        digest=row.digest,
        item_count=row.item_count,
        generated_at=to_iso(row.generated_at),
        for_date=row.for_date,
        ai_provider=row.ai_provider,
        status=row.status,
        error_message=row.error_message,
    )


def create_topic(body: TopicCreate) -> TopicOut:
    db = get_news_db()
    if db.get_topic(body.id) is not None:
        raise ValueError(f"Topic '{body.id}' already exists")
    row = TopicRow(
        id=body.id,
        label=body.label,
        goal=body.goal,
        feed_urls=body.feed_urls,
        schedule_enabled=body.schedule_enabled,
        schedule_hour=body.schedule_hour,
        schedule_minute=body.schedule_minute,
        schedule_days=body.schedule_days,
    )
    return _topic_out(db.upsert_topic(row))


def update_topic(topic_id: str, body: TopicUpdate) -> TopicOut | None:
    db = get_news_db()
    existing = db.get_topic(topic_id)
    if existing is None:
        return None
    row = TopicRow(
        id=existing.id,
        label=body.label if body.label is not None else existing.label,
        goal=body.goal if body.goal is not None else existing.goal,
        feed_urls=body.feed_urls if body.feed_urls is not None else existing.feed_urls,
        schedule_enabled=(
            body.schedule_enabled
            if body.schedule_enabled is not None
            else existing.schedule_enabled
        ),
        schedule_hour=(
            body.schedule_hour if body.schedule_hour is not None else existing.schedule_hour
        ),
        schedule_minute=(
            body.schedule_minute
            if body.schedule_minute is not None
            else existing.schedule_minute
        ),
        schedule_days=(
            body.schedule_days if body.schedule_days is not None else existing.schedule_days
        ),
        last_run_at=existing.last_run_at,
        last_run_status=existing.last_run_status,
        last_error=existing.last_error,
        created_at=existing.created_at,
    )
    return _topic_out(db.upsert_topic(row))


def get_topic(topic_id: str) -> TopicOut | None:
    row = get_news_db().get_topic(topic_id)
    return _topic_out(row) if row else None


def list_topics() -> list[TopicOut]:
    return [_topic_out(r) for r in get_news_db().list_topics()]


def delete_topic(topic_id: str) -> bool:
    return get_news_db().delete_topic(topic_id)


def list_digests(
    *, topic_id: str | None = None, for_date: str | None = None, limit: int = 50
) -> list[DigestOut]:
    rows = get_news_db().list_digests(
        topic_id=topic_id, for_date=for_date, limit=limit
    )
    return [_digest_out(r) for r in rows]


def latest_digests(for_date: str | None = None) -> list[DigestOut]:
    settings = get_settings()
    if for_date is None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        for_date = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    return [_digest_out(r) for r in get_news_db().latest_digests_by_topic(for_date)]


def run_topic(topic_id: str, *, for_date: str | None = None) -> RunResultOut:
    db = get_news_db()
    topic = db.get_topic(topic_id)
    if topic is None:
        raise LookupError(f"Topic '{topic_id}' not found")
    digest = run_topic_job(topic, db=db, force_date=for_date)
    return RunResultOut(
        digest=_digest_out(digest),
        providers_configured=configured_providers(),
    )


def get_topic_digests(*, date: str) -> list[dict]:
    """Morning-brief consumer shape matching news.by_topic entries."""
    rows = get_news_db().latest_digests_by_topic(date)
    return [
        {
            "topic_id": r.topic_id,
            "topic_label": r.topic_label,
            "digest": r.digest,
            "item_count": r.item_count,
            "generated_at": to_iso(r.generated_at),
            "ai_provider": r.ai_provider,
            "status": r.status,
        }
        for r in rows
    ]


def startup_news() -> None:
    get_news_db().init_schema()
