"""Morning BLE scan for the OKOK weight scale. Pi only — not the phone."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from server.config import get_settings
from server.modules.health.database import get_session_factory
from server.modules.health.models import Measurement
from server.modules.health.okok import ScaleReading, reading_from_advertisement
from server.modules.health.scale_window import scan_requested
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


def _data_dir() -> Path:
    path = Path(get_settings().data_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mode_path() -> Path:
    return _data_dir() / "scale_mode.json"


def _status_path() -> Path:
    return _data_dir() / "scale_status.json"


def read_scale_mode() -> str:
    """``auto``, ``on`` (manual test), or ``off``. Shared with a separate scanner process."""
    try:
        raw = json.loads(_mode_path().read_text(encoding="utf-8"))
        mode = str(raw.get("mode", "auto"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return "auto"
    return mode if mode in {"auto", "on", "off"} else "auto"


def set_scale_mode(mode: str) -> str:
    if mode not in {"auto", "on", "off"}:
        raise ValueError("mode must be auto, on, or off")
    path = _mode_path()
    payload = json.dumps({"mode": mode})
    path.write_text(payload, encoding="utf-8")
    return mode


def scale_status() -> dict:
    """Latest scanner state. The worker process writes the file; the API reads it."""
    try:
        data = json.loads(_status_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["mode"] = read_scale_mode()
            return data
    except (OSError, json.JSONDecodeError):
        pass
    with _state_lock:
        state = dict(_state)
    state["mode"] = read_scale_mode()
    return state


def _set_state(**kwargs: object) -> None:
    with _state_lock:
        _state.update(kwargs)
        snapshot = dict(_state)
    snapshot["mode"] = read_scale_mode()
    path = _status_path()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(snapshot), encoding="utf-8")
    temporary.replace(path)


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


def _tick() -> bool:
    """One scanner pass. Returns True when a Bluetooth scan was attempted."""
    settings = get_settings()
    start_hour = int(settings.scale_listen_start_hour)
    end_hour = int(settings.scale_listen_end_hour)
    window = f"{start_hour:02d}:00-{end_hour:02d}:00"
    mode = read_scale_mode()
    if not settings.scale_scan_enabled and mode != "on":
        _set_state(
            enabled=False,
            phase="disabled",
            detail="PA_SCALE_SCAN_ENABLED is off",
            window=window,
            recorded_today=False,
            mode=mode,
        )
        return False

    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    recorded = recorded_on_local_day(now.date(), tz)
    listening = scan_requested(
        mode=mode,
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
        detail = "Manual stop" if mode == "off" else detail
        _set_state(
            enabled=True,
            phase="stopped" if mode == "off" else phase,
            detail=detail,
            recorded_today=recorded,
            window=window,
            mode=mode,
        )
        return False

    _set_state(
        enabled=True,
        phase="scanning",
        detail="Looking for a stable scale broadcast",
        recorded_today=False,
        window=window,
        last_error=None,
        mode=mode,
    )
    timeout = max(3, int(settings.scale_scan_timeout_seconds))
    try:
        reading = asyncio.run(_scan_stable(timeout))
    except Exception as exc:  # noqa: BLE001 — adapter missing, BlueZ down, etc.
        logger.warning("Scale scan unavailable: %s", exc)
        _set_state(phase="error", last_error=str(exc), detail=str(exc))
        return True
    if reading is None:
        _set_state(phase="scanning", detail="No stable reading in the last scan")
        return True
    stored = _ingest(reading, datetime.now(tz))
    _set_state(
        phase="recorded" if stored else "scanning",
        recorded_today=stored,
        last_weight_kg=round(reading.weight_kg, 2),
        detail="Stored today's measurement" if stored else "Reading was not stored",
    )
    return True


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
        listened = False
        try:
            listened = _tick()
        except Exception:  # noqa: BLE001
            logger.exception("Scale scanner tick failed")
        # Idle passes stay short so a manual Start is picked up quickly.
        _stop.wait(interval if listened else 2)
    logger.info("Scale scanner stopped")


def run_forever() -> None:
    """Block as the scale worker process. SIGINT/SIGTERM ends the loop."""

    def _handle(signum, _frame) -> None:  # noqa: ANN001
        logger.info("Scale worker received signal %s", signum)
        _stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    _stop.clear()
    _loop()


def start_scale_scanner() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="scale-scanner", daemon=True)
    _thread.start()


def stop_scale_scanner() -> None:
    _stop.set()
