"""Shared climate runtime for the unified FastAPI process."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server.modules.climate.advisor import AdvisorStore
from server.modules.climate.collector import create_weather_service, default_settings
from server.modules.climate.config import AppConfig, load_config
from server.modules.climate.db import ClimateDB
from server.modules.climate.weather import WeatherService

_runtime: "ClimateRuntime | None" = None


@dataclass
class ClimateRuntime:
    cfg: AppConfig
    db: ClimateDB
    advisor: AdvisorStore
    weather: WeatherService | None


def get_runtime() -> ClimateRuntime | None:
    return _runtime


def init_runtime(cfg: AppConfig | None = None) -> ClimateRuntime:
    """Init DB/schema, advisor store, and the optional weather service."""
    global _runtime
    cfg = cfg or load_config()
    db = ClimateDB(cfg.db_path)
    db.init_schema(default_settings(cfg))
    advisor = AdvisorStore(cfg.advisor_path)
    advisor.ensure()
    weather = create_weather_service(cfg, db)

    _runtime = ClimateRuntime(cfg=cfg, db=db, advisor=advisor, weather=weather)
    return _runtime


def day_overview_payload(*, date: str, timezone: str) -> dict[str, Any] | None:
    """Cheap outdoor day-overview for morning brief (from climate outdoor cache)."""
    rt = get_runtime()
    if rt is None:
        return None
    reading = rt.db.latest_outside_reading()
    forecast = rt.db.list_forecast()
    if reading is None and not forecast:
        return None

    highs = [p.temperature_c for p in forecast if p.temperature_c is not None]
    lows = list(highs)
    if reading is not None:
        highs.append(reading.temperature_c)
        lows.append(reading.temperature_c)
    high_c = max(highs) if highs else (reading.temperature_c if reading else None)
    low_c = min(lows) if lows else (reading.temperature_c if reading else None)

    precip_vals = [
        p.precipitation_probability
        for p in forecast
        if p.precipitation_probability is not None
    ]
    precip_chance = int(round(max(precip_vals))) if precip_vals else None

    condition = None
    if reading and reading.condition:
        condition = reading.condition
    elif forecast:
        condition = next((p.condition for p in forecast if p.condition), None)

    parts: list[str] = []
    if high_c is not None and low_c is not None:
        parts.append(f"High {high_c:.0f}°C / low {low_c:.0f}°C")
    if condition:
        parts.append(condition.replace("_", " "))
    if precip_chance is not None:
        parts.append(f"{precip_chance}% precip chance")
    summary = "; ".join(parts) if parts else "Outdoor conditions from Studio Climate cache."

    rainish = bool(
        condition
        and any(x in condition for x in ("rain", "drizzle", "thunder", "sleet", "hail"))
    ) or (precip_chance is not None and precip_chance >= 40)
    cool = high_c is not None and high_c < 16

    return {
        "date": date,
        "timezone": timezone,
        "summary": summary,
        "high_c": high_c,
        "low_c": low_c,
        "precip_chance_pct": precip_chance,
        "conditions": condition,
        "clothing_hint": {
            "rain_jacket": rainish,
            "hoody": cool or rainish,
            "notes": (
                "Take a rain jacket."
                if rainish
                else ("A hoody is enough for the chill." if cool else None)
            ),
        },
        "freshness": (
            reading.ts.isoformat(timespec="seconds") if reading is not None else None
        ),
        "source": "studio_climate",
    }
