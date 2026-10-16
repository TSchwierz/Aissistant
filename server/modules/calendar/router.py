"""Personal calendar HTTP API — Pi SSOT, no M365."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query

from server.config import get_settings
from server.modules.calendar import service
from server.modules.calendar.db import to_iso
from server.modules.calendar.schemas import (
    EventCreate,
    EventListOut,
    EventOut,
    EventUpdate,
    TagColorIn,
    TagListOut,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _split_csv(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    out: list[str] = []
    for raw in values:
        for part in str(raw).split(","):
            tag = part.strip()
            if tag:
                out.append(tag)
    return out or None


def _list_payload(
    start: datetime, end: datetime, events: list[EventOut]
) -> EventListOut:
    settings = get_settings()
    return EventListOut(
        count=len(events),
        timezone=settings.timezone,
        range_start=to_iso(start),
        range_end=to_iso(end),
        events=events,
    )


@router.post("/events", response_model=EventOut, status_code=201)
def create_event(body: EventCreate) -> EventOut:
    return service.create_event(body)


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: str) -> EventOut:
    event = service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put("/events/{event_id}", response_model=EventOut)
def update_event(event_id: str, body: EventUpdate) -> EventOut:
    try:
        event = service.update_event(event_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.delete("/events/{event_id}")
def delete_event(event_id: str) -> dict:
    if not service.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": True, "id": event_id}


@router.get("/events", response_model=EventListOut)
def list_events(
    day: str | None = Query(
        default=None, description="YYYY-MM-DD — events overlapping that local day"
    ),
    month: str | None = Query(
        default=None, description="YYYY-MM — events overlapping that local month"
    ),
    window: str | None = Query(
        default=None,
        description="Use '2weeks' for a rolling 14-day window from today (or from=)",
    ),
    from_: str | None = Query(
        default=None,
        alias="from",
        description="Range start ISO date or datetime (local/offset)",
    ),
    to: str | None = Query(
        default=None, description="Range end ISO date or datetime (exclusive if date)"
    ),
    tag: list[str] | None = Query(
        default=None, description="Include events with any of these tags (repeatable)"
    ),
    exclude_tag: list[str] | None = Query(
        default=None, description="Exclude events with any of these tags (repeatable)"
    ),
) -> EventListOut:
    include = _split_csv(tag)
    exclude = _split_csv(exclude_tag)

    # Precedence: day > month > window=2weeks > custom from/to > default 2-week
    if day:
        try:
            d = date.fromisoformat(day)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD") from exc
        start, end, events = service.list_day(
            d, include_tags=include, exclude_tags=exclude
        )
        return _list_payload(start, end, events)

    if month:
        try:
            year_s, month_s = month.split("-", 1)
            y, m = int(year_s), int(month_s)
            if not (1 <= m <= 12):
                raise ValueError
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="month must be YYYY-MM") from exc
        start, end, events = service.list_month(
            y, m, include_tags=include, exclude_tags=exclude
        )
        return _list_payload(start, end, events)

    if window == "2weeks":
        anchor = None
        if from_:
            try:
                anchor = date.fromisoformat(from_[:10])
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="from must be YYYY-MM-DD for window=2weeks"
                ) from exc
        start, end, events = service.list_rolling_two_weeks(
            anchor, include_tags=include, exclude_tags=exclude
        )
        return _list_payload(start, end, events)

    if from_ or to:
        tz = service._tz()
        if not from_ or not to:
            raise HTTPException(
                status_code=400, detail="both from and to are required for a custom range"
            )
        try:
            start = _parse_bound(from_, tz, end_of_day=False)
            end = _parse_bound(to, tz, end_of_day=True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if end <= start:
            raise HTTPException(status_code=400, detail="to must be after from")
        events = service.list_in_range(
            start, end, include_tags=include, exclude_tags=exclude
        )
        return _list_payload(start, end, events)

    # Default: rolling 2-week from today
    start, end, events = service.list_rolling_two_weeks(
        include_tags=include, exclude_tags=exclude
    )
    return _list_payload(start, end, events)


def _parse_bound(value: str, tz, *, end_of_day: bool) -> datetime:
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        d = date.fromisoformat(text)
        start = datetime(d.year, d.month, d.day, tzinfo=tz)
        if end_of_day:
            from datetime import timedelta

            return start + timedelta(days=1)
        return start
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


@router.get("/day/{day}", response_model=EventListOut)
def get_day(
    day: str,
    tag: list[str] | None = Query(default=None),
    exclude_tag: list[str] | None = Query(default=None),
) -> EventListOut:
    try:
        d = date.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD") from exc
    start, end, events = service.list_day(
        d, include_tags=_split_csv(tag), exclude_tags=_split_csv(exclude_tag)
    )
    return _list_payload(start, end, events)


@router.get("/month/{month}", response_model=EventListOut)
def get_month(
    month: str,
    tag: list[str] | None = Query(default=None),
    exclude_tag: list[str] | None = Query(default=None),
) -> EventListOut:
    try:
        year_s, month_s = month.split("-", 1)
        y, m = int(year_s), int(month_s)
        if not (1 <= m <= 12):
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM") from exc
    start, end, events = service.list_month(
        y, m, include_tags=_split_csv(tag), exclude_tags=_split_csv(exclude_tag)
    )
    return _list_payload(start, end, events)


@router.get("/weeks", response_model=EventListOut)
def get_rolling_weeks(
    from_: str | None = Query(default=None, alias="from"),
    days: int = Query(default=14, ge=1, le=31),
    tag: list[str] | None = Query(default=None),
    exclude_tag: list[str] | None = Query(default=None),
) -> EventListOut:
    """Window of ``days`` (default 14) from today or from=YYYY-MM-DD."""
    anchor = None
    if from_:
        try:
            anchor = date.fromisoformat(from_)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="from must be YYYY-MM-DD") from exc
    start, end, events = service.list_span(
        anchor,
        days=days,
        include_tags=_split_csv(tag),
        exclude_tags=_split_csv(exclude_tag),
    )
    return _list_payload(start, end, events)


@router.get("/tags", response_model=TagListOut)
def get_tags() -> TagListOut:
    return TagListOut(tags=service.list_tags(), colors=service.list_tag_colors())


@router.put("/tags", response_model=TagListOut)
def put_tag_color(body: TagColorIn) -> TagListOut:
    service.set_tag_color(body.tag, body.color)
    return TagListOut(tags=service.list_tags(), colors=service.list_tag_colors())
