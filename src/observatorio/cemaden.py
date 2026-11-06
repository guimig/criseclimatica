"""Recent observed precipitation from the documented CEMADEN PED endpoint.

JWT in `token` request HEADER; never publish, log, or include the token in URLs.
Only station accumulations from exact IBGE municipalities are presented, no
arbitrary averaging or inference for municipalities without a station.
"""
from __future__ import annotations

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .cemaden_auth import SgaaAuthError, SgaaSession

API = "https://sws.cemaden.gov.br/PED/rest/pcds-acum/acumulados-recentes"
DOCS = "https://sws.cemaden.gov.br/PED/api/ui/"
KIND = "cemaden_recent_observed_station_rainfall_raw"
IBGE = re.compile(r"\d{7}")
STATION = re.compile(r"[A-Za-z0-9-]{4,25}")
ACCUMULATION_FIELDS = {
    "acc1hr": ("rain_1h_mm", 500),
    "acc3hr": ("rain_3h_mm", 750),
    "acc6hr": ("rain_6h_mm", 1000),
    "acc12hr": ("rain_12h_mm", 1200),
    "acc24hr": ("rain_24h_mm", 1500),
    "acc48hr": ("rain_48h_mm", 2500),
    "acc72hr": ("rain_72h_mm", 3500),
    "acc96hr": ("rain_96h_mm", 4500),
    "acc120hr": ("rain_120h_mm", 5500),
}


class CemadenError(RuntimeError):
    def __init__(self, message: str, reason: str = "unavailable"):
        super().__init__(message)
        self.reason = reason


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the JWT to another origin.


def fetch(ibge: str, token: str, *, timeout: int = 12) -> list[dict[str, Any]]:
    if not IBGE.fullmatch(ibge) or not token or len(token) > 4096 or any(c.isspace() for c in token):
        raise CemadenError("Invalid municipality or authorization configuration", "access_restricted")
    url = API + "?" + urlencode({"codibge": ibge, "formato": "JSON"})
    request = Request(url, headers={"Accept": "application/json", "token": token,
                                     "User-Agent": "ObservatorioClimatico/0.5 (https://github.com/guimig/criseclimatica)"})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise CemadenError("Cemaden returned unexpected status")
            body = response.read(800_001)
            if len(body) > 800_000:
                raise CemadenError("Cemaden response too large")
        raw = json.loads(body.decode("utf-8"))
        if not isinstance(raw, list) or len(raw) > 300:
            raise CemadenError("Cemaden API returned an invalid dataset")
        return raw
    except HTTPError as exc:
        reason = ("token_expired" if exc.code == 401 else
                  "bad_request" if exc.code == 400 else
                  "access_restricted" if exc.code == 403 else
                  "rate_limited" if exc.code == 429 else "unavailable")
        raise CemadenError("Cemaden request rejected", reason) from None
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise CemadenError("Cemaden request could not be completed") from None


def _number(value: Any, upper: float) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value.replace(",", ".")) if isinstance(value, str) else float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return round(n, 2) if math.isfinite(n) and 0 <= n <= upper else None


def _timestamp(value: Any) -> datetime | None:
    """PED example timestamps are UTC without TZ suffix; Cemaden records in UTC."""
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)
    except ValueError:
        return None


def normalize(raw: Any, ibge: str, now: datetime) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > 300:
        raise CemadenError("Invalid Cemaden station response")
    by_station: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or str(item.get("codibge")) != ibge:
            continue
        code = str(item.get("codestacao") or "")
        time = _timestamp(item.get("datahora"))
        if not STATION.fullmatch(code) or time is None:
            continue
        if not -timedelta(minutes=10) <= now - time <= timedelta(hours=6):
            continue
        accumulations = {field: _number(item.get(api_field), upper)
                         for api_field, (field, upper) in ACCUMULATION_FIELDS.items()}
        if all(value is None for value in accumulations.values()):
            continue
        entry = {"code": code, "observed_at": time.isoformat(timespec="seconds").replace("+00:00", "Z"),
                 **accumulations,
                 "quality": "cemaden_raw_station_accumulations_not_municipality_averages"}
        old = by_station.get(code)
        if old is None or entry["observed_at"] > old["observed_at"]:
            by_station[code] = entry
    return sorted(by_station.values(), key=lambda s: s["code"])


