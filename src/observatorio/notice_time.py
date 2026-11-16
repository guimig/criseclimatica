"""Normalize official notice windows; publication age never shortens event validity.

For INMET, when separate date and hour fields are supplied, the date is a
calendar label even if its serializer emits midnight UTC. The separate hour is
a Brazilian civil clock unless it has its own explicit UTC offset.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLOCK = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?$", re.I)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def moment(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def _source_datetime(day: object, clock: object, *, end: bool) -> tuple[datetime | None, str]:
    if not isinstance(day, str) or len(day) > 60:
        return None, "invalid"
    raw = day.strip()
    token = raw[:10]
    if not DATE.fullmatch(token):
        return None, "invalid"
    try:
        calendar = datetime.strptime(token, "%Y-%m-%d")
    except ValueError:
        return None, "invalid"
    if isinstance(clock, str) and clock.strip():
        wall = clock.strip().replace("h", ":").replace("H", ":")
        if not CLOCK.fullmatch(wall):
            return None, "invalid"
        hour = wall.split(":")[0]
        wall = hour.zfill(2) + wall[len(hour):]
        try:
            parsed = datetime.fromisoformat(token + "T" + wall.replace("Z", "+00:00"))
        except ValueError:
            return None, "invalid"
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc), "explicit_offset"
        return parsed.replace(tzinfo=BRASILIA).astimezone(timezone.utc), "brasilia_assumed"
    # An ISO timestamp without a separately supplied clock carries its own
    # time and offset. Midnight 00:00 with an offset is not a date-only field.
    if "T" in raw or " " in raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo:
                return parsed.astimezone(timezone.utc), "explicit_offset"
            return parsed.replace(tzinfo=BRASILIA).astimezone(timezone.utc), "brasilia_assumed"
        except ValueError:
            return None, "invalid"
    # Date-only end is exclusive: midnight after the final stated day.
    if end:
        calendar += timedelta(days=1)
    return calendar.replace(tzinfo=BRASILIA).astimezone(timezone.utc), "brasilia_full_day"


def normalize_window(
    start_day: object, start_clock: object, end_day: object, end_clock: object,
) -> tuple[str | None, str | None, str]:
    start, left = _source_datetime(start_day, start_clock, end=False)
    end, right = _source_datetime(end_day, end_clock, end=True)
    if not start or not end or end <= start or end - start > timedelta(days=400):
        return None, None, "invalid_or_missing"
    if left == "explicit_offset" and right == "explicit_offset":
        basis = "source_explicit_offset"
    elif "brasilia_full_day" in (left, right):
        basis = "brasilia_full_day_when_clock_absent"
    else:
        basis = "brasilia_assumed_when_offset_absent"
    return utc_text(start), utc_text(end), basis


def lifecycle(start_at: object, end_at: object, now: datetime, *, cancelled: bool = False) -> str:
    if cancelled:
        return "cancelled"
    start, end = moment(start_at), moment(end_at)
    if not start or not end or end <= start:
        return "unverified"
    return "expired" if now >= end else "future" if now < start else "ongoing"
