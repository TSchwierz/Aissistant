"""Morning brief endpoints (Phase 0 stub — no real LLM / providers yet)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from server.config import get_settings
from server.models.briefing import BriefFreshness, BriefMeta, MorningBriefResponse
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
    """Compose (stub) morning brief. Missing sections are omitted, not fatal."""
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    brief_date = _resolve_date(date_param, tz)
    date_iso = brief_date.isoformat()
    now = datetime.now(tz)

    # Phase 0: call stub modules; they return empty / None → empty brief.
    _ = weather_mod.get_day_overview(date=date_iso, timezone=settings.timezone)
    _ = calendar_mod.get_today_events(date=date_iso, timezone=settings.timezone)
    _ = news_mod.get_topic_digests(date=date_iso)

    response = MorningBriefResponse(
        meta=BriefMeta(
            date=date_iso,
            timezone=settings.timezone,
            generated_at=now.isoformat(timespec="seconds"),
            language=settings.language,
            freshness=BriefFreshness(),
            sections_present=[],
            empty_reason="no_data",
        ),
        script="",
        sections=[],
    )
    return JSONResponse(content=response.model_dump_response())
