"""Runtime configuration for the Pi SSOT server."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    # SQLite and other persistent files (health.db, climate.db, calendar.db, news.db).
    data_dir: str = Field(default_factory=lambda: str(_REPO_ROOT / "data"))
    # None = follow config.toml / climate default (mock on for PC-friendly smoke).
    climate_mock_sensor: bool | None = None

    # AI keys — Pi only. Chain: Mistral → Claude → ChatGPT → Gemini.
    # Env: PA_MISTRAL_API_KEY, PA_ANTHROPIC_API_KEY, PA_OPENAI_API_KEY, PA_GEMINI_API_KEY
    # Fallbacks without prefix: MISTRAL_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY,
    # GEMINI_API_KEY / GOOGLE_API_KEY.
    mistral_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    news_scheduler_enabled: bool = True
    news_scheduler_tick_seconds: int = 60

    # Morning BLE scale listen (Pi). Inclusive start hour, exclusive end hour, local time.
    scale_scan_enabled: bool = True
    scale_listen_start_hour: int = 6
    scale_listen_end_hour: int = 12
    scale_scan_tick_seconds: int = 30
    scale_scan_timeout_seconds: int = 12

    @model_validator(mode="after")
    def _merge_unprefixed_ai_keys(self) -> Settings:
        if not self.mistral_api_key:
            self.mistral_api_key = os.environ.get("MISTRAL_API_KEY", "")
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.gemini_api_key:
            self.gemini_api_key = (
                os.environ.get("GEMINI_API_KEY", "")
                or os.environ.get("GOOGLE_API_KEY", "")
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
