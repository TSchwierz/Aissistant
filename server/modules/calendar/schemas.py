"""Pydantic models for personal calendar API."""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

_REPEAT = {"weekly", "biweekly", "monthly"}
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = " ".join(str(raw).split())
        if not tag or tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        cleaned.append(tag)
    return cleaned


def _clean_weekdays(days: list[int] | None) -> list[int] | None:
    if days is None:
        return None
    cleaned: list[int] = []
    for raw in days:
        day = int(raw)
        if day < 0 or day > 6:
            raise ValueError("weekday must be 0 (Monday) through 6 (Sunday)")
        if day not in cleaned:
            cleaned.append(day)
    return cleaned


def _clean_color(value: str) -> str:
    text = value.strip()
    if len(text) == 4 and text.startswith("#"):
        text = "#" + "".join(ch * 2 for ch in text[1:])
    if not _HEX_COLOR.fullmatch(text):
        raise ValueError("color must be #RRGGBB")
    return text.lower()


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    repeat: str | None = None
    repeat_until: date | None = None
    repeat_weekdays: list[int] | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("title must not be empty")
        return text

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return _clean_tags(v)

    @field_validator("repeat")
    @classmethod
    def check_repeat(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if v not in _REPEAT:
            raise ValueError("repeat must be weekly, biweekly, or monthly")
        return v

    @field_validator("repeat_weekdays")
    @classmethod
    def normalize_weekdays(cls, v: list[int] | None) -> list[int] | None:
        return _clean_weekdays(v)

    @model_validator(mode="after")
    def end_after_start(self) -> EventCreate:
        if self.end is not None and self.end < self.start:
            raise ValueError("end must be >= start")
        if self.repeat_until is not None and self.repeat_until < self.start.date():
            raise ValueError("repeat_until must be on or after the start date")
        if self.repeat_until is not None and self.repeat is None:
            raise ValueError("repeat_until requires repeat")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    start: datetime | None = None
    end: datetime | None = None
    clear_end: bool = False
    all_day: bool | None = None
    location: str | None = Field(default=None, max_length=500)
    clear_location: bool = False
    notes: str | None = Field(default=None, max_length=4000)
    clear_notes: bool = False
    tags: list[str] | None = None
    repeat: str | None = None
    clear_repeat: bool = False
    repeat_until: date | None = None
    clear_repeat_until: bool = False
    repeat_weekdays: list[int] | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        if not text:
            raise ValueError("title must not be empty")
        return text

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return _clean_tags(v)

    @field_validator("repeat")
    @classmethod
    def check_repeat(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if v not in _REPEAT:
            raise ValueError("repeat must be weekly, biweekly, or monthly")
        return v

    @field_validator("repeat_weekdays")
    @classmethod
    def normalize_weekdays(cls, v: list[int] | None) -> list[int] | None:
        return _clean_weekdays(v)


class EventOut(BaseModel):
    id: str
    title: str
    start: str
    end: str | None = None
    all_day: bool = False
    location: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    series_id: str | None = None
    series_start: str | None = None
    series_end: str | None = None
    repeat: str | None = None
    repeat_until: str | None = None
    repeat_weekdays: list[int] = Field(default_factory=list)


class EventListOut(BaseModel):
    count: int
    timezone: str
    range_start: str
    range_end: str
    events: list[EventOut]


class TagColorIn(BaseModel):
    tag: str = Field(min_length=1, max_length=80)
    color: str

    @field_validator("tag")
    @classmethod
    def strip_tag(cls, v: str) -> str:
        text = " ".join(v.split())
        if not text:
            raise ValueError("tag must not be empty")
        return text

    @field_validator("color")
    @classmethod
    def normalize_color(cls, v: str) -> str:
        return _clean_color(v)


class TagListOut(BaseModel):
    tags: list[str]
    colors: dict[str, str] = Field(default_factory=dict)
