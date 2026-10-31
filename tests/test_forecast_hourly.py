"""Hourly outside forecast: 24h window, unchanged 4h dashboard, no filled gaps.

Each test points PA_DATA_DIR at a temporary directory and rebuilds the climate
runtime so climate.db stays off the user's data directory. Providers are not
called.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from api_auth import TEST_API_KEY, bearer

from fastapi import FastAPI
from fastapi.testclient import TestClient
from zoneinfo import ZoneInfo

from server.config import get_settings
from server.modules.climate.api import FORECAST_WINDOW_HOURS, create_app
from server.modules.climate.config import load_config
from server.modules.climate.db import ForecastPoint, to_iso
from server.modules.climate.runtime import get_runtime
from server.modules.climate.weather import ProviderSnapshot, combine_forecasts

import server.modules.climate.runtime as climate_runtime

NOW = datetime(2026, 10, 30, 12, 40, tzinfo=timezone.utc)
FETCHED_EARLY = datetime(2026, 10, 30, 11, 0, tzinfo=timezone.utc)
FETCHED_LATE = datetime(2026, 10, 30, 12, 5, tzinfo=timezone.utc)

HOURLY_FIELDS = {
    "ts",
    "temperature_c",
    "humidity_pct",
    "condition",
    "condition_label",
    "precipitation_probability",
    "wind_kph",
    "provider_count",
    "fetched_at",
}


def _reset_runtime() -> None:
    climate_runtime._runtime = None


def _point(
    ts: datetime,
    temperature_c: float,
    *,
    condition: str = "clear",
    humidity_pct: float = 55.0,
    precipitation_probability: float = 10.0,
    wind_kph: float = 12.0,
    provider_count: int = 2,
) -> ForecastPoint:
    return ForecastPoint(
        ts=ts,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        condition=condition,
        precipitation_probability=precipitation_probability,
        wind_kph=wind_kph,
        provider_count=provider_count,
    )


class ForecastHourlyTests(unittest.TestCase):
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

    def test_default_forecast_hours_is_24(self):
        overlay = Path(self._tmp.name) / "empty.toml"
        overlay.write_text("# no weather table\n", encoding="utf-8")
        cfg = load_config(overlay)
        self.assertEqual(cfg.weather_forecast_hours, 24)

    def test_hourly_route_returns_24h_window_and_leaves_gaps(self):
        client = self._open()
        zone = ZoneInfo("Europe/Berlin")
        start = NOW.astimezone(zone).replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=24)
        gap = start + timedelta(hours=2)
        # One hour before the window, the current hour, a hole, then later hours.
        # The hour exactly 24h later is the exclusive end and is not returned.
        stored = {
            start - timedelta(hours=1): _point(start - timedelta(hours=1), 1.0),
            start: _point(start, 10.0, condition="clear", provider_count=2),
            start + timedelta(hours=1): _point(
                start + timedelta(hours=1), 11.0, condition="heavy_rain", provider_count=3
            ),
            start + timedelta(hours=3): _point(start + timedelta(hours=3), 13.0),
            start + timedelta(hours=4): _point(start + timedelta(hours=4), 14.0),
            start + timedelta(hours=5): _point(start + timedelta(hours=5), 15.0),
            start + timedelta(hours=23): _point(start + timedelta(hours=23), 20.0),
            end: _point(end, 99.0),
        }
        db = get_runtime().db
        early = [stored[start], stored[start + timedelta(hours=1)]]
        late = [point for ts, point in stored.items() if ts not in {start, start + timedelta(hours=1)}]
        db.upsert_forecast(early, fetched_at=FETCHED_EARLY)
        db.upsert_forecast(late, fetched_at=FETCHED_LATE)

        with patch("server.modules.climate.api.utc_now", return_value=NOW):
            response = client.get("/climate/outside/hourly")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["timezone"], "Europe/Berlin")
        self.assertEqual(body["window_hours"], 24)
        self.assertEqual(body["from"], to_iso(start))
        self.assertEqual(body["to"], to_iso(end))

        expected = [
            start,
            start + timedelta(hours=1),
            start + timedelta(hours=3),
            start + timedelta(hours=4),
            start + timedelta(hours=5),
            start + timedelta(hours=23),
        ]
        points = body["points"]
        self.assertEqual([point["ts"] for point in points], [to_iso(ts) for ts in expected])
        self.assertNotIn(to_iso(gap), [point["ts"] for point in points])
        self.assertNotEqual(len(points), 24)
        self.assertEqual([point["temperature_c"] for point in points], [10.0, 11.0, 13.0, 14.0, 15.0, 20.0])

        for point in points:
            self.assertTrue(HOURLY_FIELDS <= set(point))
        self.assertEqual(points[0]["fetched_at"], to_iso(FETCHED_EARLY))
        self.assertEqual(points[0]["condition"], "clear")
        self.assertEqual(points[0]["condition_label"], "clear")
        self.assertEqual(points[0]["humidity_pct"], 55.0)
        self.assertEqual(points[0]["precipitation_probability"], 10.0)
        self.assertEqual(points[0]["wind_kph"], 12.0)
        self.assertEqual(points[0]["provider_count"], 2)
        self.assertEqual(points[1]["fetched_at"], to_iso(FETCHED_EARLY))
        self.assertEqual(points[1]["condition_label"], "heavy rain")
        self.assertEqual(points[1]["provider_count"], 3)
        self.assertEqual(points[2]["fetched_at"], to_iso(FETCHED_LATE))

    def test_outside_keeps_four_hour_window_without_fetched_at(self):
        self.assertEqual(FORECAST_WINDOW_HOURS, 4)
        client = self._open()
        floor = NOW.replace(minute=0, second=0, microsecond=0)
        window_end = NOW + timedelta(hours=FORECAST_WINDOW_HOURS)
        # Hourly series with a hole at +2h. +5h is inside 24h and outside 4h.
        hours = [0, 1, 3, 4, 5, 23]
        points = [
            _point(floor + timedelta(hours=hour), 10.0 + hour, condition="cloudy")
            for hour in hours
        ]
        points.append(_point(floor - timedelta(hours=1), 0.0))
        get_runtime().db.upsert_forecast(points, fetched_at=FETCHED_LATE)

        with patch("server.modules.climate.api.utc_now", return_value=NOW):
            response = client.get("/climate/outside")
        self.assertEqual(response.status_code, 200, response.text)
        forecast = response.json()["forecast"]
        self.assertEqual(forecast["window_hours"], 4)
        self.assertIn("summary", forecast)
        self.assertIsNotNone(forecast["summary"])
        returned = forecast["points"]
        expected = [
            floor + timedelta(hours=hour)
            for hour in hours
            if floor <= floor + timedelta(hours=hour) <= window_end
        ]
        self.assertEqual([point["ts"] for point in returned], [to_iso(ts) for ts in expected])
        self.assertNotIn(to_iso(floor + timedelta(hours=2)), [point["ts"] for point in returned])
        self.assertNotIn(to_iso(floor + timedelta(hours=5)), [point["ts"] for point in returned])
        for point in returned:
            self.assertNotIn("fetched_at", point)
            self.assertIn("condition_label", point)

    def test_window_uses_settings_timezone_and_does_not_fill_gaps(self):
        os.environ["PA_TIMEZONE"] = "Asia/Kolkata"
        client = self._open()
        # 10:15 UTC is 15:45 in Kolkata, so the local hour starts at 09:30 UTC,
        # before the UTC hour. A UTC-hour floor would drop that point.
        moment = datetime(2026, 10, 30, 10, 15, tzinfo=timezone.utc)
        zone = ZoneInfo("Asia/Kolkata")
        start = moment.astimezone(zone).replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=24)
        self.assertEqual(start, datetime(2026, 10, 30, 9, 30, tzinfo=timezone.utc))
        gap = datetime(2026, 10, 30, 11, 0, tzinfo=timezone.utc)
        included = [
            start,
            datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc),
        ]
        excluded = [
            datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc),
            end,
            datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc),
        ]
        rows = [_point(ts, 8.0 + index) for index, ts in enumerate(included + excluded)]
        get_runtime().db.upsert_forecast(rows, fetched_at=FETCHED_LATE)

        with patch("server.modules.climate.api.utc_now", return_value=moment):
            response = client.get("/climate/outside/hourly")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["timezone"], "Asia/Kolkata")
        self.assertEqual(body["from"], to_iso(start))
        self.assertEqual(body["to"], to_iso(end))
        got = [point["ts"] for point in body["points"]]
        self.assertEqual(got, [to_iso(ts) for ts in included])
        self.assertNotIn(to_iso(gap), got)
        self.assertEqual(len(body["points"]), len(included))
        for point in body["points"]:
            self.assertIn("fetched_at", point)
            self.assertEqual(point["fetched_at"], to_iso(FETCHED_LATE))

    def test_three_hour_steps_are_not_expanded(self):
        start = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
        steps = [
            _point(start, 10.0, condition="clear"),
            _point(start + timedelta(hours=3), 11.0, condition="cloudy"),
        ]
        combined = combine_forecasts([ProviderSnapshot(name="openweathermap", forecast=steps)])
        self.assertEqual([point.ts for point in combined], [point.ts for point in steps])
        self.assertEqual(len(combined), 2)
