"""Daily targets and dual-unit body composition."""

import unittest

from server.modules.health.schemas import MeasurementOut
from server.modules.health.targets import composition_amounts, daily_targets


class TargetTests(unittest.TestCase):
    def test_calories_follow_bmr_and_activity(self):
        out = daily_targets(
            activity_level="moderate",
            meals_per_day=4,
            target_fat_pct=15,
            sex="male",
            weight_kg=80,
            bmr=1600,
        )
        self.assertEqual(out["activity_factor"], 1.55)
        self.assertEqual(out["target_calories"], round(1600 * 1.55))
        self.assertEqual(out["protein_g"], round(80 * 1.6))
        self.assertEqual(out["fiber_g"], round(out["target_calories"] * 14 / 1000))
        self.assertEqual(out["per_meal_calories"], round(out["target_calories"] / 4, 1))
        self.assertEqual(out["meals_per_day"], 4)
        self.assertEqual(out["target_fat_pct"], 15)

    def test_fiber_fallback_without_bmr(self):
        out = daily_targets(
            activity_level="sedentary",
            meals_per_day=3,
            target_fat_pct=None,
            sex="female",
            weight_kg=60,
            bmr=None,
        )
        self.assertIsNone(out["target_calories"])
        self.assertEqual(out["fiber_g"], 25)
        self.assertEqual(out["protein_g"], round(60 * 0.8))

    def test_composition_has_percent_and_mass(self):
        amounts = composition_amounts(80, 20, 32, 55, 3)
        self.assertEqual(amounts["body_fat_kg"], 16.0)
        self.assertEqual(amounts["muscle_pct"], 40.0)
        self.assertEqual(amounts["water_kg"], 44.0)
        self.assertEqual(amounts["bone_pct"], 3.8)

    def test_measurement_schema_fills_both_units(self):
        row = MeasurementOut(
            id=1,
            client_id="abc",
            measured_at="2026-10-16T08:00:00+02:00",
            weight_kg=80,
            unit="kg",
            body_fat_pct=20,
            muscle_mass_kg=32,
            water_pct=55,
            bone_mass_kg=3,
        )
        self.assertEqual(row.body_fat_kg, 16.0)
        self.assertEqual(row.muscle_pct, 40.0)
        self.assertEqual(row.water_kg, 44.0)
        self.assertEqual(row.bone_pct, 3.8)
