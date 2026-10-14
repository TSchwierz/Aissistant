from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    height_cm: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    updated_at: Optional[datetime] = None
    is_complete: bool = False


class ProfileUpdate(BaseModel):
    name: str = ""
    height_cm: Optional[float] = Field(default=None, gt=0, lt=300)
    age: Optional[int] = Field(default=None, ge=1, le=120)
    sex: Optional[str] = None  # male | female


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
    created_at: Optional[datetime] = None


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


IngestPayload = Union[MeasurementIn, MeasurementBatchIn, List[MeasurementIn]]
