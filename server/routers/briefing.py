"""Morning brief endpoints — weather + calendar when available; news still stub."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from server.config import get_settings
from server.models.briefing import (
    BriefFreshness,
    BriefMeta,
    BriefSection,
    CalendarEvent,
    CalendarSection,
    ClothingHint,
    MorningBriefResponse,
    NewsSection,
    NewsTopicDigest,
    WeatherSection,
)
from server.modules import calendar as calendar_mod
from server.modules import news as news_mod
from server.modules import weather as weather_mod

router = APIRouter(prefix="/briefing", tags=["briefing"])


def _resolve_date(date_str: str | None, tz: ZoneInfo) -> date:
    if date_str:
        return date.fromisoformat(date_str)
    return datetime.now(tz).date()


def _format_event_line(ev: dict, tz: ZoneInfo) -> str:
    title = ev.get("title") or "Event"
    if ev.get("all_day"):
        when = "all day"
    else:
        try:
            start = datetime.fromisoformat(ev["start"])
            when = start.astimezone(tz).strftime("%H:%M")
        except Exception:  # noqa: BLE001
            when = ev.get("start") or ""
    return f"{when} {title}".strip()


@router.get("/morning")
def get_morning_brief(
    date_param: str | None = Query(
        default=None,
        alias="date",
        description="Calendar day YYYY-MM-DD in the Pi timezone. Omit for today.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
) -> JSONResponse:
    """Compose morning brief. Missing sections are omitted, not fatal."""
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    brief_date = _resolve_date(date_param, tz)
    date_iso = brief_date.isoformat()
    now = datetime.now(tz)

    weather_raw = weather_mod.get_day_overview(
        date=date_iso, timezone=settings.timezone
    )
    calendar_raw = calendar_mod.get_today_events(
        date=date_iso, timezone=settings.timezone
    )
    news_raw = news_mod.get_topic_digests(date=date_iso)

    sections_present: list[str] = []
    weather_section: WeatherSection | None = None
    calendar_section: CalendarSection | None = None
    news_section: NewsSection | None = None
    ui_sections: list[BriefSection] = []
    freshness = BriefFreshness()
    script_parts: list[str] = []

    if weather_raw:
        hint_raw = weather_raw.get("clothing_hint") or {}
        weather_section = WeatherSection(
            summary=weather_raw.get("summary"),
            high_c=weather_raw.get("high_c"),
            low_c=weather_raw.get("low_c"),
            precip_chance_pct=weather_raw.get("precip_chance_pct"),
            conditions=weather_raw.get("conditions"),
            clothing_hint=ClothingHint(
                rain_jacket=hint_raw.get("rain_jacket"),
                hoody=hint_raw.get("hoody"),
                notes=hint_raw.get("notes"),
            ),
        )
        sections_present.append("weather")
        freshness.weather = weather_raw.get("freshness")
        body = weather_raw.get("summary") or "Weather update available."
        ui_sections.append(BriefSection(id="weather", title="Weather", body=body))
        script_parts.append(f"Weather: {body}")

    if calendar_raw:
        events = [
            CalendarEvent(
                id=e["id"],
                title=e["title"],
                start=e["start"],
                end=e.get("end"),
                all_day=bool(e.get("all_day")),
                tags=list(e.get("tags") or []),
                location=e.get("location"),
                notes=e.get("notes"),
            )
            for e in calendar_raw
        ]
        first_start = events[0].start if events else None
        calendar_section = CalendarSection(
            events=events, first_event_start=first_start
        )
        sections_present.append("calendar")
        freshness.calendar = now.isoformat(timespec="seconds")
        lines = [_format_event_line(e, tz) for e in calendar_raw]
        body = "; ".join(lines)
        ui_sections.append(BriefSection(id="calendar", title="Today", body=body))
        if len(lines) == 1:
            script_parts.append(f"Today: {lines[0]}.")
        else:
            script_parts.append(
                "Today you have "
                + ", ".join(lines[:-1])
                + f", and {lines[-1]}."
            )

    if news_raw:
        by_topic = [
            NewsTopicDigest(
                topic_id=n["topic_id"],
                topic_label=n["topic_label"],
                digest=n["digest"],
                item_count=int(n.get("item_count") or 0),
                generated_at=n.get("generated_at"),
                ai_provider=n.get("ai_provider"),
            )
            for n in news_raw
        ]
        news_section = NewsSection(by_topic=by_topic)
        sections_present.append("news")
        # Freshest digest timestamp among topics
        gens = [n.get("generated_at") for n in news_raw if n.get("generated_at")]
        freshness.news = max(gens) if gens else now.isoformat(timespec="seconds")
        news_bits = [
            f"{n['topic_label']}: {n['digest'][:280]}"
            for n in news_raw
            if n.get("digest")
        ]
        body = " | ".join(news_bits)
        ui_sections.append(BriefSection(id="news", title="News", body=body))
        for n in news_raw:
            script_parts.append(
                f"News — {n['topic_label']}: {n['digest']}"
            )

    script = " ".join(script_parts)
    empty_reason = None if sections_present or script else "no_data"

    response = MorningBriefResponse(
        meta=BriefMeta(
            date=date_iso,
            timezone=settings.timezone,
            generated_at=now.isoformat(timespec="seconds"),
            language=settings.language,
            freshness=freshness,
            sections_present=sections_present,
            empty_reason=empty_reason,
        ),
        weather=weather_section,
        calendar=calendar_section,
        news=news_section,
        script=script,
        sections=ui_sections,
    )
    return JSONResponse(content=response.model_dump_response())
