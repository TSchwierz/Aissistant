"""Liveness / readiness endpoints."""

from fastapi import APIRouter

from server import __version__
from server.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": __version__,
        "timezone": settings.timezone,
    }
