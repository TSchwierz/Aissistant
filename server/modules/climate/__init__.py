"""Studio Climate Monitor — mounted into the unified Personal AIssistent process.

Routes live under ``/climate/*`` (former standalone port ``:8787``).
Mock sensor is the default for PC smoke tests; set ``mock_sensor = false`` in
``config.climate.toml`` (or ``PA_CLIMATE_MOCK_SENSOR=false``) on the Pi.
"""

from __future__ import annotations

from fastapi import FastAPI

from server.modules.climate.api import create_app
from server.modules.climate.runtime import (
    day_overview_payload,
    get_runtime,
    init_runtime,
)

__version__ = "0.1.0"

__all__ = [
    "mount_climate",
    "startup_climate",
    "day_overview_payload",
    "get_runtime",
]


def startup_climate() -> None:
    init_runtime()


def mount_climate(app: FastAPI) -> None:
    """Attach Studio Climate API under ``/climate``."""
    startup_climate()
    climate_app = create_app()
    app.mount("/climate", climate_app)