def collect(locations: list[dict[str, Any]], stamp: str, *, token: str | None = None,
            now: datetime | None = None, fetcher: Callable = fetch,
            session: SgaaSession | None = None) -> dict[str, Any]:
    """Obtain a temporary SGAA token or retain the legacy JWT input.

    Never call SGAA with real credentials during synthetic builds: those pass
    token="" explicitly. Session is injectable for network-free testing.
    """
    if token is None:
        email = os.environ.get("CEMADEN_PED_EMAIL", "")
        password = os.environ.get("CEMADEN_PED_PASSWORD", "")
        if email or password:
            if not email or not password:
                initial_status = "not_configured"
                initial_reason = "incomplete_sgaa_credentials"
            else:
                initial_status = "unavailable"
                initial_reason = None
                session = session or SgaaSession(email, password)
        else:
            token = os.environ.get("CEMADEN_PED_TOKEN", "")
            initial_status = "not_configured" if not token else "unavailable"
            initial_reason = "token_not_configured" if not token else None
    else:
        initial_status = "not_configured" if not token else "unavailable"
        initial_reason = "token_not_configured" if not token else None
    base = {
        "schema_version": 1, "kind": KIND, "status": initial_status,
        "checked_at": stamp,
        "source": {"id": "cemaden", "name": "Cemaden PED", "url": DOCS,
                   "attribution": "DADOS DA REDE OBSERVACIONAL DO CEMADEN/MCTIC"},
        "locations": [{"location_id": loc["id"], "ibge_code": str(loc["ibge_code"]), "stations": []}
                      for loc in locations],
        "municipalities_checked": 0, "municipalities_failed": 0,
        "diagnostic": initial_reason,
    }
    if initial_status == "not_configured":
        return base
    if session is not None:
        try:
            token = session.token()
        except SgaaAuthError as exc:
            base["status"] = "access_restricted" if exc.reason == "access_restricted" else "unavailable"
            base["diagnostic"] = "sgaa_" + exc.reason
            return base
    if not token:
        base["status"] = "not_configured"
        base["diagnostic"] = "token_not_configured"
        return base
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    def get(loc):
        ibge = str(loc["ibge_code"])
        try:
            current_token = session.token() if session is not None else token
            try:
                raw = fetcher(ibge, current_token)
            except CemadenError as exc:
                if session is None or exc.reason not in ("token_expired", "bad_request"):
                    raise
                # Retry once only when the official PED indicates expired/missing token.
                # Concurrent workers share a refreshed token, avoiding a login storm.
                current_token = session.token(rejected=current_token)
                raw = fetcher(ibge, current_token)
            return normalize(raw, ibge, now), None
        except SgaaAuthError as exc:
            return [], "access_restricted" if exc.reason == "access_restricted" else "unavailable"
        except CemadenError as exc:
            reason = "access_restricted" if exc.reason in ("token_expired", "bad_request") else exc.reason
            return [], reason
        except (ValueError, TypeError, OSError):
            return [], "unavailable"

    # The PED FAQ limits external accounts to 12 requests/minute. With one
    # sequential worker the first expired token is refreshed before the next
    # municipality is queried; normal builds issue at most seven PED GETs.
    with ThreadPoolExecutor(max_workers=(1 if session is not None else min(3, len(locations)) or 1)) as pool:
        results = list(pool.map(get, locations))
    failures = [err for _, err in results if err]
    for row, (stations, _) in zip(base["locations"], results):
        row["stations"] = stations
    base["municipalities_checked"] = len(locations)
    base["municipalities_failed"] = len(failures)
    if any(rows for rows, _ in results):
        base["status"] = "available"
    elif failures and all(reason == "access_restricted" for reason in failures):
        base["status"] = "access_restricted"
    elif failures:
        base["status"] = "unavailable"
    else:
        base["status"] = "no_recent_data"
    base["diagnostic"] = "partial" if base["status"] == "available" and failures else (failures[0] if failures else "ok")
    return base
