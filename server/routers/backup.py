"""Light Phase 6 — export SSOT SQLite files as a zip for PC backup.

Restore is intentionally manual / out of scope for this slice
(stop the server, replace files under PA_DATA_DIR, restart).
No multi-device conflict resolution; no M365.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from server import __version__
from server.config import get_settings

router = APIRouter(prefix="/backup", tags=["backup"])

# Logical name → filename under PA_DATA_DIR
_DB_FILES = {
    "calendar": "calendar.db",
    "news": "news.db",
    "health": "health.db",
    "climate": "climate.db",
}


def _data_dir() -> Path:
    return Path(get_settings().data_dir).expanduser().resolve()


def _safe_sqlite_snapshot(src: Path, dest: Path) -> None:
    """Copy a live SQLite DB via the backup API (handles WAL)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        dest_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()


def build_manifest(*, included: list[dict], notes: list[str]) -> dict:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    return {
        "format": "personal-aissistent-backup-v1",
        "created_at": now.isoformat(timespec="seconds"),
        "timezone": settings.timezone,
        "app_version": __version__,
        "data_dir": str(_data_dir()),
        "files": included,
        "notes": notes,
        "restore": (
            "Manual restore only for this V1 slice: stop the Personal AIssistent "
            "server, extract matching *.db files into PA_DATA_DIR (and optional "
            "advisor/ markdown), then restart. No automated conflict resolution."
        ),
    }


def collect_backup_plan() -> tuple[list[dict], list[tuple[str, Path]], list[str]]:
    """Return (manifest file entries, (arcname, path) pairs to pack, notes)."""
    data = _data_dir()
    included: list[dict] = []
    sources: list[tuple[str, Path]] = []
    notes: list[str] = []

    for name, filename in _DB_FILES.items():
        path = data / filename
        if path.is_file():
            included.append(
                {
                    "role": name,
                    "path": f"databases/{filename}",
                    "source": str(path),
                    "size_bytes": path.stat().st_size,
                    "present": True,
                }
            )
            sources.append((f"databases/{filename}", path))
        else:
            included.append(
                {
                    "role": name,
                    "path": f"databases/{filename}",
                    "present": False,
                }
            )
            notes.append(f"{filename} not found under data dir (skipped).")

    advisor = data / "advisor"
    if advisor.is_dir():
        for md in sorted(advisor.glob("*.md")):
            arc = f"advisor/{md.name}"
            included.append(
                {
                    "role": "advisor_markdown",
                    "path": arc,
                    "source": str(md),
                    "size_bytes": md.stat().st_size,
                    "present": True,
                }
            )
            sources.append((arc, md))

    return included, sources, notes


@router.get("")
def backup_info() -> JSONResponse:
    """List what a backup export would include (no download)."""
    included, _, notes = collect_backup_plan()
    return JSONResponse(build_manifest(included=included, notes=notes))


@router.get("/export")
def backup_export() -> StreamingResponse:
    """Download a zip of present SSOT databases (+ advisor markdown if any)."""
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    stamp = datetime.now(tz).strftime("%Y%m%d-%H%M%S")
    included, sources, notes = collect_backup_plan()
    manifest = build_manifest(included=included, notes=notes)

    buf = BytesIO()
    with tempfile.TemporaryDirectory(prefix="pa-backup-") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            )
            for arcname, src in sources:
                if arcname.startswith("databases/") and src.suffix == ".db":
                    snap = tmp_path / src.name
                    _safe_sqlite_snapshot(src, snap)
                    zf.write(snap, arcname=arcname)
                else:
                    zf.write(src, arcname=arcname)

    buf.seek(0)
    filename = f"personal-aissistent-backup-{stamp}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
