"""Health Scale Hub HTTP routes — same paths as the standalone hub."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from server.modules.health import services
from server.modules.health.database import get_db, init_db
from server.modules.health.models import Measurement  # noqa: F401 — register models
from server.modules.health.schemas import (
    IngestResult,
    MeasurementBatchIn,
    MeasurementIn,
    MeasurementOut,
    MeasurementUpdate,
    ProfileOut,
    ProfileUpdate,
    StatsOut,
)

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


def _profile_out(profile) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        name=profile.name or "",
        height_cm=profile.height_cm,
        age=profile.age,
        sex=profile.sex,
        updated_at=profile.updated_at,
        is_complete=services.profile_is_complete(profile),
    )


@router.get("/api/health")
def api_health() -> dict:
    return {"status": "ok", "service": "health-scale-hub"}


@router.get("/api/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)) -> ProfileOut:
    return _profile_out(services.get_or_create_profile(db))


@router.put("/api/profile", response_model=ProfileOut)
def put_profile(body: ProfileUpdate, db: Session = Depends(get_db)) -> ProfileOut:
    profile = services.update_profile(db, body)
    return _profile_out(profile)


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
            "muscle_mass_kg",
            "water_pct",
            "bone_mass_kg",
            "visceral_fat",
            "bmr",
            "body_age",
            "raw_hex",
        ]
    )
    for r in rows:
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
                r.muscle_mass_kg,
                r.water_pct,
                r.bone_mass_kg,
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
