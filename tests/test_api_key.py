"""PA_API_KEY is required on every HTTP route, including mounted apps."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from api_auth import TEST_API_KEY, bearer

from server.config import get_settings
from server.modules.calendar.db import reset_calendar_db_for_tests
from server.modules.health.database import reset_engine_for_tests
from server.modules.news.db import reset_news_db_for_tests

import server.modules.climate.runtime as climate_runtime

PATHS = (
    "/health",
    "/briefing/morning",
    "/calendar/weeks",
    "/backup",
    "/climate/health",
    "/api/health",
    "/static/styles.css",
)


class ApiKeyTests(unittest.TestCase):
    def setUp(self):
        self.client = None
        self._entered = False
        self._tmp = tempfile.TemporaryDirectory()
        self._old = {
            "PA_DATA_DIR": os.environ.get("PA_DATA_DIR"),
            "PA_API_KEY": os.environ.get("PA_API_KEY"),
            "PA_EMBED_WORKERS": os.environ.get("PA_EMBED_WORKERS"),
            "PA_TIMEZONE": os.environ.get("PA_TIMEZONE"),
        }
        os.environ["PA_DATA_DIR"] = self._tmp.name
        os.environ["PA_API_KEY"] = TEST_API_KEY
        os.environ["PA_EMBED_WORKERS"] = "false"
        os.environ["PA_TIMEZONE"] = "Europe/Berlin"
        get_settings.cache_clear()
        reset_engine_for_tests()
        reset_calendar_db_for_tests()
        reset_news_db_for_tests()
        climate_runtime._runtime = None
        from server.app import create_app

        self.create_app = create_app

    def tearDown(self):
        if self._entered and self.client is not None:
            self.client.__exit__(None, None, None)
        reset_engine_for_tests()
        reset_calendar_db_for_tests()
        reset_news_db_for_tests()
        climate_runtime._runtime = None
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        self._tmp.cleanup()

    def _client(self):
        if self.client is None:
            from fastapi.testclient import TestClient

            get_settings.cache_clear()
            app = self.create_app()
            self.client = TestClient(app)
            self.client.__enter__()
            self._entered = True
        return self.client

    def test_empty_key_refuses_create_app(self):
        for blank in ("", "   "):
            with self.subTest(blank=repr(blank)):
                os.environ["PA_API_KEY"] = blank
                get_settings.cache_clear()
                with self.assertRaises(RuntimeError) as caught:
                    self.create_app()
                message = str(caught.exception)
                self.assertIn("PA_API_KEY", message)
                self.assertNotIn(TEST_API_KEY, message)

    def test_missing_header_is_401(self):
        client = self._client()
        for path in PATHS:
            res = client.get(path)
            self.assertEqual(res.status_code, 401, f"{path} {res.text[:180]}")
            self.assertNotIn(TEST_API_KEY, res.text)
            self.assertEqual(res.json().get("detail"), "Unauthorized")

    def test_wrong_key_is_401_and_not_echoed(self):
        client = self._client()
        wrong = "wrong-key-should-not-echo"
        for headers in (
            {"Authorization": f"Bearer {wrong}"},
            {"X-API-Token": wrong},
        ):
            res = client.get("/health", headers=headers)
            self.assertEqual(res.status_code, 401)
            self.assertNotIn(wrong, res.text)
            self.assertNotIn(wrong, " ".join(res.headers.values()))
            self.assertEqual(res.json().get("detail"), "Unauthorized")

    def test_bearer_works(self):
        client = self._client()
        for path in PATHS:
            res = client.get(path, headers=bearer())
            self.assertEqual(res.status_code, 200, f"{path} {res.text[:180]}")

    def test_x_api_token_works(self):
        client = self._client()
        headers = {"X-API-Token": TEST_API_KEY}
        for path in ("/health", "/climate/health", "/api/health"):
            res = client.get(path, headers=headers)
            self.assertEqual(res.status_code, 200, f"{path} {res.text[:180]}")

    def test_query_string_does_not_authenticate(self):
        client = self._client()
        params = {
            "api_key": TEST_API_KEY,
            "token": TEST_API_KEY,
            "access_token": TEST_API_KEY,
        }
        for path in ("/health", "/climate/health", "/api/health", "/backup"):
            res = client.get(path, params=params)
            self.assertEqual(res.status_code, 401, path)
            self.assertNotIn(TEST_API_KEY, res.text)
            self.assertEqual(res.json().get("detail"), "Unauthorized")
