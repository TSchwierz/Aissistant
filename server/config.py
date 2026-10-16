"""Runtime configuration for the Pi SSOT server."""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_FILES = (
    "health.db",
    "climate.db",
    "calendar.db",
    "news.db",
    "scale_mode.json",
    "scale_status.json",
)


def default_user_data_dir() -> Path:
    """Stable directory outside the git checkout.

    A ``git pull`` (or a fresh clone of the repo) must not wipe calendar,
    health, climate, or news data.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "PersonalAissistent"
    xdg = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return root / "personal-aissistent"


def migrate_repo_data(target: Path, source: Path | None = None) -> Path:
    """Copy databases out of ``<repo>/data`` the first time the external dir is empty."""
    target = target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    source = (source or (_REPO_ROOT / "data")).expanduser().resolve()
    if source == target or not source.is_dir():
        return target

    for name in _DATA_FILES:
        src = source / name
        dest = target / name
        if not src.is_file() or src.stat().st_size <= 0:
            continue
        if dest.exists() and dest.stat().st_size > 0:
            continue
        shutil.copy2(src, dest)
        for suffix in ("-wal", "-shm"):
            side = Path(str(src) + suffix)
            side_dest = Path(str(dest) + suffix)
            if side.is_file() and not side_dest.exists():
                shutil.copy2(side, side_dest)

    advisor_src = source / "advisor"
    if advisor_src.is_dir():
        for path in advisor_src.rglob("*"):
            if not path.is_file():
                continue
            dest = target / "advisor" / path.relative_to(advisor_src)
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    databases_present = any((source / name).is_file() and (target / name).is_file() for name in _DATA_FILES)
    if databases_present:
        note = source / "DATA_LOCATION.txt"
        note.write_text(
            "Live data is stored outside this git checkout so version updates do not wipe it.\n"
            f"Location: {target}\n"
            "Override with the PA_DATA_DIR environment variable.\n",
            encoding="utf-8",
        )
    return target


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
    # Empty means the stable directory outside the git checkout.
    # Set PA_DATA_DIR to keep databases somewhere else (including ./data).
    data_dir: str = ""
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
    # True: background workers run as threads inside the API process (local dev).
    # False: a supervisor runs each worker as its own process. See start-server.sh.
    embed_workers: bool = True

    # Morning BLE scale listen (Pi). Inclusive start hour, exclusive end hour, local time.
    scale_scan_enabled: bool = True
    scale_listen_start_hour: int = 6
    scale_listen_end_hour: int = 12
    scale_scan_tick_seconds: int = 30
    scale_scan_timeout_seconds: int = 12

    @model_validator(mode="after")
    def _resolve_data_dir(self) -> Settings:
        raw = (self.data_dir or "").strip()
        target = Path(raw).expanduser() if raw else default_user_data_dir()
        self.data_dir = str(migrate_repo_data(target))
        return self

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
