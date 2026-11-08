"""Evidence-based advisory summaries. No institutional decisions or risk scores.

Araquari is always the institutional reference. Other municipalities supply
separate regional context, never substitutes for a missing Araquari forecast.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .inmet import haversine_km
from .pipeline import rain_window

KIND = "meteorological_evidence_and_advisory_not_institutional_decision"
SNAPSHOT_KIND = "previous_published_forecast_not_observed_history"
PRIMARY = "araquari"
FIELDS = {"precipitation_mm": (0, 1000), "temperature_c": (-80, 65),
          "wind_kmh": (0, 400), "gust_kmh": (0, 450), "humidity_pct": (0, 100)}
# Descriptive exploration only. This is NOT an IFC/INMET heat danger threshold.
HEAT_REFERENCE_C = 30


def moment(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def iso(dt):
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def valid_number(value, low=-math.inf, high=math.inf):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and low <= value <= high)


def fresh(value, now, hours):
    dt = moment(value)
    return dt is not None and -600 <= (now - dt).total_seconds() <= hours * 3600


def local(feed, slug):
    return next((row for row in feed.get("locations", []) if row.get("location_id") == slug), {})


def hourly_bins(rows, field):
    """Collapse identical duplicates; discard conflicting/invalid hourly bins."""
    if not isinstance(rows, list) or len(rows) > 500:
        return {}
    values, conflicts = {}, set()
    for row in rows:
        dt = moment(row.get("time")) if isinstance(row, dict) else None
        if dt is None or dt.minute or dt.second or dt.microsecond:
            continue
        value = row.get(field)
        if not valid_number(value, *FIELDS[field]):
            conflicts.add(dt)
        elif dt in values and values[dt] != value:
            conflicts.add(dt)
        else:
            values[dt] = value
    return {dt: value for dt, value in values.items() if dt not in conflicts}


def forecast_analysis(detail, now):
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=24)
    result = {"status": "unavailable", "start_at": iso(start), "end_at": iso(end),
              "rain": None, "rain_peaks": [], "wind": {}, "heat": None, "rain_wind_overlap": None}
    if not detail:
        return result
    result["collected_at"] = detail.get("collected_at")
    result["reference_at"] = detail.get("current", {}).get("time")
    if not fresh(result["collected_at"], now, 8) or not fresh(result["reference_at"], now, 8):
        result["status"] = "stale"
        return result
    rows = detail.get("hourly", [])
    rain = rain_window(rows, now)
    result.update(status="available", rain=rain)
    expected_rain = [start + timedelta(hours=i) for i in range(1, 25)]
    values = hourly_bins(rows, "precipitation_mm")
    # A maximum is a whole-window claim: partial data cannot establish it.
    if rain["status"] == "complete":
        for width in (3, 6):
            candidates = [(sum(values[t] for t in expected_rain[i:i+width]), i)
                          for i in range(25-width)]
            total, i = max(candidates, key=lambda entry: (entry[0], -entry[1]))
            result["rain_peaks"].append({"hours": width, "total_mm": round(total, 1),
                "start_at": iso(expected_rain[i] - timedelta(hours=1)),
                "end_at": iso(expected_rain[i+width-1])})
    instants = [start + timedelta(hours=i) for i in range(24)]
    for field in ("wind_kmh", "gust_kmh"):
        valid = hourly_bins(rows, field)
        count = sum(t in valid for t in instants)
        peak = max(instants, key=lambda t: (valid[t], -t.timestamp())) if count == 24 else None
        result["wind"][field] = {"valid_hours": count, "expected_hours": 24,
            "status": "complete" if count == 24 else "partial" if count else "unavailable",
            "maximum": valid[peak] if peak else None, "at": iso(peak) if peak else None}
    temps = hourly_bins(rows, "temperature_c")
    count = sum(t in temps for t in instants)
    heat = {"status": "complete" if count == 24 else "partial" if count else "unavailable",
            "valid_hours": count, "reference_c": HEAT_REFERENCE_C,
            "criterion": "descriptive_reference_not_official_danger_class", "maximum_c": None,
            "hours_at_or_above": None, "longest_sequence_hours": None, "start_at": None, "end_at": None}
    if count == 24:
        peak = max(instants, key=lambda t: temps[t])
        heat.update(maximum_c=temps[peak], maximum_at=iso(peak),
                    hours_at_or_above=sum(temps[t] >= HEAT_REFERENCE_C for t in instants))
        best, run = [], []
        for t in instants:
            run = run + [t] if temps[t] >= HEAT_REFERENCE_C else []
            if len(run) > len(best):
                best = run[:]
        heat["longest_sequence_hours"] = len(best)
        if best:
            heat.update(start_at=iso(best[0]), end_at=iso(best[-1]),
                        sequence_note="consecutive_hourly_references_not_continuous_measurement")
    result["heat"] = heat
    gust = result["wind"]["gust_kmh"]
    if rain["status"] == "complete" and gust["at"]:
        at = moment(gust["at"])
        # Rain ending at T+1h covers [T,T+1h]; gust timestamp is T.
        result["rain_wind_overlap"] = {"gust_at": gust["at"],
            "rain_start_at": iso(at), "rain_end_at": iso(at+timedelta(hours=1)),
            "rain_mm": values[at+timedelta(hours=1)], "gust_kmh": gust["maximum"],
            "kind": "hourly_forecast_context_not_joint_event_probability"}
    return result


def observed_rain(feed, slug, now):
    row = local(feed, slug)
    status = row.get("status", feed.get("status", "unavailable"))
    result = {"status": status, "checked_at": feed.get("checked_at"), "stations": [],
              "scope": "exact_municipality_ibge_station_points_not_municipal_mean"}
    if status != "available":
        return result
    if not fresh(feed.get("checked_at"), now, 6):
        result["status"] = "stale"
        return result
    for station in row.get("stations", []):
        if not fresh(station.get("observed_at"), now, 6):
            continue
        accumulations = {f"rain_{h}h_mm": station.get(f"rain_{h}h_mm") for h in (1, 3, 6, 12, 24, 48, 72)
                         if valid_number(station.get(f"rain_{h}h_mm"), 0, 5500)}
        if accumulations:
            result["stations"].append({"code": station["code"], "observed_at": station["observed_at"],
                                       **accumulations})
    if not result["stations"]:
        result["status"] = "no_valid_recent_readings"
    return result


def notice_analysis(feed, slug, forecast, now):
    status = feed.get("status", "unavailable")
    result = {"status": status, "retrieved_at": feed.get("retrieved_at"), "notices": []}
    if status != "available":
        return result
    if not fresh(feed.get("retrieved_at"), now, 6):
        result["status"] = "stale"
        return result
    for notice in local(feed, slug).get("alerts", []):
        start, end = moment(notice.get("start_at")), moment(notice.get("end_at"))
        relation = "unverified_timezone_or_window"
        lifecycle = "unverified"
        if start and end and start < end:
            lifecycle = "expired" if end <= now else "future" if start > now else "ongoing"
            relation = ("overlaps_forecast" if start < moment(forecast["end_at"]) and end > moment(forecast["start_at"])
                        else "outside_forecast_window")
            if forecast.get("status") != "available":
                relation = "forecast_unavailable"
        result["notices"].append({"id": notice.get("id"), "type": notice.get("type"),
            "severity": notice.get("severity"), "window_as_reported": notice.get("window_as_reported"),
            "start_at": iso(start) if start else None, "end_at": iso(end) if end else None,
            "temporal_relation": relation, "lifecycle": lifecycle, "kind": "official_notice_not_confirmed_event"})
    return result


def temperature_context(detail, place, metars, now):
    """Nearby values side by side; no spurious model-error statistic."""
    if not detail or metars.get("status") != "available" or not fresh(metars.get("retrieved_at"), now, 6):
        return {"status": "unavailable", "pairs": []}
    current = detail.get("current", {})
    if not fresh(current.get("time"), now, 8) or not fresh(detail.get("collected_at"), now, 8):
        return {"status": "unavailable", "pairs": []}
    model_temp = current.get("temperature_c")
    if not valid_number(model_temp, -80, 65):
        return {"status": "unavailable", "pairs": []}
    pairs = []
    for station in metars.get("stations", []):
        if not fresh(station.get("observed_at"), now, 6) or not valid_number(station.get("temperature_c"), -80, 65):
            continue
        if not valid_number(station.get("latitude"), -90, 90) or not valid_number(station.get("longitude"), -180, 180):
            continue
        distance = haversine_km(place["latitude"], place["longitude"], station["latitude"], station["longitude"])
        gap = abs((moment(current["time"]) - moment(station["observed_at"])).total_seconds()) / 60
        if distance <= 25 and gap <= 60:
            pairs.append({"icao": station["icao"], "name": station.get("name"), "distance_km": round(distance, 1),
                "gap_minutes": round(gap), "model_c": model_temp, "observed_c": station["temperature_c"],
                "model_at": current["time"], "observed_at": station["observed_at"],
                "kind": "exploratory_context_not_forecast_accuracy", "difference_c": None})
    return {"status": "available" if pairs else "no_compatible_pair", "pairs": pairs}


def recent_observations(metars, sensors, slug, now):
    readings = []
    if metars.get("status") == "available" and fresh(metars.get("retrieved_at"), now, 6):
        stations = {s["icao"]: s for s in metars.get("stations", [])}
        for ref in local(metars, slug).get("stations", [])[:3]:
            station = stations.get(ref.get("icao"), {})
            if (not valid_number(ref.get("distance_km"), 0, 100)
                    or not fresh(station.get("observed_at"), now, 6)):
                continue
            readings.append({"source": "NOAA/METAR", "code": ref["icao"], "name": station.get("name"),
                "distance_km": ref["distance_km"], "observed_at": station["observed_at"],
                "temperature_c": station.get("temperature_c"), "wind_kmh": station.get("wind_kmh"),
                "gust_kmh": station.get("gust_kmh"), "valid_until": iso(moment(station["observed_at"])+timedelta(hours=6))})
    if sensors.get("status") == "available" and fresh(sensors.get("checked_at"), now, 3+20/60):
        stations = {s["code"]: s for s in sensors.get("stations", [])}
        for ref in local(sensors, slug).get("stations", []):
            station = stations.get(ref.get("code"), {})
            if not valid_number(ref.get("distance_km"), 0, 130):
                continue
            temp = next((r for r in station.get("readings", []) if r.get("sensor_id") == 60
                         and r.get("unit") == "°C" and valid_number(r.get("value"), -80, 65)
                         and fresh(r.get("observed_at"), now, 3+20/60)), None)
            if temp:
                readings.append({"source": "Cemaden", "code": ref["code"], "name": station.get("name"),
                    "distance_km": ref["distance_km"], "observed_at": temp["observed_at"],
                    "temperature_c": temp["value"], "wind_kmh": None, "gust_kmh": None,
                    "valid_until": iso(moment(temp["observed_at"])+timedelta(hours=3, minutes=20))})
                if sum(r["source"] == "Cemaden" for r in readings) >= 3:
                    break
    return readings


def forecast_snapshot(details, generated_at):
    now = moment(generated_at)
    rows = []
    for slug, detail in sorted(details.items()):
        if not fresh(detail.get("collected_at"), now, 8) or not fresh(detail.get("current", {}).get("time"), now, 8):
            continue
        fields = {field: hourly_bins(detail.get("hourly", []), field) for field in FIELDS}
        times = sorted(set().union(*(set(values) for values in fields.values())))
        rows.append({"location_id": slug, "sample_point": detail.get("location"),
            "grid_point": detail.get("grid_point"), "collected_at": detail.get("collected_at"),
            "reference_at": detail.get("current", {}).get("time"),
            "hourly": [{"time": iso(t), **{field: values.get(t) for field, values in fields.items()}}
                       for t in times if now.replace(minute=0, second=0, microsecond=0) <= t <= now+timedelta(hours=48)][:49]})
    return {"schema_version": 1, "kind": SNAPSHOT_KIND, "generated_at": generated_at,
            "provider": "open-meteo", "time_basis": "UTC", "locations": rows,
            "note": "Last publication only; collection time is not model issue time."}


def revision_analysis(previous, detail, slug, forecast, now):
    result = {"status": "no_comparable_previous_publication", "rain_change_mm": None}
    if (not isinstance(previous, dict) or previous.get("kind") != SNAPSHOT_KIND
            or previous.get("schema_version") != 1 or previous.get("provider") != "open-meteo"
            or previous.get("time_basis") != "UTC" or forecast.get("status") != "available"):
        return result
    if not isinstance(previous.get("locations"), list) or len(previous["locations"]) > 100 or any(not isinstance(r, dict) for r in previous["locations"]):
        return result
    published = moment(previous.get("generated_at"))
    if published is None or not timedelta(0) < now-published <= timedelta(hours=24):
        return result
    old = local(previous, slug)
    if not isinstance(old.get("hourly"), list) or len(old["hourly"]) > 49:
        return result
    old_point, point = old.get("sample_point") or {}, detail.get("location") or {}
    if not isinstance(old_point, dict) or not isinstance(old.get("grid_point"), dict):
        return result
    if (any(old_point.get(k) != point.get(k) for k in ("id", "latitude", "longitude"))
            or not old.get("grid_point") or old.get("grid_point") != detail.get("grid_point")
            or not fresh(old.get("collected_at"), published, 8) or not fresh(old.get("reference_at"), published, 8)):
        return result
    prior_rain = rain_window(old.get("hourly", []), now)
    current_rain = forecast.get("rain") or {}
    if prior_rain.get("status") != "complete" or current_rain.get("status") != "complete":
        return result
    result.update(status="comparable_publications", previous_published_at=previous["generated_at"],
        previous_collected_at=old.get("collected_at"), current_collected_at=detail.get("collected_at"),
        start_at=current_rain["start_at"], end_at=current_rain["end_at"],
        previous_rain_mm=prior_rain["total_mm"], current_rain_mm=current_rain["total_mm"],
        rain_change_mm=round(current_rain["total_mm"]-prior_rain["total_mm"], 1),
        kind="publication_revision_same_valid_hours_not_model_skill")
    return result


def summarize(locations, details, cemaden, metars, alerts, cptec, generated_at, previous=None, sensors=None):
    now = moment(generated_at)
    if now is None:
        raise ValueError("Analysis requires timezone-aware publication time")
    results = []
    for place in locations:
        slug = place["id"]
        detail = details.get(slug, {})
        forecast = forecast_analysis(detail, now)
        observed = observed_rain(cemaden, slug, now)
        notices = notice_analysis(alerts, slug, forecast, now)
        recent = recent_observations(metars, sensors or {}, slug, now)
        pair = temperature_context(detail, place, metars, now)
        revision = revision_analysis(previous, detail, slug, forecast, now)
        limits = ["Estações medem pontos; as coordenadas do modelo são uma referência municipal, sem medição específica do campus.",
                  "Verificações de atualização programadas a cada 20 minutos, com coleta alvo de cerca de 40 minutos, sujeitas a atrasos; eventos rápidos exigem consulta aos canais oficiais."]
        suggestions = []
        expirations = [now + timedelta(hours=3)]
        notice_expirations = []
        def advise(identifier, evidence, text, limitation):
            suggestions.append({"id": identifier, "evidence": evidence, "text": text,
                                "scope": place["name"], "limitation": limitation})
        if forecast["status"] != "available":
            limits.append("Previsão local ausente ou desatualizada; municípios vizinhos não preenchem essa lacuna.")
        else:
            expirations.extend(moment(forecast[k])+timedelta(hours=8) for k in ("collected_at", "reference_at"))
            if forecast["rain"]["status"] != "complete":
                limits.append("Previsão de chuva incompleta: não é possível estabelecer o total ou o maior intervalo das 24 horas.")
            if forecast["rain_peaks"] and forecast["rain_peaks"][0]["total_mm"] > 0:
                advise("rain_timing", "forecast.rain_peaks", "Se houver atividades externas, pode ser pertinente avaliar ajustes considerando o intervalo de maior chuva prevista.",
                       "Previsão não confirma ocorrência nem condições adequadas para deslocamento.")
            if forecast.get("heat", {}).get("hours_at_or_above"):
                advise("heat_duration", "forecast.heat", "Se houver atividades externas, pode ser pertinente avaliar horários de menor exposição ao calor previsto.",
                       "30 °C é referência descritiva, sem classificação de perigo; temperatura não é sensação térmica.")
            if (forecast.get("wind", {}).get("gust_kmh", {}).get("maximum") or 0) > 0:
                advise("wind_timing", "forecast.wind.gust_kmh", "Pode ser pertinente considerar o horário das maiores rajadas previstas ao avaliar atividades externas.",
                       "O pico é descritivo: não constitui limite institucional de perigo.")
            if any(row.get("status") != "complete" for row in forecast["wind"].values()):
                limits.append("Série de vento ou rajadas incompleta; nenhum pico de 24 horas é inferido para a variável incompleta.")
            if forecast.get("heat", {}).get("status") != "complete":
                limits.append("Série de temperatura incompleta; duração de calor não calculada.")
        if observed["status"] == "available":
            expirations.append(moment(observed["checked_at"])+timedelta(hours=6))
            expirations.extend(moment(s["observed_at"])+timedelta(hours=6) for s in observed["stations"])
            if any((s.get("rain_24h_mm") or 0) > 0 for s in observed["stations"]):
                advise("antecedent_rain", "observed_rain.stations", "Há chuva medida nas estações apresentadas; pode ser pertinente considerar as condições antecedentes junto à previsão.",
                       "Acumulados sobrepostos não são somados e não demonstram, sozinhos, intensificação ou impactos locais.")
        else:
            limits.append("Não há acumulados Cemaden locais recentes utilizáveis nesta síntese; isso não significa chuva zero.")
        if notices["status"] == "available":
            notice_expirations.append(moment(notices["retrieved_at"])+timedelta(hours=6))
            if any(n["lifecycle"] != "expired" for n in notices["notices"]):
                advise("official_notice", "official_notices.notices", "Pode ser pertinente reforçar o acompanhamento dos avisos oficiais para este município e avaliar ajustes nas atividades conforme a evolução e a validade informada pela fonte.",
                       "A presença na consulta não comprova ocorrência. Suspensão, permanência abrigada e saída são possibilidades distintas, dependentes das condições locais e de deslocamento.")
            for n in notices["notices"]:
                if n["temporal_relation"] == "unverified_timezone_or_window":
                    limits.append("O fuso ou a validade de aviso não pôde ser conciliado; coincidência temporal com a previsão não foi afirmada.")
                    break
                if moment(n.get("end_at")) and moment(n["end_at"]) > now:
                    notice_expirations.append(moment(n["end_at"]))
        else:
            limits.append("Consulta de avisos ausente ou desatualizada; não se pode afirmar ausência de avisos.")
        for p in pair["pairs"]:
            expirations.append(moment(p["observed_at"])+timedelta(hours=6))
        cp = local(cptec, slug)
        cp_context = {"status": cp.get("status", "unavailable"), "locality": cp.get("nearest_cptec_locality"),
                      "day_comparison": "unverified_day_boundaries_no_numeric_difference"}
        if cp_context["status"] == "available" and not fresh(cptec.get("checked_at"), now, 6):
            cp_context["status"] = "stale"
        if revision["status"] != "comparable_publications":
            limits.append("Sem publicação anterior compatível para avaliar revisão da chuva no mesmo período futuro.")
        elif revision["rain_change_mm"] > 0:
            advise("forecast_revision", "revision", "A publicação mais recente aumentou a chuva prevista para os mesmos horários; pode ser pertinente reavaliar o acompanhamento.",
                   "Mudança entre publicações não mede precisão nem confirma intensificação observada.")
        results.append({"location_id": slug, "name": place["name"],
            "role": "primary_ifc_reference" if slug == PRIMARY else "complementary_regional_context",
            "status": "evidence_available" if forecast["status"] == "available" or observed["status"] == "available" or notices["status"] == "available" or recent else "insufficient_evidence",
            "valid_until": iso(min(expirations + notice_expirations)),
            "data_valid_until": iso(min(expirations)), "forecast": forecast, "observed_rain": observed,
            "official_notices": notices, "temperature_context": pair, "recent_observations": recent, "cptec_context": cp_context,
            "revision": revision, "suggestions": suggestions, "limitations": list(dict.fromkeys(limits))})
    return {"schema_version": 1, "kind": KIND, "generated_at": generated_at,
            "primary_location_id": PRIMARY, "locations": results,
            "protocol": {"status": "current_reference", "basis": "PN 13/2026 e PN 14/2026 — ASSINST/REI",
                         "priority_source": "Epagri/Ciram", "automatic_numeric_thresholds": False},
            "institutional_decisions_automated": False}
