"""Indoor climate comes from a DHT11, or from an explicit sensor failure.

Generated readings are not stored and are not returned. Rows left by the old
mock sampler stay in the database with source 'legacy' and are hidden.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from api_auth import TEST_API_KEY, bearer

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.config import get_settings
from server.modules.climate.api import create_app
from server.modules.climate.collector import default_settings, read_and_store
from server.modules.climate.config import load_config
from server.modules.climate.db import ClimateDB, OutsideReading, to_iso
from server.modules.climate.runtime import get_runtime
from server.modules.climate.sensor import Reading, SensorError, create_sensor

import server.modules.climate.runtime as climate_runtime
import server.modules.climate.sensor as sensor_module


def _reset_runtime() -> None:
    climate_runtime._runtime = None


class _Sensor:
    def __init__(self, reading: Reading | None = None, error: str | None = None) -> None:
        self.reading = reading
        self.error = error

    def read(self) -> Reading:
        if self.error:
            raise SensorError(self.error)
        assert self.reading is not None
        return self.reading


class ClimateSensorTests(unittest.TestCase):
    def setUp(self):
        self.client = None
        self._tmp = tempfile.TemporaryDirectory()
        self._old_env = {
            "PA_DATA_DIR": os.environ.get("PA_DATA_DIR"),
            "PA_TIMEZONE": os.environ.get("PA_TIMEZONE"),
            "PA_API_KEY": os.environ.get("PA_API_KEY"),
        }
        os.environ["PA_DATA_DIR"] = self._tmp.name
        os.environ["PA_TIMEZONE"] = "Europe/Berlin"
        os.environ["PA_API_KEY"] = TEST_API_KEY
        get_settings.cache_clear()
        _reset_runtime()

    def tearDown(self):
        if self.client is not None:
            self.client.__exit__(None, None, None)
        _reset_runtime()
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        self._tmp.cleanup()

    def _open(self) -> TestClient:
        if self.client is not None:
            self.client.__exit__(None, None, None)
        get_settings.cache_clear()
        _reset_runtime()
        parent = FastAPI()
        parent.mount("/climate", create_app(load_config()))
        self.client = TestClient(parent, headers=bearer())
        self.client.__enter__()
        return self.client

    def test_mock_switch_is_gone(self):
        self.assertFalse(hasattr(sensor_module, "MockSensor"))
        overlay = Path(self._tmp.name) / "climate.toml"
        overlay.write_text(
            "[collector]\nmock_sensor = true\ngpio_pin = 17\n",
            encoding="utf-8",
        )
        cfg = load_config(overlay)
        self.assertEqual(cfg.gpio_pin, 17)
        self.assertFalse(hasattr(cfg, "mock_sensor"))
        with self.assertRaises(TypeError):
            create_sensor(mock=True, gpio_pin=23)  # type: ignore[call-arg]

    def test_missing_driver_names_the_pin_and_config_file(self):
        with patch.dict(sys.modules, {"board": None}):
            with self.assertRaises(SensorError) as caught:
                create_sensor(gpio_pin=23)
        message = str(caught.exception)
        self.assertIn("GPIO 23", message)
        self.assertIn("config.climate.toml", message)
        self.assertIn("adafruit-circuitpython-dht", message)

    def test_unknown_pin_is_an_error(self):
        board = ModuleType("board")
        board.D23 = object()
        dht = ModuleType("adafruit_dht")

        class _Device:
            def __init__(self, pin, use_pulseio=False):
                self.pin = pin

            def exit(self):
                pass

        dht.DHT11 = _Device
        with patch.dict(sys.modules, {"board": board, "adafruit_dht": dht}):
            with self.assertRaises(SensorError) as caught:
                create_sensor(gpio_pin=99)
        self.assertIn("GPIO 99", str(caught.exception))
        self.assertIn("config.climate.toml", str(caught.exception))

    def test_failed_read_stores_nothing_and_current_warns(self):
        client = self._open()
        db = get_runtime().db
        stored = read_and_store(db, _Sensor(error="The DHT11 read failed: checksum"), 23)
        self.assertIsNone(stored)
        self.assertIsNone(db.latest_measurement())
        body = client.get("/climate/current").json()
        self.assertIsNone(body["measurement"])
        self.assertFalse(body["sensor"]["ok"])
        self.assertIsNone(body["sensor"]["age_seconds"])
        self.assertIn("checksum", body["sensor"]["message"])
        self.assertEqual(body["sensor"]["gpio_pin"], 23)
        self.assertEqual(body["status"]["overall"], "offline")

    def test_successful_read_is_the_sensor_value(self):
        client = self._open()
        db = get_runtime().db
        stored = read_and_store(db, _Sensor(reading=Reading(19.5, 41.0)), 23)
        self.assertIsNotNone(stored)
        body = client.get("/climate/current").json()
        self.assertTrue(body["sensor"]["ok"])
        self.assertEqual(body["sensor"]["message"], "")
        self.assertGreaterEqual(body["sensor"]["age_seconds"], 0)
        self.assertLess(body["sensor"]["age_seconds"], 5)
        self.assertEqual(body["measurement"]["temperature_c"], 19.5)
        self.assertEqual(body["measurement"]["humidity_pct"], 41.0)
        self.assertEqual(body["status"]["overall"], "in_band")

    def test_stale_success_keeps_the_number_and_reports_age(self):
        client = self._open()
        db = get_runtime().db
        read_and_store(db, _Sensor(reading=Reading(19.5, 41.0)), 23)
        stale = to_iso(datetime.now(timezone.utc) - timedelta(hours=2))
        with db.connect() as conn:
            conn.execute(
                """
                UPDATE sensor_status
                SET last_success_at = ?, ok = 0, message = ?
                WHERE id = 1
                """,
                (stale, "The DHT11 read failed: checksum"),
            )
        body = client.get("/climate/current").json()
        self.assertEqual(body["measurement"]["temperature_c"], 19.5)
        self.assertEqual(body["measurement"]["humidity_pct"], 41.0)
        self.assertFalse(body["sensor"]["ok"])
        self.assertEqual(body["sensor"]["message"], "")
        self.assertGreaterEqual(body["sensor"]["age_seconds"], 2 * 60 * 60 - 5)
        self.assertLess(body["sensor"]["age_seconds"], 2 * 60 * 60 + 30)
        self.assertEqual(body["status"]["overall"], "in_band")

    def test_legacy_mock_rows_and_mock_outside_are_hidden(self):
        path = Path(self._tmp.name) / "climate.db"
        raw = sqlite3.connect(path)
        raw.execute(
            """
            CREATE TABLE measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                temperature_c REAL NOT NULL,
                humidity_pct REAL NOT NULL
            )
            """
        )
        raw.execute(
            "INSERT INTO measurements(ts, temperature_c, humidity_pct) VALUES (?, ?, ?)",
            ("2026-01-01T00:00:00Z", 21.5, 48.0),
        )
        raw.execute(
            "CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        raw.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('schema_version', '2')"
        )
        raw.commit()
        raw.close()

        client = self._open()
        db = get_runtime().db
        self.assertEqual(db.list_measurements(), [])
        history = client.get("/climate/measurements").json()
        self.assertEqual(history["count"], 0)

        db.insert_outside_reading(
            OutsideReading(
                ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
                temperature_c=12.0,
                humidity_pct=70.0,
                condition="cloudy",
                sources=["mock"],
                provider_count=1,
            )
        )
        self.assertEqual(db.latest_outside_reading().sources, ["mock"])
        db.init_schema(default_settings(load_config()))
        self.assertIsNone(db.latest_outside_reading())

    def test_current_warns_before_any_sample(self):
        client = self._open()
        body = client.get("/climate/current").json()
        self.assertIsNone(body["measurement"])
        self.assertFalse(body["sensor"]["ok"])
        self.assertIn("GPIO 23", body["sensor"]["message"])
        self.assertIn("config.climate.toml", body["sensor"]["message"])
        outside = client.get("/climate/outside").json()
        self.assertIn("Indoor sensor is not reporting", outside["comparison"]["ventilation"]["reason"])


if __name__ == "__main__":
    unittest.main()
