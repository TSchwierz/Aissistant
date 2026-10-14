"""When the Pi should listen for the morning scale broadcast."""

from __future__ import annotations


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
