"""FastAPI application factory / entry."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from server import __version__
from server.config import get_settings
from server.modules.health import mount_health, startup_health
from server.routers import briefing, health as liveness


@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup_health()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Pi SSOT for Personal AIssistent. "
            "Intended for a trusted home LAN only — auth TBD; do not expose publicly."
        ),
        lifespan=lifespan,
    )
    app.include_router(liveness.router)
    app.include_router(briefing.router)
    mount_health(app)
    return app


app = create_app()
