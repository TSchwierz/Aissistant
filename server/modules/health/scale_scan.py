"""Morning BLE scan for the OKOK weight scale. Pi only — not the phone."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from server.config import get_settings
from server.modules.health.database import get_session_factory
from server.modules.health.models import Measurement
from server.modules.health.okok import ScaleReading, reading_from_advertisement
from server.modules.health.scale_window import ReadingHold, scan_requested, should_replace_reading
from server.modules.health.schemas import MeasurementIn
from server.modules.health.services import (
    apply_metrics,
    get_or_create_profile,
    ingest_measurements,
    metrics_for,
)

# The Pi's Bluetooth controller keeps only the first advertisement from a
# scale. Later packets (the locked weight, then impedance) never reach BlueZ
# until discovery is stopped and started again. Each cycle is short so a
# weigh-in of about twenty seconds yields several fresh packets.
_CYCLE_SECONDS = 2.5
_RESTART_PAUSE_SECONDS = 0.4
_SETTLE_SECONDS = 8.0
_IDLE_POLL_SECONDS = 1.0

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


def _ingest(reading: ScaleReading, when: datetime, *, replace: bool) -> bool:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        client_id = _client_id(when.date())
        weight = round(reading.weight_kg, 2)
        raw_hex = reading.raw_hex[:256] if reading.raw_hex else None
        existing = db.scalar(select(Measurement).where(Measurement.client_id == client_id))
        if existing is not None and not replace:
            logger.info("Scale reading already stored for %s", when.date().isoformat())
            return True
        if existing is not None:
            existing.measured_at = when
            existing.weight_kg = weight
            existing.impedance_ohm = reading.impedance_ohm
            existing.unit = reading.unit or "kg"
            existing.scale_mac = reading.scale_mac
            existing.raw_hex = raw_hex
            profile = get_or_create_profile(db)
            apply_metrics(existing, metrics_for(profile, weight, reading.impedance_ohm))
            db.commit()
            logger.info(
                "Updated scale weight %.2f kg (%s)", reading.weight_kg, reading.protocol
            )
            return True
        item = MeasurementIn(
            client_id=client_id,
            measured_at=when,
            weight_kg=weight,
            impedance_ohm=reading.impedance_ohm,
            unit=reading.unit or "kg",
            scale_mac=reading.scale_mac,
            raw_hex=raw_hex,
        )
        created, skipped, _ids = ingest_measurements(db, [item])
    finally:
        db.close()
    if created or skipped:
        logger.info(
            "Recorded scale weight %.2f kg (%s)", reading.weight_kg, reading.protocol
        )
        return True
    return False


def _listen_context() -> dict[str, object]:
    settings = get_settings()
    start_hour = int(settings.scale_listen_start_hour)
    end_hour = int(settings.scale_listen_end_hour)
    window = f"{start_hour:02d}:00-{end_hour:02d}:00"
    mode = read_scale_mode()
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    if not settings.scale_scan_enabled and mode != "on":
        return {
            "listening": False,
            "enabled": False,
            "phase": "disabled",
            "detail": "PA_SCALE_SCAN_ENABLED is off",
            "recorded": False,
            "window": window,
            "mode": mode,
            "tz": tz,
        }
    recorded = recorded_on_local_day(now.date(), tz)
    listening = scan_requested(
        mode=mode,
        hour=now.hour,
        recorded_today=recorded,
        start_hour=start_hour,
        end_hour=end_hour,
    )
    if mode == "off":
        phase, detail = "stopped", "Manual stop"
    elif recorded and not listening:
        phase, detail = "recorded", "Measurement already stored for today"
    elif not listening:
        phase, detail = "outside", f"Listening only {window} ({settings.timezone})"
    else:
        phase, detail = "scanning", "Looking for a stable scale broadcast"
    return {
        "listening": listening,
        "enabled": True,
        "phase": phase,
        "detail": detail,
        "recorded": recorded,
        "window": window,
        "mode": mode,
        "tz": tz,
    }


def _publish(ctx: dict[str, object], **kwargs: object) -> None:
    """Publish scanner state. Keyword arguments override the values from ``ctx``."""
    payload: dict[str, object] = {
        "enabled": ctx["enabled"],
        "recorded_today": ctx["recorded"],
        "window": ctx["window"],
        "mode": ctx["mode"],
    }
    payload.update(kwargs)
    _set_state(**payload)


def _live_detail(live: ScaleReading | None, hold: ReadingHold) -> str:
    held = hold.reading
    if held is not None and held.stable and held.impedance_ohm is None and not hold.done:
        return f"{held.weight_kg:.1f} kg locked, waiting for body composition"
    if live is not None and not live.stable:
        return f"{live.weight_kg:.1f} kg, waiting for the scale to lock"
    if live is not None:
        return f"{live.weight_kg:.1f} kg from the scale"
    return "Looking for a stable scale broadcast"


def _store(reading: ScaleReading, ctx: dict[str, object]) -> None:
    tz = ctx["tz"]
    assert isinstance(tz, ZoneInfo)
    mode = str(ctx["mode"])
    stored = _ingest(reading, datetime.now(tz), replace=(mode == "on"))
    weight = round(reading.weight_kg, 2)
    impedance = "" if reading.impedance_ohm is None else f", {reading.impedance_ohm:.0f} ohm"
    detail = (
        f"Stored {weight:.1f} kg{impedance}"
        if stored
        else "Reading was not stored"
    )
    if stored and mode == "on":
        detail += ". Still listening"
    _publish(
        ctx,
        phase="recorded" if stored else "scanning",
        recorded_today=stored or bool(ctx["recorded"]),
        last_weight_kg=weight,
        last_error=None,
        detail=detail,
    )


async def _wait(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not _stop.is_set() and time.monotonic() < deadline:
        await asyncio.sleep(min(0.25, max(0.0, deadline - time.monotonic())))


def _reading_from_advertisement(device: object, advertisement: object) -> ScaleReading | None:
    manufacturer = dict(getattr(advertisement, "manufacturer_data", None) or {})
    service = {
        str(key): value
        for key, value in (getattr(advertisement, "service_data", None) or {}).items()
    }
    return reading_from_advertisement(
        getattr(device, "address", None), manufacturer, service
    )


async def _run_cycle(seconds: float, on_reading, stop_when) -> None:  # noqa: ANN001
    from bleak import BleakScanner

    def on_advertisement(device: object, advertisement: object) -> None:
        # Bleak rejects a callback unless inspect.signature shows exactly two
        # parameters (BLEDevice, AdvertisementData). *args counts as one.
        try:
            reading = _reading_from_advertisement(device, advertisement)
        except Exception:  # noqa: BLE001 — one bad packet should not stop the scan
            logger.debug("Scale advertisement could not be parsed", exc_info=True)
            return
        if reading is not None:
            try:
                on_reading(reading)
            except Exception:  # noqa: BLE001
                logger.exception("Scale reading was not handled")

    scanner = BleakScanner(detection_callback=on_advertisement)
    await scanner.start()
    try:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not _stop.is_set():
            if stop_when():
                break
            await asyncio.sleep(0.2)
    finally:
        try:
            await scanner.stop()
        except Exception:  # noqa: BLE001 — stop races with adapter resets
            logger.debug("Scale scan stop failed", exc_info=True)


async def _scan_while_requested() -> None:
    """Listen until the window closes, the mode changes, or the process stops.

    Discovery restarts every few seconds. That clears the controller's
    duplicate filter, which otherwise hides the locked weight.
    """
    ctx = _listen_context()
    hold = ReadingHold(settle_seconds=_SETTLE_SECONDS)
    live: ScaleReading | None = None
    committed: ScaleReading | None = None
    saved: ScaleReading | None = None
    last_publish = 0.0

    def publish(force: bool = False) -> None:
        nonlocal last_publish
        now = time.monotonic()
        if not force and now - last_publish < 1.0:
            return
        last_publish = now
        weight = live.weight_kg if live is not None else None
        _publish(
            ctx,
            phase="scanning",
            detail=_live_detail(live, hold),
            last_weight_kg=None if weight is None else round(weight, 2),
            last_error=None,
        )

    def on_reading(reading: ScaleReading) -> None:
        nonlocal live, committed
        live = reading
        chosen = hold.offer(reading, time.monotonic())
        if chosen is not None:
            committed = chosen
        publish()

    def stop_when() -> bool:
        return committed is not None or hold.due(time.monotonic()) or _stop.is_set()

    publish(force=True)
    while not _stop.is_set():
        ctx = _listen_context()
        if not ctx["listening"]:
            break
        await _run_cycle(_CYCLE_SECONDS, on_reading, stop_when)
        chosen = committed
        if chosen is None and hold.due(time.monotonic()):
            chosen = hold.take()
        if chosen is not None and should_replace_reading(
            None if saved is None else saved.weight_kg,
            None if saved is None else saved.impedance_ohm,
            chosen.weight_kg,
            chosen.impedance_ohm,
        ):
            _store(chosen, ctx)
            saved = chosen
            hold = ReadingHold(settle_seconds=_SETTLE_SECONDS)
            committed = None
            if ctx["mode"] != "on":
                return
        elif chosen is not None:
            hold = ReadingHold(settle_seconds=_SETTLE_SECONDS)
            committed = None
        if not _listen_context()["listening"]:
            break
        await _wait(_RESTART_PAUSE_SECONDS)

    final = committed or hold.flush()
    if final is not None and should_replace_reading(
        None if saved is None else saved.weight_kg,
        None if saved is None else saved.impedance_ohm,
        final.weight_kg,
        final.impedance_ohm,
    ):
        _store(final, _listen_context())


async def _serve() -> None:
    settings = get_settings()
    logger.info(
        "Scale scanner started (cycle=%ss, window=%02d:00-%02d:00)",
        _CYCLE_SECONDS,
        settings.scale_listen_start_hour,
        settings.scale_listen_end_hour,
    )
    while not _stop.is_set():
        ctx = _listen_context()
        if not ctx["listening"]:
            detail = ctx["detail"]
            if ctx["phase"] == "recorded":
                with _state_lock:
                    weight = _state.get("last_weight_kg")
                if weight is not None:
                    detail = f"Stored {weight} kg for today"
            _publish(
                ctx,
                phase=ctx["phase"],
                detail=detail,
                last_error=None,
            )
            await _wait(_IDLE_POLL_SECONDS)
            continue
        try:
            await _scan_while_requested()
        except Exception as exc:  # noqa: BLE001 — adapter missing, BlueZ down, etc.
            logger.warning("Scale scan unavailable: %s", exc)
            _publish(ctx, phase="error", last_error=str(exc), detail=str(exc))
            await _wait(5)
    logger.info("Scale scanner stopped")


def _loop() -> None:
    asyncio.run(_serve())


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
