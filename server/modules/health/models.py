from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.modules.health.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)  # male / female
    # sedentary / light / moderate / active / very_active
    activity_level: Mapped[str] = mapped_column(String(32), default="moderate")
    target_fat_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    meals_per_day: Mapped[int] = mapped_column(Integer, default=3)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("client_id", name="uq_client_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    impedance_ohm: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="kg")
    scale_mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_hex: Mapped[str | None] = mapped_column(String(256), nullable=True)

    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    muscle_mass_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    bone_mass_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    visceral_fat: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmr: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_age: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # text / barcode / photo
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    items: Mapped[list["MealItem"]] = relationship(
        "MealItem",
        back_populates="meal",
        cascade="all, delete-orphan",
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_id: Mapped[int] = mapped_column(
        ForeignKey("meals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    grams: Mapped[float] = mapped_column(Float, nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float] = mapped_column(Float, nullable=False)
    # ciqual / off / manual
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meal: Mapped["Meal"] = relationship("Meal", back_populates="items")


class FoodGeneric(Base):
    __tablename__ = "food_generics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name_fr: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kcal_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_100g: Mapped[float] = mapped_column(Float, nullable=False)


class FoodProduct(Base):
    __tablename__ = "food_products"

    barcode: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    brand: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    kcal_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
