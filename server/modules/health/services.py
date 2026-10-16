from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.modules.health.bia import BodyMetrics, compute_metrics
from server.modules.health.models import Measurement, Profile, utcnow
from server.modules.health.targets import daily_targets, normalize_activity


def get_or_create_profile(db: Session) -> Profile:
    profile = db.scalar(select(Profile).limit(1))
    if profile is None:
        profile = Profile(name="")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def profile_is_complete(profile: Profile) -> bool:
    return bool(
        profile.height_cm
        and profile.height_cm > 0
        and profile.age
        and profile.age > 0
        and profile.sex
        and profile.sex.lower() in ("male", "female", "m", "f")
    )


def metrics_for(
    profile: Profile, weight_kg: float, impedance_ohm: Optional[float]
) -> BodyMetrics:
    if not profile_is_complete(profile):
        if profile.height_cm and profile.height_cm > 0 and weight_kg > 0:
            height_m = profile.height_cm / 100.0
            return BodyMetrics(bmi=round(weight_kg / (height_m * height_m), 2))
        return BodyMetrics()
    return compute_metrics(
        weight_kg=weight_kg,
        height_cm=float(profile.height_cm),
        age=int(profile.age),
        sex=str(profile.sex),
        impedance_ohm=impedance_ohm,
    )


def apply_metrics(measurement: Measurement, metrics: BodyMetrics) -> None:
    measurement.bmi = metrics.bmi
    measurement.body_fat_pct = metrics.body_fat_pct
    measurement.muscle_mass_kg = metrics.muscle_mass_kg
    measurement.water_pct = metrics.water_pct
    measurement.bone_mass_kg = metrics.bone_mass_kg
    measurement.visceral_fat = metrics.visceral_fat
    measurement.bmr = metrics.bmr
    measurement.body_age = metrics.body_age


def ingest_measurements(db: Session, items: Sequence) -> Tuple[int, int, List[int]]:
    profile = get_or_create_profile(db)
    created = 0
    skipped = 0
    ids: List[int] = []

    for item in items:
        existing = db.scalar(
            select(Measurement).where(Measurement.client_id == item.client_id)
        )
        if existing is not None:
            skipped += 1
            ids.append(existing.id)
            continue

        measured_at = item.measured_at
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=timezone.utc)

        row = Measurement(
            client_id=item.client_id,
            measured_at=measured_at,
            weight_kg=item.weight_kg,
            impedance_ohm=item.impedance_ohm,
            unit=item.unit or "kg",
            scale_mac=item.scale_mac,
            raw_hex=item.raw_hex,
        )
        apply_metrics(row, metrics_for(profile, item.weight_kg, item.impedance_ohm))
        db.add(row)
        db.flush()
        ids.append(row.id)
        created += 1

    db.commit()
    return created, skipped, ids


def recalculate_all(db: Session) -> int:
    profile = get_or_create_profile(db)
    rows = db.scalars(select(Measurement)).all()
    for row in rows:
        apply_metrics(row, metrics_for(profile, row.weight_kg, row.impedance_ohm))
    db.commit()
    return len(rows)


def list_measurements(
    db: Session,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
    limit: int = 500,
) -> List[Measurement]:
    stmt = select(Measurement).order_by(Measurement.measured_at.desc())
    if from_dt is not None:
        if from_dt.tzinfo is None:
            from_dt = from_dt.replace(tzinfo=timezone.utc)
        stmt = stmt.where(Measurement.measured_at >= from_dt)
    if to_dt is not None:
        if to_dt.tzinfo is None:
            to_dt = to_dt.replace(tzinfo=timezone.utc)
        stmt = stmt.where(Measurement.measured_at <= to_dt)
    stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def get_measurement(db: Session, measurement_id: int) -> Optional[Measurement]:
    return db.get(Measurement, measurement_id)


def update_measurement(db: Session, measurement_id: int, data) -> Optional[Measurement]:
    row = get_measurement(db, measurement_id)
    if row is None:
        return None

    updates = data.model_dump(exclude_unset=True)
    if "measured_at" in updates and updates["measured_at"] is not None:
        measured_at = updates["measured_at"]
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=timezone.utc)
        row.measured_at = measured_at
    if "weight_kg" in updates and updates["weight_kg"] is not None:
        row.weight_kg = updates["weight_kg"]
    if "impedance_ohm" in updates:
        row.impedance_ohm = updates["impedance_ohm"]
    if "unit" in updates and updates["unit"] is not None:
        row.unit = updates["unit"]

    profile = get_or_create_profile(db)
    apply_metrics(row, metrics_for(profile, row.weight_kg, row.impedance_ohm))
    db.commit()
    db.refresh(row)
    return row


def delete_measurement(db: Session, measurement_id: int) -> bool:
    row = get_measurement(db, measurement_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def compute_stats(db: Session) -> dict:
    profile = get_or_create_profile(db)
    count = db.scalar(select(func.count()).select_from(Measurement)) or 0
    latest = db.scalar(select(Measurement).order_by(Measurement.measured_at.desc()).limit(1))

    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    avg_7 = db.scalar(
        select(func.avg(Measurement.weight_kg)).where(Measurement.measured_at >= d7)
    )
    avg_30 = db.scalar(
        select(func.avg(Measurement.weight_kg)).where(Measurement.measured_at >= d30)
    )
    min_w = db.scalar(select(func.min(Measurement.weight_kg)))
    max_w = db.scalar(select(func.max(Measurement.weight_kg)))

    weight_delta_7d = None
    if latest is not None:
        older = db.scalar(
            select(Measurement)
            .where(Measurement.measured_at <= d7)
            .order_by(Measurement.measured_at.desc())
            .limit(1)
        )
        if older is not None:
            weight_delta_7d = round(latest.weight_kg - older.weight_kg, 2)

    return {
        "count": count,
        "latest": latest,
        "avg_weight_7d": round(float(avg_7), 2) if avg_7 is not None else None,
        "avg_weight_30d": round(float(avg_30), 2) if avg_30 is not None else None,
        "min_weight": round(float(min_w), 2) if min_w is not None else None,
        "max_weight": round(float(max_w), 2) if max_w is not None else None,
        "weight_delta_7d": weight_delta_7d,
        "profile_complete": profile_is_complete(profile),
        "nutrition": nutrition_for(profile, latest),
    }


def nutrition_for(profile: Profile, latest: Optional[Measurement]) -> dict:
    return daily_targets(
        activity_level=getattr(profile, "activity_level", None),
        meals_per_day=getattr(profile, "meals_per_day", None),
        target_fat_pct=getattr(profile, "target_fat_pct", None),
        sex=profile.sex,
        weight_kg=latest.weight_kg if latest is not None else None,
        bmr=latest.bmr if latest is not None else None,
    )


def update_profile(db: Session, data) -> Profile:
    profile = get_or_create_profile(db)
    profile.name = data.name or ""
    profile.height_cm = data.height_cm
    profile.age = data.age
    sex = (data.sex or "").strip().lower()
    if sex in ("m", "male"):
        profile.sex = "male"
    elif sex in ("f", "female"):
        profile.sex = "female"
    else:
        profile.sex = data.sex
    profile.activity_level = normalize_activity(getattr(data, "activity_level", None))
    profile.target_fat_pct = data.target_fat_pct
    meals = getattr(data, "meals_per_day", None)
    profile.meals_per_day = 3 if meals is None else max(1, min(8, int(meals)))
    profile.updated_at = utcnow()
    db.commit()
    db.refresh(profile)
    return profile
