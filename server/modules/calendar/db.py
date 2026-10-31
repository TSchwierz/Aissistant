"""SQLite store for personal calendar events (Pi SSOT)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from server.config import get_settings


def _db_path() -> Path:
    settings = get_settings()
    data_dir = Path(settings.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "calendar.db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def parse_weekdays(value: str | list[int] | None) -> list[int]:
    if not value:
        return []
    parts = value if isinstance(value, list) else str(value).split(",")
    out: list[int] = []
    for raw in parts:
        text = str(raw).strip()
        if not text.lstrip("-").isdigit():
            continue
        day = int(text)
        if 0 <= day <= 6 and day not in out:
            out.append(day)
    return out


def format_weekdays(days: list[int] | None) -> str | None:
    cleaned = parse_weekdays(days)
    if not cleaned:
        return None
    return ",".join(str(day) for day in cleaned)


def new_event_id() -> str:
    return f"evt_{uuid4().hex[:12]}"


@dataclass
class EventRow:
    id: str
    title: str
    start: datetime
    end: datetime | None
    all_day: bool
    location: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    repeat_rule: str | None = None
    repeat_until: date | None = None
    repeat_weekdays: list[int] = field(default_factory=list)
    remind_before_minutes: int | None = None
    ics_uid: str | None = None


class CalendarDB:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT,
                    all_day INTEGER NOT NULL DEFAULT 0,
                    location TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    repeat_rule TEXT,
                    repeat_until TEXT,
                    repeat_weekdays TEXT,
                    remind_before_minutes INTEGER,
                    ics_uid TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_at);
                CREATE INDEX IF NOT EXISTS idx_events_end ON events(end_at);

                CREATE TABLE IF NOT EXISTS event_tags (
                    event_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (event_id, tag),
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
            if "repeat_rule" not in columns:
                conn.execute("ALTER TABLE events ADD COLUMN repeat_rule TEXT")
            if "repeat_until" not in columns:
                conn.execute("ALTER TABLE events ADD COLUMN repeat_until TEXT")
            if "repeat_weekdays" not in columns:
                conn.execute("ALTER TABLE events ADD COLUMN repeat_weekdays TEXT")
            if "remind_before_minutes" not in columns:
                conn.execute("ALTER TABLE events ADD COLUMN remind_before_minutes INTEGER")
            if "ics_uid" not in columns:
                conn.execute("ALTER TABLE events ADD COLUMN ics_uid TEXT")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_ics_uid
                ON events(ics_uid)
                WHERE ics_uid IS NOT NULL
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_colors (
                    tag TEXT PRIMARY KEY,
                    color TEXT NOT NULL
                )
                """
            )

    def _parse_dt(self, value: str | None) -> datetime | None:
        if value is None:
            return None
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _row_to_event(self, row: sqlite3.Row, tags: list[str]) -> EventRow:
        return EventRow(
            id=str(row["id"]),
            title=str(row["title"]),
            start=self._parse_dt(row["start_at"]),  # type: ignore[arg-type]
            end=self._parse_dt(row["end_at"]),
            all_day=bool(row["all_day"]),
            location=row["location"],
            notes=row["notes"],
            tags=tags,
            created_at=self._parse_dt(row["created_at"]),
            updated_at=self._parse_dt(row["updated_at"]),
            repeat_rule=(row["repeat_rule"] or None) if "repeat_rule" in row.keys() else None,
            repeat_until=_parse_date(row["repeat_until"]) if "repeat_until" in row.keys() else None,
            repeat_weekdays=parse_weekdays(row["repeat_weekdays"])
            if "repeat_weekdays" in row.keys()
            else [],
            remind_before_minutes=int(row["remind_before_minutes"])
            if "remind_before_minutes" in row.keys() and row["remind_before_minutes"] is not None
            else None,
            ics_uid=(row["ics_uid"] or None) if "ics_uid" in row.keys() else None,
        )

    def _tags_for(self, conn: sqlite3.Connection, event_ids: list[str]) -> dict[str, list[str]]:
        if not event_ids:
            return {}
        placeholders = ",".join("?" * len(event_ids))
        rows = conn.execute(
            f"""
            SELECT event_id, tag FROM event_tags
            WHERE event_id IN ({placeholders})
            ORDER BY tag ASC
            """,
            event_ids,
        ).fetchall()
        out: dict[str, list[str]] = {eid: [] for eid in event_ids}
        for r in rows:
            out[str(r["event_id"])].append(str(r["tag"]))
        return out

    def _set_tags(self, conn: sqlite3.Connection, event_id: str, tags: list[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in tags:
            tag = " ".join(str(raw).split())
            if not tag or tag.casefold() in seen:
                continue
            seen.add(tag.casefold())
            cleaned.append(tag)
        conn.execute("DELETE FROM event_tags WHERE event_id = ?", (event_id,))
        for tag in cleaned:
            conn.execute(
                "INSERT INTO event_tags(event_id, tag) VALUES (?, ?)",
                (event_id, tag),
            )

    def create_event(
        self,
        *,
        title: str,
        start: datetime,
        end: datetime | None,
        all_day: bool,
        location: str | None,
        notes: str | None,
        tags: list[str],
        event_id: str | None = None,
        repeat_rule: str | None = None,
        repeat_until: date | None = None,
        repeat_weekdays: list[int] | None = None,
        remind_before_minutes: int | None = None,
        ics_uid: str | None = None,
    ) -> EventRow:
        eid = event_id or new_event_id()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events(
                    id, title, start_at, end_at, all_day, location, notes,
                    created_at, updated_at, repeat_rule, repeat_until, repeat_weekdays,
                    remind_before_minutes, ics_uid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    title,
                    to_iso(start),
                    to_iso(end) if end else None,
                    1 if all_day else 0,
                    location,
                    notes,
                    to_iso(now),
                    to_iso(now),
                    repeat_rule,
                    repeat_until.isoformat() if repeat_until else None,
                    format_weekdays(repeat_weekdays),
                    remind_before_minutes,
                    ics_uid or None,
                ),
            )
            self._set_tags(conn, eid, tags)
            tags_map = self._tags_for(conn, [eid])
            row = conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
        return self._row_to_event(row, tags_map.get(eid, []))

    def get_event(self, event_id: str) -> EventRow | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            if row is None:
                return None
            tags = self._tags_for(conn, [event_id]).get(event_id, [])
        return self._row_to_event(row, tags)

    def update_event(
        self,
        event_id: str,
        *,
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = ...,  # type: ignore[assignment]
        all_day: bool | None = None,
        location: str | None = ...,  # type: ignore[assignment]
        notes: str | None = ...,  # type: ignore[assignment]
        tags: list[str] | None = None,
        repeat_rule: str | None = ...,  # type: ignore[assignment]
        repeat_until: date | None = ...,  # type: ignore[assignment]
        repeat_weekdays: list[int] | None = ...,  # type: ignore[assignment]
        remind_before_minutes: int | None = ...,  # type: ignore[assignment]
        ics_uid: str | None = ...,  # type: ignore[assignment]
    ) -> EventRow | None:
        existing = self.get_event(event_id)
        if existing is None:
            return None
        now = utc_now()
        new_title = existing.title if title is None else title
        new_start = existing.start if start is None else start
        new_end = existing.end if end is ... else end
        new_all_day = existing.all_day if all_day is None else all_day
        new_location = existing.location if location is ... else location
        new_notes = existing.notes if notes is ... else notes
        new_tags = existing.tags if tags is None else tags
        new_repeat = existing.repeat_rule if repeat_rule is ... else repeat_rule
        new_until = existing.repeat_until if repeat_until is ... else repeat_until
        new_days = existing.repeat_weekdays if repeat_weekdays is ... else (repeat_weekdays or [])
        new_remind = (
            existing.remind_before_minutes
            if remind_before_minutes is ...
            else remind_before_minutes
        )
        new_uid = existing.ics_uid if ics_uid is ... else (ics_uid or None)

        with self.connect() as conn:
            conn.execute(
                """
                UPDATE events SET
                    title = ?, start_at = ?, end_at = ?, all_day = ?,
                    location = ?, notes = ?, updated_at = ?,
                    repeat_rule = ?, repeat_until = ?, repeat_weekdays = ?,
                    remind_before_minutes = ?, ics_uid = ?
                WHERE id = ?
                """,
                (
                    new_title,
                    to_iso(new_start),
                    to_iso(new_end) if new_end else None,
                    1 if new_all_day else 0,
                    new_location,
                    new_notes,
                    to_iso(now),
                    new_repeat,
                    new_until.isoformat() if new_until else None,
                    format_weekdays(new_days) if new_repeat else None,
                    new_remind,
                    new_uid,
                    event_id,
                ),
            )
            if tags is not None:
                self._set_tags(conn, event_id, new_tags)
            tags_map = self._tags_for(conn, [event_id])
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return self._row_to_event(row, tags_map.get(event_id, []))

    def get_event_by_uid(self, uid: str) -> EventRow | None:
        if not uid:
            return None
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE ics_uid = ? ORDER BY id ASC LIMIT 1",
                (uid,),
            ).fetchone()
            if row is None:
                return None
            event_id = str(row["id"])
            tags = self._tags_for(conn, [event_id]).get(event_id, [])
        return self._row_to_event(row, tags)

    def find_event_by_slot(
        self, title: str, start: datetime, end: datetime | None
    ) -> EventRow | None:
        start_iso = to_iso(start)
        end_iso = to_iso(end) if end else None
        with self.connect() as conn:
            if end_iso is None:
                row = conn.execute(
                    """
                    SELECT * FROM events
                    WHERE title = ? AND start_at = ? AND end_at IS NULL
                    ORDER BY id ASC LIMIT 1
                    """,
                    (title, start_iso),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM events
                    WHERE title = ? AND start_at = ? AND end_at = ?
                    ORDER BY id ASC LIMIT 1
                    """,
                    (title, start_iso, end_iso),
                ).fetchone()
            if row is None:
                return None
            event_id = str(row["id"])
            tags = self._tags_for(conn, [event_id]).get(event_id, [])
        return self._row_to_event(row, tags)

    def delete_event(self, event_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            return cur.rowcount > 0

    def list_events(
        self,
        *,
        range_start: datetime,
        range_end: datetime,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        limit: int = 5000,
    ) -> list[EventRow]:
        """Events overlapping [range_start, range_end)."""
        start_iso = to_iso(range_start)
        end_iso = to_iso(range_end)
        # Overlap: start < range_end AND coalesce(end, start) >= range_start
        # For all-day multi-day, end is exclusive-ish; treat end as inclusive instant.
        sql = """
            SELECT e.* FROM events e
            WHERE COALESCE(e.repeat_rule, '') = ''
              AND e.start_at < ?
              AND COALESCE(e.end_at, e.start_at) >= ?
        """
        params: list[object] = [end_iso, start_iso]

        if include_tags:
            placeholders = ",".join("?" * len(include_tags))
            sql += f"""
                AND e.id IN (
                    SELECT event_id FROM event_tags
                    WHERE lower(tag) IN ({placeholders})
                )
            """
            params.extend(t.casefold() for t in include_tags)

        if exclude_tags:
            placeholders = ",".join("?" * len(exclude_tags))
            sql += f"""
                AND e.id NOT IN (
                    SELECT event_id FROM event_tags
                    WHERE lower(tag) IN ({placeholders})
                )
            """
            params.extend(t.casefold() for t in exclude_tags)

        sql += " ORDER BY e.start_at ASC, e.id ASC LIMIT ?"
        params.append(max(1, min(limit, 10_000)))

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            ids = [str(r["id"]) for r in rows]
            tags_map = self._tags_for(conn, ids)
        return [self._row_to_event(r, tags_map.get(str(r["id"]), [])) for r in rows]

    def list_recurring_masters(
        self,
        *,
        range_start: datetime,
        range_end: datetime,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
    ) -> list[EventRow]:
        """Series that could still place an occurrence inside the range."""
        until_day = range_start.date().isoformat()
        sql = """
            SELECT e.* FROM events e
            WHERE COALESCE(e.repeat_rule, '') != ''
              AND e.start_at < ?
              AND (
                    e.repeat_until IS NULL OR e.repeat_until = ''
                    OR e.repeat_until >= ?
              )
        """
        params: list[object] = [to_iso(range_end), until_day]
        if include_tags:
            placeholders = ",".join("?" * len(include_tags))
            sql += f"""
                AND e.id IN (
                    SELECT event_id FROM event_tags
                    WHERE lower(tag) IN ({placeholders})
                )
            """
            params.extend(t.casefold() for t in include_tags)
        if exclude_tags:
            placeholders = ",".join("?" * len(exclude_tags))
            sql += f"""
                AND e.id NOT IN (
                    SELECT event_id FROM event_tags
                    WHERE lower(tag) IN ({placeholders})
                )
            """
            params.extend(t.casefold() for t in exclude_tags)
        sql += " ORDER BY e.start_at ASC, e.id ASC"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            ids = [str(r["id"]) for r in rows]
            tags_map = self._tags_for(conn, ids)
        return [self._row_to_event(r, tags_map.get(str(r["id"]), [])) for r in rows]

    def list_all_tags(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT tag FROM event_tags ORDER BY lower(tag) ASC"
            ).fetchall()
        return [str(r["tag"]) for r in rows]

    def list_tag_colors(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT tag, color FROM tag_colors ORDER BY lower(tag) ASC"
            ).fetchall()
        return {str(row["tag"]): str(row["color"]) for row in rows}

    def set_tag_color(self, tag: str, color: str) -> None:
        cleaned = " ".join(str(tag).split())
        if not cleaned:
            raise ValueError("tag must not be empty")
        with self.connect() as conn:
            conn.execute("DELETE FROM tag_colors WHERE lower(tag) = lower(?)", (cleaned,))
            conn.execute(
                "INSERT INTO tag_colors(tag, color) VALUES (?, ?)",
                (cleaned, color),
            )


_db: CalendarDB | None = None


def get_calendar_db() -> CalendarDB:
    global _db
    if _db is None:
        _db = CalendarDB()
        _db.init_schema()
    return _db


def reset_calendar_db_for_tests() -> None:
    global _db
    _db = None
