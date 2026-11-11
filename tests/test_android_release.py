"""The phone updates from an APK published under PA_DATA_DIR/android."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from api_auth import TEST_API_KEY, bearer

from server.config import get_settings
from server.modules.calendar.db import reset_calendar_db_for_tests
from server.modules.health.database import reset_engine_for_tests
from server.modules.news.db import reset_news_db_for_tests
from server.routers.android_release import clear_release_cache

import server.modules.climate.runtime as climate_runtime

SECRET = b"TOP-SECRET-BYTES"


class AndroidReleaseTests(unittest.TestCase):
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
        clear_release_cache()
        reset_engine_for_tests()
        reset_calendar_db_for_tests()
        reset_news_db_for_tests()
        climate_runtime._runtime = None
        from server.app import create_app

        self.client = TestClient(create_app())
        self.client.__enter__()
        self._entered = True
        self.folder = Path(get_settings().data_dir) / "android"

    def tearDown(self):
        clear_release_cache()
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

    def test_missing_release_is_unavailable(self):
        release = self.client.get("/app/release", headers=bearer())
        self.assertEqual(release.status_code, 200)
        self.assertEqual(release.json(), {"available": False})
        apk = self.client.get("/app/apk", headers=bearer())
        self.assertEqual(apk.status_code, 404)
        self.assertEqual(apk.json().get("detail"), "No Android release is published")

    def test_missing_key_is_401(self):
        for path in ("/app/release", "/app/apk"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401, path)
            self.assertNotIn(TEST_API_KEY, response.text)

    def test_published_apk_is_served_and_described(self):
        payload = b"healthscale-apk-bytes"
        self._publish(payload, version_code=5, version_name="1.2.0")
        release = self.client.get("/app/release", headers=bearer())
        self.assertEqual(release.status_code, 200, release.text)
        body = release.json()
        self.assertEqual(body["available"], True)
        self.assertEqual(body["versionCode"], 5)
        self.assertEqual(body["versionName"], "1.2.0")
        self.assertEqual(body["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(body["bytes"], len(payload))
        self.assertEqual(body["apkPath"], "/app/apk")
        self.assertNotIn(str(self.folder), release.text)

        apk = self.client.get("/app/apk", headers=bearer())
        self.assertEqual(apk.status_code, 200, apk.text)
        self.assertEqual(apk.content, payload)
        self.assertEqual(apk.headers["content-type"], "application/vnd.android.package-archive")
        self.assertIn("HealthScale.apk", apk.headers["content-disposition"])

        again = self.client.get("/app/release", headers=bearer())
        self.assertEqual(again.json()["versionCode"], 5)

    def test_uppercase_sha_is_accepted(self):
        payload = b"signed-bytes"
        self._publish(payload, sha=hashlib.sha256(payload).hexdigest().upper())
        body = self.client.get("/app/release", headers=bearer()).json()
        self.assertEqual(body["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(self.client.get("/app/apk", headers=bearer()).content, payload)

    def test_bad_metadata_is_not_published(self):
        payload = b"apk-bytes"
        digest = hashlib.sha256(payload).hexdigest()
        cases = [
            {"sha256": "0" * 64},
            {"versionCode": True},
            {"versionCode": 0},
            {"versionCode": 2_147_483_648},
            {"versionName": "1.2.0\n"},
            {"versionName": ""},
            {"apk": "../secret.txt"},
            {"sha256": "zz" + digest[2:]},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                clear_release_cache()
                self._publish(payload, **overrides)
                release = self.client.get("/app/release", headers=bearer())
                self.assertEqual(release.json(), {"available": False})
                self.assertNotIn(digest, release.text)
                self.assertNotIn("apk-bytes", release.text)
                apk = self.client.get("/app/apk", headers=bearer())
                self.assertEqual(apk.status_code, 404)
                self.assertNotIn(b"apk-bytes", apk.content)

    def test_apk_field_cannot_escape_the_release_directory(self):
        secret = Path(get_settings().data_dir) / "secret.txt"
        secret.write_bytes(SECRET)
        self._publish(b"real-apk", apk="../secret.txt")
        response = self.client.get("/app/apk", headers=bearer())
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(SECRET, response.content)
        self.assertTrue(secret.is_file())

    def test_replaced_files_publish_the_new_version(self):
        self._publish(b"first", version_code=5, version_name="1.2.0")
        self.assertEqual(self.client.get("/app/release", headers=bearer()).json()["versionCode"], 5)
        self._publish(b"second", version_code=6, version_name="1.2.1")
        body = self.client.get("/app/release", headers=bearer()).json()
        self.assertEqual(body["versionCode"], 6)
        self.assertEqual(body["versionName"], "1.2.1")
        self.assertEqual(body["sha256"], hashlib.sha256(b"second").hexdigest())
        self.assertEqual(self.client.get("/app/apk", headers=bearer()).content, b"second")

    def _publish(self, payload: bytes, **overrides) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "HealthScale.apk").write_bytes(payload)
        meta = {
            "versionCode": 5,
            "versionName": "1.2.0",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "apk": "HealthScale.apk",
        }
        if "version_code" in overrides:
            overrides["versionCode"] = overrides.pop("version_code")
        if "version_name" in overrides:
            overrides["versionName"] = overrides.pop("version_name")
        meta.update(overrides)
        (self.folder / "release.json").write_text(json.dumps(meta), encoding="utf-8")
