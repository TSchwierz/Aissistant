"""When the Pi should listen for the morning scale broadcast."""

from __future__ import annotations

from dataclasses import dataclass

from server.modules.health.okok import ScaleReading


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


def should_replace_reading(
    previous_kg: float | None,
    previous_impedance: float | None,
    weight_kg: float,
    impedance: float | None,
    *,
    same_kg: float = 0.15,
) -> bool:
    """A new locked reading is worth storing when the weight moved or impedance arrived."""
    if previous_kg is None:
        return True
    if abs(previous_kg - weight_kg) > same_kg:
        return True
    return impedance is not None and previous_impedance is None


@dataclass
class ReadingHold:
    """Wait briefly after a lock so a follow-up packet can add impedance.

    Body-composition scales often lock the weight first and send impedance
    a few seconds later. Storing the first lock drops body fat.
    """

    settle_seconds: float = 8.0
    same_kg: float = 0.15
    reading: ScaleReading | None = None
    since: float | None = None
    done: bool = False

    def offer(self, reading: ScaleReading, now: float) -> ScaleReading | None:
        """Return a reading once it should be stored. Unstable packets are ignored."""
        if self.done or not reading.stable:
            return None
        if (
            self.reading is None
            or not self.reading.stable
            or abs(self.reading.weight_kg - reading.weight_kg) > self.same_kg
        ):
            self.reading = reading
            self.since = now
            if reading.impedance_ohm is not None:
                return self._finish(reading)
            return None
        self.reading = reading
        if reading.impedance_ohm is not None:
            return self._finish(reading)
        if self.since is not None and now - self.since >= self.settle_seconds:
            return self._finish(reading)
        return None

    def due(self, now: float) -> bool:
        """True when a held lock has waited long enough and no new packet is required."""
        if self.done or self.reading is None or not self.reading.stable:
            return False
        if self.reading.impedance_ohm is not None:
            return True
        return self.since is not None and now - self.since >= self.settle_seconds

    def take(self) -> ScaleReading | None:
        if self.done or self.reading is None or not self.reading.stable:
            return None
        return self._finish(self.reading)

    def flush(self) -> ScaleReading | None:
        """Store a lock when listening stops, without waiting out the settle time."""
        return self.take()

    def _finish(self, reading: ScaleReading) -> ScaleReading:
        self.reading = reading
        self.done = True
        return reading
