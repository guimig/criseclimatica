"""Build an entirely static, attributed regional weather dataset."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class ForecastClient(Protocol):
    def fetch(self, location: dict[str, Any]) -> dict[str, Any]: ...


def next_24h_rain(series: list[dict[str, Any]], now: datetime) -> float | None:
    end = now + timedelta(hours=24)
    points: list[float] = []
    for row in series:
        try:
            moment = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError):
            continue
        value = row.get("precipitation_mm")
        if now <= moment < end and isinstance(value, (int, float)) and not isinstance(value, bool):
            points.append(float(value))
    return round(sum(points), 1) if points else None


def collect(locations: list[dict[str, Any]], client: ForecastClient, now: datetime | None = None) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
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
            records[location["id"]] = detail
            current = detail["current"]
            items.append({
                "id": location["id"], "name": location["name"], "state": location["state"],
                "latitude": location["latitude"], "longitude": location["longitude"],
                "featured": location["featured"], "status": "available",
                "current": current, "collected_at": detail["collected_at"],
                "rain_next_24h_mm": next_24h_rain(detail["hourly"], now),
            })
        except (Exception) as exc:
            errors.append({"location_id": location["id"], "message": str(exc)[:160]})
            items.append({
                "id": location["id"], "name": location["name"], "state": location["state"],
                "latitude": location["latitude"], "longitude": location["longitude"],
                "featured": location["featured"], "status": "unavailable",
                "current": None, "collected_at": None, "rain_next_24h_mm": None,
            })
    if not records:
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
