"""Calendar file import and reminder bounds."""

import io
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from server.modules.calendar.db import CalendarDB
from server.modules.calendar.importers import parse_ics_text
from server.modules.calendar.schemas import EventCreate, EventUpdate
from server.modules.calendar.service import create_event, import_file, list_in_range, update_event

TZ = ZoneInfo("Europe/Berlin")
START = datetime(2026, 10, 12, 9, 0, tzinfo=TZ)


def _ics(body: str) -> str:
    return "BEGIN:VCALENDAR\nVERSION:2.0\n" + body + "END:VCALENDAR\n"


class ImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.db = CalendarDB(Path(self._dir.name) / "calendar.db")
        self.db.init_schema()

    def tearDown(self) -> None:
        self._dir.cleanup()

    def _import(self, name: str, text: str):
        return import_file(name, text.encode("utf-8"), db=self.db)

    def _between(self, start: datetime, end: datetime):
        return list_in_range(start, end, db=self.db)

    def test_ics_weekly_is_kept(self):
        text = _ics(
            """BEGIN:VEVENT
UID:weekly-standup@test
SUMMARY:Standup
DTSTART;TZID=Europe/Berlin:20261012T090000
DTEND;TZID=Europe/Berlin:20261012T100000
RRULE:FREQ=WEEKLY;WKST=MO;UNTIL=20261019T235959Z;BYDAY=MO
CATEGORIES:work
END:VEVENT
"""
        )
        result = self._import("work.ics", text)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.repeat_dropped, [])
        events = self._between(datetime(2026, 10, 1, tzinfo=TZ), datetime(2026, 11, 1, tzinfo=TZ))
        self.assertEqual([event.start[:10] for event in events], ["2026-10-12", "2026-10-19"])
        self.assertEqual(events[0].repeat, "weekly")
        self.assertEqual(events[0].repeat_until, "2026-10-19")
        self.assertEqual(events[0].repeat_weekdays, [0])
        self.assertEqual(events[0].tags, ["work"])
        self.assertEqual(events[0].ics_uid, "weekly-standup@test")

    def test_ics_biweekly_and_monthly_are_kept(self):
        text = _ics(
            """BEGIN:VEVENT
UID:class@test
SUMMARY:Class
DTSTART;TZID=Europe/Berlin:20261014T090000
DTEND;TZID=Europe/Berlin:20261014T100000
RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH
END:VEVENT
BEGIN:VEVENT
UID:rent@test
SUMMARY:Rent
DTSTART;TZID=Europe/Berlin:20261031T180000
RRULE:FREQ=MONTHLY
END:VEVENT
"""
        )
        result = self._import("rules.ics", text)
        self.assertEqual(result.repeat_dropped, [])
        classes = [
            event.start[:10]
            for event in self._between(datetime(2026, 10, 1, tzinfo=TZ), datetime(2026, 11, 15, tzinfo=TZ))
            if event.title == "Class"
        ]
        self.assertEqual(classes, ["2026-10-15", "2026-10-26", "2026-10-29", "2026-11-09", "2026-11-12"])
        rent = [
            event.start[:10]
            for event in self._between(datetime(2026, 10, 1, tzinfo=TZ), datetime(2027, 4, 1, tzinfo=TZ))
            if event.title == "Rent"
        ]
        self.assertEqual(
            rent,
            ["2026-10-31", "2026-11-30", "2026-12-31", "2027-01-31", "2027-02-28", "2027-03-31"],
        )

    def test_count_and_exdate_drop_the_repeat(self):
        text = _ics(
            """BEGIN:VEVENT
UID:counted@test
SUMMARY:Counted
DTSTART;TZID=Europe/Berlin:20261012T090000
DTEND;TZID=Europe/Berlin:20261012T100000
RRULE:FREQ=WEEKLY;COUNT=5
END:VEVENT
BEGIN:VEVENT
UID:excepted@test
SUMMARY:Excepted
DTSTART;TZID=Europe/Berlin:20261013T090000
DTEND;TZID=Europe/Berlin:20261013T100000
RRULE:FREQ=WEEKLY
EXDATE;TZID=Europe/Berlin:20261020T090000
END:VEVENT
"""
        )
        result = self._import("exceptions.ics", text)
        self.assertEqual(sorted(issue.title for issue in result.repeat_dropped), ["Counted", "Excepted"])
        events = self._between(datetime(2026, 10, 1, tzinfo=TZ), datetime(2026, 12, 1, tzinfo=TZ))
        self.assertEqual(len(events), 2)
        self.assertTrue(all(event.repeat is None for event in events))

    def test_ics_daily_becomes_one_event(self):
        text = _ics(
            """BEGIN:VEVENT
UID:daily@test
SUMMARY:Stretch
DTSTART;TZID=Europe/Berlin:20261012T090000
DTEND;TZID=Europe/Berlin:20261012T091500
RRULE:FREQ=DAILY
END:VEVENT
"""
        )
        result = self._import("daily.ics", text)
        events = self._between(datetime(2026, 10, 1, tzinfo=TZ), datetime(2026, 11, 1, tzinfo=TZ))
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0].repeat)
        self.assertEqual(result.repeat_dropped[0].title, "Stretch")
        self.assertEqual(result.repeat_dropped[0].detail, "repeat not kept")

    def test_uid_upsert(self):
        first = _ics(
            """BEGIN:VEVENT
UID:same-uid@test
SUMMARY:First
DTSTART;TZID=Europe/Berlin:20261012T090000
DTEND;TZID=Europe/Berlin:20261012T100000
END:VEVENT
"""
        )
        second = first.replace("SUMMARY:First", "SUMMARY:Second")
        created = self._import("one.ics", first)
        updated = self._import("one.ics", second)
        events = self._between(datetime(2026, 10, 12, tzinfo=TZ), datetime(2026, 10, 13, tzinfo=TZ))
        self.assertEqual(created.created, 1)
        self.assertEqual(updated.updated, 1)
        self.assertEqual(updated.created, 0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Second")
        self.assertEqual(events[0].ics_uid, "same-uid@test")

    def test_zip_of_ics(self):
        text = _ics(
            """BEGIN:VEVENT
UID:zipped@test
SUMMARY:Packed
DTSTART;TZID=Europe/Berlin:20261013T110000
DTEND;TZID=Europe/Berlin:20261013T120000
END:VEVENT
"""
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("Takeout/Calendar/packed.ics", text)
        result = import_file("calendars.zip", buf.getvalue(), db=self.db)
        events = self._between(datetime(2026, 10, 13, tzinfo=TZ), datetime(2026, 10, 14, tzinfo=TZ))
        self.assertEqual(result.created, 1)
        self.assertEqual(events[0].title, "Packed")

    def test_csv_title_start_end_upsert(self):
        header = "Subject,Start Date,Start Time,End Date,End Time,All day event,Description,Location,Categories"
        first = (
            f"{header}\n"
            "Standup,10/12/2026,9:00:00 AM,10/12/2026,10:00:00 AM,False,Notes,Room,work\n"
        )
        second = (
            f"{header}\n"
            "Standup,10/12/2026,9:00:00 AM,10/12/2026,10:00:00 AM,False,Moved,Hall,work\n"
        )
        created = self._import("outlook.csv", first)
        updated = self._import("outlook.csv", second)
        events = self._between(datetime(2026, 10, 12, tzinfo=TZ), datetime(2026, 10, 13, tzinfo=TZ))
        self.assertEqual(created.created, 1)
        self.assertEqual(updated.updated, 1)
        self.assertEqual(updated.created, 0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Standup")
        self.assertEqual(events[0].location, "Hall")
        self.assertEqual(events[0].notes, "Moved")
        self.assertIsNone(events[0].ics_uid)

    def test_empty_title_skipped(self):
        text = (
            "Subject,Start Date,Start Time,End Date,End Time\n"
            ",10/12/2026,9:00:00 AM,10/12/2026,10:00:00 AM\n"
            "Keep,10/13/2026,9:00:00 AM,10/13/2026,10:00:00 AM\n"
        )
        result = self._import("outlook.csv", text)
        events = self._between(datetime(2026, 10, 1, tzinfo=TZ), datetime(2026, 11, 1, tzinfo=TZ))
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.created, 1)
        self.assertEqual([event.title for event in events], ["Keep"])

    def test_valarm_negative_duration(self):
        text = _ics(
            """BEGIN:VEVENT
UID:remind-min@test
SUMMARY:Soon
DTSTART;TZID=Europe/Berlin:20261012T090000
DTEND;TZID=Europe/Berlin:20261012T100000
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT15M
END:VALARM
END:VEVENT
BEGIN:VEVENT
UID:remind-hour@test
SUMMARY:Later
DTSTART;TZID=Europe/Berlin:20261012T130000
DTEND;TZID=Europe/Berlin:20261012T140000
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT2H
END:VALARM
END:VEVENT
"""
        )
        result = self._import("reminders.ics", text)
        events = self._between(datetime(2026, 10, 12, tzinfo=TZ), datetime(2026, 10, 13, tzinfo=TZ))
        by_title = {event.title: event for event in events}
        self.assertEqual(result.alarm_dropped, [])
        self.assertEqual(by_title["Soon"].remind_before_minutes, 15)
        self.assertEqual(by_title["Later"].remind_before_minutes, 120)

    def test_email_alarm_reported(self):
        text = _ics(
            """BEGIN:VEVENT
UID:email-alarm@test
SUMMARY:Mail me
DTSTART;TZID=Europe/Berlin:20261012T090000
DTEND;TZID=Europe/Berlin:20261012T100000
BEGIN:VALARM
ACTION:EMAIL
TRIGGER:-PT15M
DESCRIPTION:Reminder
END:VALARM
END:VEVENT
"""
        )
        result = self._import("email.ics", text)
        events = self._between(datetime(2026, 10, 12, tzinfo=TZ), datetime(2026, 10, 13, tzinfo=TZ))
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0].remind_before_minutes)
        self.assertEqual(result.alarm_dropped[0].title, "Mail me")
        self.assertIn("email", result.alarm_dropped[0].detail)

    def test_absolute_alarm_reported(self):
        text = _ics(
            """BEGIN:VEVENT
UID:absolute-alarm@test
SUMMARY:Fixed
DTSTART;TZID=Europe/Berlin:20261012T090000
DTEND;TZID=Europe/Berlin:20261012T100000
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER;VALUE=DATE-TIME:20261012T080000Z
END:VALARM
END:VEVENT
"""
        )
        result = self._import("absolute.ics", text)
        events = self._between(datetime(2026, 10, 12, tzinfo=TZ), datetime(2026, 10, 13, tzinfo=TZ))
        self.assertIsNone(events[0].remind_before_minutes)
        self.assertIn("absolute", result.alarm_dropped[0].detail)

    def test_all_day_date_is_not_shifted(self):
        text = _ics(
            """BEGIN:VEVENT
UID:holiday@test
SUMMARY:Holiday
DTSTART;VALUE=DATE:20261015
DTEND;VALUE=DATE:20261016
END:VEVENT
"""
        )
        parsed = parse_ics_text(text, ZoneInfo("America/Los_Angeles"))
        self.assertEqual(parsed.events[0].start.date().isoformat(), "2026-10-15")
        self.assertEqual(parsed.events[0].start.hour, 0)
        self.assertTrue(parsed.events[0].all_day)
        self.assertIsNone(parsed.events[0].end)
        result = self._import("holiday.ics", text)
        events = self._between(datetime(2026, 10, 15, tzinfo=TZ), datetime(2026, 10, 16, tzinfo=TZ))
        self.assertEqual(result.created, 1)
        self.assertTrue(events[0].start.startswith("2026-10-15"))
        self.assertTrue(events[0].all_day)

    def test_timed_utc_instant_is_kept(self):
        text = _ics(
            """BEGIN:VEVENT
UID:utc@test
SUMMARY:Call
DTSTART:20261015T150000Z
DTEND:20261015T160000Z
END:VEVENT
"""
        )
        self._import("utc.ics", text)
        events = self._between(datetime(2026, 10, 15, tzinfo=TZ), datetime(2026, 10, 16, tzinfo=TZ))
        got = datetime.fromisoformat(events[0].start)
        self.assertEqual(
            got.astimezone(timezone.utc),
            datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc),
        )


class RemindTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.db = CalendarDB(Path(self._dir.name) / "calendar.db")
        self.db.init_schema()

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_remind_before_minutes_bounds(self):
        self.assertIsNone(EventCreate(title="A", start=START, remind_before_minutes=None).remind_before_minutes)
        self.assertEqual(EventCreate(title="A", start=START, remind_before_minutes=1).remind_before_minutes, 1)
        self.assertEqual(
            EventCreate(title="A", start=START, remind_before_minutes=10080).remind_before_minutes,
            10080,
        )
        self.assertIsNone(EventUpdate(remind_before_minutes=None).remind_before_minutes)
        for bad in (0, 10081, -5):
            with self.assertRaises(ValidationError):
                EventCreate(title="A", start=START, remind_before_minutes=bad)
            with self.assertRaises(ValidationError):
                EventUpdate(remind_before_minutes=bad)

    def test_remind_round_trip_and_clear(self):
        created = create_event(
            EventCreate(title="Meet", start=START, remind_before_minutes=30),
            db=self.db,
        )
        self.assertEqual(created.remind_before_minutes, 30)
        untouched = self.db.create_event(
            title="Plain",
            start=START,
            end=None,
            all_day=False,
            location=None,
            notes=None,
            tags=[],
        )
        self.assertIsNone(untouched.remind_before_minutes)
        changed = update_event(created.id, EventUpdate(remind_before_minutes=45), db=self.db)
        assert changed is not None
        self.assertEqual(changed.remind_before_minutes, 45)
        cleared = update_event(created.id, EventUpdate(clear_remind=True), db=self.db)
        assert cleared is not None
        self.assertIsNone(cleared.remind_before_minutes)
