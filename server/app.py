"""FastAPI application factory / entry."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from server import __version__
from server.config import get_settings
from server.modules.calendar import router as calendar_router
from server.modules.calendar import startup_calendar
from server.modules.climate import mount_climate, startup_climate
from server.modules.health import mount_health, startup_health
from server.routers import briefing, health as liveness


@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup_health()
    startup_climate()
    startup_calendar()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Pi SSOT for Personal AIssistent "
            "(Health + Studio Climate + personal calendar + morning brief). "
            "Trusted home LAN only — auth TBD; do not expose publicly. "
            "Former Health :8000 and Climate :8787 → this process :8741 "
            "(climate routes under /climate)."
        ),
        lifespan=lifespan,
    )
    app.include_router(liveness.router)
    app.include_router(briefing.router)
    app.include_router(calendar_router)
    mount_health(app)
    mount_climate(app)
    return app


app = create_app()
