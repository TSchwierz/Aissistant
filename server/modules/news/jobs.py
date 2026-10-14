"""Collect → summarize job for one news topic."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from server.config import get_settings
from server.modules.news.db import (
    DigestRow,
    NewsDB,
    TopicRow,
    get_news_db,
    new_digest_id,
    to_iso,
    utc_now,
)
from server.modules.news.feeds import collect_feeds, items_as_jsonable, items_to_prompt_block
from server.modules.news.providers import configured_providers, summarize_digest

logger = logging.getLogger(__name__)


def run_topic_job(
    topic: TopicRow,
    *,
    db: NewsDB | None = None,
    force_date: str | None = None,
) -> DigestRow:
    """Fetch feeds, summarize (or skip), persist digest + topic run status."""
    db = db or get_news_db()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz)
    for_date = force_date or now_local.date().isoformat()
    generated_at = utc_now()

    items, feed_status = collect_feeds(topic.feed_urls)
    item_count = len(items)
    items_json = json.dumps(
        {"feeds": feed_status, "items": items_as_jsonable(items)},
        ensure_ascii=False,
    )

    providers = configured_providers(settings)

    if item_count == 0:
        digest = DigestRow(
            id=new_digest_id(),
            topic_id=topic.id,
            topic_label=topic.label,
            digest=f"No feed items collected for {topic.label}.",
            item_count=0,
            generated_at=generated_at,
            for_date=for_date,
            ai_provider=None,
            status="error",
            error_message="No items from configured feeds",
            items_json=items_json,
        )
        db.insert_digest(digest)
        db.mark_topic_run(topic.id, status="error", error=digest.error_message, when=generated_at)
        return digest

    if not providers:
        # Graceful degrade for smoke / no keys on Pi yet.
        titles = "; ".join(i.title for i in items[:8])
        text = (
            f"Feeds fetched ({item_count} items) for {topic.label}; "
            f"summarize skipped (no API keys configured). Headlines: {titles}"
        )
        digest = DigestRow(
            id=new_digest_id(),
            topic_id=topic.id,
            topic_label=topic.label,
            digest=text,
            item_count=item_count,
            generated_at=generated_at,
            for_date=for_date,
            ai_provider=None,
            status="skipped_summarize",
            error_message=None,
            items_json=items_json,
        )
        db.insert_digest(digest)
        db.mark_topic_run(topic.id, status="skipped_summarize", when=generated_at)
        return digest

    block = items_to_prompt_block(items)
    result, attempts = summarize_digest(
        label=topic.label, goal=topic.goal, items_block=block, settings=settings
    )
    if result is None:
        err_bits = [
            f"{a.provider}: {a.error}" for a in attempts if not a.ok and a.error
        ]
        error = (
            "All AI providers failed: " + "; ".join(err_bits)
            if err_bits
            else "All AI providers failed"
        )
        digest = DigestRow(
            id=new_digest_id(),
            topic_id=topic.id,
            topic_label=topic.label,
            digest=(
                f"News digest for {topic.label} could not be generated "
                f"({item_count} items collected). {error}"
            ),
            item_count=item_count,
            generated_at=generated_at,
            for_date=for_date,
            ai_provider=None,
            status="error",
            error_message=error,
            items_json=items_json,
        )
        db.insert_digest(digest)
        db.mark_topic_run(topic.id, status="error", error=error, when=generated_at)
        return digest

    digest = DigestRow(
        id=new_digest_id(),
        topic_id=topic.id,
        topic_label=topic.label,
        digest=result.text,
        item_count=item_count,
        generated_at=generated_at,
        for_date=for_date,
        ai_provider=result.provider,
        status="ok",
        error_message=None,
        items_json=items_json,
    )
    db.insert_digest(digest)
    db.mark_topic_run(topic.id, status="ok", when=generated_at)
    logger.info(
        "News digest %s topic=%s provider=%s items=%s",
        digest.id,
        topic.id,
        result.provider,
        item_count,
    )
    return digest


def topic_is_due(topic: TopicRow, *, now_local: datetime | None = None) -> bool:
    """True if schedule matches local time and not already run today successfully."""
    if not topic.schedule_enabled:
        return False
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    now_local = now_local or datetime.now(tz)
    # ISO weekday Mon=1..Sun=7 → our 0..6
    dow = now_local.isoweekday() - 1
    if dow not in topic.schedule_days:
        return False
    if (now_local.hour, now_local.minute) < (topic.schedule_hour, topic.schedule_minute):
        return False
    if topic.last_run_at is not None:
        last_local = topic.last_run_at.astimezone(tz)
        if last_local.date() == now_local.date() and topic.last_run_status in (
            "ok",
            "skipped_summarize",
            "error",
        ):
            # Already attempted today — do not re-fire automatically.
            return False
    return True
