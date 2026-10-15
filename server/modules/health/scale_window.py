"""When the Pi should listen for the morning scale broadcast."""

from __future__ import annotations


def scan_requested(
    *,
    mode: str,
    hour: int,
    recorded_today: bool,
    start_hour: int = 6,
    end_hour: int = 12,
) -> bool:
    """Manual test override, otherwise the morning window.

    ``on`` scans even outside the window and after today's reading is stored.
    ``off`` stays quiet. ``auto`` uses :func:`should_listen`.
    """
    if mode == "off":
        return False
    if mode == "on":
        return True
    return should_listen(
        hour=hour,
        recorded_today=recorded_today,
        start_hour=start_hour,
        end_hour=end_hour,
    )


def should_listen(
    *,
    hour: int,
    recorded_today: bool,
    start_hour: int = 6,
    end_hour: int = 12,
) -> bool:
    """Listen only inside the morning window, and only until today's reading exists.

    ``start_hour`` is inclusive and ``end_hour`` is exclusive, in local time.
    """
    if recorded_today:
        return False
    if end_hour <= start_hour:
        return False
    return start_hour <= hour < end_hour
