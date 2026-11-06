"""Geographic and temporal inventory for future comparisons, never an accuracy score."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from .inmet import haversine_km

KIND = "territorial_source_alignment_not_model_validation"
NEAR_KM = 25.0
PRIORITY_KM = 10.0
MAX_CANDIDATES = 6
TIME_WINDOW_MINUTES = 60
GROUPS = {"norte-sc":"Norte de Santa Catarina", "vale-itajai":"Vale e foz do Itajaí",
          "grande-florianopolis":"Grande Florianópolis", "curitiba-planalto":"Curitiba e planalto próximo"}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _point(row):
    lat, lon = row.get("latitude"), row.get("longitude")
    return (lat, lon) if _number(lat) and _number(lon) and -90 <= lat <= 90 and -180 <= lon <= 180 else None


def _time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def _fresh(value, now, hours):
    time = _time(value)
    return time is not None and -600 <= (now-time).total_seconds() <= hours*3600


def summarize(locations: list[dict], details: dict, cemaden: dict, sensors: dict,
              metars: dict, checked_at: str) -> dict:
    now = _time(checked_at)
    if now is None:
        raise ValueError("Alignment requires a timezone-aware timestamp")
    rain_places = {row["location_id"]: row for row in cemaden.get("locations", [])}
    out = []
    for place in locations:
        slug = place["id"]
        sample = _point(place)
        detail = details.get(slug, {})
        current = detail.get("current") or {}
        grid = detail.get("grid_point") or {}
        grid_point = _point(grid)
        model_available = bool(detail) and _fresh(current.get("time"), now, 8) and _fresh(detail.get("collected_at"), now, 8)
        nearby_cemaden = []
        for station in sensors.get("stations", []) if sensors.get("status") == "available" else []:
            point = _point(station)
            if point is None:
                continue
            distance = haversine_km(*sample, *point)
            if distance > NEAR_KM:
                continue
            readings = [row for row in station.get("readings", [])
                        if _fresh(row.get("observed_at"), now, 3+20/60) and _number(row.get("value"))]
            if not readings:
                continue
            temperature = next((row for row in readings if row.get("sensor_id") == 60 and row.get("unit") == "°C"), None)
            nearby_cemaden.append({"code":station["code"], "name":station["name"],
                "municipality":station.get("municipality"), "state":station.get("state"),
                "latitude":point[0], "longitude":point[1], "sample_distance_km":round(distance, 2),
                "model_grid_distance_km":round(haversine_km(*grid_point,*point), 2) if grid_point else None,
                "reference_at": temperature["observed_at"] if temperature else max(row["observed_at"] for row in readings),
                "potential_variables":["temperature_c"] if temperature else [],
                "elevation_m":None})
        nearby_metar = []
        for station in metars.get("stations", []) if metars.get("status") == "available" else []:
            point = _point(station)
            if point is None or not _fresh(station.get("observed_at"), now, 6):
                continue
            distance = haversine_km(*sample,*point)
            if distance > NEAR_KM:
                continue
            variables = [key for key in ("temperature_c","wind_kmh","gust_kmh","pressure_hpa")
                         if _number(station.get(key)) and _number(current.get(key))]
            nearby_metar.append({"code":station["icao"],"name":station["name"],
                "latitude":point[0],"longitude":point[1],"sample_distance_km":round(distance, 2),
                "model_grid_distance_km":round(haversine_km(*grid_point,*point), 2) if grid_point else None,
                "reference_at":station["observed_at"],"potential_variables":variables,"elevation_m":None})
        nearby_cemaden.sort(key=lambda row:(row["sample_distance_km"],row["code"]))
        nearby_metar.sort(key=lambda row:(row["sample_distance_km"],row["code"]))
        # Include a close temperature sensor even if the nearest gauges dominate.
        selected = sorted(nearby_cemaden, key=lambda row:(not bool(row["potential_variables"]),row["sample_distance_km"],row["code"]))[:MAX_CANDIDATES]
        selected.sort(key=lambda row:(row["sample_distance_km"],row["code"]))
        triads = []
        for sensor in selected:
            for metar in nearby_metar[:MAX_CANDIDATES]:
                distance = haversine_km(sensor["latitude"],sensor["longitude"],metar["latitude"],metar["longitude"])
                if distance > NEAR_KM or not model_available:
                    continue
                grid_distances = [sensor["model_grid_distance_km"],metar["model_grid_distance_km"]]
                grid_verified = grid_point is not None and all(dist is not None and dist <= NEAR_KM for dist in grid_distances)
                moments = [_time(current.get("time")),_time(sensor["reference_at"]),_time(metar["reference_at"])]
                gap = round((max(moments)-min(moments)).total_seconds()/60, 1)
                variables = sorted(set(sensor["potential_variables"]) & set(metar["potential_variables"]))
                triads.append({"cemaden_code":sensor["code"],"metar_code":metar["code"],
                    "station_distance_km":round(distance, 2),"time_gap_minutes":gap,
                    "time_window_aligned":gap <= TIME_WINDOW_MINUTES,
                    "model_grid_proximity_verified":grid_verified,"potential_common_variables":variables,
                    "relation":"priority_geographic_candidate" if max(sensor["sample_distance_km"],metar["sample_distance_km"],distance) <= PRIORITY_KM else "nearby_geographic_candidate",
                    "elevation_match_verified":False,"measurement_protocols_verified":False,
                    "comparison_ready":False})
        triads.sort(key=lambda row:(not bool(row["potential_common_variables"]),not row["time_window_aligned"],row["station_distance_km"],row["cemaden_code"],row["metar_code"]))
        rain = rain_places.get(slug,{})
        out.append({"location_id":slug,"territorial_group":place.get("territorial_group","unassigned"),
            "sample_point":{"latitude":sample[0],"longitude":sample[1],"kind":"approximate_municipal_sampling_point"},
            "model":{"status":"available" if model_available else "unavailable","reference_at":current.get("time"),
                     "grid_point":grid if grid_point else None},
            "cemaden_local_rain":{"status":rain.get("status",cemaden.get("status","unavailable")),
                "station_count":len(rain.get("stations",[])),"individual_station_positions_verified":False,
                "comparison_note":"Municipal IBGE query is not proof of station proximity; accumulation windows must be aligned separately."},
            "cemaden_state_query_status":sensors.get("state_queries", {}).get(place.get("state")),
            "cemaden_nearby_count":len(nearby_cemaden),"metar_nearby_count":len(nearby_metar),
            "cemaden_candidates":selected,"metar_candidates":nearby_metar[:MAX_CANDIDATES],
            "candidate_triads":triads[:MAX_CANDIDATES],
            "coverage_status":"three_sources_nearby" if any(row["model_grid_proximity_verified"] for row in triads) else "candidate_overlap_grid_unverified" if triads else "two_sources_nearby" if model_available and (nearby_cemaden or nearby_metar) else "insufficient_overlap",
            "limitations":["elevation_and_terrain_not_verified","sensor_height_and_aggregation_not_verified",
                           "model_reference_is_not_forecast_issue_time","no_accuracy_metric_computed"]})
    return {"schema_version":1,"kind":KIND,"checked_at":checked_at,
            "groups":GROUPS,"spatial_radius_km":NEAR_KM,"priority_radius_km":PRIORITY_KM,
            "time_window_minutes":TIME_WINDOW_MINUTES,"locations":out}
