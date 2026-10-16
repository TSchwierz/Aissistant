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

    def test_weekly_on_several_weekdays(self):
        start = datetime(2026, 10, 12, 9, 0, tzinfo=TZ)
        self.db.create_event(
            title="Gym",
            start=start,
            end=datetime(2026, 10, 12, 10, 0, tzinfo=TZ),
            all_day=False,
            location=None,
            notes=None,
            tags=[],
            repeat_rule="weekly",
            repeat_weekdays=[0, 3],
        )
        events = list_in_range(
            datetime(2026, 10, 12, tzinfo=TZ),
            datetime(2026, 10, 26, tzinfo=TZ),
            db=self.db,
        )
        self.assertEqual(
            [event.start[:10] for event in events],
            ["2026-10-12", "2026-10-15", "2026-10-19", "2026-10-22"],
        )

    def test_biweekly_skips_the_off_week(self):
        start = datetime(2026, 10, 14, 9, 0, tzinfo=TZ)
        self.db.create_event(
            title="Class",
            start=start,
            end=datetime(2026, 10, 14, 10, 0, tzinfo=TZ),
            all_day=False,
            location=None,
            notes=None,
            tags=[],
            repeat_rule="biweekly",
            repeat_weekdays=[0, 3],
        )
        events = list_in_range(
            datetime(2026, 10, 1, tzinfo=TZ),
            datetime(2026, 11, 15, tzinfo=TZ),
            db=self.db,
        )
        self.assertEqual(
            [event.start[:10] for event in events],
            ["2026-10-15", "2026-10-26", "2026-10-29", "2026-11-09", "2026-11-12"],
        )

    def test_monthly_first_weekdays(self):
        start = datetime(2026, 10, 1, 9, 0, tzinfo=TZ)
        self.db.create_event(
            title="Review",
            start=start,
            end=datetime(2026, 10, 1, 10, 0, tzinfo=TZ),
            all_day=False,
            location=None,
            notes=None,
            tags=["work"],
            repeat_rule="monthly",
            repeat_weekdays=[0, 3],
        )
        events = list_in_range(
            datetime(2026, 10, 1, tzinfo=TZ),
            datetime(2026, 12, 1, tzinfo=TZ),
            db=self.db,
        )
        self.assertEqual(
            [event.start[:10] for event in events],
            ["2026-10-01", "2026-10-05", "2026-11-02", "2026-11-05"],
        )
        self.assertEqual(events[0].repeat, "monthly")
        self.assertEqual(events[0].repeat_weekdays, [0, 3])

    def test_monthly_same_day_clamps_short_months(self):
        start = datetime(2026, 10, 31, 18, 0, tzinfo=TZ)
        self.db.create_event(
            title="Rent",
            start=start,
            end=None,
            all_day=False,
            location=None,
            notes=None,
            tags=[],
            repeat_rule="monthly",
        )
        events = list_in_range(
            datetime(2026, 10, 1, tzinfo=TZ),
            datetime(2027, 4, 1, tzinfo=TZ),
            db=self.db,
        )
        self.assertEqual(
            [event.start[:10] for event in events],
            ["2026-10-31", "2026-11-30", "2026-12-31", "2027-01-31", "2027-02-28", "2027-03-31"],
        )
