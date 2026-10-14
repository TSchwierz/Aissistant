"""Morning BLE scan for the OKOK weight scale. Pi only — not the phone."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from server.config import get_settings
from server.modules.health.database import get_session_factory
from server.modules.health.models import Measurement
from server.modules.health.okok import ScaleReading, reading_from_advertisement
from server.modules.health.scale_window import should_listen
from server.modules.health.schemas import MeasurementIn
from server.modules.health.services import ingest_measurements

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None
_state_lock = threading.Lock()
_state: dict[str, object] = {
    "enabled": True,
    "phase": "idle",
    "detail": "",
    "recorded_today": False,
    "window": "06:00-12:00",
    "last_weight_kg": None,
    "last_error": None,
}


def scale_status() -> dict:
    with _state_lock:
        return dict(_state)


def _set_state(**kwargs: object) -> None:
    with _state_lock:
        _state.update(kwargs)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def recorded_on_local_day(day, tz: ZoneInfo) -> bool:
    """True when health.db already has a measurement on this local calendar day."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        start = datetime(day.year, day.month, day.day, tzinfo=tz) - timedelta(days=1)
        rows = db.scalars(
            select(Measurement.measured_at).where(
                Measurement.measured_at >= start.astimezone(timezone.utc)
            )
        ).all()
    finally:
        db.close()
    for measured_at in rows:
        if _as_utc(measured_at).astimezone(tz).date() == day:
            return True
    return False


def _client_id(day) -> str:
    return f"pi-scale-{day.isoformat()}"


def _ingest(reading: ScaleReading, when: datetime) -> bool:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        item = MeasurementIn(
            client_id=_client_id(when.date()),
            measured_at=when,
            weight_kg=round(reading.weight_kg, 2),
            impedance_ohm=reading.impedance_ohm,
            unit=reading.unit or "kg",
            scale_mac=reading.scale_mac,
            raw_hex=reading.raw_hex[:256] if reading.raw_hex else None,
        )
        created, skipped, _ids = ingest_measurements(db, [item])
    finally:
        db.close()
    if created:
        logger.info(
            "Recorded scale weight %.2f kg (%s)", reading.weight_kg, reading.protocol
        )
        return True
    if skipped:
        logger.info("Scale reading already stored for %s", when.date().isoformat())
        return True
    return False


async def _scan_stable(timeout: float) -> ScaleReading | None:
    from bleak import BleakScanner

    found = asyncio.Event()
    holder: dict[str, ScaleReading] = {}

    def on_advertisement(device, advertisement) -> None:
        if found.is_set():
            return
        manufacturer = dict(getattr(advertisement, "manufacturer_data", None) or {})
        service = {
            str(key): value
            for key, value in (getattr(advertisement, "service_data", None) or {}).items()
        }
        reading = reading_from_advertisement(
            getattr(device, "address", None), manufacturer, service
        )
        if reading is None or not reading.stable:
            return
        holder["reading"] = reading
        found.set()

    scanner = BleakScanner(detection_callback=on_advertisement)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), timeout)
    except TimeoutError:
        return None
    finally:
        await scanner.stop()
    return holder.get("reading")


def _tick() -> None:
    settings = get_settings()
    start_hour = int(settings.scale_listen_start_hour)
    end_hour = int(settings.scale_listen_end_hour)
    window = f"{start_hour:02d}:00-{end_hour:02d}:00"
    if not settings.scale_scan_enabled:
        _set_state(
            enabled=False,
            phase="disabled",
            detail="PA_SCALE_SCAN_ENABLED is off",
            window=window,
            recorded_today=False,
        )
        return

    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    recorded = recorded_on_local_day(now.date(), tz)
    listening = should_listen(
        hour=now.hour,
        recorded_today=recorded,
        start_hour=start_hour,
        end_hour=end_hour,
    )
    if not listening:
        phase = "recorded" if recorded else "outside"
        detail = (
            "Measurement already stored for today"
            if recorded
            else f"Listening only {window} ({settings.timezone})"
        )
        _set_state(
            enabled=True,
            phase=phase,
            detail=detail,
            recorded_today=recorded,
            window=window,
        )
        return

    _set_state(
        enabled=True,
        phase="scanning",
        detail="Looking for a stable scale broadcast",
        recorded_today=False,
        window=window,
        last_error=None,
    )
    timeout = max(3, int(settings.scale_scan_timeout_seconds))
    try:
        reading = asyncio.run(_scan_stable(timeout))
    except Exception as exc:  # noqa: BLE001 — adapter missing, BlueZ down, etc.
        logger.warning("Scale scan unavailable: %s", exc)
        _set_state(phase="error", last_error=str(exc), detail=str(exc))
        return
    if reading is None:
        _set_state(phase="scanning", detail="No stable reading in the last scan")
        return
    stored = _ingest(reading, datetime.now(tz))
    _set_state(
        phase="recorded" if stored else "scanning",
        recorded_today=stored,
        last_weight_kg=round(reading.weight_kg, 2),
        detail="Stored today's measurement" if stored else "Reading was not stored",
    )


def _loop() -> None:
    settings = get_settings()
    interval = max(15, int(settings.scale_scan_tick_seconds))
    logger.info(
        "Scale scanner started (tick=%ss, window=%02d:00-%02d:00)",
        interval,
        settings.scale_listen_start_hour,
        settings.scale_listen_end_hour,
    )
    _stop.wait(3)
    while not _stop.is_set():
        try:
            _tick()
        except Exception:  # noqa: BLE001
            logger.exception("Scale scanner tick failed")
        _stop.wait(interval)
    logger.info("Scale scanner stopped")


def start_scale_scanner() -> None:
    global _thread
    if not get_settings().scale_scan_enabled:
        _set_state(enabled=False, phase="disabled", detail="PA_SCALE_SCAN_ENABLED is off")
        logger.info("Scale scanner disabled")
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="scale-scanner", daemon=True)
    _thread.start()


def stop_scale_scanner() -> None:
    _stop.set()
