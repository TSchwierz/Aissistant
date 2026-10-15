"""Calendar business logic — ranges in Europe/Berlin (or PA_TIMEZONE)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date as Date
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from server.config import get_settings
from server.modules.calendar.db import CalendarDB, EventRow, get_calendar_db, to_iso
from server.modules.calendar.schemas import EventCreate, EventOut, EventUpdate


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def _ensure_aware(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


_REPEAT_DAYS = {"weekly": 7, "biweekly": 14}


def _master_id(event_id: str) -> str:
    return event_id.split("~", 1)[0]


def _add_wall_days(moment: datetime, days: int, tz: ZoneInfo) -> datetime:
    """Add calendar days while keeping the local wall-clock time."""
    local = moment.astimezone(tz).replace(tzinfo=None)
    return (local + timedelta(days=days)).replace(tzinfo=tz)


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
    )


def event_to_out(row: EventRow) -> EventOut:
    return _event_out(row)


def expand_series(
    row: EventRow, range_start: datetime, range_end: datetime
) -> list[EventOut]:
    step = _REPEAT_DAYS.get(row.repeat_rule or "")
    if step is None:
        return []
    tz = _tz()
    duration = (row.end - row.start) if row.end is not None else None
    cursor = row.start
    if cursor < range_start:
        days_back = (
            range_start.astimezone(tz).date() - row.start.astimezone(tz).date()
        ).days
        span = 1 if duration is None else max(1, duration.days + 1)
        jumps = max(0, (days_back - span) // step)
        if jumps:
            cursor = _add_wall_days(row.start, jumps * step, tz)
    found: list[EventOut] = []
    for _ in range(500):
        local_day = cursor.astimezone(tz).date()
        if row.repeat_until is not None and local_day > row.repeat_until:
            break
        if cursor >= range_end:
            break
        occ_end = cursor + duration if duration is not None else None
        tail = occ_end or cursor
        if tail >= range_start:
            found.append(_event_out(row, start=cursor, end=occ_end, occurrence=True))
        cursor = _add_wall_days(cursor, step, tz)
    return found


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
    elif body.repeat is not None:
        kwargs["repeat_rule"] = body.repeat
    if "repeat_until" not in kwargs:
        if body.clear_repeat_until:
            kwargs["repeat_until"] = None
        elif body.repeat_until is not None:
            kwargs["repeat_until"] = body.repeat_until

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


def startup_calendar() -> None:
    get_calendar_db().init_schema()
