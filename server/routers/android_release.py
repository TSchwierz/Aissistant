"""Phone APK updates.

The build script writes ``android/release/HealthScale.apk`` and ``release.json``.
Those files are tracked, so a git pull on the Pi publishes the build. The phone
compares ``versionCode`` and downloads the APK with the same API key it already uses.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from server.config import get_settings

router = APIRouter(prefix="/app", tags=["app"])

_REPO_ROOT = Path(__file__).resolve().parents[2]

APK_NAME = "HealthScale.apk"
RELEASE_NAME = "release.json"
APK_MEDIA_TYPE = "application/vnd.android.package-archive"
_MAX_VERSION_CODE = 2_147_483_647
_MAX_VERSION_NAME = 32

_cache_lock = threading.Lock()
_cache: dict[str, tuple | dict | None] = {"key": None, "value": None}


def android_release_dir() -> Path:
    raw = get_settings().android_release_dir.strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (_REPO_ROOT / "android" / "release").resolve()


def clear_release_cache() -> None:
    with _cache_lock:
        _cache["key"] = None
        _cache["value"] = None


def load_release(directory: Path | None = None) -> dict | None:
    """Return the published release, or None when nothing valid is on disk."""
    folder = (directory if directory is not None else android_release_dir()).expanduser().resolve()
    meta_path = (folder / RELEASE_NAME).resolve()
    apk_path = (folder / APK_NAME).resolve()
    if not _inside(folder, meta_path) or not _inside(folder, apk_path):
        return None
    if not meta_path.is_file() or not apk_path.is_file():
        return None
    try:
        # Hash the small JSON every time. A copy onto the Pi can keep the old
        # timestamp, and the APK itself is only re-read when this changes.
        meta_hash = hashlib.sha256(meta_path.read_bytes()).hexdigest()
        apk_stat = apk_path.stat()
        key = (str(apk_path), apk_stat.st_mtime_ns, apk_stat.st_size, meta_hash)
    except OSError:
        return None
    with _cache_lock:
        if _cache["key"] == key:
            cached = _cache["value"]
            return cached if isinstance(cached, dict) or cached is None else None
    value = _read_release(meta_path, apk_path)
    with _cache_lock:
        _cache["key"] = key
        _cache["value"] = value
    return value


def _inside(folder: Path, path: Path) -> bool:
    try:
        path.relative_to(folder)
    except ValueError:
        return False
    return True


def _read_release(meta_path: Path, apk_path: Path) -> dict | None:
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        size = apk_path.stat().st_size
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or size <= 0:
        return None
    if raw.get("apk", APK_NAME) != APK_NAME:
        return None
    version_code = raw.get("versionCode")
    version_name = raw.get("versionName")
    sha = raw.get("sha256")
    if isinstance(version_code, bool) or not isinstance(version_code, int):
        return None
    if version_code < 1 or version_code > _MAX_VERSION_CODE:
        return None
    if not isinstance(version_name, str):
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in version_name):
        return None
    version_name = version_name.strip()
    if not version_name or len(version_name) > _MAX_VERSION_NAME:
        return None
    if not isinstance(sha, str) or len(sha) != 64:
        return None
    if any(char not in "0123456789abcdefABCDEF" for char in sha):
        return None
    digest = _sha256(apk_path)
    if digest is None or digest.lower() != sha.lower():
        return None
    return {
        "available": True,
        "versionCode": version_code,
        "versionName": version_name,
        "sha256": digest,
        "bytes": size,
        "apkPath": "/app/apk",
    }


def _sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


@router.get("/release")
def app_release() -> dict:
    found = load_release()
    if found is None:
        return {"available": False}
    return found


@router.get("/apk")
def app_apk() -> FileResponse:
    found = load_release()
    if found is None:
        raise HTTPException(status_code=404, detail="No Android release is published")
    path = android_release_dir() / APK_NAME
    return FileResponse(
        path,
        media_type=APK_MEDIA_TYPE,
        filename=APK_NAME,
    )
