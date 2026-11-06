"""Bounded, portable DAILY MODEL PUBLICATION SNAPSHOTS, not climate observations.

A one-year rolling publication history may be embedded in GitHub Pages, but it
is not a backup or scientifically valid measured climate series. A future
external archive can store raw observations and long-lived rollups.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Sao_Paulo")
MAX_SAVED_DAYS = 400
MAX_PREVIOUS_RECORDS = 6000
_KIND = "daily_last_model_publication_not_station_observation"


def _moment(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid history timestamp")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid history timestamp") from exc
    if moment.tzinfo is None:
        raise ValueError("History timestamp lacks timezone")
    return moment.astimezone(timezone.utc)


def _number(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and -1e6 < value < 1e6 else None


def merge_daily_publications(
    previous: dict[str, Any] | None,
    overview: dict[str, Any],
    details: dict[str, dict[str, Any]],
    *, now: datetime | None = None,
    keep_days: int = 366,
) -> dict[str, Any]:
    """One latest successfully collected model state per locality/day, idempotently."""
    if not (1 <= keep_days <= MAX_SAVED_DAYS):
        raise ValueError("Retention must be between 1 and 400 days")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = (now.astimezone(TIMEZONE).date() - timedelta(days=keep_days - 1))
    permitted = {loc["id"] for loc in overview["locations"]}
    records: dict[tuple[str, str], dict[str, Any]] = {}

    if previous is not None:
        if not isinstance(previous, dict) or previous.get("schema_version") != 1 or previous.get("kind") != _KIND:
            raise ValueError("Unrecognized previous model history schema")
        entries = previous.get("records")
        if not isinstance(entries, list) or len(entries) > MAX_PREVIOUS_RECORDS:
            raise ValueError("Previous model history size/shape invalid")
        for record in entries:
            if not isinstance(record, dict):
                raise ValueError("Malformed previous model history row")
            if record.get("kind") != "model_snapshot_not_observation" or record.get("source") != "open-meteo":
                raise ValueError("Previous history changed source or classification")
            slug, day = record.get("location_id"), record.get("day_local")
            if slug not in permitted or not isinstance(day, str):
                continue
            try:
                parsed_day = date.fromisoformat(day)
                timestamp = _moment(record.get("collected_at"))
                _moment(record.get("model_reference_at"))
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid previous model history record") from exc
            if not cutoff <= parsed_day <= now.astimezone(TIMEZONE).date():
                continue
            key = (slug, day)
            if key in records:
                raise ValueError("Duplicate previous model history record")
            if timestamp > now + timedelta(hours=3):
                raise ValueError("Future model history timestamp")
            records[key] = record

    next24 = {place["id"]: place.get("rain_next_24h_mm") for place in overview["locations"]}
    for slug, detail in details.items():
        current = detail.get("current") or {}
        collected = _moment(detail.get("collected_at"))
        ref = _moment(current.get("time"))
        day = collected.astimezone(TIMEZONE).date()
        if day < cutoff or day > now.astimezone(TIMEZONE).date() or collected > now + timedelta(hours=3):
            continue
        new = {
            "location_id": slug, "day_local": day.isoformat(),
            "collected_at": detail["collected_at"],
            "model_reference_at": current["time"],
            "source": "open-meteo", "kind": "model_snapshot_not_observation",
            "temperature_c": _number(current.get("temperature_c")),
            "wind_kmh": _number(current.get("wind_kmh")),
            "gust_kmh": _number(current.get("gust_kmh")),
            "rain_next_24h_mm": _number(next24.get(slug)),
        }
        key = (slug, day.isoformat())
        old = records.get(key)
        if old is None or _moment(new["collected_at"]) >= _moment(old["collected_at"]):
            records[key] = new
    return {
        "schema_version": 1, "kind": _KIND,
        "retention_days": keep_days,
        "updated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "note": "Ultima estimativa de modelo publicada no dia; nao representa maxima, media ou chuva medida.",
        "records": [records[key] for key in sorted(records)],
    }
