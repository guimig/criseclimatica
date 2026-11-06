"""Build an entirely static, attributed regional weather dataset."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class ForecastClient(Protocol):
    def fetch(self, location: dict[str, Any]) -> dict[str, Any]: ...


def rain_window(series: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """24 complete hourly bins from the current UTC hour, never a partial total.

    Open-Meteo precipitation at T represents the preceding hour. Thus the
    24 endpoints are start+1h through start+24h, including the current hour.
    Identical duplicates are collapsed; conflicting values invalidate a bin.
    """
    if now.tzinfo is None:
        raise ValueError("Rain window timestamp must be timezone-aware")
    start = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=24)
    expected = {start + timedelta(hours=i) for i in range(1, 25)}
    bins: dict[datetime, float] = {}
    conflicts: set[datetime] = set()
    for row in series:
        try:
            moment = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
            if moment.tzinfo is None:
                continue
            moment = moment.astimezone(timezone.utc)
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if moment not in expected:
            continue
        val = row.get("precipitation_mm")
        if (not isinstance(val, (int, float)) or isinstance(val, bool)
                or not math.isfinite(val) or not 0 <= val <= 1000):
            conflicts.add(moment)
            continue
        if moment in bins and bins[moment] != float(val):
            conflicts.add(moment)
        bins[moment] = float(val)
    valid = [val for moment, val in bins.items() if moment not in conflicts]
    complete = len(valid) == 24
    return {
        "status": "complete" if complete else "partial" if valid else "unavailable",
        "expected_hours": 24, "valid_hours": len(valid),
        "conflicting_hours": len(conflicts),
        "start_at": start.isoformat().replace("+00:00", "Z"),
        "end_at": end.isoformat().replace("+00:00", "Z"),
        "total_mm": round(sum(valid), 1) if complete else None,
        "partial_sum_mm": round(sum(valid), 1) if valid else None,
        "kind": "model_forecast_hourly_bins_including_current_hour",
    }


def next_24h_rain(series: list[dict[str, Any]], now: datetime) -> float | None:
    return rain_window(series, now)["total_mm"]


def collect(locations: list[dict[str, Any]], client: ForecastClient, now: datetime | None = None, *, allow_empty: bool = False) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Collection timestamp must be timezone-aware")
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    records: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    def fetch_safe(location: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        try:
            return client.fetch(location), None
        except Exception as exc:
            return None, str(exc)[:160]

    # Small bounded concurrency reduces total time during a failing provider outage.
    with ThreadPoolExecutor(max_workers=min(4, len(locations))) as executor:
        outcomes = list(executor.map(fetch_safe, locations))
    for location, (detail, fetch_error) in zip(locations, outcomes):
        try:
            if fetch_error is not None:
                raise ValueError(fetch_error)
            if detail is None:
                raise ValueError("Provider returned no data")
            if detail.get("location", {}).get("id") != location["id"]:
                raise ValueError("Provider returned wrong location")
            if detail.get("source", {}).get("id") != "open-meteo":
                raise ValueError("Provider returned wrong source")
            current = detail["current"]
            window = rain_window(detail["hourly"], now)
            records[location["id"]] = detail
            items.append({
                "id": location["id"], "name": location["name"], "state": location["state"],
                "latitude": location["latitude"], "longitude": location["longitude"],
                "featured": location["featured"], "status": "available",
                "current": current, "collected_at": detail["collected_at"],
                "rain_next_24h_mm": window["total_mm"], "rain_window": window,
            })
        except (Exception) as exc:
            errors.append({"location_id": location["id"], "message": str(exc)[:160]})
            items.append({
                "id": location["id"], "name": location["name"], "state": location["state"],
                "latitude": location["latitude"], "longitude": location["longitude"],
                "featured": location["featured"], "status": "unavailable",
                "current": None, "collected_at": None, "rain_next_24h_mm": None,
            })
    if not records and not allow_empty:
        raise RuntimeError("All weather sources failed; publication aborted")
    manifest = {
        "schema_version": 1, "generated_at": stamp,
        "provider": "Open-Meteo", "provider_url": "https://open-meteo.com/en/docs",
        "data_kind": "model_estimates_and_forecasts_not_station_observations",
        "official_alerts_integrated": False,
        "geography_scope": "Litoral Norte de Santa Catarina, Brazil",
        "total_locations": len(locations), "available_locations": len(records),
        "locations": items, "errors": errors,
    }
    return manifest, records

