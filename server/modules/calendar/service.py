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


def event_to_out(row: EventRow) -> EventOut:
    return EventOut(
        id=row.id,
        title=row.title,
        start=to_iso(row.start),
        end=to_iso(row.end) if row.end else None,
        all_day=row.all_day,
        location=row.location,
        notes=row.notes,
        tags=list(row.tags),
        created_at=to_iso(row.created_at) if row.created_at else None,
        updated_at=to_iso(row.updated_at) if row.updated_at else None,
    )


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


def rolling_two_week_bounds(
    anchor: Date | None = None, tz: ZoneInfo | None = None
) -> tuple[datetime, datetime]:
    """Rolling 14-day window starting at local midnight of anchor (default today)."""
    zone = tz or _tz()
    if anchor is None:
        anchor = datetime.now(zone).date()
    start = datetime(anchor.year, anchor.month, anchor.day, tzinfo=zone)
    end = start + timedelta(days=14)
    return start, end


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
    )
    return event_to_out(row)


def get_event(event_id: str, db: CalendarDB | None = None) -> EventOut | None:
    db = db or get_calendar_db()
    row = db.get_event(event_id)
    return event_to_out(row) if row else None


def update_event(
    event_id: str, body: EventUpdate, db: CalendarDB | None = None
) -> EventOut | None:
    db = db or get_calendar_db()
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

    # Validate end >= start after merge
    existing = db.get_event(event_id)
    if existing is None:
        return None
    merged_start = kwargs.get("start", existing.start)
    merged_end = kwargs["end"] if "end" in kwargs else existing.end
    if merged_end is not None and merged_end < merged_start:
        raise ValueError("end must be >= start")

    row = db.update_event(event_id, **kwargs)
    return event_to_out(row) if row else None


def delete_event(event_id: str, db: CalendarDB | None = None) -> bool:
    db = db or get_calendar_db()
    return db.delete_event(event_id)


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
    return [event_to_out(r) for r in rows]


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


def list_rolling_two_weeks(
    anchor: Date | None = None,
    *,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    db: CalendarDB | None = None,
) -> tuple[datetime, datetime, list[EventOut]]:
    start, end = rolling_two_week_bounds(anchor)
    return start, end, list_in_range(
        start, end, include_tags=include_tags, exclude_tags=exclude_tags, db=db
    )


def get_today_events(*, date: str, timezone: str) -> list[dict]:
    """Brief consumer: today's events as plain dicts matching morning-brief shape."""
    day = Date.fromisoformat(date)
    zone = ZoneInfo(timezone)
    start, end = day_bounds(day, zone)
    db = get_calendar_db()
    rows = db.list_events(range_start=start, range_end=end)
    return [
        {
            "id": r.id,
            "title": r.title,
            "start": to_iso(r.start.astimezone(zone)),
            "end": to_iso(r.end.astimezone(zone)) if r.end else None,
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
