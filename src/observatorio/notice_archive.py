"""Compact, bounded archive of *published INMET notices*, not actual disasters.

Preserves provenance and visibility of each notice in the current feed.  Missing
from a later feed means 'not in feed', NOT proof of cancellation or resolution.
The Pages JSON is a convenience copy, not an independent durable backup.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

KIND = "archive_of_inmet_notices_not_confirmed_weather_events"
MAX_RECORDS = 2000
KEEP_DAYS = 366


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid notice archive timestamp")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid notice archive timestamp") from exc
    if moment.tzinfo is None:
        raise ValueError("Notice archive timestamps need timezone")
    return moment.astimezone(timezone.utc)


def _place_refs(feed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Collapse multiple municipalities of one notice into a single source record."""
    found: dict[str, dict[str, Any]] = {}
    for place in feed["locations"]:
        for notice in place.get("alerts", []):
            key = notice["id"]
            existing = found.get(key)
            if existing is None:
                found[key] = {
                    "id": key, "revision": notice["revision"],
                    "type": notice["type"], "severity": notice["severity"],
                    "window_as_reported": notice["window_as_reported"],
                    "municipality_ids": [place["location_id"]],
                    **{field:notice.get(field) for field in ("start_at", "end_at", "start_as_reported", "end_as_reported", "validity_hours", "duration_kind")},
                }
            else:
                existing["municipality_ids"].append(place["location_id"])
                if notice["revision"] > existing["revision"]:
                    for field in ("revision", "type", "severity", "window_as_reported", "start_at", "end_at", "start_as_reported", "end_as_reported", "validity_hours", "duration_kind"):
                        existing[field] = notice.get(field)
    for item in found.values():
        item["municipality_ids"].sort()
    return found


def merge_notice_archive(previous: dict[str, Any] | None, alerts: dict[str, Any],
                         *, now: datetime | None = None, keep_days: int = KEEP_DAYS) -> dict[str, Any]:
    if not 1 <= keep_days <= 400:
        raise ValueError("Invalid notice archive retention")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must have timezone")
    now = now.astimezone(timezone.utc)
    stamp = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    cutoff = now - timedelta(days=keep_days)
    records: dict[str, dict[str, Any]] = {}
    if previous is not None:
        if (not isinstance(previous, dict) or previous.get("schema_version") != 1 or previous.get("kind") != KIND
                or not isinstance(previous.get("records"), list) or len(previous["records"]) > MAX_RECORDS):
            raise ValueError("Unrecognized previous notice archive")
        for row in previous["records"]:
            if not isinstance(row, dict):
                raise ValueError("Malformed previous notice")
            identifier = row.get("id")
            if not isinstance(identifier, str) or not identifier or len(identifier) > 50 or identifier in records:
                raise ValueError("Invalid or duplicate notice identifier")
            first, last = _parse_timestamp(row.get("first_seen_at")), _parse_timestamp(row.get("last_seen_at"))
            if first > last or last > now + timedelta(hours=1):
                raise ValueError("Notice archive timestamps inconsistent")
            if last >= cutoff:
                records[identifier] = dict(row)
    if alerts.get("schema_version") != 1 or alerts.get("kind") != "inmet_official_notices_by_municipality":
        raise ValueError("Unexpected official notice feed")
    status = alerts.get("status")
    if status not in ("available", "unavailable"):
        raise ValueError("Invalid official notice feed status")
    if status == "available":
        for old in records.values():
            old["present_in_latest_successful_feed"] = False
        current = _place_refs(alerts)
        for key, observed in current.items():
            if key in records:
                row = records[key]
                if observed["revision"] >= row["revision"]:
                    for field in ("revision", "type", "severity", "window_as_reported", "municipality_ids", "start_at", "end_at", "start_as_reported", "end_as_reported", "validity_hours", "duration_kind"):
                        row[field] = observed[field]
                row["last_seen_at"] = stamp
                row["present_in_latest_successful_feed"] = True
            else:
                records[key] = {**observed, "first_seen_at": stamp, "last_seen_at": stamp,
                                "present_in_latest_successful_feed": True}
    # A network failure cannot prove a notice ended, so leave previous visibility intact.
    if len(records) > MAX_RECORDS:
        raise ValueError("Notice archive exceeded safe record limit")
    return {
        "schema_version": 1, "kind": KIND, "retention_days": keep_days,
        "updated_at": stamp,
        "feed_status": status,
        "note": "Historical official notices; their presence does not confirm that a disaster occurred. A missing notice is not proof of cancellation.",
        "records": sorted(records.values(), key=lambda x: (x["last_seen_at"], x["id"]), reverse=True),
    }
