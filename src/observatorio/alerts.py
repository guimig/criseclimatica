"""Regional INMET notices, matched by exact municipal IBGE code.

The undocumented INMET JSON endpoint is an opportunistic source; outages must
never be interpreted as an absence of official warnings.  Dates and separate
clock fields are deliberately *not* converted into a guessed timezone.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"
PUBLIC_PORTAL = "https://alertas2.inmet.gov.br/"
KIND = "inmet_official_notices_by_municipality"
_CODE = re.compile(r"(?<!\d)\d{7}(?!\d)")


class AlertSourceError(RuntimeError):
    """INMET notices could not be verified."""


def _text(value: Any, limit: int = 350) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _codes(value: Any) -> set[str]:
    """API delivers geocodes as CSV text, sometimes as a list; match exact codes."""
    if isinstance(value, list):
        value = ",".join(str(item) for item in value)
    if not isinstance(value, str):
        return set()
    return set(_CODE.findall(value))


def _lines(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_text(value, 1100)] if value.strip() else []
    if isinstance(value, list):
        return [_text(entry, 1100) for entry in value[:5] if _text(entry)]
    return []


def _source_window(record: dict[str, Any]) -> str:
    """Preserve the API's separate calendar and wall-clock fields without TZ inference."""
    parts: list[str] = []
    for key in ("inicio", "fim"):
        raw_date = record.get("data_" + key)
        raw_time = record.get("hora_" + key)
        date_text = _text(raw_date, 10)
        time_text = _text(raw_time, 5)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
            parts.append("não informado")
        else:
            try:
                datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                parts.append("não informado")
            else:
                parts.append(f"{date_text[8:10]}/{date_text[5:7]}/{date_text[:4]} {time_text if re.fullmatch(r'\d{2}:\d{2}', time_text) else ''}".strip())
    return " — ".join(parts)


def _explicit_time(value: Any) -> str | None:
    """Only preserve instants whose offset is explicitly supplied by the source."""
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if moment.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def _sequence(value: Any) -> int:
    try:
        number = int(value)
        return number if 0 <= number < 1_000_000 else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def normalize_alerts(payload: Any, locations: list[dict[str, Any]], collected_at: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or not {"hoje", "futuro"} & payload.keys():
        raise AlertSourceError("Unknown INMET alert payload")
    blocks: dict[str, list[dict[str, Any]]] = {}
    for name in ("hoje", "futuro"):
        entries = payload.get(name, [])
        if not isinstance(entries, list) or len(entries) > 1000:
            raise AlertSourceError("Invalid INMET alert list")
        if any(not isinstance(item, dict) for item in entries):
            raise AlertSourceError("Invalid INMET alert entry")
        blocks[name] = entries

    by_id: dict[str, tuple[int, dict[str, Any], set[str]]] = {}
    for block_name, entries in blocks.items():
        for raw in entries:
            notice_id = _text(str(raw.get("id_aviso") or raw.get("id") or ""), 50)
            if not notice_id or not re.fullmatch(r"[a-zA-Z0-9_-]+", notice_id):
                continue
            if raw.get("encerrado") is True:
                continue
            codes = _codes(raw.get("geocodes"))
            if not codes:
                codes = _codes(raw.get("municipios"))
            seq = _sequence(raw.get("id_sequencia"))
            previous = by_id.get(notice_id)
            if previous is None or seq > previous[0]:
                by_id[notice_id] = (seq, raw, (previous[2] if previous else set()) | {block_name})
            else:
                previous[2].add(block_name)

    regional_ids: set[str] = set()
    result_places = []
    for place in locations:
        ibge = str(place.get("ibge_code") or "")
        if not re.fullmatch(r"\d{7}", ibge):
            raise ValueError(f"Missing valid IBGE code for {place['id']}")
        matches: list[dict[str, Any]] = []
        for identifier, (seq, raw, source_blocks) in by_id.items():
            code_set = _codes(raw.get("geocodes")) or _codes(raw.get("municipios"))
            if ibge not in code_set:
                continue
            regional_ids.add(identifier)
            matches.append({
                "id": identifier, "revision": seq, "type": _text(raw.get("descricao"), 140) or "Aviso meteorológico",
                "severity": _text(raw.get("severidade"), 80) or "Não informada",
                "window_as_reported": _source_window(raw),
                "start_at": _explicit_time(raw.get("data_inicio")),
                "end_at": _explicit_time(raw.get("data_fim")),
                "risks": _lines(raw.get("riscos")),
                "instructions": _lines(raw.get("instrucoes")),
                "phases": sorted(source_blocks),
            })
        matches.sort(key=lambda item: (item["type"], item["id"]))
        result_places.append({"location_id": place["id"], "ibge_code": ibge, "alerts": matches[:100]})

    return {
        "schema_version": 1, "kind": KIND, "status": "available",
        "retrieved_at": collected_at,
        "source": {"id": "inmet", "name": "INMET", "url": PUBLIC_PORTAL, "api_url": URL},
        "time_notice": "Datas e horas apresentadas conforme a fonte; fuso dos campos separados não foi inferido.",
        "regional_distinct_notices": len(regional_ids),
        "locations": result_places,
    }


def unavailable_alerts(locations: list[dict[str, Any]], checked_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1, "kind": KIND, "status": "unavailable", "retrieved_at": None,
        "checked_at": checked_at,
        "source": {"id": "inmet", "name": "INMET", "url": PUBLIC_PORTAL, "api_url": URL},
        "time_notice": "Fonte indisponível; não é possível afirmar ausência de avisos.",
        "regional_distinct_notices": None,
        "locations": [{"location_id": loc["id"], "ibge_code": str(loc["ibge_code"]), "alerts": []} for loc in locations],
    }


def fetch_alerts(*, timeout: int = 20) -> dict[str, Any]:
    request = Request(URL, headers={"Accept": "application/json", "User-Agent": "ObservatorioTempoClima/0.3 (+https://github.com/guimig/criseclimatica)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise AlertSourceError(f"INMET notices HTTP {response.status}")
            raw = response.read(6_000_001)
            if len(raw) > 6_000_000:
                raise AlertSourceError("INMET notices response too large")
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise AlertSourceError("INMET notice root is not a JSON object")
        return data
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AlertSourceError(f"INMET notice request failed: {type(exc).__name__}") from exc
