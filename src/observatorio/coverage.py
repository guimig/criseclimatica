"""Small per-locality inventory; never treats station proximity as coverage of a city."""
from __future__ import annotations

from datetime import datetime, timezone

KIND = "local_source_coverage_not_municipal_weather_measurement"


def _latest(values):
    parsed = []
    for value in values:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if moment.tzinfo is not None:
                parsed.append(moment.astimezone(timezone.utc))
        except (ValueError, TypeError, AttributeError):
            continue
    return max(parsed).isoformat().replace("+00:00", "Z") if parsed else None


def summarize(locations: list[dict], manifest: dict, cemaden: dict, sensors: dict,
              observations: dict, checked_at: str) -> dict:
    """Inventory only confirmed variables and the original observation times."""
    models = {row["id"]: row for row in manifest["locations"]}
    rain_places = {row["location_id"]: row for row in cemaden["locations"]}
    sensor_places = {row["location_id"]: row for row in sensors["locations"]}
    sensor_stations = {row["code"]: row for row in sensors.get("stations", [])}
    metars = {row["location_id"]: row for row in observations["locations"]}
    metar_stations = {row["icao"]: row for row in observations.get("stations", [])}
    out = []
    for place in locations:
        slug = place["id"]
        rain = rain_places.get(slug, {})
        gauges = rain.get("stations", [])
        matches = sensor_places.get(slug, {}).get("stations", [])
        readings = [reading for ref in matches for reading in
                    sensor_stations.get(ref["code"], {}).get("readings", [])]
        metar = metars.get(slug, {})
        observation = metar.get("observation") or {}
        metar_refs = metar.get("stations", [])
        metar_readings = [metar_stations[ref["icao"]] for ref in metar_refs if ref["icao"] in metar_stations]
        if not metar_readings and observation:
            metar_readings = [observation]
        model = models[slug]
        rain_variables = sorted({key for row in gauges for key, val in row.items()
                                 if key.startswith("rain_") and key.endswith("_mm") and val is not None})
        sensor_variables = sorted({(row["sensor_name"], row.get("unit") or "unidade não confirmada")
                                   for row in readings})
        products = [
            {"id": "open-meteo", "name": "Open-Meteo · modelo", "kind": "model_forecast",
             "status": model["status"], "checked_at": model.get("collected_at"),
             "reference_at": (model.get("current") or {}).get("time"),
             "station_count": None, "variables": [label for key, label in
                 (("temperature_c", "Temperatura (°C)"), ("humidity_pct", "Umidade (%)"),
                  ("precipitation_mm", "Precipitação estimada (mm)"),
                  ("wind_kmh", "Vento (km/h)"), ("gust_kmh", "Rajadas (km/h)"))
                 if (model.get("current") or {}).get(key) is not None]},
            {"id": "cemaden-rain", "name": "Cemaden · acumulados", "kind": "station_observation",
             "status": rain.get("status", cemaden["status"]),
             "diagnostic": rain.get("diagnostic"), "checked_at": cemaden.get("checked_at"),
             "reference_at": _latest(row.get("observed_at") for row in gauges),
             "station_count": len(gauges), "variables": [f"Chuva acumulada {key.removeprefix('rain_').removesuffix('_mm')} (mm)" for key in rain_variables]},
            {"id": "cemaden-sensors", "name": "Cemaden · sensores próximos", "kind": "nearby_station_observation",
             "status": ("available" if readings else "no_recent_data") if sensors["status"] == "available"
             else sensors["status"], "checked_at": sensors.get("checked_at"),
             "reference_at": _latest(row.get("observed_at") for row in readings),
             "station_count": len({ref["code"] for ref in matches if ref["code"] in sensor_stations}),
             "nearest_distance_km": min((ref["distance_km"] for ref in matches), default=None),
             "variables": [f"{name} ({unit})" for name, unit in sensor_variables]},
            {"id": "metar", "name": "NOAA · METAR", "kind": "aerodrome_observation",
             "status": "available" if metar_readings else metar.get("status", observations["status"]),
             "checked_at": observations.get("retrieved_at"),
             "reference_at": _latest(row.get("observed_at") for row in metar_readings),
             "station_count": len(metar_readings),
             "regional_context_only_count": sum(ref.get("scope") == "regional_context_only" for ref in metar_refs),
             "variables": [name for key, name in (("temperature_c", "Temperatura (°C)"),
                           ("wind_kmh", "Vento (km/h)"), ("gust_kmh", "Rajada (km/h)"))
                           if any(row.get(key) is not None for row in metar_readings)]},
        ]
        out.append({"location_id": slug, "products": products})
    return {"schema_version": 1, "kind": KIND, "checked_at": checked_at, "locations": out}
