"""Open-Meteo forecast adapter; its current values are model estimates, not stations."""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL = "https://api.open-meteo.com/v1/forecast"
SOURCE_URL = "https://open-meteo.com/en/docs"
CURRENT = (
    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
    "precipitation", "weather_code", "cloud_cover", "pressure_msl",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
)
HOURLY = (
    "temperature_2m", "relative_humidity_2m", "precipitation",
    "precipitation_probability", "wind_speed_10m", "wind_gusts_10m",
    "weather_code",
)
DAILY = (
    "weather_code", "temperature_2m_max", "temperature_2m_min",
    "precipitation_sum", "precipitation_probability_max", "wind_gusts_10m_max",
)


class ProviderError(RuntimeError):
    """A provider request or payload could not be used safely."""


def timestamp(value: str) -> str:
    """The request sets timezone=UTC; provider times have no trailing offset."""
    if not isinstance(value, str):
        raise ProviderError("Missing provider timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderError(f"Invalid provider timestamp: {value!r}") from exc
    return value if value.endswith("Z") else value + "Z"


def number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _section(payload: dict[str, Any], name: str, required: tuple[str, ...]) -> dict[str, Any]:
    obj = payload.get(name)
    if not isinstance(obj, dict):
        raise ProviderError(f"Open-Meteo response is missing {name}")
    if any(key not in obj for key in required):
        raise ProviderError(f"Open-Meteo response has incomplete {name} fields")
    return obj


def _rows(section: dict[str, Any], mapping: dict[str, str], *, date_only: bool = False) -> list[dict[str, Any]]:
    times = section.get("time")
    if not isinstance(times, list) or not times:
        raise ProviderError("Open-Meteo time series is empty")
    if len(times) > 500:
        raise ProviderError("Open-Meteo response exceeds allowed series length")
    for field in mapping:
        if not isinstance(section.get(field), list) or len(section[field]) != len(times):
            raise ProviderError(f"Mismatched time series for {field}")
    rows = []
    for index, time_string in enumerate(times):
        if date_only:
            try:
                datetime.strptime(time_string, "%Y-%m-%d")
            except (ValueError, TypeError) as exc:
                raise ProviderError("Invalid daily date") from exc
        else:
            time_string = timestamp(time_string)
        row = {"time": time_string}
        row.update({label: number(section[field][index]) for field, label in mapping.items()})
        rows.append(row)
    return rows


def normalize(location: dict[str, Any], payload: dict[str, Any], collected_at: str) -> dict[str, Any]:
    """Converts provider JSON into explicit, attributed, unit-stable structures."""
    if not isinstance(payload, dict) or payload.get("error"):
        raise ProviderError("Open-Meteo returned an error response")
    current = _section(payload, "current", CURRENT + ("time",))
    hourly = _section(payload, "hourly", HOURLY + ("time",))
    daily = _section(payload, "daily", DAILY + ("time",))
    current_map = {
        "temperature_2m": "temperature_c", "relative_humidity_2m": "humidity_pct",
        "apparent_temperature": "feels_like_c", "precipitation": "precipitation_mm",
        "weather_code": "weather_code", "cloud_cover": "cloud_cover_pct",
        "pressure_msl": "pressure_hpa", "wind_speed_10m": "wind_kmh",
        "wind_direction_10m": "wind_direction_deg", "wind_gusts_10m": "gust_kmh",
    }
    hourly_map = {
        "temperature_2m": "temperature_c", "relative_humidity_2m": "humidity_pct",
        "precipitation": "precipitation_mm", "precipitation_probability": "rain_probability_pct",
        "wind_speed_10m": "wind_kmh", "wind_gusts_10m": "gust_kmh",
        "weather_code": "weather_code",
    }
    daily_map = {
        "weather_code": "weather_code", "temperature_2m_max": "temp_max_c",
        "temperature_2m_min": "temp_min_c", "precipitation_sum": "precipitation_sum_mm",
        "precipitation_probability_max": "rain_probability_max_pct",
        "wind_gusts_10m_max": "gust_max_kmh",
    }
    units = payload.get("current_units")
    if not isinstance(units, dict) or units.get("temperature_2m") != "\u00b0C" or units.get("wind_speed_10m") != "km/h" or units.get("precipitation") != "mm":
        raise ProviderError("Unexpected Open-Meteo current units")
    current_values = {label: number(current[field]) for field, label in current_map.items()}
    current_values["time"] = timestamp(current["time"])
    return {
        "schema_version": 1,
        "location": location,
        "grid_point": {
            "latitude": number(payload.get("latitude")),
            "longitude": number(payload.get("longitude")),
            "elevation_m": number(payload.get("elevation")),
            "kind": "provider_grid_reference_not_station_location",
        },
        "source": {"id": "open-meteo", "name": "Open-Meteo", "url": SOURCE_URL,
                   "kind": "numerical_model", "license": "Free non-commercial use with attribution"},
        "measurement_status": "estimated_model_not_station_observation",
        "collected_at": collected_at,
        "current": current_values,
        "hourly": _rows(hourly, hourly_map),
        "daily": _rows(daily, daily_map, date_only=True),
    }


class OpenMeteoClient:
    def __init__(self, timeout: int = 12, attempts: int = 2):
        self.timeout = timeout
        self.attempts = attempts

    def fetch(self, location: dict[str, Any]) -> dict[str, Any]:
        params = {
            "latitude": location["latitude"], "longitude": location["longitude"],
            "current": ",".join(CURRENT), "hourly": ",".join(HOURLY),
            "daily": ",".join(DAILY), "forecast_days": 5, "timezone": "UTC",
            "wind_speed_unit": "kmh", "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }
        url = URL + "?" + urlencode(params)
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                request = Request(url, headers={"User-Agent": "criseclimatica-observatorio/0.1 (research; public weather portal)", "Accept": "application/json"})
                with urlopen(request, timeout=self.timeout) as response:
                    if response.status != 200:
                        raise ProviderError(f"Unexpected provider status {response.status}")
                    raw = response.read(2_000_001)
                    if len(raw) > 2_000_000:
                        raise ProviderError("Provider response exceeded 2 MB")
                obj = json.loads(raw.decode("utf-8"))
                collected = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                return normalize(location, obj, collected)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                last_error = exc
                if isinstance(exc, HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                    break
                if attempt + 1 < self.attempts:
                    time.sleep(1 + attempt)
        raise ProviderError(f"Open-Meteo request failed for {location['id']}: {type(last_error).__name__}") from last_error

