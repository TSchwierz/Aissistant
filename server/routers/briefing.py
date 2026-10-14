"""Morning brief endpoints (Phase 0/1 stub — optional weather from climate cache)."""

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
    ClothingHint,
    MorningBriefResponse,
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
    _ = calendar_mod.get_today_events(date=date_iso, timezone=settings.timezone)
    _ = news_mod.get_topic_digests(date=date_iso)

    sections_present: list[str] = []
    weather_section: WeatherSection | None = None
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
        script=script,
        sections=ui_sections,
    )
    return JSONResponse(content=response.model_dump_response())
