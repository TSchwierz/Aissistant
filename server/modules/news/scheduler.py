"""Lightweight in-process news scheduler (Europe/Berlin)."""

from __future__ import annotations

import logging
import threading
import time

from server.config import get_settings
from server.modules.news.db import get_news_db
from server.modules.news.jobs import run_topic_job, topic_is_due

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


def _tick() -> None:
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
