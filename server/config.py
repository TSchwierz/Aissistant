"""Runtime configuration for the Pi SSOT server."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App settings. Override via environment variables (prefix PA_)."""

    model_config = SettingsConfigDict(
        env_prefix="PA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Personal AIssistent"
    timezone: str = "Europe/Berlin"
    # LAN-trusted home network: no auth in Phase 0/1. Bind to all interfaces
    # only when the Pi sits on a trusted LAN; prefer 127.0.0.1 for local dev.
    host: str = "127.0.0.1"
    port: int = 8741
    language: str = "en"
    # SQLite and other persistent files (health.db lives here).
    data_dir: str = Field(default_factory=lambda: str(_REPO_ROOT / "data"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
