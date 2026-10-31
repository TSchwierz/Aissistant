"""Lightweight news scheduler (Europe/Berlin)."""

from __future__ import annotations

import logging
import signal
import threading
import time

from server.config import get_settings
from server.modules.news.db import get_news_db
from server.modules.news.jobs import run_topic_job, topic_is_due

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


def _tick() -> None:
    # Once a minute: write today's brief at 04:00 local time if it is missing
    # or was generated earlier than 04:00. Later digest runs refresh the file
    # themselves. A brief failure must not skip the news jobs.
    try:
        from server.modules.briefing.store import pregenerate_morning_brief_if_due

        pregenerate_morning_brief_if_due()
    except Exception:  # noqa: BLE001
        logger.exception("Morning brief pre-generation failed")

    db = get_news_db()
    for topic in db.list_topics():
        try:
            if topic_is_due(topic):
                logger.info("Scheduled news run for topic=%s", topic.id)
                run_topic_job(topic, db=db)
        except Exception:  # noqa: BLE001
            logger.exception("Scheduled news run failed for topic=%s", topic.id)


def _loop() -> None:
    settings = get_settings()
    interval = max(15, int(settings.news_scheduler_tick_seconds))
    logger.info("News scheduler started (tick=%ss)", interval)
    # Initial delay so startup isn't blocked by feeds.
    _stop.wait(5)
    while not _stop.is_set():
        try:
            _tick()
        except Exception:  # noqa: BLE001
            logger.exception("News scheduler tick failed")
        _stop.wait(interval)
    logger.info("News scheduler stopped")


def run_forever() -> None:
    """Block as the news worker process."""

    def _handle(signum, _frame) -> None:  # noqa: ANN001
        logger.info("News worker received signal %s", signum)
        _stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    _stop.clear()
    _loop()


def start_scheduler() -> None:
    global _thread
    settings = get_settings()
    if not settings.news_scheduler_enabled:
        logger.info("News scheduler disabled")
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="news-scheduler", daemon=True)
    _thread.start()


def stop_scheduler() -> None:
    _stop.set()
