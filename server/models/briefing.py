"""Morning brief response models (aligned with morning-brief-api sketch)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BriefFreshness(BaseModel):
    weather: str | None = None
    calendar: str | None = None
    news: str | None = None


class BriefMeta(BaseModel):
    date: str
    timezone: str
    generated_at: str
    language: str = "en"
    freshness: BriefFreshness = Field(default_factory=BriefFreshness)
    sections_present: list[str] = Field(default_factory=list)
    empty_reason: str | None = None


class ClothingHint(BaseModel):
    rain_jacket: bool | None = None
    hoody: bool | None = None
    notes: str | None = None


class WeatherSection(BaseModel):
    summary: str | None = None
    high_c: float | None = None
    low_c: float | None = None
    precip_chance_pct: int | None = None
    conditions: str | None = None
    clothing_hint: ClothingHint | None = None


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: str
    end: str | None = None
    all_day: bool = False
    tags: list[str] = Field(default_factory=list)
    location: str | None = None
    notes: str | None = None


class CalendarSection(BaseModel):
    events: list[CalendarEvent] = Field(default_factory=list)
    first_event_start: str | None = None


class NewsTopicDigest(BaseModel):
    topic_id: str
    topic_label: str
    digest: str
    item_count: int = 0
    generated_at: str | None = None
    ai_provider: str | None = None


class NewsSection(BaseModel):
    by_topic: list[NewsTopicDigest] = Field(default_factory=list)


class BriefSection(BaseModel):
    id: str
    title: str
    body: str


class MorningBriefResponse(BaseModel):
    """GET /briefing/morning payload. Absent sections are omitted via exclude_none."""

    meta: BriefMeta
    weather: WeatherSection | None = None
    calendar: CalendarSection | None = None
    news: NewsSection | None = None
    script: str = ""
    sections: list[BriefSection] = Field(default_factory=list)

    def model_dump_response(self) -> dict[str, Any]:
        """Serialize for JSON: drop null top-level section keys."""
        return self.model_dump(mode="json", exclude_none=True)
