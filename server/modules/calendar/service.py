"""Calendar business logic — ranges in Europe/Berlin (or PA_TIMEZONE)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date as Date
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from server.config import get_settings
from server.modules.calendar.db import CalendarDB, EventRow, get_calendar_db, to_iso
from server.modules.calendar.importers import read_upload
from server.modules.calendar.schemas import (
    EventCreate,
    EventOut,
    EventUpdate,
    ImportIssue,
    ImportResult,
)


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def _ensure_aware(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


_REPEAT_DAYS = {"weekly": 7, "biweekly": 14}


def _master_id(event_id: str) -> str:
    return event_id.split("~", 1)[0]


def _event_out(
    row: EventRow,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    occurrence: bool = False,
) -> EventOut:
    start_dt = row.start if start is None else start
    end_dt = end if occurrence else (row.end if end is None else end)
    zone = _tz()
    day = start_dt.astimezone(zone).date().isoformat()
    event_id = f"{row.id}~{day}" if occurrence and row.repeat_rule else row.id
    return EventOut(
        id=event_id,
        series_id=row.id,
        title=row.title,
        start=to_iso(start_dt),
        end=to_iso(end_dt) if end_dt else None,
        all_day=row.all_day,
        location=row.location,
        notes=row.notes,
        tags=list(row.tags),
        created_at=to_iso(row.created_at) if row.created_at else None,
        updated_at=to_iso(row.updated_at) if row.updated_at else None,
        series_start=to_iso(row.start),
        series_end=to_iso(row.end) if row.end else None,
        repeat=row.repeat_rule,
        repeat_until=row.repeat_until.isoformat() if row.repeat_until else None,
        repeat_weekdays=list(row.repeat_weekdays),
        remind_before_minutes=row.remind_before_minutes,
        ics_uid=row.ics_uid,
    )


def event_to_out(row: EventRow) -> EventOut:
    return _event_out(row)


def _on_date(moment: datetime, day: Date, tz: ZoneInfo) -> datetime:
    local = moment.astimezone(tz)
    return datetime(
        day.year, day.month, day.day, local.hour, local.minute, local.second, tzinfo=tz
    )


def _append_occurrence(
    found: list[EventOut],
    row: EventRow,
    cursor: datetime,
    duration: timedelta | None,
    range_start: datetime,
    range_end: datetime,
) -> None:
    if cursor >= range_end:
        return
    occ_end = cursor + duration if duration is not None else None
    tail = occ_end or cursor
    if tail >= range_start:
        found.append(_event_out(row, start=cursor, end=occ_end, occurrence=True))


def _expand_weekly(
    row: EventRow, range_start: datetime, range_end: datetime, tz: ZoneInfo
) -> list[EventOut]:
    step_days = _REPEAT_DAYS.get(row.repeat_rule or "")
    if step_days is None:
        return []
    week_step = 1 if row.repeat_rule == "weekly" else 2
    start_local = row.start.astimezone(tz)
    weekdays = list(row.repeat_weekdays) or [start_local.weekday()]
    anchor = start_local.date() - timedelta(days=start_local.weekday())
    duration = (row.end - row.start) if row.end is not None else None
    range_day = range_start.astimezone(tz).date()
    week_index = 0
    if range_day > anchor:
        weeks = (range_day - anchor).days // 7
        week_index = (weeks // week_step) * week_step
        if week_index >= week_step:
            week_index -= week_step
    found: list[EventOut] = []
    for _ in range(800):
        week_monday = anchor + timedelta(days=week_index * 7)
        if week_monday > range_end.astimezone(tz).date():
            break
        if row.repeat_until is not None and week_monday > row.repeat_until + timedelta(days=6):
            break
        for weekday in weekdays:
            day = week_monday + timedelta(days=weekday)
            if day < start_local.date():
                continue
            if row.repeat_until is not None and day > row.repeat_until:
                continue
            _append_occurrence(
                found, row, _on_date(row.start, day, tz), duration, range_start, range_end
            )
        week_index += week_step
    return found


def _expand_monthly(
    row: EventRow, range_start: datetime, range_end: datetime, tz: ZoneInfo
) -> list[EventOut]:
    start_local = row.start.astimezone(tz)
    weekdays = list(row.repeat_weekdays)
    duration = (row.end - row.start) if row.end is not None else None
    year, month = start_local.year, start_local.month
    range_day = range_start.astimezone(tz).date()
    start_index = start_local.year * 12 + start_local.month - 1
    range_index = range_day.year * 12 + range_day.month - 1
    jump = max(0, range_index - start_index - 1)
    if jump:
        index = start_index + jump
        year, month = index // 12, index % 12 + 1
    found: list[EventOut] = []
    for _ in range(480):
        month_start = Date(year, month, 1)
        if month_start > range_end.astimezone(tz).date():
            break
        if row.repeat_until is not None and month_start > row.repeat_until:
            break
        if weekdays:
            dates = []
            for weekday in weekdays:
                offset = (weekday - month_start.weekday()) % 7
                dates.append(month_start + timedelta(days=offset))
        else:
            last = monthrange(year, month)[1]
            dates = [Date(year, month, min(start_local.day, last))]
        for day in dates:
            if day < start_local.date():
                continue
            if row.repeat_until is not None and day > row.repeat_until:
                continue
            _append_occurrence(
                found, row, _on_date(row.start, day, tz), duration, range_start, range_end
            )
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return found


def expand_series(
    row: EventRow, range_start: datetime, range_end: datetime
) -> list[EventOut]:
    tz = _tz()
    if row.repeat_rule == "monthly":
        return _expand_monthly(row, range_start, range_end, tz)
    if row.repeat_rule in _REPEAT_DAYS:
        return _expand_weekly(row, range_start, range_end, tz)
    return []


def day_bounds(day: Date, tz: ZoneInfo | None = None) -> tuple[datetime, datetime]:
    zone = tz or _tz()
    start = datetime(day.year, day.month, day.day, tzinfo=zone)
    end = start + timedelta(days=1)
    return start, end


def month_bounds(year: int, month: int, tz: ZoneInfo | None = None) -> tuple[datetime, datetime]:
    zone = tz or _tz()
    start = datetime(year, month, 1, tzinfo=zone)
    last = monthrange(year, month)[1]
    end = datetime(year, month, last, tzinfo=zone) + timedelta(days=1)
    return start, end


def rolling_bounds(
    anchor: Date | None = None, *, days: int = 14, tz: ZoneInfo | None = None
) -> tuple[datetime, datetime]:
    """Window of ``days`` starting at local midnight of anchor (default today)."""
    zone = tz or _tz()
    if anchor is None:
        anchor = datetime.now(zone).date()
    start = datetime(anchor.year, anchor.month, anchor.day, tzinfo=zone)
    end = start + timedelta(days=max(1, days))
    return start, end


def rolling_two_week_bounds(
    anchor: Date | None = None, tz: ZoneInfo | None = None
) -> tuple[datetime, datetime]:
    """Rolling 14-day window starting at local midnight of anchor (default today)."""
    return rolling_bounds(anchor, days=14, tz=tz)


def create_event(body: EventCreate, db: CalendarDB | None = None) -> EventOut:
    db = db or get_calendar_db()
    tz = _tz()
    start = _ensure_aware(body.start, tz)
    end = _ensure_aware(body.end, tz) if body.end else None
    row = db.create_event(
        title=body.title,
        start=start,
        end=end,
        all_day=body.all_day,
        location=body.location,
        notes=body.notes,
        tags=body.tags,
        repeat_rule=body.repeat,
        repeat_until=body.repeat_until,
        repeat_weekdays=body.repeat_weekdays if body.repeat else None,
        remind_before_minutes=body.remind_before_minutes,
    )
    return event_to_out(row)


def get_event(event_id: str, db: CalendarDB | None = None) -> EventOut | None:
    db = db or get_calendar_db()
    row = db.get_event(_master_id(event_id))
    return event_to_out(row) if row else None


def update_event(
    event_id: str, body: EventUpdate, db: CalendarDB | None = None
) -> EventOut | None:
    db = db or get_calendar_db()
    event_id = _master_id(event_id)
    tz = _tz()
    kwargs: dict = {}
    if body.title is not None:
        kwargs["title"] = body.title
    if body.start is not None:
        kwargs["start"] = _ensure_aware(body.start, tz)
    if body.clear_end:
        kwargs["end"] = None
    elif body.end is not None:
        kwargs["end"] = _ensure_aware(body.end, tz)
    if body.all_day is not None:
        kwargs["all_day"] = body.all_day
    if body.clear_location:
        kwargs["location"] = None
    elif body.location is not None:
        kwargs["location"] = body.location
    if body.clear_notes:
        kwargs["notes"] = None
    elif body.notes is not None:
        kwargs["notes"] = body.notes
    if body.tags is not None:
        kwargs["tags"] = body.tags
    if body.clear_repeat:
        kwargs["repeat_rule"] = None
        kwargs["repeat_until"] = None
        kwargs["repeat_weekdays"] = []
    elif body.repeat is not None:
        kwargs["repeat_rule"] = body.repeat
    if body.repeat_weekdays is not None and "repeat_weekdays" not in kwargs:
        kwargs["repeat_weekdays"] = body.repeat_weekdays
    if "repeat_until" not in kwargs:
        if body.clear_repeat_until:
            kwargs["repeat_until"] = None
        elif body.repeat_until is not None:
            kwargs["repeat_until"] = body.repeat_until
    if body.remind_before_minutes is not None:
        kwargs["remind_before_minutes"] = body.remind_before_minutes
    elif body.clear_remind:
        kwargs["remind_before_minutes"] = None

    # Validate end >= start after merge
    existing = db.get_event(event_id)
    if existing is None:
        return None
    merged_start = kwargs.get("start", existing.start)
    merged_end = kwargs["end"] if "end" in kwargs else existing.end
    if merged_end is not None and merged_end < merged_start:
        raise ValueError("end must be >= start")
    merged_until = kwargs["repeat_until"] if "repeat_until" in kwargs else existing.repeat_until
    merged_repeat = kwargs["repeat_rule"] if "repeat_rule" in kwargs else existing.repeat_rule
    if merged_until is not None and merged_until < merged_start.astimezone(tz).date():
        raise ValueError("repeat_until must be on or after the start date")
    if merged_until is not None and not merged_repeat:
        raise ValueError("repeat_until requires repeat")

    row = db.update_event(event_id, **kwargs)
    return event_to_out(row) if row else None


def delete_event(event_id: str, db: CalendarDB | None = None) -> bool:
    db = db or get_calendar_db()
    return db.delete_event(_master_id(event_id))


def list_in_range(
    range_start: datetime,
    range_end: datetime,
    *,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    db: CalendarDB | None = None,
) -> list[EventOut]:
    db = db or get_calendar_db()
    rows = db.list_events(
        range_start=range_start,
        range_end=range_end,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
    )
    masters = db.list_recurring_masters(
        range_start=range_start,
        range_end=range_end,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
    )
    events = [event_to_out(r) for r in rows]
    for master in masters:
        events.extend(expand_series(master, range_start, range_end))
    events.sort(key=lambda event: (event.start, event.id))
    return events


def list_day(
    day: Date,
    *,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    db: CalendarDB | None = None,
) -> tuple[datetime, datetime, list[EventOut]]:
    start, end = day_bounds(day)
    return start, end, list_in_range(
        start, end, include_tags=include_tags, exclude_tags=exclude_tags, db=db
    )


def list_month(
    year: int,
    month: int,
    *,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    db: CalendarDB | None = None,
) -> tuple[datetime, datetime, list[EventOut]]:
    start, end = month_bounds(year, month)
    return start, end, list_in_range(
        start, end, include_tags=include_tags, exclude_tags=exclude_tags, db=db
    )


def list_span(
    anchor: Date | None = None,
    *,
    days: int = 14,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    db: CalendarDB | None = None,
) -> tuple[datetime, datetime, list[EventOut]]:
    start, end = rolling_bounds(anchor, days=days)
    return start, end, list_in_range(
        start, end, include_tags=include_tags, exclude_tags=exclude_tags, db=db
    )


def list_rolling_two_weeks(
    anchor: Date | None = None,
    *,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    db: CalendarDB | None = None,
) -> tuple[datetime, datetime, list[EventOut]]:
    return list_span(
        anchor,
        days=14,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        db=db,
    )


def get_today_events(*, date: str, timezone: str) -> list[dict]:
    """Brief consumer: today's events as plain dicts matching morning-brief shape."""
    day = Date.fromisoformat(date)
    zone = ZoneInfo(timezone)
    start, end = day_bounds(day, zone)
    rows = list_in_range(start, end)
    return [
        {
            "id": r.series_id or r.id,
            "title": r.title,
            "start": r.start,
            "end": r.end,
            "all_day": r.all_day,
            "tags": list(r.tags),
            "location": r.location,
            "notes": r.notes,
        }
        for r in rows
    ]


