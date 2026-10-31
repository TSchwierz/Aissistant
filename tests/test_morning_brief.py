"""Today's morning brief is a file under the data dir, not an in-memory cache."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from server.config import get_settings
from server.models.briefing import BriefMeta, MorningBriefResponse
from server.modules.briefing import composer
from server.modules.briefing.store import (
    load_morning_brief,
    morning_brief_path,
    pregenerate_morning_brief_if_due,
    resolve_morning_brief,
    save_morning_brief,
)
from server.modules.news import scheduler
from server.modules.news.db import NewsDB, TopicRow, reset_news_db_for_tests
from server.modules.news.feeds import FeedItem
from server.modules.news.jobs import run_topic_job
from server.modules.news.providers import SummarizeResult
from server.routers.briefing import get_morning_brief, get_morning_brief_latest

BERLIN = ZoneInfo("Europe/Berlin")
_ITEM = FeedItem(
    title="Headline",
    link="https://example.test/story",
    summary="A thing happened.",
    published=None,
    source_url="https://example.test/rss",
)


def _local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=BERLIN)


class MorningBriefTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_env = {
            "PA_DATA_DIR": os.environ.get("PA_DATA_DIR"),
            "PA_TIMEZONE": os.environ.get("PA_TIMEZONE"),
        }
        os.environ["PA_DATA_DIR"] = self._tmp.name
        os.environ["PA_TIMEZONE"] = "Europe/Berlin"
        get_settings.cache_clear()
        reset_news_db_for_tests()

    def tearDown(self):
        reset_news_db_for_tests()
        for key, old in self._old_env.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        get_settings.cache_clear()
        self._tmp.cleanup()

    def _brief(self, day: str, generated_at: str, script: str) -> MorningBriefResponse:
        return MorningBriefResponse(
            meta=BriefMeta(
                date=day,
                timezone="Europe/Berlin",
                generated_at=generated_at,
                language="en",
            ),
            script=script,
        )

    def _today(self) -> str:
        return datetime.now(BERLIN).date().isoformat()

    def _stamp(self, hour: int = 4, minute: int = 0) -> str:
        now = datetime.now(BERLIN).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return now.isoformat(timespec="seconds")

    def _news_db(self) -> tuple[NewsDB, TopicRow]:
        db = NewsDB(morning_brief_path().parent / "news-job-test.db")
        db.init_schema()
        topic = TopicRow(
            id="world",
            label="World",
            goal="Headlines",
            feed_urls=["https://example.test/rss"],
        )
        db.upsert_topic(topic)
        return db, topic

    def _stored_script(self) -> str:
        stored = load_morning_brief()
        self.assertIsNotNone(stored)
        assert stored is not None
        return stored.script

    def test_today_is_written_and_reread(self):
        today = self._today()
        brief = self._brief(today, self._stamp(), "from-compose")
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=brief,
        ) as compose:
            first = get_morning_brief(date_param=None, refresh=False)
            second = get_morning_brief(date_param=today, refresh=False)
            latest = get_morning_brief_latest(refresh=False)

        self.assertEqual(compose.call_count, 1)
        first_body = json.loads(first.body)
        second_body = json.loads(second.body)
        latest_body = json.loads(latest.body)
        self.assertEqual(first_body["script"], "from-compose")
        self.assertEqual(second_body["script"], "from-compose")
        self.assertEqual(latest_body["script"], "from-compose")
        self.assertEqual(first_body["meta"]["date"], today)
        self.assertEqual(first_body["meta"]["generated_at"], brief.meta.generated_at)

        path = morning_brief_path()
        self.assertEqual(path.name, "morning_brief.json")
        self.assertTrue(path.is_file())
        payload = json.loads(path.read_text(encoding="utf-8"))
        restored = MorningBriefResponse.model_validate(payload)
        self.assertEqual(restored.script, "from-compose")
        self.assertEqual(restored.meta.generated_at, brief.meta.generated_at)
        self.assertEqual(restored.meta.date, today)

    def test_refresh_replaces_the_file(self):
        today = self._today()
        first = self._brief(today, self._stamp(4, 0), "one")
        second = self._brief(today, self._stamp(5, 40), "two")
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            side_effect=[first, second],
        ) as compose:
            resolve_morning_brief(date_param=None, refresh=False)
            updated = resolve_morning_brief(date_param=today, refresh=True)
            reread = resolve_morning_brief(date_param=None, refresh=False)

        self.assertEqual(compose.call_count, 2)
        self.assertEqual(updated.script, "two")
        self.assertEqual(reread.script, "two")
        self.assertEqual(self._stored_script(), "two")
        stored = load_morning_brief()
        assert stored is not None
        self.assertEqual(stored.meta.generated_at, second.meta.generated_at)

    def test_other_date_is_not_stored_as_the_morning_file(self):
        today = self._today()
        other = (datetime.now(BERLIN).date() - timedelta(days=1)).isoformat()
        other_brief = self._brief(other, self._stamp(), "other-day")
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=other_brief,
        ) as compose:
            got = resolve_morning_brief(date_param=other, refresh=False)
            refreshed = resolve_morning_brief(date_param=other, refresh=True)

        self.assertEqual(got.script, "other-day")
        self.assertEqual(refreshed.script, "other-day")
        self.assertEqual(compose.call_count, 2)
        self.assertFalse(morning_brief_path().is_file())

        today_brief = self._brief(today, self._stamp(), "today")
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=today_brief,
        ):
            resolve_morning_brief(date_param=None, refresh=False)
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=other_brief,
        ) as compose:
            resolve_morning_brief(date_param=other, refresh=True)

        self.assertEqual(compose.call_count, 1)
        stored = load_morning_brief()
        assert stored is not None
        self.assertEqual(stored.meta.date, today)
        self.assertEqual(stored.script, "today")

    def test_memory_ttl_is_gone_and_disk_is_reread(self):
        self.assertFalse(hasattr(composer, "_CACHE"))
        self.assertFalse(hasattr(composer, "_CACHE_TTL"))
        self.assertFalse(hasattr(composer, "clear_brief_cache"))

        today = self._today()
        brief = self._brief(today, self._stamp(), "from-compose")
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=brief,
        ) as compose:
            resolve_morning_brief(date_param=None, refresh=False)
            path = morning_brief_path()
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["script"] = "edited-on-disk"
            path.write_text(json.dumps(payload), encoding="utf-8")
            reread = resolve_morning_brief(date_param=today, refresh=False)

        self.assertEqual(compose.call_count, 1)
        self.assertEqual(reread.script, "edited-on-disk")

    def test_missing_file_is_composed_once_at_or_after_four(self):
        day = "2026-10-30"
        fresh = self._brief(day, _local(2026, 10, 30, 4, 0).isoformat(timespec="seconds"), "fresh")
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=fresh,
        ) as compose:
            self.assertFalse(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 3, 59)))
            self.assertFalse(morning_brief_path().exists())
            self.assertTrue(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 4, 0)))
            self.assertFalse(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 4, 1)))

        self.assertEqual(compose.call_count, 1)
        stored = load_morning_brief()
        assert stored is not None
        self.assertEqual(stored.meta.date, day)
        self.assertEqual(stored.script, "fresh")

    def test_file_from_before_four_is_replaced_then_left_alone(self):
        day = "2026-10-30"
        save_morning_brief(
            self._brief(day, _local(2026, 10, 30, 2, 15).isoformat(timespec="seconds"), "early")
        )
        fresh = self._brief(day, _local(2026, 10, 30, 4, 0).isoformat(timespec="seconds"), "fresh")
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=fresh,
        ) as compose:
            self.assertFalse(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 3, 59)))
            self.assertEqual(self._stored_script(), "early")
            self.assertTrue(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 4, 0)))
            self.assertFalse(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 6, 0)))

        self.assertEqual(compose.call_count, 1)
        self.assertEqual(self._stored_script(), "fresh")

    def test_file_generated_at_four_is_not_composed_again(self):
        day = "2026-10-30"
        stamp = _local(2026, 10, 30, 4, 0).isoformat(timespec="seconds")
        save_morning_brief(self._brief(day, stamp, "on-time"))
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
        ) as compose:
            self.assertFalse(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 4, 0)))
            self.assertFalse(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 5, 30)))

        compose.assert_not_called()
        self.assertEqual(self._stored_script(), "on-time")

    def test_previous_day_file_waits_until_four(self):
        save_morning_brief(
            self._brief(
                "2026-10-29",
                _local(2026, 10, 29, 5, 0).isoformat(timespec="seconds"),
                "yesterday",
            )
        )
        fresh = self._brief(
            "2026-10-30",
            _local(2026, 10, 30, 4, 0).isoformat(timespec="seconds"),
            "today",
        )
        with patch(
            "server.modules.briefing.store.compose_morning_brief",
            return_value=fresh,
        ) as compose:
            self.assertFalse(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 3, 0)))
            self.assertEqual(self._stored_script(), "yesterday")
            self.assertTrue(pregenerate_morning_brief_if_due(now=_local(2026, 10, 30, 4, 0)))

        self.assertEqual(compose.call_count, 1)
        stored = load_morning_brief()
        assert stored is not None
        self.assertEqual(stored.meta.date, "2026-10-30")
        self.assertEqual(stored.script, "today")

    def test_scheduler_tick_pregenerates_and_continues_when_that_fails(self):
        db = MagicMock()
        db.list_topics.return_value = []
        with (
            patch("server.modules.briefing.store.pregenerate_morning_brief_if_due") as pre,
            patch("server.modules.news.scheduler.get_news_db", return_value=db),
        ):
            scheduler._tick()
        pre.assert_called_once_with()
        db.list_topics.assert_called_once()

        db.list_topics.reset_mock()
        with (
            patch(
                "server.modules.briefing.store.pregenerate_morning_brief_if_due",
                side_effect=RuntimeError("disk"),
            ),
            patch("server.modules.news.scheduler.get_news_db", return_value=db),
            self.assertLogs("server.modules.news.scheduler", level="ERROR"),
        ):
            scheduler._tick()
        db.list_topics.assert_called_once()

    def test_successful_digest_rebuilds_today_and_failure_does_not_fail_the_job(self):
        today = self._today()
        save_morning_brief(self._brief(today, self._stamp(4, 0), "at-four"))
        rebuilt = self._brief(today, self._stamp(5, 31), "with-news")
        db, topic = self._news_db()
        with (
            patch(
                "server.modules.news.jobs.collect_feeds",
                return_value=([_ITEM], [{"url": _ITEM.source_url, "item_count": 1, "ok": True}]),
            ),
            patch("server.modules.news.jobs.configured_providers", return_value=["mistral"]),
            patch(
                "server.modules.news.jobs.summarize_digest",
                return_value=(SummarizeResult(text="Summarized", provider="mistral"), []),
            ),
            patch(
                "server.modules.briefing.store.compose_morning_brief",
                return_value=rebuilt,
            ),
        ):
            digest = run_topic_job(topic, db=db)

        self.assertEqual(digest.status, "ok")
        self.assertEqual(digest.for_date, today)
        self.assertEqual(self._stored_script(), "with-news")

        with (
            patch(
                "server.modules.news.jobs.collect_feeds",
                return_value=([_ITEM], [{"url": _ITEM.source_url, "item_count": 1, "ok": True}]),
            ),
            patch("server.modules.news.jobs.configured_providers", return_value=["mistral"]),
            patch(
                "server.modules.news.jobs.summarize_digest",
                return_value=(SummarizeResult(text="Summarized again", provider="mistral"), []),
            ),
            patch(
                "server.modules.briefing.store.refresh_stored_morning_brief",
                side_effect=RuntimeError("rebuild failed"),
            ),
            self.assertLogs("server.modules.news.jobs", level="ERROR"),
        ):
            again = run_topic_job(topic, db=db)

        self.assertEqual(again.status, "ok")
        self.assertEqual(self._stored_script(), "with-news")
        row = db.latest_digest_for_topic(topic.id, today)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.id, again.id)

    def test_digest_for_another_date_does_not_replace_the_morning_file(self):
        today = self._today()
        save_morning_brief(self._brief(today, self._stamp(4, 0), "stay"))
        db, topic = self._news_db()
        with (
            patch(
                "server.modules.news.jobs.collect_feeds",
                return_value=([_ITEM], [{"url": _ITEM.source_url, "item_count": 1, "ok": True}]),
            ),
            patch("server.modules.news.jobs.configured_providers", return_value=["mistral"]),
            patch(
                "server.modules.news.jobs.summarize_digest",
                return_value=(SummarizeResult(text="Old day", provider="mistral"), []),
            ),
            patch("server.modules.briefing.store.compose_morning_brief") as compose,
        ):
            digest = run_topic_job(topic, db=db, force_date="2020-01-15")

        self.assertEqual(digest.status, "ok")
        self.assertEqual(digest.for_date, "2020-01-15")
        compose.assert_not_called()
        self.assertEqual(self._stored_script(), "stay")

    def test_failed_digest_does_not_rebuild_the_brief(self):
        today = self._today()
        save_morning_brief(self._brief(today, self._stamp(4, 0), "stay"))
        db, topic = self._news_db()
        with (
            patch("server.modules.news.jobs.collect_feeds", return_value=([], [])),
            patch("server.modules.briefing.store.compose_morning_brief") as compose,
        ):
            digest = run_topic_job(topic, db=db)

        self.assertEqual(digest.status, "error")
        compose.assert_not_called()
        self.assertEqual(self._stored_script(), "stay")

    def test_skipped_summarize_refreshes_todays_brief(self):
        today = self._today()
        save_morning_brief(self._brief(today, self._stamp(4, 0), "at-four"))
        rebuilt = self._brief(today, self._stamp(5, 31), "headlines")
        db, topic = self._news_db()
        with (
            patch(
                "server.modules.news.jobs.collect_feeds",
                return_value=([_ITEM], [{"url": _ITEM.source_url, "item_count": 1, "ok": True}]),
            ),
            patch("server.modules.news.jobs.configured_providers", return_value=[]),
            patch(
                "server.modules.briefing.store.compose_morning_brief",
                return_value=rebuilt,
            ) as compose,
        ):
            digest = run_topic_job(topic, db=db)

        self.assertEqual(digest.status, "skipped_summarize")
        compose.assert_called_once()
        self.assertEqual(self._stored_script(), "headlines")
