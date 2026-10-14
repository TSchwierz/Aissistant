"""Morning brief HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from server.modules.briefing import compose_morning_brief

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
        description="Bust the short-lived in-memory cache and recompose.",
    ),
) -> JSONResponse:
    """Compose English radio-style morning brief. Skip missing sections; never abort."""
    response = compose_morning_brief(date_param=date_param, refresh=refresh)
    return JSONResponse(content=response.model_dump_response())


@router.get("/morning/latest")
def get_morning_brief_latest(
    refresh: bool = Query(default=False),
) -> JSONResponse:
    """Alias for today's brief with no date query."""
    response = compose_morning_brief(date_param=None, refresh=refresh)
    return JSONResponse(content=response.model_dump_response())
