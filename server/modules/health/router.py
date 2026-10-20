"""Health Scale Hub HTTP routes — same paths as the standalone hub."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.modules.health import nutrition, services
from server.modules.health.database import get_db, init_db
from server.modules.health.models import Measurement  # noqa: F401 — register models
from server.modules.health.scale_scan import scale_status, set_scale_mode
from server.modules.health.schemas import (
    FoodSearchOut,
    IngestResult,
    MealCreate,
    MealListOut,
    MealOut,
    MealSummaryOut,
    MealUpdate,
    MeasurementBatchIn,
    MeasurementIn,
    MeasurementOut,
    MeasurementUpdate,
    NutritionOut,
    ParseIn,
    ParseOut,
    ProfileOut,
    ProfileUpdate,
    StatsOut,
)
from server.modules.health.targets import composition_amounts

MODULE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(MODULE_DIR / "templates"))

router = APIRouter(tags=["health-scale"])


def startup_health() -> None:
    """Init SQLite schema and ensure a default profile row exists."""
    init_db()
    db = next(get_db())
    try:
        services.get_or_create_profile(db)
    finally:
        db.close()


def mount_health(app: FastAPI) -> None:
    """Attach Health static files + API/dashboard routes to the unified app."""
    app.mount(
        "/static",
        StaticFiles(directory=str(MODULE_DIR / "static")),
        name="health-static",
    )
    app.include_router(router)


def _normalize_ingest(payload: Any) -> List[MeasurementIn]:
    if isinstance(payload, list):
        return [MeasurementIn.model_validate(x) for x in payload]
    if isinstance(payload, dict) and "measurements" in payload:
        batch = MeasurementBatchIn.model_validate(payload)
        return batch.measurements
    return [MeasurementIn.model_validate(payload)]


def _profile_out(profile, nutrition: dict | None = None) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        name=profile.name or "",
        height_cm=profile.height_cm,
        age=profile.age,
        sex=profile.sex,
        activity_level=getattr(profile, "activity_level", None) or "moderate",
        target_fat_pct=getattr(profile, "target_fat_pct", None),
        meals_per_day=getattr(profile, "meals_per_day", None) or 3,
        updated_at=profile.updated_at,
        is_complete=services.profile_is_complete(profile),
        nutrition=NutritionOut.model_validate(nutrition) if nutrition else None,
    )


@router.get("/api/health")
def api_health() -> dict:
    return {"status": "ok", "service": "health-scale-hub"}


class ScaleModeIn(BaseModel):
    action: str = Field(pattern="^(start|stop|auto)$")


@router.get("/api/scale")
def api_scale() -> dict:
    """Whether the Pi is listening for the morning scale broadcast."""
    return scale_status()


@router.post("/api/scale/mode")
def post_scale_mode(body: ScaleModeIn) -> dict:
    """Manual test control. ``start`` scans now, ``stop`` stays quiet, ``auto`` uses 06:00–12:00."""
    mode = {"start": "on", "stop": "off", "auto": "auto"}[body.action]
    set_scale_mode(mode)
    return scale_status()


@router.get("/api/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)) -> ProfileOut:
    raw = services.compute_stats(db)
    return _profile_out(services.get_or_create_profile(db), raw["nutrition"])


@router.put("/api/profile", response_model=ProfileOut)
def put_profile(body: ProfileUpdate, db: Session = Depends(get_db)) -> ProfileOut:
    profile = services.update_profile(db, body)
    raw = services.compute_stats(db)
    return _profile_out(profile, raw["nutrition"])


@router.post("/api/measurements", response_model=IngestResult)
async def post_measurements(
    request: Request, db: Session = Depends(get_db)
) -> IngestResult:
    payload = await request.json()
    items = _normalize_ingest(payload)
    created, skipped, ids = services.ingest_measurements(db, items)
    return IngestResult(created=created, skipped=skipped, ids=ids)


@router.get("/api/measurements", response_model=List[MeasurementOut])
def get_measurements(
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> List[Measurement]:
    return services.list_measurements(db, from_dt=from_, to_dt=to, limit=limit)


@router.put("/api/measurements/{measurement_id}", response_model=MeasurementOut)
def put_measurement(
    measurement_id: int,
    body: MeasurementUpdate,
    db: Session = Depends(get_db),
) -> Measurement:
    row = services.update_measurement(db, measurement_id, body)
    if row is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return row


@router.delete("/api/measurements/{measurement_id}")
def delete_measurement(measurement_id: int, db: Session = Depends(get_db)) -> dict:
    deleted = services.delete_measurement(db, measurement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return {"deleted": True, "id": measurement_id}


@router.get("/api/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    raw = services.compute_stats(db)
    latest = raw["latest"]
    return StatsOut(
        count=raw["count"],
        latest=MeasurementOut.model_validate(latest) if latest else None,
        avg_weight_7d=raw["avg_weight_7d"],
        avg_weight_30d=raw["avg_weight_30d"],
        min_weight=raw["min_weight"],
        max_weight=raw["max_weight"],
        weight_delta_7d=raw["weight_delta_7d"],
        profile_complete=raw["profile_complete"],
        nutrition=NutritionOut.model_validate(raw["nutrition"]),
    )


@router.post("/api/measurements/recalculate")
def recalculate(db: Session = Depends(get_db)) -> dict:
    n = services.recalculate_all(db)
    return {"recalculated": n}


@router.get("/api/measurements/export.csv")
def export_csv(
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = services.list_measurements(db, from_dt=from_, to_dt=to, limit=5000)
    rows = list(reversed(rows))

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "client_id",
            "measured_at",
            "weight_kg",
            "impedance_ohm",
            "unit",
            "scale_mac",
            "bmi",
            "body_fat_pct",
            "body_fat_kg",
            "muscle_pct",
            "muscle_mass_kg",
            "water_pct",
            "water_kg",
            "bone_mass_kg",
            "bone_pct",
            "visceral_fat",
            "bmr",
            "body_age",
            "raw_hex",
        ]
    )
    for r in rows:
        amounts = composition_amounts(
            r.weight_kg,
            r.body_fat_pct,
            r.muscle_mass_kg,
            r.water_pct,
            r.bone_mass_kg,
        )
        writer.writerow(
            [
                r.id,
                r.client_id,
                r.measured_at.isoformat() if r.measured_at else "",
                r.weight_kg,
                r.impedance_ohm,
                r.unit,
                r.scale_mac,
                r.bmi,
                r.body_fat_pct,
                amounts["body_fat_kg"],
                amounts["muscle_pct"],
                r.muscle_mass_kg,
                r.water_pct,
                amounts["water_kg"],
                r.bone_mass_kg,
                amounts["bone_pct"],
                r.visceral_fat,
                r.bmr,
                r.body_age,
                r.raw_hex,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=measurements.csv"},
    )


@router.get("/api/foods/search", response_model=FoodSearchOut)
def get_food_search(q: str = Query(default=""), db: Session = Depends(get_db)) -> dict:
    return {"foods": nutrition.search_foods(db, q)}


@router.get("/api/foods/barcode/{code}")
def get_food_barcode(code: str, db: Session = Depends(get_db)) -> dict:
    try:
        hit = nutrition.lookup_barcode(db, code)
    except nutrition.BarcodeLookupError as exc:
        raise HTTPException(status_code=502, detail="Open Food Facts unavailable") from exc
    if hit is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return hit


@router.post("/api/nutrition/parse", response_model=ParseOut)
def post_nutrition_parse(body: ParseIn, db: Session = Depends(get_db)) -> dict:
    try:
        items = nutrition.parse_text(db, body.text)
    except nutrition.ModelOutputError as exc:
        raise HTTPException(status_code=422, detail="Model output is not a list") from exc
    if items is None:
        raise HTTPException(status_code=503, detail=nutrition.NO_AI_DETAIL)
    return {"items": items}


@router.post("/api/nutrition/parse-image", response_model=ParseOut)
async def post_nutrition_parse_image(
    image: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if image is None:
        raise HTTPException(status_code=400, detail="Image file is required")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Image file is empty")
    media_type = (image.content_type or "image/jpeg").split(";", 1)[0].strip().lower()
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if not media_type:
        media_type = "image/jpeg"
    try:
        items = nutrition.parse_image(db, data, media_type)
    except nutrition.ModelOutputError as exc:
        raise HTTPException(status_code=422, detail="Model output is not a list") from exc
    if items is None:
        raise HTTPException(status_code=503, detail=nutrition.NO_AI_DETAIL)
    return {"items": items}


@router.post("/api/meals", response_model=MealOut)
def post_meal(body: MealCreate, db: Session = Depends(get_db)) -> dict:
    return nutrition.create_meal(
        db,
        eaten_at=body.eaten_at,
        note=body.note,
        source=body.source,
        items=body.items,
    )


@router.get("/api/meals/summary", response_model=MealSummaryOut)
def get_meal_summary(day: date = Query(...), db: Session = Depends(get_db)) -> dict:
    return nutrition.summary_for_day(db, day)


@router.get("/api/meals", response_model=MealListOut)
def get_meals(day: date = Query(...), db: Session = Depends(get_db)) -> dict:
    return {"meals": nutrition.meals_for_day(db, day)}


@router.put("/api/meals/{meal_id}", response_model=MealOut)
def put_meal(meal_id: int, body: MealUpdate, db: Session = Depends(get_db)) -> dict:
    updated = nutrition.update_meal(
        db,
        meal_id,
        eaten_at=body.eaten_at,
        note=body.note,
        items=body.items,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return updated


@router.delete("/api/meals/{meal_id}")
def delete_meal(meal_id: int, db: Session = Depends(get_db)) -> dict:
    deleted = nutrition.delete_meal(db, meal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"deleted": True, "id": meal_id}


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    profile = services.get_or_create_profile(db)
    stats = services.compute_stats(db)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "profile": profile,
            "profile_complete": services.profile_is_complete(profile),
            "stats": stats,
        },
    )
