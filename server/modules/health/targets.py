"""Daily calorie, protein, and fiber targets from profile + latest BMR."""

from __future__ import annotations

from typing import Optional

# Standard TDEE multipliers applied to the scale's existing BMR.
ACTIVITY_FACTORS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

# Grams of protein per kilogram of body weight.
PROTEIN_G_PER_KG: dict[str, float] = {
    "sedentary": 0.8,
    "light": 1.2,
    "moderate": 1.6,
    "active": 1.8,
    "very_active": 2.0,
}

# Institute of Medicine: 14 g fiber per 1,000 kcal.
FIBER_G_PER_1000_KCAL = 14.0


def normalize_activity(value: str | None) -> str:
    key = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "lightly_active": "light",
        "moderately_active": "moderate",
        "extra_active": "very_active",
    }
    key = aliases.get(key, key)
    if key not in ACTIVITY_FACTORS:
        return "moderate"
    return key


def composition_amounts(
    weight_kg: Optional[float],
    body_fat_pct: Optional[float],
    muscle_mass_kg: Optional[float],
    water_pct: Optional[float],
    bone_mass_kg: Optional[float],
) -> dict[str, Optional[float]]:
    """Fill the missing unit so fat, muscle, water, and bone have % and kg."""
    weight = float(weight_kg) if weight_kg else 0.0

    def pct_to_kg(pct: Optional[float]) -> Optional[float]:
        if pct is None or weight <= 0:
            return None
        return round(weight * float(pct) / 100.0, 2)

    def kg_to_pct(kg: Optional[float]) -> Optional[float]:
        if kg is None or weight <= 0:
            return None
        return round(float(kg) / weight * 100.0, 1)

    return {
        "body_fat_kg": pct_to_kg(body_fat_pct),
        "muscle_pct": kg_to_pct(muscle_mass_kg),
        "water_kg": pct_to_kg(water_pct),
        "bone_pct": kg_to_pct(bone_mass_kg),
    }


def _split(total: float | int | None, meals: int) -> Optional[float]:
    if total is None:
        return None
    return round(float(total) / meals, 1)


def daily_targets(
    *,
    activity_level: str | None,
    meals_per_day: int | None,
    target_fat_pct: float | None,
    sex: str | None,
    weight_kg: float | None,
    bmr: float | None,
) -> dict:
    level = normalize_activity(activity_level)
    meals = 3 if meals_per_day is None else int(meals_per_day)
    meals = max(1, min(8, meals))
    factor = ACTIVITY_FACTORS[level]
    calories = round(float(bmr) * factor) if bmr else None
    protein = (
        round(float(weight_kg) * PROTEIN_G_PER_KG[level])
        if weight_kg and weight_kg > 0
        else None
    )
    if calories:
        fiber: Optional[int] = round(calories * FIBER_G_PER_1000_KCAL / 1000.0)
    else:
        sex_norm = (sex or "").strip().lower()
        if sex_norm in ("male", "m"):
            fiber = 38
        elif sex_norm in ("female", "f"):
            fiber = 25
        else:
            fiber = None
    return {
        "activity_level": level,
        "activity_factor": factor,
        "target_fat_pct": target_fat_pct,
        "meals_per_day": meals,
        "bmr": round(float(bmr)) if bmr else None,
        "target_calories": calories,
        "protein_g": protein,
        "fiber_g": fiber,
        "per_meal_calories": _split(calories, meals),
        "per_meal_protein_g": _split(protein, meals),
        "per_meal_fiber_g": _split(fiber, meals),
    }