def list_tags(db: CalendarDB | None = None) -> list[str]:
    db = db or get_calendar_db()
    return db.list_all_tags()


def list_tag_colors(db: CalendarDB | None = None) -> dict[str, str]:
    db = db or get_calendar_db()
    return db.list_tag_colors()


def set_tag_color(tag: str, color: str, db: CalendarDB | None = None) -> None:
    db = db or get_calendar_db()
    db.set_tag_color(tag, color)


def import_file(filename: str, raw: bytes, db: CalendarDB | None = None) -> ImportResult:
    db = db or get_calendar_db()
    batch = read_upload(filename, raw, _tz())
    result = ImportResult(skipped=batch.skipped)
    for item in batch.events:
        if item.uid:
            existing = db.get_event_by_uid(item.uid)
        elif item.match_slot:
            existing = db.find_event_by_slot(item.title, item.start, item.end)
        else:
            existing = None
        fields = dict(
            title=item.title,
            start=item.start,
            end=item.end,
            all_day=item.all_day,
            location=item.location,
            notes=item.notes,
            tags=item.tags,
            repeat_rule=item.repeat,
            repeat_until=item.repeat_until,
            repeat_weekdays=item.repeat_weekdays,
            remind_before_minutes=item.remind_before_minutes,
            ics_uid=item.uid,
        )
        if existing is None:
            db.create_event(**fields)
            result.created += 1
        elif item.uid:
            db.update_event(existing.id, **fields)
            result.updated += 1
        else:
            db.update_event(
                existing.id,
                title=item.title,
                start=item.start,
                end=item.end,
                all_day=item.all_day,
                location=item.location,
                notes=item.notes,
                tags=item.tags,
            )
            result.updated += 1
        if item.repeat_note:
            result.repeat_dropped.append(
                ImportIssue(title=item.title, uid=item.uid, detail=item.repeat_note)
            )
        if item.alarm_note:
            result.alarm_dropped.append(
                ImportIssue(title=item.title, uid=item.uid, detail=item.alarm_note)
            )
    return result


def startup_calendar() -> None:
    get_calendar_db().init_schema()
