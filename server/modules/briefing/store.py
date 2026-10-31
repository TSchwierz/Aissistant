"""On-disk morning brief for the server's local today.

``{data_dir}/morning_brief.json`` is the source of truth for today's brief.
A process restart serves that file. Other dates are composed on demand and
are not written here.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from server.config import get_settings
from server.models.briefing import MorningBriefResponse
from server.modules.briefing.composer import compose_morning_brief

logger = logging.getLogger(__name__)

MORNING_BRIEF_FILENAME = "morning_brief.json"
PREGENERATE_HOUR = 4
PREGENERATE_MINUTE = 0

_STORE_LOCK = threading.RLock()


def morning_brief_path() -> Path:
    """Path of today's stored brief under ``settings.data_dir``."""
    data_dir = Path(get_settings().data_dir).expanduser().resolve()
    return data_dir / MORNING_BRIEF_FILENAME


def load_morning_brief() -> MorningBriefResponse | None:
    """Read the stored brief, or None when the file is missing or unreadable."""
    path = morning_brief_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return MorningBriefResponse.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        logger.warning("Ignoring unreadable morning brief %s: %s", path, exc)
        return None


def save_morning_brief(brief: MorningBriefResponse) -> Path:
    """Atomically replace today's morning brief file."""
    path = morning_brief_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = brief.model_dump(mode="json")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def _local_now(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(get_settings().timezone)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def _parse_generated_at(value: str, tz: ZoneInfo) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _pregenerate_cutoff(now_local: datetime) -> datetime:
    return now_local.replace(
        hour=PREGENERATE_HOUR,
        minute=PREGENERATE_MINUTE,
        second=0,
        microsecond=0,
    )


def stored_brief_covers_pregenerate(now_local: datetime) -> bool:
    """True when today's file was generated at or after 04:00 local time."""
    stored = load_morning_brief()
    if stored is None or stored.meta.date != now_local.date().isoformat():
        return False
    tz = now_local.tzinfo
    if not isinstance(tz, ZoneInfo):
        tz = ZoneInfo(get_settings().timezone)
    generated = _parse_generated_at(stored.meta.generated_at, tz)
    if generated is None:
        return False
    return generated >= _pregenerate_cutoff(now_local)


def resolve_morning_brief(
    *,
    date_param: str | None = None,
    refresh: bool = False,
) -> MorningBriefResponse:
    """Serve today's stored brief, or compose a date without storing it.

    A missing file, a file for another day, or ``refresh`` composes today and
    replaces the morning file. Any other date is composed and discarded.
    """
    now_local = _local_now()
    today = now_local.date()
    brief_date = date.fromisoformat(date_param) if date_param else today
    if brief_date != today:
        return compose_morning_brief(date_param=brief_date.isoformat())

    with _STORE_LOCK:
        if not refresh:
            stored = load_morning_brief()
            if stored is not None and stored.meta.date == today.isoformat():
                return stored
        response = compose_morning_brief(date_param=today.isoformat())
        save_morning_brief(response)
        return response


def refresh_stored_morning_brief() -> MorningBriefResponse:
    """Recompose today's brief and replace the file, even after 04:00."""
    now_local = _local_now()
    today = now_local.date().isoformat()
    with _STORE_LOCK:
        response = compose_morning_brief(date_param=today)
        save_morning_brief(response)
        return response


def pregenerate_morning_brief_if_due(*, now: datetime | None = None) -> bool:
    """Compose today's brief once local time reaches 04:00.

    Idempotent when today's file already exists and ``generated_at`` is at or
    after 04:00 local time. A missing file, a file for another day, or a file
    generated earlier today is composed. Returns True when a new file is written.
    """
    now_local = _local_now(now)
    if now_local < _pregenerate_cutoff(now_local):
        return False
    with _STORE_LOCK:
        if stored_brief_covers_pregenerate(now_local):
            logger.debug(
                "Morning brief for %s already generated at or after %02d:%02d",
                now_local.date().isoformat(),
                PREGENERATE_HOUR,
                PREGENERATE_MINUTE,
            )
            return False
        today = now_local.date().isoformat()
        logger.info("Pre-generating morning brief for %s", today)
        response = compose_morning_brief(date_param=today)
        save_morning_brief(response)
        return True
