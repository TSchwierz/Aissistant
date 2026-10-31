"""OKOK parser, morning listen window, and scale scan. No Bluetooth adapter required."""

import asyncio
import inspect
import json
import logging
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bleak.backends.scanner import BaseBleakScanner
from sqlalchemy import delete, select

from server.config import get_settings
from server.modules.health import scale_scan
from server.modules.health.database import get_session_factory, init_db, reset_engine_for_tests
from server.modules.health.models import Measurement
from server.modules.health.router import router
from server.modules.health.okok import (
    ScaleReading,
    parse_c0_payload,
    parse_manufacturer_data,
    reading_from_advertisement,
)
from server.modules.health.scale_window import (
    ReadingHold,
    scan_requested,
    should_listen,
    should_replace_reading,
)


class ListenWindowTests(unittest.TestCase):
    def test_morning_hours_only(self):
        self.assertFalse(should_listen(hour=7, recorded_today=False))
        self.assertTrue(should_listen(hour=8, recorded_today=False))
        self.assertTrue(should_listen(hour=9, recorded_today=False))
        self.assertFalse(should_listen(hour=10, recorded_today=False))
        self.assertFalse(should_listen(hour=6, recorded_today=False))
        self.assertFalse(should_listen(hour=11, recorded_today=False))

    def test_stops_after_today_is_recorded(self):
        self.assertFalse(should_listen(hour=8, recorded_today=True))

    def test_manual_override(self):
        self.assertTrue(scan_requested(mode="on", hour=20, recorded_today=True))
        self.assertFalse(scan_requested(mode="off", hour=8, recorded_today=False))
        self.assertTrue(scan_requested(mode="auto", hour=8, recorded_today=False))
        self.assertFalse(scan_requested(mode="auto", hour=8, recorded_today=True))


def _reading(weight: float, *, stable: bool, impedance: float | None = None) -> ScaleReading:
    return ScaleReading(
        weight_kg=weight,
        impedance_ohm=impedance,
        unit="kg",
        decimals=1,
        stable=stable,
        scale_mac=None,
        protocol="C0",
        raw_hex="",
    )


class ReadingHoldTests(unittest.TestCase):
    def test_unstable_is_not_stored(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(74.2, stable=False), 0))
        self.assertIsNone(hold.flush())

    def test_impedance_is_stored_immediately(self):
        hold = ReadingHold(settle_seconds=8)
        stored = hold.offer(_reading(74.2, stable=True, impedance=520), 0)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.impedance_ohm, 520)

    def test_lock_without_impedance_waits(self):
        hold = ReadingHold(settle_seconds=8)
        first = _reading(74.2, stable=True)
        self.assertIsNone(hold.offer(first, 0))
        self.assertFalse(hold.due(7.9))
        self.assertTrue(hold.due(8))
        stored = hold.take()
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertAlmostEqual(stored.weight_kg, 74.2)

    def test_impedance_after_the_lock_is_stored(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(74.2, stable=True), 0))
        stored = hold.offer(_reading(74.2, stable=True, impedance=480), 2)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.impedance_ohm, 480)

    def test_weight_change_resets_the_wait(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(70.0, stable=True), 0))
        self.assertIsNone(hold.offer(_reading(74.0, stable=True), 5))
        self.assertFalse(hold.due(12))
        self.assertTrue(hold.due(13))

    def test_flush_keeps_a_lock_when_listening_stops(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(74.2, stable=True), 1))
        stored = hold.flush()
        self.assertIsNotNone(stored)
        self.assertIsNone(hold.flush())

    def test_same_weight_is_not_replaced_until_impedance_arrives(self):
        self.assertFalse(should_replace_reading(74.2, None, 74.2, None))
        self.assertTrue(should_replace_reading(74.2, None, 74.2, 500))
        self.assertTrue(should_replace_reading(74.2, 500, 75.0, 500))
        self.assertFalse(should_replace_reading(74.2, 500, 74.25, 510))


# 75.0 kg, divisor 10. 0x01 = kg locked. 0x24 = kg still measuring.
# Impedance bytes 0x1450 are 520.0 ohm.
_LOCKED_75_KG = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x01])
_LOCKED_75_KG_520_OHM = bytes([0x02, 0xEE, 0x14, 0x50, 0x00, 0x00, 0x01])
_MEASURING_75_KG = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x24])
_SCALE_ADDRESS = "AA:BB:CC:DD:EE:FF"


