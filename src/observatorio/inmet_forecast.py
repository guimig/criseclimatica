"""INMET municipal daily/period forecasts, complementary and never risk inputs."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

URL = "https://apiprevmet3.inmet.gov.br/previsao/4201307"
PORTAL = "https://previsao.inmet.gov.br/4201307"
KIND = "inmet_araquari_municipal_forecast_not_observations_or_risk_criteria"
TZ = ZoneInfo("America/Sao_Paulo")
PERIODS = ("manha", "tarde", "noite")


def moment(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value, low, high):
    return value if (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) and low <= value <= high) else None


def text(value, limit=350):
    return value.strip()[:limit] if isinstance(value, str) else ""


def unavailable(stamp, status="unavailable"):
    return {"schema_version": 1, "kind": KIND, "location_id": "araquari", "ibge_code": "4201307",
            "source_url": PORTAL, "api_url": URL, "risk_criteria": False, "status": status,
            "retrieved_at": None, "last_attempt_at": stamp, "issued_at": None,
            "timezone": "America/Sao_Paulo", "days": [], "daily_comparison": [],
            "numeric_rain_or_gust_inferred": False}


def normalize(payload, stamp):
    now = moment(stamp)
    if now is None or not isinstance(payload, dict) or not isinstance(payload.get("4201307"), dict):
        raise ValueError("Invalid INMET municipal forecast")
    root = payload["4201307"]
    if not 1 <= len(root) <= 10:
        raise ValueError("Unbounded INMET municipal forecast")
    days = []
    today = now.astimezone(TZ).date()
    for date, record in root.items():
        try:
            day = datetime.strptime(date, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            raise ValueError("Invalid INMET forecast date") from None
        if not today <= day <= today+timedelta(days=6):
            continue
        if not isinstance(record, dict):
            raise ValueError("Invalid INMET day")
        entries = [(period, record[period]) for period in PERIODS if period in record]
        if not entries:
            entries = [("dia", record)]
        periods = []
        for period, raw in entries:
            if not isinstance(raw, dict) or raw.get("uf") != "SC" or text(raw.get("entidade")).casefold() != "araquari":
                raise ValueError("INMET forecast municipality mismatch")
            minimum, maximum = number(raw.get("temp_min"), -50, 65), number(raw.get("temp_max"), -50, 65)
            if minimum is not None and maximum is not None and minimum > maximum:
                minimum = maximum = None
            low, high = number(raw.get("umidade_min"), 0, 100), number(raw.get("umidade_max"), 0, 100)
            if low is not None and high is not None and low > high:
                low = high = None
            periods.append({"period": period, "summary": text(raw.get("resumo")),
                            "minimum_c": minimum, "maximum_c": maximum,
                            "humidity_min_pct": low, "humidity_max_pct": high,
                            "wind_direction": text(raw.get("dir_vento"), 60),
                            "wind_intensity_text": text(raw.get("int_vento"), 120),
                            "hour_as_reported": text(raw.get("hora"), 20)})
        minima = {p["minimum_c"] for p in periods}
        maxima = {p["maximum_c"] for p in periods}
        minimum = next(iter(minima)) if len(minima) == 1 and None not in minima else None
        maximum = next(iter(maxima)) if len(maxima) == 1 and None not in maxima else None
        days.append({"day": day.isoformat(), "minimum_c": minimum, "maximum_c": maximum,
                     "daily_extremes_status": "reported_consistently" if minimum is not None and maximum is not None else "missing_or_conflicting",
                     "periods": periods})
    if not days:
        raise ValueError("No current INMET forecast dates")
    days.sort(key=lambda row: row["day"])
    result = unavailable(stamp, "available")
    result.update(retrieved_at=stamp, days=days[:7], valid_until=iso(now+timedelta(hours=6)))
    result["content_fingerprint"] = sha256(json.dumps(result["days"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    result["content_first_seen_at"] = stamp
    return result


def fetch_payload():
    request = Request(URL, headers={"Accept": "application/json", "User-Agent": "criseclimatica/1.1"})
    with urlopen(request, timeout=18) as response:
        body = response.read(1_000_001)
        if response.status != 200 or len(body) > 1_000_000:
            raise ValueError("INMET forecast response invalid or oversized")
    return json.loads(body)


def collect(stamp, *, previous=None, fixture=None):
    now = moment(stamp)
    try:
        result = normalize(fixture if fixture is not None else fetch_payload(), stamp)
        if (isinstance(previous, dict) and previous.get("kind") == KIND and previous.get("content_fingerprint") == result["content_fingerprint"]
                and moment(previous.get("content_first_seen_at")) is not None and moment(previous["content_first_seen_at"]) <= now):
            result["content_first_seen_at"] = previous["content_first_seen_at"]
        return result
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, TypeError):
        if isinstance(previous, dict) and previous.get("kind") == KIND:
            try:
                validate_product(previous)
                collected = moment(previous.get("retrieved_at"))
                if collected and timedelta(0) <= now-collected <= timedelta(hours=36):
                    result = deepcopy(previous)
                    result.pop("publication_at", None)
                    result.update(status="cached" if now-collected <= timedelta(hours=6) else "stale",
                                  last_attempt_at=stamp, diagnostic="query_failed_previous_forecast")
                    result["days"] = [d for d in result["days"] if d["day"] >= now.astimezone(TZ).date().isoformat()]
                    result["daily_comparison"] = []
                    if result["days"]:
                        return result
            except (ValueError, KeyError, TypeError):
                pass
        return unavailable(stamp)


def compare_daily(feed, detail):
    """Compare the same BRT civil day, requiring all 24 hourly model samples."""
    result = deepcopy(feed)
    result["daily_comparison"] = []
    if feed.get("status") not in ("available", "cached"):
        return result
    rows = (detail or {}).get("hourly", [])
    collected = moment((detail or {}).get("collected_at"))
    now = moment(feed.get("last_attempt_at"))
    model_fresh = collected and now and timedelta(0) <= now-collected <= timedelta(hours=8)
    for day in feed.get("days", []):
        start = datetime.fromisoformat(day["day"]).replace(tzinfo=TZ)
        slots = {iso(start+timedelta(hours=i)) for i in range(24)}
        samples = {}
        conflicts = set()
        if model_fresh:
            for row in rows:
                timestamp = moment(row.get("time"))
                if timestamp and (timestamp.minute or timestamp.second or timestamp.microsecond):
                    continue
                key = iso(timestamp) if timestamp else None
                value = number(row.get("temperature_c"), -50, 65)
                if key not in slots or value is None:
                    continue
                if key in samples and samples[key] != value:
                    conflicts.add(key)
                samples[key] = value
        values = [value for key, value in samples.items() if key not in conflicts]
        complete = len(values) == 24
        result["daily_comparison"].append({"day": day["day"], "start_at": iso(start), "end_at": iso(start+timedelta(days=1)),
            "status": "comparable_context" if complete and day["daily_extremes_status"] == "reported_consistently" else "incomplete",
            "model_hours": len(values), "expected_hours": 24,
            "model_minimum_c": min(values) if complete else None, "model_maximum_c": max(values) if complete else None,
            "model_collected_at": (detail or {}).get("collected_at")})
    return result


def validate_product(data, *, fixture=False):
    if (not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("kind") != KIND
            or data.get("location_id") != "araquari" or data.get("ibge_code") != "4201307"
            or data.get("risk_criteria") is not False or data.get("numeric_rain_or_gust_inferred") is not False
            or data.get("issued_at") is not None or data.get("api_url") != URL or data.get("source_url") != PORTAL
            or data.get("status") not in ("available", "cached", "stale", "unavailable", "fixture_mode")
            or (data.get("status") == "fixture_mode" and not fixture)
            or not isinstance(data.get("days"), list) or len(data["days"]) > 7):
        raise ValueError("Invalid INMET municipal forecast product")
    if data["status"] in ("unavailable", "fixture_mode") and data["days"]:
        raise ValueError("Unavailable INMET forecast has data")
    if data["days"] and (moment(data.get("retrieved_at")) is None or moment(data.get("valid_until")) != moment(data["retrieved_at"])+timedelta(hours=6)):
        raise ValueError("Invalid INMET forecast collection validity")
    if data["status"] in ("available", "cached", "stale") and not data["days"]:
        raise ValueError("INMET forecast has no dated records")
    attempted, retrieved = moment(data.get("last_attempt_at")), moment(data.get("retrieved_at"))
    if attempted is None or (retrieved and attempted < retrieved):
        raise ValueError("Invalid INMET forecast attempt clock")
    dates = [row["day"] for row in data["days"]]
    if dates != sorted(set(dates)):
        raise ValueError("Duplicate or unordered INMET forecast dates")
    for day in data["days"]:
        datetime.strptime(day["day"], "%Y-%m-%d")
        if not 1 <= len(day.get("periods", [])) <= 3:
            raise ValueError("Invalid INMET forecast periods")
        for row in [day, *day["periods"]]:
            for key in ("minimum_c", "maximum_c"):
                if row.get(key) is not None and number(row[key], -50, 65) is None:
                    raise ValueError("Invalid INMET temperature")
        for period in day["periods"]:
            if any(not isinstance(period.get(k), str) for k in ("summary", "wind_direction", "wind_intensity_text", "hour_as_reported")):
                raise ValueError("Invalid INMET forecast text")
            for key in ("humidity_min_pct", "humidity_max_pct"):
                if period.get(key) is not None and number(period[key], 0, 100) is None:
                    raise ValueError("Invalid INMET forecast humidity")
        if any(p.get("period") not in (*PERIODS, "dia") for p in day["periods"]):
            raise ValueError("Invalid INMET period label")
    for row in data.get("daily_comparison", []):
        start = datetime.fromisoformat(row["day"]).replace(tzinfo=TZ)
        if (row["day"] not in dates or row.get("start_at") != iso(start) or row.get("end_at") != iso(start+timedelta(days=1))
                or row.get("expected_hours") != 24 or row.get("status") not in ("comparable_context", "incomplete")
                or not isinstance(row.get("model_hours"), int) or not 0 <= row["model_hours"] <= 24):
            raise ValueError("Invalid INMET/model civil day comparison")
        for key in ("model_minimum_c", "model_maximum_c"):
            if row.get(key) is not None and (number(row[key], -50, 65) is None or row["model_hours"] != 24):
                raise ValueError("Invalid model daily extreme")
        if row.get("status") == "comparable_context" and row.get("model_hours") != 24:
            raise ValueError("Incomplete model day cannot be compared to INMET")
