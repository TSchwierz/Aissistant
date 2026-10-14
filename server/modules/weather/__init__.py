"""Weather day-overview for morning brief.

Uses Studio Climate outdoor cache when available (no separate provider yet).
"""

from __future__ import annotations

from typing import Any


def get_day_overview(*, date: str, timezone: str) -> dict[str, Any] | None:
    """Return day overview + clothing hint, or None if unavailable."""
    try:
        from server.modules.climate.runtime import day_overview_payload
    except Exception:  # noqa: BLE001
        return None
    return day_overview_payload(date=date, timezone=timezone)
