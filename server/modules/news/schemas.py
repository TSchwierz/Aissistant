"""Pydantic models for news topics and digests."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class TopicCreate(BaseModel):
    id: str = Field(description="Stable slug id, e.g. politics")
    label: str = Field(min_length=1, max_length=120)
    goal: str = Field(default="", max_length=2000)
    feed_urls: list[str] = Field(default_factory=list)
    schedule_enabled: bool = True
    schedule_hour: int = Field(default=5, ge=0, le=23)
    schedule_minute: int = Field(default=30, ge=0, le=59)
    schedule_days: list[int] = Field(
        default_factory=lambda: [0, 1, 2, 3, 4, 5, 6],
        description="0=Mon … 6=Sun",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        text = v.strip().lower()
        if not _SLUG_RE.match(text):
            raise ValueError("id must be a slug: lowercase letters, digits, _-")
        return text

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("label must not be empty")
        return text

    @field_validator("feed_urls")
    @classmethod
    def clean_urls(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in v:
            url = str(raw).strip()
            if not url or url in seen:
                continue
            if not (
                url.startswith("http://")
                or url.startswith("https://")
                or url.startswith("mock://")
            ):
                raise ValueError(f"feed URL must be http(s) or mock://: {url}")
            seen.add(url)
            out.append(url)
        return out

    @field_validator("schedule_days")
    @classmethod
    def clean_days(cls, v: list[int]) -> list[int]:
        days = sorted({int(d) for d in v if 0 <= int(d) <= 6})
        return days or [0, 1, 2, 3, 4, 5, 6]


class TopicUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    goal: str | None = Field(default=None, max_length=2000)
    feed_urls: list[str] | None = None
    schedule_enabled: bool | None = None
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)
    schedule_days: list[int] | None = None

    @field_validator("feed_urls")
    @classmethod
    def clean_urls(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return TopicCreate.clean_urls(v)

    @field_validator("schedule_days")
    @classmethod
    def clean_days(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        return TopicCreate.clean_days(v)

    @model_validator(mode="after")
    def at_least_one_field(self) -> TopicUpdate:
        if all(
            getattr(self, f) is None
            for f in (
                "label",
                "goal",
                "feed_urls",
                "schedule_enabled",
                "schedule_hour",
                "schedule_minute",
                "schedule_days",
            )
        ):
            raise ValueError("No fields to update")
        return self


class TopicOut(BaseModel):
    id: str
    label: str
    goal: str
    feed_urls: list[str]
    schedule_enabled: bool
    schedule_hour: int
    schedule_minute: int
    schedule_days: list[int]
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DigestOut(BaseModel):
    id: str
    topic_id: str
    topic_label: str
    digest: str
    item_count: int
    generated_at: str
    for_date: str
    ai_provider: str | None = None
    status: str
    error_message: str | None = None


class RunResultOut(BaseModel):
    digest: DigestOut
    providers_configured: list[str]
