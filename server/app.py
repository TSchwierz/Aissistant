"""FastAPI application factory / entry."""

from fastapi import FastAPI

from server import __version__
from server.config import get_settings
from server.routers import briefing, health


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Pi SSOT for Personal AIssistent. "
            "Intended for a trusted home LAN only — auth TBD; do not expose publicly."
        ),
    )
    app.include_router(health.router)
    app.include_router(briefing.router)
    return app


app = create_app()
