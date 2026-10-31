"""Parse .ics, a zip of .ics files, and Outlook CSV into calendar events.

Repeats are kept only when they already match weekly, biweekly, or monthly.
Anything else becomes one event and is reported as not kept.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_DAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_RULE_KEYS = {"FREQ", "INTERVAL", "UNTIL", "BYDAY", "WKST", "BYMONTHDAY"}
_DURATION = re.compile(
    r"^(?P<sign>[-+])?P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
    re.IGNORECASE,
)
_TZ_ALIASES = {
    "UTC": "UTC",
    "W. EUROPE STANDARD TIME": "Europe/Berlin",
    "CENTRAL EUROPEAN STANDARD TIME": "Europe/Warsaw",
    "ROMANCE STANDARD TIME": "Europe/Paris",
    "GMT STANDARD TIME": "Europe/London",
    "GREENWICH STANDARD TIME": "Etc/UTC",
}


@dataclass
class IncomingEvent:
    title: str
    start: datetime
    end: datetime | None
    all_day: bool
    location: str | None
    notes: str | None
    tags: list[str]
    uid: str | None
    repeat: str | None
    repeat_until: date | None
    repeat_weekdays: list[int] | None
    remind_before_minutes: int | None
    repeat_note: str | None
    alarm_note: str | None
    match_slot: bool


@dataclass
class ParseBatch:
    events: list[IncomingEvent] = field(default_factory=list)
    skipped: int = 0


@dataclass
class _Component:
    name: str
    props: list[tuple[str, dict[str, str], str]] = field(default_factory=list)
    children: list[_Component] = field(default_factory=list)


def read_upload(filename: str, raw: bytes, tz: ZoneInfo) -> ParseBatch:
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name.endswith(".zip") or raw[:4] == b"PK\x03\x04":
        return _read_zip(raw, tz)
    text = _decode(raw)
    head = text.lstrip().upper()
    if name.endswith(".csv") or (not name.endswith((".ics", ".ical")) and _looks_like_csv(text)):
        return parse_csv_text(text, tz)
    if "BEGIN:VCALENDAR" in head or name.endswith((".ics", ".ical")):
        return parse_ics_text(text, tz)
    if _looks_like_csv(text):
        return parse_csv_text(text, tz)
    raise ValueError("file must be an .ics calendar, a .zip of .ics files, or an Outlook CSV export")


def parse_ics_text(text: str, tz: ZoneInfo) -> ParseBatch:
    batch = ParseBatch()
    root = _parse_components(text)
    for event in _walk_events(root):
        parsed = _event_from_vevent(event, tz)
        if parsed is None:
            batch.skipped += 1
            continue
        batch.events.append(parsed)
    return batch


def parse_csv_text(text: str, tz: ZoneInfo) -> ParseBatch:
    body, delimiter = _csv_body(text)
    reader = csv.DictReader(io.StringIO(body), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV export has no header row")
    fields = {_norm_header(name): name for name in reader.fieldnames if name}
    if "subject" not in fields and "title" not in fields and "summary" not in fields:
        raise ValueError("CSV export needs a Subject column")
    batch = ParseBatch()
    for raw in reader:
        if raw is None or not any((value or "").strip() for value in raw.values()):
            continue
        row = {_norm_header(key): (value or "").strip() for key, value in raw.items() if key}
        parsed = _event_from_csv(row, tz)
        if parsed is None:
            batch.skipped += 1
            continue
        batch.events.append(parsed)
    return batch


def _read_zip(raw: bytes, tz: ZoneInfo) -> ParseBatch:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ValueError("zip file could not be read") from exc
    names = [
        name
        for name in archive.namelist()
        if name.lower().endswith(".ics") and not name.startswith("__MACOSX/") and not name.endswith("/")
    ]
    if not names:
        raise ValueError("zip does not contain an .ics file")
    batch = ParseBatch()
    for name in names:
        part = parse_ics_text(_decode(archive.read(name)), tz)
        batch.events.extend(part.events)
        batch.skipped += part.skipped
    return batch


def _decode(raw: bytes) -> str:
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _looks_like_csv(text: str) -> bool:
    line = text.lstrip("\ufeff").splitlines()[0].lower() if text.strip() else ""
    if line.startswith("sep="):
        return True
    return "subject" in line and "start" in line


def _csv_body(text: str) -> tuple[str, str]:
    lines = text.lstrip("\ufeff").splitlines()
    delimiter = ","
    if lines and lines[0].lower().startswith("sep=") and len(lines[0]) >= 5:
        delimiter = lines[0][4]
        lines = lines[1:]
    elif lines:
        header = lines[0]
        counts = {",": header.count(","), ";": header.count(";"), "\t": header.count("\t")}
        delimiter = max(counts, key=lambda key: counts[key])
    return "\n".join(lines), delimiter


def _norm_header(name: str) -> str:
    return " ".join(name.replace("\ufeff", "").strip().casefold().split())


def _cell(row: dict[str, str], *names: str) -> str:
    for name in names:
        if row.get(name):
            return row[name]
    return ""


def _event_from_csv(row: dict[str, str], tz: ZoneInfo) -> IncomingEvent | None:
    title = " ".join(_cell(row, "subject", "title", "summary").split())
    if not title:
        return None
    all_day = _cell(row, "all day event", "all day", "all-day event").casefold() in {
        "true",
        "yes",
        "1",
        "y",
    }
    try:
        start = _csv_moment(row, "start", tz, all_day)
        end = _csv_moment(row, "end", tz, all_day, missing_ok=True)
    except ValueError:
        return None
    if start is None:
        return None
    if all_day:
        if end is not None and end.date() <= start.date():
            end = None
        elif end is not None:
            end = datetime(end.year, end.month, end.day, tzinfo=tz)
        start = datetime(start.year, start.month, start.day, tzinfo=tz)
    elif end is not None and end < start:
        return None
    tags = _split_tags(_cell(row, "categories", "category", "tags"))
    return IncomingEvent(
        title=title[:300],
        start=start,
        end=end,
        all_day=all_day,
        location=_clip(_cell(row, "location"), 500),
        notes=_clip(_cell(row, "description", "notes", "body"), 4000),
        tags=tags,
        uid=None,
        repeat=None,
        repeat_until=None,
        repeat_weekdays=None,
        remind_before_minutes=None,
        repeat_note=None,
        alarm_note=None,
        match_slot=True,
    )


def _csv_moment(
    row: dict[str, str],
    which: str,
    tz: ZoneInfo,
    all_day: bool,
    *,
    missing_ok: bool = False,
) -> datetime | None:
    date_text = _cell(row, f"{which} date")
    time_text = _cell(row, f"{which} time")
    if date_text:
        day = _parse_csv_date(date_text)
        if all_day or not time_text:
            return datetime(day.year, day.month, day.day, tzinfo=tz)
        hour, minute, second = _parse_csv_time(time_text)
        return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=tz)
    combined = _cell(row, which, f"dt{which}")
    if not combined:
        if missing_ok:
            return None
        raise ValueError(f"missing {which}")
    if " " in combined.strip():
        date_part, time_part = combined.strip().split(None, 1)
        day = _parse_csv_date(date_part)
        if all_day:
            return datetime(day.year, day.month, day.day, tzinfo=tz)
        hour, minute, second = _parse_csv_time(time_part)
        return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=tz)
    day = _parse_csv_date(combined)
    return datetime(day.year, day.month, day.day, tzinfo=tz)


def _parse_csv_date(text: str) -> date:
    raw = text.strip()
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    dotted = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", raw)
    if dotted:
        return _ymd(_year(dotted.group(3)), int(dotted.group(2)), int(dotted.group(1)))
    dashed = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", raw)
    if dashed:
        return _ymd(_year(dashed.group(3)), int(dashed.group(2)), int(dashed.group(1)))
    slashed = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", raw)
    if slashed:
        first = int(slashed.group(1))
        second = int(slashed.group(2))
        year = _year(slashed.group(3))
        if first > 12:
            return _ymd(year, second, first)
        if second > 12:
            return _ymd(year, first, second)
        return _ymd(year, first, second)
    raise ValueError(f"bad date {text}")


def _year(text: str) -> int:
    year = int(text)
    if year < 100:
        return 2000 + year
    return year


def _ymd(year: int, month: int, day: int) -> date:
    return date(year, month, day)


def _parse_csv_time(text: str) -> tuple[int, int, int]:
    raw = text.strip()
    if not raw:
        return 0, 0, 0
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?", raw)
    if not match:
        raise ValueError(f"bad time {text}")
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    ampm = match.group(4)
    if ampm:
        hour %= 12
        if ampm.casefold() == "pm":
            hour += 12
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError(f"bad time {text}")
    return hour, minute, second


def _parse_components(text: str) -> _Component:
    root = _Component("ROOT")
    stack = [root]
    for line in _unfold(text):
        upper = line.upper()
        if upper.startswith("BEGIN:"):
            child = _Component(line.split(":", 1)[1].strip().upper())
            stack[-1].children.append(child)
            stack.append(child)
            continue
        if upper.startswith("END:"):
            if len(stack) > 1:
                stack.pop()
            continue
        name, params, value = _split_prop(line)
        stack[-1].props.append((name, params, value))
    return root


def _unfold(text: str) -> list[str]:
    logical: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in " \t" and logical:
            logical[-1] += line[1:]
        elif line:
            logical.append(line)
    return logical


def _split_prop(line: str) -> tuple[str, dict[str, str], str]:
    quoted = False
    colon = None
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == ":" and not quoted:
            colon = index
            break
    if colon is None:
        return line.strip().upper(), {}, ""
    left, value = line[:colon], line[colon + 1 :]
    name, _, param_text = left.partition(";")
    return name.strip().upper(), _params(param_text), _unescape(value)


def _params(text: str) -> dict[str, str]:
    if not text:
        return {}
    parts: list[str] = []
    buf: list[str] = []
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
            buf.append(char)
        elif char == ";" and not quoted:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(char)
    if buf:
        parts.append("".join(buf))
    out: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        val = val.strip()
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        out[key.strip().upper()] = val
    return out


def _unescape(value: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            if nxt in "nN":
                out.append("\n")
            else:
                out.append(nxt)
            index += 2
            continue
        out.append(value[index])
        index += 1
    return "".join(out)


def _walk_events(comp: _Component):
    if comp.name == "VEVENT":
        yield comp
        return
    for child in comp.children:
        yield from _walk_events(child)


def _props(comp: _Component, name: str) -> list[tuple[dict[str, str], str]]:
    return [(params, value) for prop, params, value in comp.props if prop == name]


def _first(comp: _Component, name: str) -> tuple[dict[str, str], str]:
    found = _props(comp, name)
    if not found:
        return {}, ""
    return found[0]


def _event_from_vevent(comp: _Component, tz: ZoneInfo) -> IncomingEvent | None:
    _, summary = _first(comp, "SUMMARY")
    title = " ".join(summary.replace("\n", " ").split())
    if not title:
        return None
    start_params, start_raw = _first(comp, "DTSTART")
    if not start_raw:
        return None
    try:
        start, start_all_day = _ics_datetime(start_raw, start_params, tz)
    except ValueError:
        return None
    end_params, end_raw = _first(comp, "DTEND")
    end: datetime | None = None
    end_all_day = False
    if end_raw:
        try:
            end, end_all_day = _ics_datetime(end_raw, end_params, tz)
        except ValueError:
            return None
    all_day = start_all_day
    if all_day and end is not None and end_all_day:
        last = end.date() - timedelta(days=1)
        if last <= start.date():
            end = None
        else:
            end = datetime(last.year, last.month, last.day, tzinfo=tz)
        start = datetime(start.year, start.month, start.day, tzinfo=tz)
    elif all_day:
        start = datetime(start.year, start.month, start.day, tzinfo=tz)
        end = None
    elif end is not None and end < start:
        return None

    uid = _first(comp, "UID")[1].strip() or None
    recurrence = _first(comp, "RECURRENCE-ID")[1].strip()
    if uid and recurrence:
        uid = f"{uid}#{recurrence}"
    rules = _props(comp, "RRULE")
    has_exdate = any(prop == "EXDATE" for prop, _, _ in comp.props)
    has_rdate = any(prop == "RDATE" for prop, _, _ in comp.props)
    repeat, until, weekdays, repeat_note = _repeat_from_rule(
        rules[0][1] if len(rules) == 1 else "",
        start,
        dropped=bool(recurrence or has_exdate or has_rdate or len(rules) > 1),
        had_rule=bool(rules or recurrence or has_exdate or has_rdate),
    )
    remind, alarm_note = _alarms(comp)
    tags: list[str] = []
    for _, value in _props(comp, "CATEGORIES"):
        tags.extend(_split_tags(value))
    _, location = _first(comp, "LOCATION")
    _, notes = _first(comp, "DESCRIPTION")
    return IncomingEvent(
        title=title[:300],
        start=start,
        end=end,
        all_day=all_day,
        location=_clip(location, 500),
        notes=_clip(notes, 4000),
        tags=tags,
        uid=uid,
        repeat=repeat,
        repeat_until=until,
        repeat_weekdays=weekdays,
        remind_before_minutes=remind,
        repeat_note=repeat_note,
        alarm_note=alarm_note,
        match_slot=False,
    )


def _ics_datetime(value: str, params: dict[str, str], tz: ZoneInfo) -> tuple[datetime, bool]:
    raw = value.strip()
    as_date = params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", raw) is not None
    if as_date:
        if len(raw) < 8 or not raw[:8].isdigit():
            raise ValueError(raw)
        day = date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))
        return datetime(day.year, day.month, day.day, tzinfo=tz), True
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z)?", raw, re.IGNORECASE)
    if not match:
        raise ValueError(raw)
    stamp = datetime(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
        int(match.group(5)),
        int(match.group(6)),
    )
    if match.group(7):
        stamp = stamp.replace(tzinfo=timezone.utc)
    else:
        stamp = stamp.replace(tzinfo=_zone(params.get("TZID"), tz))
    return stamp.astimezone(tz), False


def _zone(tzid: str | None, fallback: ZoneInfo) -> ZoneInfo:
    if not tzid:
        return fallback
    key = tzid.strip().strip('"')
    mapped = _TZ_ALIASES.get(key.upper(), key)
    try:
        return ZoneInfo(mapped)
    except Exception:
        return fallback


def _repeat_from_rule(
    raw: str,
    start: datetime,
    *,
    dropped: bool,
    had_rule: bool,
) -> tuple[str | None, date | None, list[int] | None, str | None]:
    if dropped:
        return None, None, None, "repeat not kept" if had_rule else None
    if not raw:
        return None, None, None, None
    parts: dict[str, str] = {}
    for piece in raw.split(";"):
        if "=" not in piece:
            continue
        key, val = piece.split("=", 1)
        parts[key.strip().upper()] = val.strip()
    if set(parts) - _RULE_KEYS:
        return None, None, None, "repeat not kept"
    freq = parts.get("FREQ", "").upper()
    if "INTERVAL" in parts:
        if not parts["INTERVAL"].isdigit():
            return None, None, None, "repeat not kept"
        interval = int(parts["INTERVAL"])
    else:
        interval = 1
    until = None
    if "UNTIL" in parts:
        until = _parse_until(parts["UNTIL"])
        if until is None or until < start.date():
            return None, None, None, "repeat not kept"
    weekdays = None
    if "BYDAY" in parts:
        days: list[int] = []
        for token in parts["BYDAY"].split(","):
            token = token.strip().upper()
            if not token:
                continue
            if token not in _DAY:
                return None, None, None, "repeat not kept"
            if _DAY[token] not in days:
                days.append(_DAY[token])
        weekdays = days or None
    if "BYMONTHDAY" in parts:
        if freq != "MONTHLY":
            return None, None, None, "repeat not kept"
        month_days = []
        for token in parts["BYMONTHDAY"].split(","):
            token = token.strip()
            if not token.lstrip("-").isdigit():
                return None, None, None, "repeat not kept"
            month_days.append(int(token))
        if month_days != [start.day]:
            return None, None, None, "repeat not kept"
    if freq == "WEEKLY" and interval == 1:
        return "weekly", until, weekdays, None
    if freq == "WEEKLY" and interval == 2:
        return "biweekly", until, weekdays, None
    if freq == "MONTHLY" and interval == 1 and not weekdays:
        return "monthly", until, None, None
    return None, None, None, "repeat not kept"


def _parse_until(value: str) -> date | None:
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) < 8:
        return None
    try:
        return date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def _alarms(comp: _Component) -> tuple[int | None, str | None]:
    chosen: int | None = None
    reasons: list[str] = []
    for child in comp.children:
        if child.name != "VALARM":
            continue
        action = _first(child, "ACTION")[1].strip().upper()
        params, trigger = _first(child, "TRIGGER")
        trigger = trigger.strip()
        if action == "EMAIL":
            reasons.append("email alarm ignored")
            continue
        if action not in {"", "DISPLAY", "AUDIO"}:
            reasons.append("alarm not kept")
            continue
        if not trigger:
            reasons.append("alarm not kept")
            continue
        related = params.get("RELATED", "START").upper()
        if related not in {"", "START"}:
            reasons.append("alarm not kept")
            continue
        if params.get("VALUE", "").upper() == "DATE-TIME" or _absolute_trigger(trigger):
            reasons.append("absolute alarm ignored")
            continue
        minutes, reason = _duration_minutes(trigger)
        if reason or minutes is None:
            reasons.append(reason or "alarm not kept")
            continue
        if chosen is None:
            chosen = minutes
        else:
            reasons.append("alarm not kept")
    if not reasons:
        return chosen, None
    unique: list[str] = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    return chosen, "; ".join(unique)


def _absolute_trigger(trigger: str) -> bool:
    upper = trigger.upper()
    if upper.startswith("-P") or upper.startswith("+P") or upper.startswith("P"):
        return False
    return re.match(r"\d{8}", upper) is not None


def _duration_minutes(trigger: str) -> tuple[int | None, str | None]:
    match = _DURATION.fullmatch(trigger.strip())
    if not match or match.group("sign") != "-":
        if match and match.group("sign") != "-":
            return None, "alarm not kept"
        return None, "absolute alarm ignored" if _absolute_trigger(trigger) else "alarm not kept"
    weeks = int(match.group("weeks") or 0)
    days = int(match.group("days") or 0)
    seconds = int(match.group("seconds") or 0)
    if weeks or days or seconds:
        return None, "alarm not kept"
    if match.group("hours") is None and match.group("minutes") is None:
        return None, "alarm not kept"
    total = int(match.group("hours") or 0) * 60 + int(match.group("minutes") or 0)
    if total < 1 or total > 10080:
        return None, "alarm not kept"
    return total, None


def _split_tags(value: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;]", value):
        tag = " ".join(part.split())
        if not tag or tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        tags.append(tag)
    return tags


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return text[:limit]
