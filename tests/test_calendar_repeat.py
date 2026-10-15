"""Recurring calendar events expand inside a requested window."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from server.modules.calendar.db import CalendarDB
from server.modules.calendar.service import list_in_range

TZ = ZoneInfo("Europe/Berlin")


class RepeatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.db = CalendarDB(Path(self._dir.name) / "calendar.db")
        self.db.init_schema()

    def tearDown(self) -> None:
        self._dir.cleanup()

    def _weekly(self, *, until=None):
        start = datetime(2026, 10, 12, 9, 0, tzinfo=TZ)
        end = datetime(2026, 10, 12, 10, 0, tzinfo=TZ)
        return self.db.create_event(
            title="Standup",
            start=start,
            end=end,
            all_day=False,
            location=None,
            notes=None,
            tags=["work"],
            repeat_rule="weekly",
            repeat_until=until,
        )

    def test_weekly_occurrences_inside_window(self):
        self._weekly()
        events = list_in_range(
            datetime(2026, 10, 12, tzinfo=TZ),
            datetime(2026, 10, 26, tzinfo=TZ),
            db=self.db,
        )
        self.assertEqual([event.start[:10] for event in events], ["2026-10-12", "2026-10-19"])
        self.assertTrue(all(event.series_id == events[0].series_id for event in events))
        self.assertNotEqual(events[0].id, events[1].id)

    def test_repeat_until_is_inclusive(self):
        from datetime import date

        self._weekly(until=date(2026, 10, 12))
        events = list_in_range(
            datetime(2026, 10, 1, tzinfo=TZ),
            datetime(2026, 11, 1, tzinfo=TZ),
            db=self.db,
        )
        self.assertEqual([event.start[:10] for event in events], ["2026-10-12"])

    def test_single_event_is_unchanged(self):
        start = datetime(2026, 10, 15, 18, 30, tzinfo=TZ)
        self.db.create_event(
            title="Bijles",
            start=start,
            end=None,
            all_day=False,
            location="Online",
            notes=None,
            tags=[],
        )
        events = list_in_range(
            datetime(2026, 10, 1, tzinfo=TZ),
            datetime(2026, 11, 1, tzinfo=TZ),
            db=self.db,
        )
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0].repeat)
        self.assertEqual(events[0].id, events[0].series_id)
