"""Compose an English radio-style morning brief.

Today's brief is stored on disk by ``server.modules.briefing.store``. This
module only builds a fresh response. It does not cache one in memory.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

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


def _weekday_name(d: date) -> str:
    return d.strftime("%A")


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
    loc = ev.get("location")
    if loc:
        return f"{when}, {title}, at {loc}"
    return f"{when}, {title}"


def _weather_spoken(weather_raw: dict) -> str:
    parts: list[str] = []
    summary = (weather_raw.get("summary") or "").strip()
    if summary:
        parts.append(summary.rstrip("."))
    hint = weather_raw.get("clothing_hint") or {}
    notes = (hint.get("notes") or "").strip()
    if notes:
        parts.append(notes.rstrip("."))
    else:
        bits: list[str] = []
        if hint.get("rain_jacket"):
            bits.append("a rain jacket")
        if hint.get("hoody"):
            bits.append("a hoody")
        if bits:
            if len(bits) == 1:
                parts.append(f"Consider bringing {bits[0]}")
            else:
                parts.append(f"Consider bringing {' and '.join(bits)}")
    return ". ".join(parts) + "." if parts else "Weather is available for today."


def _calendar_spoken(events: list[dict], tz: ZoneInfo) -> str:
    lines = [_format_event_line(e, tz) for e in events]
    if not lines:
        return ""
    if len(lines) == 1:
        return f"On your calendar: {lines[0]}."
    body = ", ".join(lines[:-1]) + f", and {lines[-1]}"
    return f"On your calendar today: {body}."


def _news_spoken(news_raw: list[dict]) -> str:
    chunks: list[str] = []
    for n in news_raw:
        label = n.get("topic_label") or n.get("topic_id") or "News"
        digest = (n.get("digest") or "").strip()
        if not digest:
            continue
        # Keep TTS manageable
        if len(digest) > 500:
            digest = digest[:497].rstrip() + "…"
        chunks.append(f"In {label}: {digest}")
    if not chunks:
        return ""
    return " ".join(chunks)


def compose_morning_brief(
    *,
    date_param: str | None = None,
) -> MorningBriefResponse:
    """Build a fresh brief. Callers decide whether to read or write the disk file."""
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    brief_date = (
        date.fromisoformat(date_param) if date_param else datetime.now(tz).date()
    )
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
    spoken_parts: list[str] = []

    month_day = f"{brief_date.strftime('%B')} {brief_date.day}"
    greeting = (
        f"Good morning. Here's your brief for {_weekday_name(brief_date)}, "
        f"{month_day}."
    )

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
        weather_body = _weather_spoken(weather_raw)
        ui_sections.append(
            BriefSection(id="weather", title="Weather", body=weather_body)
        )
        spoken_parts.append(weather_body)

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
        calendar_section = CalendarSection(
            events=events,
            first_event_start=events[0].start if events else None,
        )
        sections_present.append("calendar")
        freshness.calendar = now.isoformat(timespec="seconds")
        cal_body = _calendar_spoken(calendar_raw, tz)
        ui_sections.append(BriefSection(id="calendar", title="Today", body=cal_body))
        spoken_parts.append(cal_body)

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
        gens = [n.get("generated_at") for n in news_raw if n.get("generated_at")]
        freshness.news = max(gens) if gens else now.isoformat(timespec="seconds")
        news_body = _news_spoken(news_raw)
        ui_sections.append(BriefSection(id="news", title="News", body=news_body))
        spoken_parts.append(news_body)

    if spoken_parts:
        script = f"{greeting} " + " ".join(spoken_parts)
        if not script.endswith("."):
            script += "."
        script += " That's your brief. Have a good day."
        empty_reason = None
    else:
        script = (
            f"{greeting} I don't have weather, calendar, or news for you yet. "
            "Check back after your sources update."
        )
        empty_reason = "no_data"

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
    return response
