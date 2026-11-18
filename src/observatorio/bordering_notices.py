"""INMET notices in municipalities sharing a border with Araquari.

This is a separate source-context channel: it never adds evidence to the
Araquari risk classifier. IBGE codes, not municipal sample-point distances,
identify the jurisdictions selected for this context.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta
import unicodedata
from pathlib import Path

from .alerts import KIND as INMET_KIND, PUBLIC_PORTAL, normalize_alerts, merge_active_notices, retain_valid_notices
from .notice_time import moment

KIND = "inmet_bordering_municipality_warning_context_not_araquari_alert"
RANKS = {"perigo potencial": 1, "perigo": 2, "grande perigo": 3}


def severity_rank(label: object) -> int:
    folded = "".join(c for c in unicodedata.normalize("NFKD", str(label or "").casefold())
                     if not unicodedata.combining(c))
    return RANKS.get(" ".join(folded.split()), 0)


def load_bordering(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    places = data.get("municipalities")
    if data.get("schema_version") != 1 or data.get("municipality", {}).get("ibge_code") != "4201307" or not isinstance(places, list) or len(places) > 20:
        raise ValueError("Invalid official bordering-municipality configuration")
    ids, codes, result = set(), set(), []
    for place in places:
        if not isinstance(place, dict):
            raise ValueError("Invalid bordering municipality")
        slug, name, code = place.get("id"), place.get("name"), str(place.get("ibge_code") or "")
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9-]{3,50}", slug) or not isinstance(name, str) or not name.strip() or len(name) > 100 or not re.fullmatch(r"42\d{5}", code) or code == "4201307" or slug in ids or code in codes:
            raise ValueError("Invalid or repeated bordering municipality/code")
        ids.add(slug); codes.add(code)
        result.append({"id": slug, "name": name.strip(), "ibge_code": code})
    if not result:
        raise ValueError("Empty bordering-municipality registry")
    return result


def _previous_bordering(previous: dict | None) -> dict | None:
    if not isinstance(previous, dict) or previous.get("kind") != INMET_KIND:
        return None
    if previous.get("status") == "available":
        return {"kind": INMET_KIND, "status": "available",
                "locations": previous.get("bordering_locations", []),
                "retrieved_at": previous.get("retrieved_at")}
    return {"kind": INMET_KIND, "status": "unavailable",
            "retained_locations": previous.get("retained_bordering_locations", []),
            "last_success_at": previous.get("last_success_at")}


def append_bordering(current: dict, *, previous: dict | None, places: list[dict],
                     stamp: str, raw: dict | None) -> dict:
    """Use the SAME INMET response, and retain previous active notices on failures."""
    old = _previous_bordering(previous)
    if current.get("status") == "available" and raw is not None:
        border = normalize_alerts(raw, places, stamp)
        border = merge_active_notices(border, old, places, stamp)
        current["bordering_locations"] = border["locations"]
        current["retained_bordering_locations"] = []
    else:
        if current.get("status") != "unavailable":
            raise ValueError("Inconsistent INMET bordering collection")
        border = retain_valid_notices(old, places, stamp)
        current["bordering_locations"] = []
        current["retained_bordering_locations"] = border.get("retained_locations", [])
    return current


def summarize_bordering(feed: dict, places: list[dict], stamp: str) -> dict:
    """Only windows with a confirmed clock are eligible for a visible highlight."""
    now = moment(stamp)
    if now is None:
        raise ValueError("Invalid publication time")
    source_available = feed.get("status") == "available"
    rows = feed.get("bordering_locations" if source_available else "retained_bordering_locations", [])
    registry = {p["id"]: p for p in places}
    local_rows = feed.get("locations", []) if source_available else feed.get("retained_locations", [])
    local = next((p for p in local_rows if p.get("location_id") == "araquari"), {})
    local_ids = {n.get("id") for n in local.get("alerts", [])}
    # A retained local alert is still an official notice for Araquari.
    grouped: dict[str, dict] = {}
    for place in rows if isinstance(rows, list) else []:
        slug = place.get("location_id")
        reference = registry.get(slug)
        if reference is None or str(place.get("ibge_code")) != reference["ibge_code"]:
            continue
        for n in place.get("alerts", []) if isinstance(place.get("alerts"), list) else []:
            identifier = n.get("id")
            start, end = moment(n.get("start_at")), moment(n.get("end_at"))
            rank = severity_rank(n.get("severity"))
            if not isinstance(identifier, str) or identifier in local_ids or not start or not end or not start < end or not now < end or end-start > timedelta(days=400) or not rank:
                continue
            row = grouped.get(identifier)
            if row is None:
                row = {"id": identifier, "title": n.get("type") or "Aviso meteorológico",
                       "severity": n.get("severity"), "severity_rank": rank,
                       "start_at": n["start_at"], "end_at": n["end_at"],
                       "url": PUBLIC_PORTAL,  # A numeric API identifier is not a verified public permalink.
                       "municipalities": [], "retained_previous": not source_available or bool(n.get("retained_previous")),
                       "risks": n.get("risks", [])[:5] if isinstance(n.get("risks"), list) else [],
                       "instructions": n.get("instructions", [])[:5] if isinstance(n.get("instructions"), list) else [],
                       "scope": "bordering_municipalities_only", "araquari_included": False}
                grouped[identifier] = row
            row["municipalities"].append({"id": slug, "name": reference["name"], "ibge_code": reference["ibge_code"]})
            row["retained_previous"] = row["retained_previous"] or bool(n.get("retained_previous"))
    alerts = sorted(grouped.values(), key=lambda r: (-r["severity_rank"], r["start_at"], r["id"]))
    for row in alerts:
        row["municipalities"].sort(key=lambda m: m["name"])
    return {"schema_version": 1, "kind": KIND, "status": "available" if source_available else "retained_unconfirmed" if alerts else "unavailable",
            "retrieved_at": feed.get("retrieved_at") if source_available else feed.get("last_success_at"),
            "checked_at": stamp, "municipalities_monitored": len(places),
            "selection": "exact_7_digit_ibge_of_curated_bordering_municipalities",
            "effect_on_local_risk": "none", "role": "regional_context_only_not_official_warning_for_araquari",
            "notices": alerts[:100]}
