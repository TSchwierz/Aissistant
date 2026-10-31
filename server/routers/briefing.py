"""Morning brief HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from server.modules.briefing.store import resolve_morning_brief

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.get("/morning")
def get_morning_brief(
    date_param: str | None = Query(
        default=None,
        alias="date",
        description="Calendar day YYYY-MM-DD in the Pi timezone. Omit for today.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    refresh: bool = Query(
        default=False,
        description=(
            "Compose again. For today, replace the stored morning brief. "
            "Any other date is composed on demand and is not stored."
        ),
    ),
) -> JSONResponse:
    """English radio-style morning brief. Today is the file on disk."""
    response = resolve_morning_brief(date_param=date_param, refresh=refresh)
    return JSONResponse(content=response.model_dump_response())


@router.get("/morning/latest")
def get_morning_brief_latest(
    refresh: bool = Query(default=False),
) -> JSONResponse:
    """Alias for today's brief with no date query."""
    response = resolve_morning_brief(date_param=None, refresh=refresh)
    return JSONResponse(content=response.model_dump_response())
