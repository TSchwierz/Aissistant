"""Climate module config — defaults for unified Personal AIssistent process."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from server.config import get_settings

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent.parent.parent
EXAMPLE_CONFIG_PATH = REPO_ROOT / "config.climate.example.toml"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.climate.toml"


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    db_path: Path
    sample_interval_seconds: int
    gpio_pin: int
    mock_sensor: bool
    ntfy_server: str
    ntfy_topic: str
    ntfy_token: str
    humidity_min: float
    humidity_max: float
    temp_min: float
    temp_max: float
    sustain_minutes: int
    alert_cooldown_minutes: int
    rolling_window_points: int
    incident_humidity_delta: float
    incident_temp_delta: float
    incident_cooldown_minutes: int
    quiet_hours_enabled: bool
    quiet_hours_start: str
    quiet_hours_end: str
    quiet_hours_timezone: str
    weather_enabled: bool
    latitude: float
    longitude: float
    weather_poll_interval_minutes: int
    weather_alert_max_age_minutes: int
    weather_forecast_hours: int
    weather_request_timeout_seconds: float
    openweathermap_api_key: str
    advisor_path: Path


def _resolve_under_data(raw: str, data_dir: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = data_dir / path
    return path


def load_config(path: Path | None = None) -> AppConfig:
    """Load optional TOML overlay; otherwise use PA_* / safe PC defaults."""
    settings = get_settings()
    data_dir = Path(settings.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    raw: dict = {}
    config_path = path or DEFAULT_CONFIG_PATH
    if config_path.exists():
        with config_path.open("rb") as fh:
            raw = tomllib.load(fh)
    elif EXAMPLE_CONFIG_PATH.exists() and path is not None:
        with EXAMPLE_CONFIG_PATH.open("rb") as fh:
            raw = tomllib.load(fh)

    server = raw.get("server", {})
    database = raw.get("database", {})
    collector = raw.get("collector", {})
    ntfy = raw.get("ntfy", {})
    defaults = raw.get("defaults", {})
    quiet_hours = raw.get("quiet_hours", {})
    weather = raw.get("weather", {})
    advisor = raw.get("advisor", {})

    db_raw = str(database.get("path", "climate.db"))
    db_path = _resolve_under_data(db_raw, data_dir)
    # If toml still says data/climate.db relative to old pi/, flatten under PA_DATA_DIR.
    if db_path.name == "climate.db" or str(database.get("path", "")).endswith("climate.db"):
        db_path = data_dir / "climate.db"

    advisor_raw = str(advisor.get("path", "")).strip()
    advisor_path = (
        _resolve_under_data(advisor_raw, data_dir) if advisor_raw else data_dir / "advisor"
    )

    # PC / CI smoke: mock sensor unless config or PA_CLIMATE_MOCK_SENSOR says otherwise.
    mock_default = True
    mock_sensor = bool(collector.get("mock_sensor", mock_default))
    if settings.climate_mock_sensor is not None:
        mock_sensor = settings.climate_mock_sensor

    return AppConfig(
        host=str(server.get("host", settings.host)),
        port=int(server.get("port", settings.port)),
        db_path=db_path,
        sample_interval_seconds=int(collector.get("sample_interval_seconds", 60)),
        gpio_pin=int(collector.get("gpio_pin", 23)),
        mock_sensor=mock_sensor,
        ntfy_server=str(ntfy.get("server", "https://ntfy.sh")).rstrip("/"),
        ntfy_topic=str(ntfy.get("topic", "")),
        ntfy_token=str(ntfy.get("token", "")),
        humidity_min=float(defaults.get("humidity_min", 40)),
        humidity_max=float(defaults.get("humidity_max", 55)),
        temp_min=float(defaults.get("temp_min", 18)),
        temp_max=float(defaults.get("temp_max", 24)),
        sustain_minutes=int(defaults.get("sustain_minutes", 30)),
        alert_cooldown_minutes=int(defaults.get("alert_cooldown_minutes", 360)),
        rolling_window_points=max(2, int(defaults.get("rolling_window_points", 8))),
        incident_humidity_delta=float(defaults.get("incident_humidity_delta", 6)),
        incident_temp_delta=float(defaults.get("incident_temp_delta", 1.5)),
        incident_cooldown_minutes=int(defaults.get("incident_cooldown_minutes", 20)),
        quiet_hours_enabled=bool(quiet_hours.get("enabled", False)),
        quiet_hours_start=str(quiet_hours.get("start", "23:00")),
        quiet_hours_end=str(quiet_hours.get("end", "08:00")),
        quiet_hours_timezone=str(quiet_hours.get("timezone", settings.timezone)),
        weather_enabled=bool(weather.get("enabled", True)),
        latitude=float(weather.get("latitude", 51.2277)),
        longitude=float(weather.get("longitude", 6.7735)),
        weather_poll_interval_minutes=max(5, int(weather.get("poll_interval_minutes", 60))),
        weather_alert_max_age_minutes=max(1, int(weather.get("alert_max_age_minutes", 30))),
        weather_forecast_hours=max(4, min(int(weather.get("forecast_hours", 24)), 24)),
        weather_request_timeout_seconds=float(weather.get("request_timeout_seconds", 10)),
        openweathermap_api_key=str(weather.get("openweathermap_api_key", "")),
        advisor_path=advisor_path,
    )
