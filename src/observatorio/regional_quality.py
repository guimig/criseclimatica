"""Regional measurement coverage and cautious model/observation comparison.

No aggregation across stations: a station describes only its physical location.
No totals from incomplete days; missing rain cannot be interpreted as 0 mm.
This module never certifies an emergency alert or numerical-model accuracy.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any

KIND = "regional_gauge_coverage_and_spatial_model_context_not_live_alert"
INMET_KIND = "inmet_annual_zip_delayed_station_measurements_not_real_time"
NASA_KIND = "nasa_power_daily_gridded_estimate_not_station_observation"
MAX_AGE_DAYS = 35
MAX_STATIONS_PER_PLACE = 12


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Invalid regional reference time")
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid regional reference time") from exc
    if when.tzinfo is None:
        raise ValueError("Naive regional reference time")
    return when.astimezone(timezone.utc)


def _rain(value: Any) -> float | None:
    if (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 3000):
        return round(float(value), 2)
    return None


def _days(station: dict, today: date) -> list[dict]:
    result = []
    seen = set()
    for row in station.get("days", []) if isinstance(station.get("days"), list) else []:
        if not isinstance(row, dict):
            continue
        day_str = row.get("day_utc")
        try:
            day = date.fromisoformat(day_str)
        except (TypeError, ValueError):
            continue
        if day > today or (today - day).days > MAX_AGE_DAYS or day in seen:
            continue
        seen.add(day)
        hours = row.get("rain_measured_hours")
        rain = _rain(row.get("rain_total_complete_mm")) if hours == 24 else None
        result.append({"date": day, "complete_mm": rain, "measured_hours": hours if isinstance(hours, int) and 0 <= hours <= 24 else 0})
    return sorted(result, key=lambda x: x["date"], reverse=True)


def _station_record(ref: dict, station: dict, today: date) -> dict | None:
    distance = ref.get("distance_km")
    if (not isinstance(distance, (int, float)) or isinstance(distance, bool)
            or not math.isfinite(distance) or distance < 0 or distance > 130):
        return None
    code = ref.get("code")
    if not isinstance(code, str) or code != station.get("code"):
        return None
    days = _days(station, today)
    valid = [day for day in days if day["complete_mm"] is not None]
    latest = valid[0] if valid else None
    return {
        "code": code, "name": str(station.get("name") or code)[:100],
        "distance_km": round(float(distance), 1),
        "complete_days_in_window": len(valid),
        "last_complete_day_utc": latest["date"].isoformat() if latest else None,
        "last_complete_rain_mm": latest["complete_mm"] if latest else None,
        "status": "has_complete_observations" if latest else "no_complete_rain_days",
        "_complete_days": {day["date"]: day["complete_mm"] for day in valid},
    }


def _seven_day_total(row: dict) -> float | None:
    """Seven UTC calendar days ending at the last complete day; require 7/7."""
    from datetime import timedelta
    key = row.get("last_complete_day_utc")
    if not key:
        return None
    last = date.fromisoformat(key)
    readings = row["_complete_days"]
    window = [readings.get(last - timedelta(days=i)) for i in range(7)]
    return round(sum(window), 2) if all(x is not None for x in window) else None


def summarize(locations: list[dict], inmet: dict, nasa: dict, epagri: dict, checked_at: str) -> dict:
    """Select the closest station with a complete observation day for each place.

    Distances are explicit, even when 60+ km; the city is NOT deemed measured.
    The NASA value is added only for the Araquari sampling point and the same
    UTC day. Comparison is qualitative context, not model-validation statistics.
    """
    inmet = inmet if isinstance(inmet, dict) else {}
    nasa = nasa if isinstance(nasa, dict) else {}
    epagri = epagri if isinstance(epagri, dict) else {}
    now = _time(checked_at)
    today = now.date()
    valid_archive = (isinstance(inmet, dict) and inmet.get("kind") == INMET_KIND
                     and inmet.get("status") in ("available", "cached", "stale")
                     and isinstance(inmet.get("stations"), list)
                     and isinstance(inmet.get("locations"), list))
    archive_stations = {s["code"]: s for s in inmet.get("stations", [])
                        if valid_archive and isinstance(s, dict) and isinstance(s.get("code"), str)}
    archive_places = {p["location_id"]: p for p in inmet.get("locations", [])
                      if valid_archive and isinstance(p, dict) and isinstance(p.get("location_id"), str)}
    geo_places = {p["location_id"]: p for p in epagri.get("locations", [])
                  if isinstance(epagri, dict) and isinstance(epagri.get("locations"), list)
                  and isinstance(p, dict) and isinstance(p.get("location_id"), str)}
    nasa_ok = (isinstance(nasa, dict) and nasa.get("kind") == NASA_KIND
               and nasa.get("status") in ("available", "cached", "stale")
               and isinstance(nasa.get("daily"), list))
    nasa_days = {r.get("date_utc"): r for r in nasa.get("daily", [])
                 if nasa_ok and isinstance(r, dict) and isinstance(r.get("date_utc"), str)}
    nasa_point = nasa.get("point", {}).get("location_id") if nasa_ok and isinstance(nasa.get("point"), dict) else None

    out = []
    valid_places = 0
    for place in locations:
        slug = place["id"]
        references = archive_places.get(slug, {}).get("stations", [])
        candidates = []
        for ref in references[:MAX_STATIONS_PER_PLACE] if isinstance(references, list) else []:
            if not isinstance(ref, dict):
                continue
            station = archive_stations.get(ref.get("code"))
            if station:
                record = _station_record(ref, station, today)
                if record:
                    candidates.append(record)
        candidates.sort(key=lambda r: (r["distance_km"], r["code"]))
        valid = [r for r in candidates if r["status"] == "has_complete_observations"]
        chosen = valid[0] if valid else None
        if chosen:
            valid_places += 1
        no_rain_nearest = bool(candidates and candidates[0]["status"] == "no_complete_rain_days")
        recent_total = _seven_day_total(chosen) if chosen else None
        spatial_comparison = None
        if chosen and nasa_point == slug:
            model = nasa_days.get(chosen["last_complete_day_utc"])
            estimate = _rain(model.get("rain_estimated_mm_day")) if isinstance(model, dict) else None
            if estimate is not None:
                spatial_comparison = {
                    "day_utc": chosen["last_complete_day_utc"],
                    "nasa_gridded_estimate_mm": estimate,
                    "inmet_station_measurement_mm": chosen["last_complete_rain_mm"],
                    "distance_station_to_sample_km": chosen["distance_km"],
                    "note": "Pontos espaciais diferentes; diferenca NAO demonstra erro do modelo nem chuva municipal."
                }
        geo_rec = geo_places.get(slug)
        geo_stations = geo_rec.get("stations", []) if isinstance(geo_rec, dict) else []
        epagri_within_30 = sum(1 for r in geo_stations if isinstance(r, dict)
                               and isinstance(r.get("distance_km"), (int, float))
                               and not isinstance(r["distance_km"], bool) and 0 <= r["distance_km"] <= 30)
        selected = ({k: v for k, v in chosen.items() if not k.startswith("_")} if chosen else None)
        if selected:
            selected["total_7_complete_days_mm"] = recent_total
            selected["days_since_complete_observation"] = (today - date.fromisoformat(selected["last_complete_day_utc"])).days
        out.append({
            "location_id": slug, "status": "available" if chosen else
            ("no_complete_gauge_data" if valid_archive else "unavailable"),
            "nearest_station_missing_rain": no_rain_nearest,
            "selected_station": selected,
            "station_candidates": [{k: v for k, v in r.items() if not k.startswith("_")} for r in candidates[:6]],
            "epagri_catalog_within_30km": epagri_within_30,
            "epagri_catalog_is_measurement": False,
            "spatial_comparison": spatial_comparison,
        })
    return {
        "schema_version": 1,
        "kind": KIND,
        "checked_at": checked_at,
        "status": "available" if valid_places else "no_complete_gauge_data" if valid_archive else "unavailable",
        "source": {"id": "inmet-annual", "url": "https://portal.inmet.gov.br/dadoshistoricos"},
        "supporting_source": {"id": "epagri-gis", "kind": "station_registry_not_measurements"},
        "comparison_source": {"id": "nasa-power", "kind": "gridded_estimate_not_measurement"},
        "note": "Chuva observada apenas em estacoes, de arquivo anual atrasado; nunca chuva atual do municipio.",
        "locations": out,
    }
