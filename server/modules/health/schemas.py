from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from server.modules.health.targets import composition_amounts, normalize_activity


class NutritionOut(BaseModel):
    activity_level: str = "moderate"
    activity_factor: float = 1.55
    target_fat_pct: Optional[float] = None
    meals_per_day: int = 3
    bmr: Optional[float] = None
    target_calories: Optional[int] = None
    protein_g: Optional[int] = None
    fiber_g: Optional[int] = None
    per_meal_calories: Optional[float] = None
    per_meal_protein_g: Optional[float] = None
    per_meal_fiber_g: Optional[float] = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    height_cm: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    activity_level: str = "moderate"
    target_fat_pct: Optional[float] = None
    meals_per_day: int = 3
    updated_at: Optional[datetime] = None
    is_complete: bool = False
    nutrition: Optional[NutritionOut] = None


class ProfileUpdate(BaseModel):
    name: str = ""
    height_cm: Optional[float] = Field(default=None, gt=0, lt=300)
    age: Optional[int] = Field(default=None, ge=1, le=120)
    sex: Optional[str] = None  # male | female
    activity_level: str = "moderate"
    target_fat_pct: Optional[float] = Field(default=None, ge=2, le=70)
    meals_per_day: int = Field(default=3, ge=1, le=8)

    @field_validator("activity_level")
    @classmethod
    def check_activity(cls, value: str) -> str:
        return normalize_activity(value)


class MeasurementIn(BaseModel):
    client_id: str
    measured_at: datetime
    weight_kg: float = Field(gt=0, lt=500)
    impedance_ohm: Optional[float] = Field(default=None, ge=0)
    unit: str = "kg"
    scale_mac: Optional[str] = None
    raw_hex: Optional[str] = None


class MeasurementUpdate(BaseModel):
    measured_at: Optional[datetime] = None
    weight_kg: Optional[float] = Field(default=None, gt=0, lt=500)
    impedance_ohm: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None


class MeasurementBatchIn(BaseModel):
    measurements: List[MeasurementIn]


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: str
    measured_at: datetime
    weight_kg: float
    impedance_ohm: Optional[float] = None
    unit: str
    scale_mac: Optional[str] = None
    raw_hex: Optional[str] = None
    bmi: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    water_pct: Optional[float] = None
    bone_mass_kg: Optional[float] = None
    visceral_fat: Optional[float] = None
    bmr: Optional[float] = None
    body_age: Optional[float] = None
    body_fat_kg: Optional[float] = None
    muscle_pct: Optional[float] = None
    water_kg: Optional[float] = None
    bone_pct: Optional[float] = None
    created_at: Optional[datetime] = None

    @model_validator(mode="after")
    def fill_dual_units(self) -> MeasurementOut:
        amounts = composition_amounts(
            self.weight_kg,
            self.body_fat_pct,
            self.muscle_mass_kg,
            self.water_pct,
            self.bone_mass_kg,
        )
        self.body_fat_kg = amounts["body_fat_kg"]
        self.muscle_pct = amounts["muscle_pct"]
        self.water_kg = amounts["water_kg"]
        self.bone_pct = amounts["bone_pct"]
        return self


class IngestResult(BaseModel):
    created: int
    skipped: int
    ids: List[int]


class StatsOut(BaseModel):
    count: int
    latest: Optional[MeasurementOut] = None
    avg_weight_7d: Optional[float] = None
    avg_weight_30d: Optional[float] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None
    weight_delta_7d: Optional[float] = None
    profile_complete: bool = False
    nutrition: Optional[NutritionOut] = None


IngestPayload = Union[MeasurementIn, MeasurementBatchIn, List[MeasurementIn]]


class FoodHit(BaseModel):
    name: str
    source: str  # ciqual | off
    source_id: str
    kcal_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    fiber_100g: float


class FoodSearchOut(BaseModel):
    foods: List[FoodHit]


class ParseIn(BaseModel):
    text: str


class ParsedItem(BaseModel):
    name: str
    grams: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    source: str  # ciqual | off | manual
    source_id: Optional[str] = None


class ParseOut(BaseModel):
    items: List[ParsedItem]


class MealItemIn(BaseModel):
    name: str = Field(min_length=1)
    grams: float = Field(ge=0)
    kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float = Field(ge=0)
    source: str = Field(pattern="^(ciqual|off|manual)$")
    source_id: Optional[str] = None


class MealItemOut(BaseModel):
    id: int
    name: str
    grams: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    source: str
    source_id: Optional[str] = None


class MealCreate(BaseModel):
    eaten_at: Optional[datetime] = None
    note: str = ""
    source: str = Field(pattern="^(text|barcode|photo)$")
    items: List[MealItemIn] = Field(default_factory=list)


class MealUpdate(BaseModel):
    eaten_at: Optional[datetime] = None
    note: str = ""
    items: List[MealItemIn] = Field(default_factory=list)


class MealOut(BaseModel):
    id: int
    eaten_at: datetime
    note: str = ""
    source: str
    created_at: datetime
    items: List[MealItemOut]


class MealListOut(BaseModel):
    meals: List[MealOut]


class MacroTotals(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float


class DayTargets(BaseModel):
    target_calories: Optional[float] = None
    protein_g: Optional[float] = None
    fiber_g: Optional[float] = None


class MealSummaryOut(BaseModel):
    day: str
    totals: MacroTotals
    targets: Optional[DayTargets] = None
    meals: List[MealOut]
