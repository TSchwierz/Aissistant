"""Meal log, generic foods, and Open Food Facts lookup.

The bundled ``data/generics.json`` table is a starter subset of common foods
with per-100g values in the style of ANSES CIQUAL, not the full CIQUAL table.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from server.modules.health import services
from server.modules.health.models import (
    FoodGeneric,
    FoodProduct,
    Meal,
    MealItem,
    Measurement,
    utcnow,
)

logger = logging.getLogger(__name__)

BERLIN = ZoneInfo("Europe/Berlin")
GENERICS_PATH = Path(__file__).resolve().parent / "data" / "generics.json"
MAX_FOOD_HITS = 20
OFF_USER_AGENT = "PersonalAissistent/1.0 (personal health log)"
OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
NO_AI_DETAIL = "No AI provider configured. Search for foods and add them manually."

PARSE_SYSTEM = (
    "You extract foods from a meal description for a nutrition log. "
    "Reply with a JSON array only. Do not use markdown fences or any text outside the array. "
    "Each element must be an object with query_fr, query_user, and grams. "
    "query_fr is a French generic food name (for example Banane, Pomme, Poulet, Riz). "
    "query_user is the user's own wording, used to search packaged products. "
    "grams is a number: the estimated edible weight in grams. "
    'Example: [{"query_fr":"Banane","query_user":"banana","grams":120}]'
)
PARSE_SYSTEM_IMAGE = (
    PARSE_SYSTEM
    + " The user message is a photo of a meal or of food. Estimate the foods and portions you can see."
)

_NAME_KEYS = (
    "product_name",
    "product_name_fr",
    "product_name_de",
    "product_name_en",
    "generic_name",
    "generic_name_fr",
    "abbreviated_product_name",
)


class ModelOutputError(Exception):
    """The model reply was not a JSON list."""


class BarcodeLookupError(Exception):
    """Open Food Facts could not be reached for a barcode lookup."""


def _normalize_aliases(value: object) -> str:
    if isinstance(value, list):
        parts = [str(part) for part in value]
    else:
        parts = str(value or "").split(",")
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = part.strip().casefold()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return ",".join(cleaned)


def seed_food_generics(db: Session) -> None:
    """Insert or update generic foods by code from the bundled JSON file."""
    payload = json.loads(GENERICS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("generics.json must be a list of foods")
    existing = {row.code: row for row in db.scalars(select(FoodGeneric)).all()}
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        fields = {
            "name_fr": str(item.get("name_fr") or "").strip(),
            "aliases": _normalize_aliases(item.get("aliases", "")),
            "kcal_100g": float(item["kcal_100g"]),
            "protein_100g": float(item["protein_100g"]),
            "carbs_100g": float(item["carbs_100g"]),
            "fat_100g": float(item["fat_100g"]),
            "fiber_100g": float(item["fiber_100g"]),
        }
        row = existing.get(code)
        if row is None:
            row = FoodGeneric(code=code, **fields)
            db.add(row)
            existing[code] = row
        else:
            for key, field_value in fields.items():
                setattr(row, key, field_value)
    db.commit()


def coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return coerce_datetime(value).astimezone(timezone.utc)


def on_berlin_day(value: datetime | str, day: date) -> bool:
    return coerce_datetime(value).astimezone(BERLIN).date() == day


def off_get(url: str, params: dict | None = None) -> httpx.Response:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url, params=params, headers={"User-Agent": OFF_USER_AGENT})
        response.raise_for_status()
        response.read()
        return response


def _first_float(data: dict, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in data:
            continue
        raw = data[key]
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _macro(value: float | None) -> float:
    if value is None:
        return 0.0
    rounded = round(float(value), 1)
    if rounded < 0:
        return 0.0
    return rounded


def _product_name(product: dict, fallback: str) -> str:
    for key in _NAME_KEYS:
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:512]
    return (fallback or "Unknown")[:512]


def _brand(product: dict) -> str:
    raw = product.get("brands")
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raw = str(raw)
    return raw.strip()[:200]


def map_off_product(
    product: dict,
    *,
    barcode: str | None = None,
    require_kcal: bool = True,
) -> dict | None:
    code = (barcode if barcode is not None else str(product.get("code") or "")).strip()
    if not code:
        return None
    nutriments = product.get("nutriments")
    if not isinstance(nutriments, dict):
        nutriments = {}
    kcal = _first_float(nutriments, ("energy-kcal_100g", "energy-kcal"))
    if require_kcal and kcal is None:
        return None
    return {
        "barcode": code[:64],
        "name": _product_name(product, code),
        "brand": _brand(product),
        "kcal_100g": _macro(kcal),
        "protein_100g": _macro(_first_float(nutriments, ("proteins_100g", "proteins"))),
        "carbs_100g": _macro(_first_float(nutriments, ("carbohydrates_100g", "carbohydrates"))),
        "fat_100g": _macro(_first_float(nutriments, ("fat_100g", "fat"))),
        "fiber_100g": _macro(_first_float(nutriments, ("fiber_100g", "fiber"))),
    }


def _off_hit(mapped: dict) -> dict:
    return {
        "name": mapped["name"],
        "source": "off",
        "source_id": mapped["barcode"],
        "kcal_100g": mapped["kcal_100g"],
        "protein_100g": mapped["protein_100g"],
        "carbs_100g": mapped["carbs_100g"],
        "fat_100g": mapped["fat_100g"],
        "fiber_100g": mapped["fiber_100g"],
    }


def _product_hit(row: FoodProduct) -> dict:
    return {
        "name": row.name,
        "source": "off",
        "source_id": row.barcode,
        "kcal_100g": row.kcal_100g,
        "protein_100g": row.protein_100g,
        "carbs_100g": row.carbs_100g,
        "fat_100g": row.fat_100g,
        "fiber_100g": row.fiber_100g,
    }


def _generic_hit(row: FoodGeneric) -> dict:
    return {
        "name": row.name_fr,
        "source": "ciqual",
        "source_id": row.code,
        "kcal_100g": row.kcal_100g,
        "protein_100g": row.protein_100g,
        "carbs_100g": row.carbs_100g,
        "fat_100g": row.fat_100g,
        "fiber_100g": row.fiber_100g,
    }


def cache_product(db: Session, mapped: dict) -> None:
    row = db.get(FoodProduct, mapped["barcode"])
    if row is None:
        row = FoodProduct(barcode=mapped["barcode"], name=mapped["name"])
        db.add(row)
    row.name = mapped["name"]
    row.brand = mapped["brand"] or ""
    row.kcal_100g = mapped["kcal_100g"]
    row.protein_100g = mapped["protein_100g"]
    row.carbs_100g = mapped["carbs_100g"]
    row.fat_100g = mapped["fat_100g"]
    row.fiber_100g = mapped["fiber_100g"]
    row.fetched_at = utcnow()
    db.commit()


def search_off_products(query: str) -> list[dict]:
    response = off_get(
        OFF_SEARCH_URL,
        params={
            "search_terms": query,
            "search_simple": "1",
            "action": "process",
            "json": "1",
            "page_size": "8",
        },
    )
    try:
        data = response.json()
    except ValueError:
        return []
    products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(products, list):
        return []
    return [item for item in products if isinstance(item, dict)]


def fetch_off_product(code: str) -> dict | None:
    url = OFF_PRODUCT_URL.format(code=quote(code, safe=""))
    try:
        response = off_get(url)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status == 404:
            return None
        raise
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("status") == 0:
        return None
    product = data.get("product")
    if not isinstance(product, dict) or not product:
        return None
    return product


def _generic_matches(row: FoodGeneric, needle: str) -> bool:
    if needle in (row.name_fr or "").casefold():
        return True
    return needle in (row.aliases or "").casefold()


def find_generic(db: Session, query: str) -> FoodGeneric | None:
    needle = (query or "").strip().casefold()
    if not needle:
        return None
    alias_hit: FoodGeneric | None = None
    rows = db.scalars(select(FoodGeneric).order_by(FoodGeneric.id.asc())).all()
    for row in rows:
        if (row.name_fr or "").strip().casefold() == needle:
            return row
        tokens = [part.strip() for part in (row.aliases or "").split(",") if part.strip()]
        if needle in tokens and alias_hit is None:
            alias_hit = row
    return alias_hit


def search_foods(db: Session, query: str) -> list[dict]:
    text = (query or "").strip()
    if not text:
        return []
    needle = text.casefold()
    rows = db.scalars(select(FoodGeneric).order_by(FoodGeneric.name_fr.asc(), FoodGeneric.id.asc())).all()
    hits = [_generic_hit(row) for row in rows if _generic_matches(row, needle)]
    hits = hits[:MAX_FOOD_HITS]
    if len(hits) >= MAX_FOOD_HITS:
        return hits
    try:
        products = search_off_products(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Open Food Facts search failed (%s)", type(exc).__name__)
        return hits
    seen = {hit["source_id"] for hit in hits}
    for product in products:
        mapped = map_off_product(product, require_kcal=True)
        if mapped is None or mapped["barcode"] in seen:
            continue
        hits.append(_off_hit(mapped))
        seen.add(mapped["barcode"])
        if len(hits) >= MAX_FOOD_HITS:
            break
    return hits


def lookup_barcode(db: Session, code: str) -> dict | None:
    barcode = (code or "").strip()
    if not barcode:
        return None
    cached = db.get(FoodProduct, barcode)
    if cached is not None:
        return _product_hit(cached)
    try:
        product = fetch_off_product(barcode)
    except httpx.HTTPError as exc:
        logger.warning("Open Food Facts barcode lookup failed (%s)", type(exc).__name__)
        raise BarcodeLookupError("Open Food Facts unavailable") from exc
    if product is None:
        return None
    mapped = map_off_product(product, barcode=barcode, require_kcal=False)
    if mapped is None:
        return None
    cache_product(db, mapped)
    return _off_hit(mapped)


def _grams(value: object) -> float:
    try:
        grams = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if grams != grams or grams < 0:
        return 0.0
    return grams


def _scaled_item(
    name: str,
    grams: float,
    per100: tuple[float, float, float, float, float],
    source: str,
    source_id: str | None,
) -> dict:
    factor = grams / 100.0
    kcal, protein, carbs, fat, fiber = per100
    return {
        "name": name or "Unknown",
        "grams": grams,
        "kcal": _macro(float(kcal) * factor),
        "protein_g": _macro(float(protein) * factor),
        "carbs_g": _macro(float(carbs) * factor),
        "fat_g": _macro(float(fat) * factor),
        "fiber_g": _macro(float(fiber) * factor),
        "source": source,
        "source_id": source_id,
    }


def _resolve_entry(db: Session, entry: dict) -> dict:
    query_fr = str(entry.get("query_fr") or "").strip()
    query_user = str(entry.get("query_user") or "").strip() or query_fr
    grams = _grams(entry.get("grams"))
    generic = find_generic(db, query_fr)
    if generic is not None:
        return _scaled_item(
            generic.name_fr,
            grams,
            (
                generic.kcal_100g,
                generic.protein_100g,
                generic.carbs_100g,
                generic.fat_100g,
                generic.fiber_100g,
            ),
            "ciqual",
            generic.code,
        )
    products: list[dict] = []
    if query_user:
        try:
            products = search_off_products(query_user)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Open Food Facts parse search failed (%s)", type(exc).__name__)
            products = []
    for product in products:
        mapped = map_off_product(product, require_kcal=True)
        if mapped is None:
            continue
        cache_product(db, mapped)
        return _scaled_item(
            mapped["name"],
            grams,
            (
                mapped["kcal_100g"],
                mapped["protein_100g"],
                mapped["carbs_100g"],
                mapped["fat_100g"],
                mapped["fiber_100g"],
            ),
            "off",
            mapped["barcode"],
        )
    return {
        "name": query_user or query_fr or "Unknown",
        "grams": grams,
        "kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "source": "manual",
        "source_id": None,
    }


def strip_markdown_fences(text: str) -> str:
    cleaned = (text or "").strip().lstrip("\ufeff").strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```"):
        body = lines[1:]
        if body and body[-1].strip() == "```":
            body = body[:-1]
        return "\n".join(body).strip()
    cleaned = cleaned.strip("`").strip()
    if cleaned[:4].lower() == "json":
        remainder = cleaned[4:]
        if not remainder or remainder[0].isspace():
            cleaned = remainder.strip()
    return cleaned


def parse_model_list(raw: str) -> list:
    try:
        parsed = json.loads(strip_markdown_fences(raw))
    except json.JSONDecodeError as exc:
        raise ModelOutputError("Model output is not a list") from exc
    if not isinstance(parsed, list):
        raise ModelOutputError("Model output is not a list")
    return parsed


def items_from_model_text(db: Session, raw: str) -> list[dict]:
    items: list[dict] = []
    for entry in parse_model_list(raw):
        if isinstance(entry, dict):
            items.append(_resolve_entry(db, entry))
    return items


def parse_text(db: Session, text: str) -> list[dict] | None:
    from server.modules.news import providers

    raw = providers.complete_text(PARSE_SYSTEM, text or "")
    if raw is None:
        return None
    return items_from_model_text(db, raw)


def parse_image(db: Session, image: bytes, media_type: str) -> list[dict] | None:
    """Match foods in a photo. Image bytes are not written to disk or the database."""
    from server.modules.news import providers

    raw = providers.complete_vision(PARSE_SYSTEM_IMAGE, image, media_type or "image/jpeg")
    if raw is None:
        return None
    return items_from_model_text(db, raw)


def _item_from_payload(payload) -> MealItem:
    return MealItem(
        name=payload.name,
        grams=payload.grams,
        kcal=payload.kcal,
        protein_g=payload.protein_g,
        carbs_g=payload.carbs_g,
        fat_g=payload.fat_g,
        fiber_g=payload.fiber_g,
        source=payload.source,
        source_id=payload.source_id or None,
    )


def _item_out(item: MealItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "grams": item.grams,
        "kcal": item.kcal,
        "protein_g": item.protein_g,
        "carbs_g": item.carbs_g,
        "fat_g": item.fat_g,
        "fiber_g": item.fiber_g,
        "source": item.source,
        "source_id": item.source_id,
    }


def meal_out(meal: Meal) -> dict:
    items = sorted(meal.items, key=lambda item: item.id or 0)
    return {
        "id": meal.id,
        "eaten_at": coerce_datetime(meal.eaten_at),
        "note": meal.note or "",
        "source": meal.source,
        "created_at": coerce_datetime(meal.created_at),
        "items": [_item_out(item) for item in items],
    }


def create_meal(db: Session, *, eaten_at, note: str, source: str, items: list) -> dict:
    meal = Meal(
        eaten_at=ensure_utc(eaten_at),
        note="" if note is None else note,
        source=source,
        created_at=utcnow(),
        items=[_item_from_payload(item) for item in items],
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return meal_out(meal)


def update_meal(db: Session, meal_id: int, *, eaten_at, note: str, items: list) -> dict | None:
    meal = db.get(Meal, meal_id)
    if meal is None:
        return None
    if eaten_at is not None:
        meal.eaten_at = ensure_utc(eaten_at)
    meal.note = "" if note is None else note
    meal.items = [_item_from_payload(item) for item in items]
    db.commit()
    db.refresh(meal)
    return meal_out(meal)


def delete_meal(db: Session, meal_id: int) -> bool:
    meal = db.get(Meal, meal_id)
    if meal is None:
        return False
    db.delete(meal)
    db.commit()
    return True


def meals_for_day(db: Session, day: date) -> list[dict]:
    rows = list(db.scalars(select(Meal).options(selectinload(Meal.items))).all())
    rows.sort(key=lambda row: (coerce_datetime(row.eaten_at), row.id))
    return [meal_out(row) for row in rows if on_berlin_day(row.eaten_at, day)]


def totals_for(meals: list[dict]) -> dict:
    kcal = protein = carbs = fat = fiber = 0.0
    for meal in meals:
        for item in meal.get("items") or []:
            kcal += float(item.get("kcal") or 0)
            protein += float(item.get("protein_g") or 0)
            carbs += float(item.get("carbs_g") or 0)
            fat += float(item.get("fat_g") or 0)
            fiber += float(item.get("fiber_g") or 0)
    return {
        "kcal": round(kcal, 1),
        "protein_g": round(protein, 1),
        "carbs_g": round(carbs, 1),
        "fat_g": round(fat, 1),
        "fiber_g": round(fiber, 1),
    }


def day_targets(db: Session) -> dict | None:
    try:
        profile = services.get_or_create_profile(db)
        latest = db.scalar(select(Measurement).order_by(Measurement.measured_at.desc()).limit(1))
        raw = services.nutrition_for(profile, latest)
    except Exception:  # noqa: BLE001
        logger.warning("Nutrition targets could not be computed")
        return None
    if not isinstance(raw, dict):
        return None
    return {
        "target_calories": raw.get("target_calories"),
        "protein_g": raw.get("protein_g"),
        "fiber_g": raw.get("fiber_g"),
    }


def summary_for_day(db: Session, day: date) -> dict:
    meals = meals_for_day(db, day)
    return {
        "day": day.isoformat(),
        "totals": totals_for(meals),
        "targets": day_targets(db),
        "meals": meals,
    }