class _FrozenDateTime(datetime):
    """08:00 on a fixed day, the inclusive start of the default 08:00–10:00 window."""

    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        if tz is None:
            return datetime(2026, 10, 22, 8, 0)
        return datetime(2026, 10, 22, 8, 0, tzinfo=tz)


class _Device:
    def __init__(self, address: str = _SCALE_ADDRESS) -> None:
        self.address = address


class _Advertisement:
    def __init__(self, payload: bytes | None = None, *, broken: bool = False) -> None:
        self._payload = payload
        self._broken = broken
        self.service_data: dict[str, bytes] = {}

    @property
    def manufacturer_data(self):
        if self._broken:
            raise RuntimeError("bad packet")
        if self._payload is None:
            return {}
        return {0x00C0: self._payload}


class _RecordingScanner(BaseBleakScanner):
    """Bleak stand-in that enforces the real two-argument callback check."""

    created: list["_RecordingScanner"] = []
    scripts: list[list[tuple[object, object]]] = []
    before_start = None

    def __init__(self, detection_callback=None, **kwargs):  # noqa: ANN001
        super().__init__(detection_callback, None)
        self.detection_callback = detection_callback
        self.started = False
        self.stopped = False
        self.index = len(type(self).created)
        type(self).created.append(self)

    async def start(self) -> None:
        self.started = True
        hook = type(self).before_start
        if hook is not None:
            hook(self.index)
        script = type(self).scripts
        packets = script[self.index] if self.index < len(script) else []
        for device, advertisement in packets:
            self.detection_callback(device, advertisement)

    async def stop(self) -> None:
        self.stopped = True


class _StopRaises(_RecordingScanner):
    async def stop(self) -> None:
        self.stopped = True
        raise OSError("adapter reset")


class _AdapterDown(BaseBleakScanner):
    def __init__(self, detection_callback=None, **kwargs):  # noqa: ANN001
        super().__init__(detection_callback, None)

    async def start(self) -> None:
        raise OSError("adapter missing")

    async def stop(self) -> None:
        return None


def _reset_scanner() -> None:
    _RecordingScanner.created = []
    _RecordingScanner.scripts = []
    _RecordingScanner.before_start = None


def _packet(payload: bytes | None = None, *, broken: bool = False):
    return (_Device(), _Advertisement(payload, broken=broken))


def _run(coro):
    try:
        return asyncio.run(asyncio.wait_for(coro, timeout=2))
    except TimeoutError:
        scale_scan._stop.set()
        raise


def _measurements() -> list[Measurement]:
    db = get_session_factory()()
    try:
        return list(db.scalars(select(Measurement)).all())
    finally:
        db.close()


async def _end_when_idle(_seconds: float) -> None:
    scale_scan._stop.set()


class ScaleScanCallbackTests(unittest.TestCase):
    def setUp(self):
        _reset_scanner()
        scale_scan._stop.clear()

    def test_detection_callback_is_accepted_by_bleak(self):
        readings: list[ScaleReading] = []
        _RecordingScanner.scripts = [[_packet(_LOCKED_75_KG)]]

        async def run() -> None:
            with patch("bleak.BleakScanner", _RecordingScanner):
                await scale_scan._run_cycle(0, readings.append, lambda: True)

        _run(run())
        callback = _RecordingScanner.created[0].detection_callback
        self.assertEqual(len(inspect.signature(callback).parameters), 2)
        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0].weight_kg, 75.0)
        self.assertEqual(readings[0].scale_mac, _SCALE_ADDRESS)
        self.assertTrue(_RecordingScanner.created[0].started)
        self.assertTrue(_RecordingScanner.created[0].stopped)

    def test_star_args_callback_is_rejected(self):
        def on_advertisement(*args):  # noqa: ANN002
            del args

        class Scanner(BaseBleakScanner):
            async def start(self) -> None:
                return None

            async def stop(self) -> None:
                return None

        with self.assertRaises(TypeError) as caught:
            Scanner(on_advertisement, None)
        self.assertIn("2 parameters", str(caught.exception))

    def test_bad_packet_does_not_stop_the_cycle(self):
        readings: list[ScaleReading] = []
        _RecordingScanner.scripts = [[
            _packet(broken=True),
            _packet(None),
            _packet(_LOCKED_75_KG),
        ]]

        async def run() -> None:
            with patch("bleak.BleakScanner", _RecordingScanner):
                await scale_scan._run_cycle(0, readings.append, lambda: True)

        _run(run())
        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0].weight_kg, 75.0)
        self.assertTrue(_RecordingScanner.created[0].stopped)

    def test_stop_failure_does_not_raise(self):
        readings: list[ScaleReading] = []
        _RecordingScanner.scripts = [[_packet(_LOCKED_75_KG)]]

        async def run() -> None:
            with patch("bleak.BleakScanner", _StopRaises):
                await scale_scan._run_cycle(0, readings.append, lambda: True)

        _run(run())
        self.assertEqual(len(readings), 1)
        self.assertTrue(_RecordingScanner.created[0].stopped)

    def test_reading_handler_error_does_not_raise(self):
        _RecordingScanner.scripts = [[_packet(_LOCKED_75_KG)]]

        def fail(_reading: ScaleReading) -> None:
            raise RuntimeError("handler failed")

        async def run() -> None:
            with patch("bleak.BleakScanner", _RecordingScanner):
                await scale_scan._run_cycle(0, fail, lambda: True)

        logging.disable(logging.CRITICAL)
        try:
            _run(run())
        finally:
            logging.disable(logging.NOTSET)
        self.assertTrue(_RecordingScanner.created[0].stopped)


class ScaleScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_env = {
            "PA_DATA_DIR": os.environ.get("PA_DATA_DIR"),
            "PA_TIMEZONE": os.environ.get("PA_TIMEZONE"),
            "PA_SCALE_SCAN_ENABLED": os.environ.get("PA_SCALE_SCAN_ENABLED"),
            "PA_SCALE_LISTEN_START_HOUR": os.environ.get("PA_SCALE_LISTEN_START_HOUR"),
            "PA_SCALE_LISTEN_END_HOUR": os.environ.get("PA_SCALE_LISTEN_END_HOUR"),
        }
        os.environ["PA_DATA_DIR"] = self._tmp.name
        os.environ["PA_TIMEZONE"] = "Europe/Berlin"
        os.environ["PA_SCALE_SCAN_ENABLED"] = "true"
        os.environ["PA_SCALE_LISTEN_START_HOUR"] = "8"
        os.environ["PA_SCALE_LISTEN_END_HOUR"] = "10"
        get_settings.cache_clear()
        reset_engine_for_tests()
        init_db()
        db = get_session_factory()()
        try:
            db.execute(delete(Measurement))
            db.commit()
        finally:
            db.close()
        scale_scan.set_scale_mode("auto")
        scale_scan._stop.clear()
        scale_scan._state.update(
            enabled=True,
            phase="idle",
            detail="",
            recorded_today=False,
            window="08:00-10:00",
            start_hour=8,
            end_hour=10,
            last_weight_kg=None,
            last_error=None,
        )
        _reset_scanner()
        self._patches = [
            patch("server.modules.health.scale_scan.datetime", _FrozenDateTime),
            patch.object(scale_scan, "_CYCLE_SECONDS", 0),
            patch.object(scale_scan, "_RESTART_PAUSE_SECONDS", 0),
            patch.object(scale_scan, "_SETTLE_SECONDS", 30),
        ]
        for item in self._patches:
            item.start()

    def tearDown(self):
        scale_scan._stop.set()
        for item in getattr(self, "_patches", []):
            item.stop()
        reset_engine_for_tests()
        for key, old in getattr(self, "_old_env", {}).items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        get_settings.cache_clear()
        if getattr(self, "_tmp", None) is not None:
            self._tmp.cleanup()
        scale_scan._stop.clear()

    def _assert_closed(self, count: int) -> None:
        self.assertEqual(len(_RecordingScanner.created), count)
        for scanner in _RecordingScanner.created:
            self.assertTrue(scanner.started)
            self.assertTrue(scanner.stopped)

    def test_auto_scan_stores_one_reading_and_stops(self):
        _RecordingScanner.scripts = [[_packet(_LOCKED_75_KG_520_OHM)]]

        async def run() -> None:
            with (
                patch("bleak.BleakScanner", _RecordingScanner),
                patch.object(scale_scan, "_wait", _end_when_idle),
                self.assertNoLogs("server.modules.health.scale_scan", level="WARNING"),
            ):
                await scale_scan._serve()

        _run(run())
        self._assert_closed(1)
        rows = _measurements()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].weight_kg, 75.0)
        self.assertAlmostEqual(rows[0].impedance_ohm, 520.0)
        self.assertEqual(rows[0].scale_mac, _SCALE_ADDRESS)
        self.assertEqual(rows[0].client_id, "pi-scale-2026-10-22")
        status = scale_scan.scale_status()
        self.assertEqual(status["phase"], "recorded")
        self.assertIsNone(status["last_error"])
        self.assertIn("75.0", status["detail"])
        self.assertNotIn("callback", status["detail"])

    def test_discovery_restarts_until_impedance_arrives(self):
        rows_before_followup: list[int] = []

        def before_start(index: int) -> None:
            if index >= 2:
                scale_scan._stop.set()
            if index == 1:
                rows_before_followup.append(len(_measurements()))

        _RecordingScanner.before_start = before_start
        _RecordingScanner.scripts = [
            [_packet(_LOCKED_75_KG)],
            [_packet(_LOCKED_75_KG_520_OHM)],
        ]

        async def run() -> None:
            with (
                patch("bleak.BleakScanner", _RecordingScanner),
                self.assertNoLogs("server.modules.health.scale_scan", level="WARNING"),
            ):
                await scale_scan._scan_while_requested()

        _run(run())
        self.assertEqual(rows_before_followup, [0])
        self._assert_closed(2)
        rows = _measurements()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].weight_kg, 75.0)
        self.assertAlmostEqual(rows[0].impedance_ohm, 520.0)
        self.assertIn("520", scale_scan.scale_status()["detail"])

    def test_manual_mode_keeps_listening_after_a_store(self):
        scale_scan.set_scale_mode("on")

        def before_start(index: int) -> None:
            if index >= 1:
                scale_scan._stop.set()

        _RecordingScanner.before_start = before_start
        _RecordingScanner.scripts = [[_packet(_LOCKED_75_KG_520_OHM)]]

        async def run() -> None:
            with patch("bleak.BleakScanner", _RecordingScanner):
                await scale_scan._scan_while_requested()

        _run(run())
        self._assert_closed(2)
        self.assertEqual(len(_measurements()), 1)
        self.assertIn("Still listening", scale_scan.scale_status()["detail"])

    def test_unstable_packet_is_not_stored(self):
        def before_start(index: int) -> None:
            if index >= 1:
                scale_scan._stop.set()

        _RecordingScanner.before_start = before_start
        _RecordingScanner.scripts = [[_packet(_MEASURING_75_KG)]]

        async def run() -> None:
            with patch("bleak.BleakScanner", _RecordingScanner):
                await scale_scan._scan_while_requested()

        _run(run())
        self._assert_closed(2)
        self.assertEqual(_measurements(), [])
        self.assertNotEqual(scale_scan.scale_status()["phase"], "recorded")

    def test_adapter_failure_is_reported_and_does_not_crash(self):
        async def run() -> None:
            with (
                patch("bleak.BleakScanner", _AdapterDown),
                patch.object(scale_scan, "_wait", _end_when_idle),
                self.assertLogs("server.modules.health.scale_scan", level="WARNING") as captured,
            ):
                await scale_scan._serve()
            self.assertTrue(any("adapter missing" in line for line in captured.output))

        _run(run())
        self.assertEqual(_measurements(), [])
        status = scale_scan.scale_status()
        self.assertEqual(status["phase"], "error")
        self.assertIn("adapter missing", status["detail"])
        self.assertIn("adapter missing", status["last_error"])

    def test_absent_file_uses_settings_and_auto_uses_the_saved_window(self):
        os.environ["PA_SCALE_LISTEN_START_HOUR"] = "6"
        os.environ["PA_SCALE_LISTEN_END_HOUR"] = "7"
        get_settings.cache_clear()
        data_dir = Path(get_settings().data_dir)
        self.assertFalse((data_dir / "scale_window.json").is_file())
        self.assertEqual(scale_scan.read_scale_window(), (6, 7))
        self.assertFalse(scale_scan._listen_context()["listening"])

        scale_scan.set_scale_window(8, 10)
        saved = json.loads((data_dir / "scale_window.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, {"start_hour": 8, "end_hour": 10})
        self.assertTrue((data_dir / "scale_mode.json").parent == (data_dir / "scale_window.json").parent)
        ctx = scale_scan._listen_context()
        self.assertEqual(ctx["mode"], "auto")
        self.assertTrue(ctx["listening"])
        self.assertEqual(ctx["window"], "08:00-10:00")
        status = scale_scan.scale_status()
        self.assertEqual(status["start_hour"], 8)
        self.assertEqual(status["end_hour"], 10)
        self.assertEqual(status["window"], "08:00-10:00")
        self.assertIsInstance(status["start_hour"], int)
        self.assertIsInstance(status["end_hour"], int)

    def test_saved_window_outside_the_hour_does_not_scan(self):
        scale_scan.set_scale_window(11, 14)
        _RecordingScanner.scripts = [[_packet(_LOCKED_75_KG_520_OHM)]]

        async def run() -> None:
            with (
                patch("bleak.BleakScanner", _RecordingScanner),
                patch.object(scale_scan, "_wait", _end_when_idle),
            ):
                await scale_scan._serve()

        _run(run())
        self.assertEqual(_RecordingScanner.created, [])
        self.assertEqual(_measurements(), [])
        status = scale_scan.scale_status()
        self.assertEqual(status["mode"], "auto")
        self.assertEqual(status["phase"], "outside")
        self.assertEqual(status["start_hour"], 11)
        self.assertEqual(status["end_hour"], 14)
        self.assertEqual(status["window"], "11:00-14:00")
        self.assertIn("11:00-14:00", status["detail"])

    def test_auto_stops_for_the_day_once_today_is_stored(self):
        scale_scan.set_scale_window(8, 10)
        db = get_session_factory()()
        try:
            db.add(
                Measurement(
                    client_id="already-today",
                    measured_at=datetime(2026, 10, 22, 8, 5, tzinfo=ZoneInfo("Europe/Berlin")),
                    weight_kg=74.0,
                    unit="kg",
                )
            )
            db.commit()
        finally:
            db.close()
        _RecordingScanner.scripts = [[_packet(_LOCKED_75_KG_520_OHM)]]

        async def run() -> None:
            with (
                patch("bleak.BleakScanner", _RecordingScanner),
                patch.object(scale_scan, "_wait", _end_when_idle),
            ):
                await scale_scan._serve()

        _run(run())
        self.assertEqual(_RecordingScanner.created, [])
        self.assertEqual(len(_measurements()), 1)
        status = scale_scan.scale_status()
        self.assertEqual(status["phase"], "recorded")
        self.assertTrue(status["recorded_today"])
        self.assertEqual(status["mode"], "auto")

        scale_scan._stop.clear()
        scale_scan.set_scale_mode("on")
        self.assertTrue(scale_scan._listen_context()["listening"])

    def test_invalid_window_is_not_stored(self):
        for start_hour, end_hour in ((10, 10), (14, 8), (-1, 5), (8, 24), (True, 10)):
            with self.assertRaises(ValueError):
                scale_scan.set_scale_window(start_hour, end_hour)
        self.assertFalse((Path(get_settings().data_dir) / "scale_window.json").is_file())

    def test_settings_default_window_is_eight_to_ten(self):
        os.environ.pop("PA_SCALE_LISTEN_START_HOUR", None)
        os.environ.pop("PA_SCALE_LISTEN_END_HOUR", None)
        get_settings.cache_clear()
        settings = get_settings()
        self.assertEqual(settings.scale_listen_start_hour, 8)
        self.assertEqual(settings.scale_listen_end_hour, 10)
        self.assertEqual(scale_scan.read_scale_window(), (8, 10))
        status = scale_scan.scale_status()
        self.assertEqual(status["window"], "08:00-10:00")


class ScaleWindowApiTests(unittest.TestCase):
    def setUp(self):
        self.client = None
        self._tmp = tempfile.TemporaryDirectory()
        self._old_env = {
            "PA_DATA_DIR": os.environ.get("PA_DATA_DIR"),
            "PA_TIMEZONE": os.environ.get("PA_TIMEZONE"),
            "PA_SCALE_LISTEN_START_HOUR": os.environ.get("PA_SCALE_LISTEN_START_HOUR"),
            "PA_SCALE_LISTEN_END_HOUR": os.environ.get("PA_SCALE_LISTEN_END_HOUR"),
        }
        os.environ["PA_DATA_DIR"] = self._tmp.name
        os.environ["PA_TIMEZONE"] = "Europe/Berlin"
        os.environ.pop("PA_SCALE_LISTEN_START_HOUR", None)
        os.environ.pop("PA_SCALE_LISTEN_END_HOUR", None)
        get_settings.cache_clear()
        scale_scan._state.update(
            enabled=True,
            phase="idle",
            detail="",
            recorded_today=False,
            window="08:00-10:00",
            start_hour=8,
            end_hour=10,
            last_weight_kg=None,
            last_error=None,
        )
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        if self.client is not None:
            self.client.__exit__(None, None, None)
        for key, old in self._old_env.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        get_settings.cache_clear()
        self._tmp.cleanup()

    def test_get_reports_default_window_without_a_file(self):
        res = self.client.get("/api/scale")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["start_hour"], 8)
        self.assertEqual(body["end_hour"], 10)
        self.assertEqual(body["window"], "08:00-10:00")
        self.assertIsInstance(body["start_hour"], int)
        self.assertIsInstance(body["end_hour"], int)
        self.assertFalse((Path(get_settings().data_dir) / "scale_window.json").exists())

    def test_post_persists_window_beside_scale_mode(self):
        mode = self.client.post("/api/scale/mode", json={"action": "auto"})
        self.assertEqual(mode.status_code, 200)
        saved = self.client.post("/api/scale/window", json={"start_hour": 7, "end_hour": 11})
        self.assertEqual(saved.status_code, 200)
        body = saved.json()
        self.assertEqual(body["start_hour"], 7)
        self.assertEqual(body["end_hour"], 11)
        self.assertEqual(body["window"], "07:00-11:00")
        self.assertEqual(body["mode"], "auto")
        data_dir = Path(get_settings().data_dir)
        self.assertTrue((data_dir / "scale_mode.json").is_file())
        on_disk = json.loads((data_dir / "scale_window.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, {"start_hour": 7, "end_hour": 11})
        again = self.client.get("/api/scale")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["start_hour"], 7)
        self.assertEqual(again.json()["end_hour"], 11)
        self.assertEqual(again.json()["window"], "07:00-11:00")

    def test_post_rejects_end_not_after_start(self):
        for body in ({"start_hour": 10, "end_hour": 10}, {"start_hour": 12, "end_hour": 8}):
            res = self.client.post("/api/scale/window", json=body)
            self.assertEqual(res.status_code, 422, body)
        self.assertFalse((Path(get_settings().data_dir) / "scale_window.json").exists())

    def test_post_rejects_hours_outside_0_23(self):
        for body in (
            {"start_hour": -1, "end_hour": 10},
            {"start_hour": 8, "end_hour": 24},
            {"start_hour": 25, "end_hour": 26},
            {"start_hour": 8.5, "end_hour": 10},
        ):
            res = self.client.post("/api/scale/window", json=body)
            self.assertEqual(res.status_code, 422, body)
        self.assertFalse((Path(get_settings().data_dir) / "scale_window.json").exists())


class OkokParserTests(unittest.TestCase):
    def test_c0_locked_kg(self):
        # 75.0 kg, divider 10, kg, stable. Company id low byte is C0.
        payload = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x01])
        reading = parse_manufacturer_data(0x00C0, payload)
        self.assertIsNotNone(reading)
        assert reading is not None
        self.assertAlmostEqual(reading.weight_kg, 75.0)
        self.assertTrue(reading.stable)
        self.assertEqual(reading.unit, "kg")
        self.assertEqual(reading.protocol, "C0")

    def test_unstable_c0_is_not_stable(self):
        # 0x24 = kg measuring (not locked): bit0 clear, divisor 10, unit kg.
        payload = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x24])
        reading = parse_c0_payload(payload)
        self.assertIsNotNone(reading)
        assert reading is not None
        self.assertFalse(reading.stable)

    def test_advertisement_uses_device_address_when_mac_missing(self):
        payload = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x01])
        reading = reading_from_advertisement(
            "AA:BB:CC:DD:EE:FF",
            {0x00C0: payload},
        )
        self.assertIsNotNone(reading)
        assert reading is not None
        self.assertEqual(reading.scale_mac, "AA:BB:CC:DD:EE:FF")

    def test_rejects_zero_weight(self):
        payload = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01])
        self.assertIsNone(parse_c0_payload(payload))


if __name__ == "__main__":
    unittest.main()
