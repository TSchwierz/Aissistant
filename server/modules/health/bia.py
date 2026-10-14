"""OKOK / Chipsea BIA body-composition formulas.

Adapted from documented reverse-engineering of CsAlgoBuilder
(https://github.com/100nandoo/okok-bia-formulas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BodyMetrics:
    bmi: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    water_pct: Optional[float] = None
    bone_mass_kg: Optional[float] = None
    visceral_fat: Optional[float] = None
    bmr: Optional[float] = None
    body_age: Optional[float] = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round_half(value: float) -> float:
    return round(value * 2) / 2


def compute_metrics(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    impedance_ohm: Optional[float],
) -> BodyMetrics:
    """Compute body metrics. Missing impedance skips BIA fields; BMI still set."""
    if weight_kg <= 0 or height_cm <= 0:
        return BodyMetrics()

    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m * height_m), 2)

    if impedance_ohm is None or impedance_ohm <= 0 or age <= 0:
        return BodyMetrics(bmi=bmi)

    sex_norm = (sex or "").strip().lower()
    is_male = sex_norm in ("male", "m", "1")
    h, wt, z = float(height_cm), float(weight_kg), float(impedance_ohm)
    age_f = float(age)

    if is_male:
        raw_bfr = (
            (-0.3315 * h) + (0.6216 * wt) + (0.0183 * age_f) + (0.0085 * z) + 22.554
        ) / wt * 100
        vfr = (-0.2675 * h) + (0.42 * wt) + (0.1462 * age_f) + (0.0123 * z) + 13.9871
        water = (
            ((0.0939 * h) + (0.3758 * wt) - (0.0032 * age_f) - (0.006925 * z) + 0.097)
            / wt
        ) * 100
        slm = (0.2867 * h) + (0.3894 * wt) - (0.0408 * age_f) - (0.01235 * z) - 15.7665
        bmr = (7.5037 * h) + (13.1523 * wt) - (4.3376 * age_f) - (0.3486 * z) - 311.7751
        body_age = (-0.7471 * h) + (0.9161 * wt) + (0.4184 * age_f) + (0.0517 * z) + 54.2267
    else:
        raw_bfr = (
            (-0.3332 * h) + (0.7509 * wt) + (0.0196 * age_f) + (0.0072 * z) + 22.7193
        ) / wt * 100
        vfr = (-0.1651 * h) + (0.2628 * wt) + (0.0649 * age_f) + (0.0024 * z) + 12.3445
        water = (
            ((0.0877 * h) + (0.2973 * wt) + (0.0128 * age_f) - (0.00603 * z) + 0.5175)
            / wt
        ) * 100
        slm = (0.3186 * h) + (0.1934 * wt) - (0.0206 * age_f) - (0.0132 * z) - 16.4556
        bmr = (7.5432 * h) + (9.9474 * wt) - (3.4382 * age_f) - (0.309 * z) - 288.2821
        body_age = (-1.1165 * h) + (1.5784 * wt) + (0.4615 * age_f) + (0.0415 * z) + 83.2548

    body_fat_pct = _clamp(raw_bfr, 5.0, 45.0)
    fat_mass = (body_fat_pct * wt) / 100.0
    muscle_mass = max(0.0, slm)
    bone_mass = _clamp(wt - fat_mass - muscle_mass, 1.0, 4.0)

    if age > 17:
        visceral = _clamp(_round_half(vfr), 1.0, 59.0)
        water_pct = _clamp(water, 20.0, 85.0)
    else:
        visceral = None
        water_pct = None

    body_age_clamped = _clamp(body_age, max(18.0, age_f - 10), min(80.0, age_f + 10))

    return BodyMetrics(
        bmi=bmi,
        body_fat_pct=round(body_fat_pct, 1),
        muscle_mass_kg=round(muscle_mass, 2),
        water_pct=round(water_pct, 1) if water_pct is not None else None,
        bone_mass_kg=round(bone_mass, 2),
        visceral_fat=visceral,
        bmr=round(max(0.0, bmr)),
        body_age=round(body_age_clamped),
    )
