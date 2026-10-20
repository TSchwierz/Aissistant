"""Meal logging API.

Each test points PA_DATA_DIR at a temporary directory and drops the cached
health engine so health.db is isolated from the user's data directory.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from server.config import get_settings
from server.modules.health.database import get_session_factory, init_db, reset_engine_for_tests
from server.modules.health.models import FoodGeneric, FoodProduct, Meal
from server.modules.health.router import router


def _meal_item(**overrides):
    item = {
        "name": "Banane",
        "grams": 100,
        "kcal": 89.0,
        "protein_g": 1.1,
        "carbs_g": 20.0,
        "fat_g": 0.3,
        "fiber_g": 2.6,
        "source": "ciqual",
        "source_id": "banane",
    }
    item.update(overrides)
    return item


class MealApiTests(unittest.TestCase):
    def setUp(self):
        self.client = None
        self._tmp = None
        self._old_data_dir = os.environ.get("PA_DATA_DIR")
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["PA_DATA_DIR"] = self._tmp.name
        get_settings.cache_clear()
        reset_engine_for_tests()
        init_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        if self.client is not None:
            self.client.__exit__(None, None, None)
        reset_engine_for_tests()
        if self._old_data_dir is None:
            os.environ.pop("PA_DATA_DIR", None)
        else:
            os.environ["PA_DATA_DIR"] = self._old_data_dir
        get_settings.cache_clear()
        if self._tmp is not None:
            self._tmp.cleanup()

    def _session(self):
        return get_session_factory()()

    def test_parse_does_not_insert_meal(self):
        def fake_complete(system, user, settings=None):
            return json.dumps(
                [{"query_fr": "Banane", "query_user": "banana", "grams": 100}]
            )

        def offline(*args, **kwargs):
            raise AssertionError("generic parse must not call Open Food Facts")

        with (
            patch("server.modules.news.providers.complete_text", fake_complete),
            patch("server.modules.health.nutrition.off_get", offline),
        ):
            response = self.client.post("/api/nutrition/parse", json={"text": "a banana"})
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "ciqual")
        self.assertEqual(items[0]["source_id"], "banane")
        self.assertGreater(items[0]["kcal"], 0)
        db = self._session()
        try:
            generic = db.scalar(select(FoodGeneric).where(FoodGeneric.code == "banane"))
            self.assertIsNotNone(generic)
            self.assertEqual(items[0]["kcal"], round(generic.kcal_100g, 1))
            count = db.scalar(select(func.count()).select_from(Meal))
            self.assertEqual(count, 0)
        finally:
            db.close()

    def test_confirm_inserts_and_summary_matches_item(self):
        created = self.client.post(
            "/api/meals",
            json={
                "eaten_at": "2026-10-20T00:30:00+02:00",
                "note": "breakfast",
                "source": "text",
                "items": [_meal_item()],
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        saved = created.json()
        self.assertIsInstance(saved["id"], int)
        self.assertIsInstance(saved["items"][0]["id"], int)
        saved_item = saved["items"][0]

        listed = self.client.get("/api/meals", params={"day": "2026-10-20"})
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()["meals"]), 1)

        summary = self.client.get("/api/meals/summary", params={"day": "2026-10-20"})
        self.assertEqual(summary.status_code, 200, summary.text)
        data = summary.json()
        totals = data["totals"]
        for key in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"):
            self.assertEqual(totals[key], round(saved_item[key], 1))
        targets = data["targets"]
        self.assertTrue(targets is None or isinstance(targets, dict))
        if isinstance(targets, dict):
            self.assertIn("target_calories", targets)
            self.assertIn("protein_g", targets)
            self.assertIn("fiber_g", targets)
        self.assertEqual(len(data["meals"]), 1)

    def test_banane_alias_finds_banana(self):
        def offline(*args, **kwargs):
            raise RuntimeError("network disabled")

        with patch("server.modules.health.nutrition.off_get", offline):
            response = self.client.get("/api/foods/search", params={"q": "Banane"})
        self.assertEqual(response.status_code, 200, response.text)
        foods = response.json()["foods"]
        banana = next(
            (
                food
                for food in foods
                if food["source"] == "ciqual" and food["source_id"] == "banane"
            ),
            None,
        )
        self.assertIsNotNone(banana)
        self.assertGreater(banana["kcal_100g"], 0)

    def test_barcode_second_call_uses_cache(self):
        calls = []
        product = {
            "status": 1,
            "product": {
                "code": "4006381333931",
                "product_name": "Test Yogurt",
                "brands": "DairyCo",
                "nutriments": {
                    "energy-kcal_100g": 87,
                    "proteins_100g": 4.2,
                    "carbohydrates_100g": 9.1,
                    "fat_100g": 3.5,
                    "fiber_100g": 0.2,
                },
            },
        }

        def fake_off_get(url, params=None):
            calls.append(url)
            return httpx.Response(200, json=product, request=httpx.Request("GET", url))

        with patch("server.modules.health.nutrition.off_get", fake_off_get):
            first = self.client.get("/api/foods/barcode/4006381333931")
            second = self.client.get("/api/foods/barcode/4006381333931")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(calls), 1)
        self.assertIn("4006381333931", calls[0])
        body = first.json()
        self.assertEqual(body["name"], "Test Yogurt")
        self.assertEqual(body["source"], "off")
        self.assertEqual(body["source_id"], "4006381333931")
        self.assertEqual(body["kcal_100g"], 87)
        self.assertEqual(body["protein_100g"], 4.2)
        self.assertEqual(body["carbs_100g"], 9.1)
        self.assertEqual(body["fat_100g"], 3.5)
        self.assertEqual(body["fiber_100g"], 0.2)
        self.assertEqual(second.json(), body)
        db = self._session()
        try:
            row = db.get(FoodProduct, "4006381333931")
            self.assertIsNotNone(row)
            self.assertEqual(row.kcal_100g, 87)
            self.assertEqual(row.protein_100g, 4.2)
        finally:
            db.close()

    def test_update_replaces_items_and_delete(self):
        created = self.client.post(
            "/api/meals",
            json={
                "eaten_at": "2026-10-20T08:00:00+02:00",
                "note": "lunch",
                "source": "text",
                "items": [_meal_item(), _meal_item(name="Pomme", kcal=52.0, source_id="pomme")],
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        meal_id = created.json()["id"]
        updated = self.client.put(
            f"/api/meals/{meal_id}",
            json={
                "note": "updated",
                "eaten_at": "2026-10-20T09:00:00+02:00",
                "items": [_meal_item(kcal=50.0, protein_g=2.0, carbs_g=8.0, fat_g=1.0, fiber_g=1.0)],
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        body = updated.json()
        self.assertEqual(body["note"], "updated")
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["kcal"], 50.0)
        summary = self.client.get("/api/meals/summary", params={"day": "2026-10-20"})
        self.assertEqual(summary.json()["totals"]["kcal"], 50.0)
        deleted = self.client.delete(f"/api/meals/{meal_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json(), {"deleted": True, "id": meal_id})
        missing = self.client.delete(f"/api/meals/{meal_id}")
        self.assertEqual(missing.status_code, 404)
        empty = self.client.get("/api/meals/summary", params={"day": "2026-10-20"})
        self.assertEqual(empty.json()["totals"]["kcal"], 0.0)

    def test_parse_image_rejects_missing_or_empty_file(self):
        missing = self.client.post("/api/nutrition/parse-image")
        self.assertEqual(missing.status_code, 400)
        empty = self.client.post(
            "/api/nutrition/parse-image",
            files={"image": ("meal.jpg", b"", "image/jpeg")},
        )
        self.assertEqual(empty.status_code, 400)


if __name__ == "__main__":
    unittest.main()
