"""SQLite store for news topics, digests, and job runs."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from server.config import get_settings


def _db_path() -> Path:
    settings = get_settings()
    data_dir = Path(settings.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "news.db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class TopicRow:
    id: str
    label: str
    goal: str
    feed_urls: list[str] = field(default_factory=list)
    schedule_enabled: bool = True
    schedule_hour: int = 5
    schedule_minute: int = 30
    schedule_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    # 0=Mon … 6=Sun (ISO weekday - 1)
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class DigestRow:
    id: str
    topic_id: str
    topic_label: str
    digest: str
    item_count: int
    generated_at: datetime
    for_date: str
    ai_provider: str | None
    status: str  # ok | skipped_summarize | error
    error_message: str | None = None
    items_json: str = "[]"


class NewsDB:
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
                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    goal TEXT NOT NULL DEFAULT '',
                    feed_urls_json TEXT NOT NULL DEFAULT '[]',
                    schedule_enabled INTEGER NOT NULL DEFAULT 1,
                    schedule_hour INTEGER NOT NULL DEFAULT 5,
                    schedule_minute INTEGER NOT NULL DEFAULT 30,
                    schedule_days_json TEXT NOT NULL DEFAULT '[0,1,2,3,4,5,6]',
                    last_run_at TEXT,
                    last_run_status TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS digests (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL,
                    topic_label TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    generated_at TEXT NOT NULL,
                    for_date TEXT NOT NULL,
                    ai_provider TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    items_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_digests_topic_date
                    ON digests(topic_id, for_date, generated_at);
                CREATE INDEX IF NOT EXISTS idx_digests_date
                    ON digests(for_date, generated_at);
                """
            )

    def _topic_from_row(self, row: sqlite3.Row) -> TopicRow:
        days = json.loads(row["schedule_days_json"] or "[0,1,2,3,4,5,6]")
        return TopicRow(
            id=str(row["id"]),
            label=str(row["label"]),
            goal=str(row["goal"] or ""),
            feed_urls=list(json.loads(row["feed_urls_json"] or "[]")),
            schedule_enabled=bool(row["schedule_enabled"]),
            schedule_hour=int(row["schedule_hour"]),
            schedule_minute=int(row["schedule_minute"]),
            schedule_days=[int(d) for d in days],
            last_run_at=parse_iso(row["last_run_at"]),
            last_run_status=row["last_run_status"],
            last_error=row["last_error"],
            created_at=parse_iso(row["created_at"]),
            updated_at=parse_iso(row["updated_at"]),
        )

    def _digest_from_row(self, row: sqlite3.Row) -> DigestRow:
        return DigestRow(
            id=str(row["id"]),
            topic_id=str(row["topic_id"]),
            topic_label=str(row["topic_label"]),
            digest=str(row["digest"]),
            item_count=int(row["item_count"] or 0),
            generated_at=parse_iso(row["generated_at"]),  # type: ignore[arg-type]
            for_date=str(row["for_date"]),
            ai_provider=row["ai_provider"],
            status=str(row["status"]),
            error_message=row["error_message"],
            items_json=str(row["items_json"] or "[]"),
        )

    def upsert_topic(self, topic: TopicRow) -> TopicRow:
        now = utc_now()
        created = topic.created_at or now
        updated = now
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO topics(
                    id, label, goal, feed_urls_json, schedule_enabled,
                    schedule_hour, schedule_minute, schedule_days_json,
                    last_run_at, last_run_status, last_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    goal = excluded.goal,
                    feed_urls_json = excluded.feed_urls_json,
                    schedule_enabled = excluded.schedule_enabled,
                    schedule_hour = excluded.schedule_hour,
                    schedule_minute = excluded.schedule_minute,
                    schedule_days_json = excluded.schedule_days_json,
                    updated_at = excluded.updated_at
                """,
                (
                    topic.id,
                    topic.label,
                    topic.goal,
                    json.dumps(topic.feed_urls),
                    1 if topic.schedule_enabled else 0,
                    topic.schedule_hour,
                    topic.schedule_minute,
                    json.dumps(topic.schedule_days),
                    to_iso(topic.last_run_at) if topic.last_run_at else None,
                    topic.last_run_status,
                    topic.last_error,
                    to_iso(created),
                    to_iso(updated),
                ),
            )
        return self.get_topic(topic.id)  # type: ignore[return-value]

    def get_topic(self, topic_id: str) -> TopicRow | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM topics WHERE id = ?", (topic_id,)
            ).fetchone()
        return None if row is None else self._topic_from_row(row)

    def list_topics(self) -> list[TopicRow]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM topics ORDER BY label ASC"
            ).fetchall()
        return [self._topic_from_row(r) for r in rows]

    def delete_topic(self, topic_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            return cur.rowcount > 0

    def mark_topic_run(
        self,
        topic_id: str,
        *,
        status: str,
        error: str | None = None,
        when: datetime | None = None,
    ) -> None:
        when = when or utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE topics SET
                    last_run_at = ?, last_run_status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (to_iso(when), status, error, to_iso(when), topic_id),
            )

    def insert_digest(self, digest: DigestRow) -> DigestRow:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO digests(
                    id, topic_id, topic_label, digest, item_count,
                    generated_at, for_date, ai_provider, status,
                    error_message, items_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    digest.id,
                    digest.topic_id,
                    digest.topic_label,
                    digest.digest,
                    digest.item_count,
                    to_iso(digest.generated_at),
                    digest.for_date,
                    digest.ai_provider,
                    digest.status,
                    digest.error_message,
                    digest.items_json,
                ),
            )
        return digest

    def latest_digest_for_topic(
        self, topic_id: str, for_date: str | None = None
    ) -> DigestRow | None:
        with self.connect() as conn:
            if for_date:
                row = conn.execute(
                    """
                    SELECT * FROM digests
                    WHERE topic_id = ? AND for_date = ?
                    ORDER BY generated_at DESC LIMIT 1
                    """,
                    (topic_id, for_date),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM digests
                    WHERE topic_id = ?
                    ORDER BY generated_at DESC LIMIT 1
                    """,
                    (topic_id,),
                ).fetchone()
        return None if row is None else self._digest_from_row(row)

    def list_digests(
        self,
        *,
        topic_id: str | None = None,
        for_date: str | None = None,
        limit: int = 50,
    ) -> list[DigestRow]:
        clauses: list[str] = []
        params: list[Any] = []
        if topic_id:
            clauses.append("topic_id = ?")
            params.append(topic_id)
        if for_date:
            clauses.append("for_date = ?")
            params.append(for_date)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM digests
                {where}
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._digest_from_row(r) for r in rows]

    def latest_digests_by_topic(self, for_date: str) -> list[DigestRow]:
        """One latest digest per topic for the given local date (ok/skipped only)."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT d.* FROM digests d
                INNER JOIN (
                    SELECT topic_id, MAX(generated_at) AS max_gen
                    FROM digests
                    WHERE for_date = ? AND status IN ('ok', 'skipped_summarize')
                    GROUP BY topic_id
                ) latest
                  ON d.topic_id = latest.topic_id
                 AND d.generated_at = latest.max_gen
                ORDER BY d.topic_label ASC
                """,
                (for_date,),
            ).fetchall()
        return [self._digest_from_row(r) for r in rows]


_db: NewsDB | None = None


def get_news_db() -> NewsDB:
    global _db
    if _db is None:
        _db = NewsDB()
        _db.init_schema()
    return _db


def reset_news_db_for_tests() -> None:
    global _db
    _db = None


def new_digest_id() -> str:
    return f"dig_{uuid4().hex[:12]}"
