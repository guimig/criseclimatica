"""Validate public static artifact before publishing; avoids synthetic builds in Pages."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from urllib.parse import urlparse


def validate(output: Path, *, fixture: bool = False) -> None:
    data = output / "data"
    overview = json.loads((data / "latest.json").read_text(encoding="utf-8"))
    history = json.loads((data / "history.json").read_text(encoding="utf-8"))
    analysis = json.loads((data / "analysis.json").read_text(encoding="utf-8"))
    snapshot = json.loads((data / "forecast_snapshot.json").read_text(encoding="utf-8"))
    expected_ids = {row["id"] for row in overview.get("locations", [])}
    if (analysis.get("schema_version") != 1 or analysis.get("kind") != "meteorological_evidence_and_advisory_not_institutional_decision"
            or analysis.get("primary_location_id") != "araquari" or "araquari" not in expected_ids
            or analysis.get("institutional_decisions_automated") is not False
            or analysis.get("generated_at") != overview.get("generated_at")
            or analysis.get("fixture_mode", False) is not fixture
            or {row.get("location_id") for row in analysis.get("locations", [])} != expected_ids
            or len(analysis["locations"]) != len(expected_ids)):
        raise ValueError("Invalid Araquari advisory synthesis")
    for row in analysis["locations"]:
        expected_role = "primary_ifc_reference" if row["location_id"] == "araquari" else "complementary_regional_context"
        if row.get("role") != expected_role or not row.get("valid_until"):
            raise ValueError("Regional context cannot replace Araquari")
        forecast = row.get("forecast", {})
        rain_window = forecast.get("rain") or {}
        if rain_window.get("status") != "complete" and forecast.get("rain_peaks"):
            raise ValueError("Incomplete rainfall cannot establish whole-window peaks")
        for peak in forecast.get("rain_peaks", []):
            if peak.get("hours") not in (3, 6) or not isinstance(peak.get("total_mm"), (int, float)):
                raise ValueError("Invalid rain concentration window")
        if forecast.get("status") != "available" and any(s.get("evidence", "").startswith("forecast.") for s in row.get("suggestions", [])):
            raise ValueError("Unavailable forecast cannot support advisory suggestions")
        for pair in row.get("temperature_context", {}).get("pairs", []):
            if pair.get("difference_c") is not None or pair.get("kind") != "exploratory_context_not_forecast_accuracy":
                raise ValueError("Exploratory station context cannot claim forecast error")
        if row.get("revision", {}).get("status") != "comparable_publications" and row.get("revision", {}).get("rain_change_mm") is not None:
            raise ValueError("Incompatible revisions cannot claim forecast changes")
    if (snapshot.get("schema_version") != 1 or snapshot.get("kind") != "previous_published_forecast_not_observed_history"
            or snapshot.get("generated_at") != overview.get("generated_at")
            or snapshot.get("fixture_mode", False) is not fixture
            or any(len(row.get("hourly", [])) > 49 for row in snapshot.get("locations", []))
            or (data / "forecast_snapshot.json").stat().st_size > 1_000_000):
        raise ValueError("Invalid bounded forecast snapshot")

    comparison = json.loads((data / 'forecast_comparison.json').read_text(encoding='utf-8'))
    model_archive = json.loads((data / 'model_forecast_history.json').read_text(encoding='utf-8'))
    if (comparison.get('kind') != 'araquari_comparable_forecasts_not_probability'
            or comparison.get('generated_at') != overview.get('generated_at')
            or comparison.get('location_id') != 'araquari'
            or comparison.get('fixture_mode', False) is not fixture
            or comparison.get('primary_id') != 'best_match'
            or comparison.get('cptec', {}).get('numeric_comparison') is not False):
        raise ValueError('Invalid comparative forecasts')
    for window in comparison.get('windows', []):
        for metric in window['metrics']:
            eligible = [m['value'] for m in metric['members'] if m['value'] is not None]
            if metric['status'] == 'comparable' and (len(eligible) < 2 or min(eligible) != metric['minimum'] or max(eligible) != metric['maximum']):
                raise ValueError('Invalid comparative range')
            if any(m['value'] is not None and m['valid_hours'] != window['hours'] for m in metric['members']):
                raise ValueError('Incomplete comparison window cannot produce a total or maximum')
    if (model_archive.get('kind') != 'araquari_forecasts_saved_before_verification'
            or model_archive.get('generated_at') != overview.get('generated_at')
            or model_archive.get('fixture_mode', False) is not fixture
            or model_archive.get('verification_performed') is not False
            or len(model_archive.get('publications', [])) > 64
            or (data / 'model_forecast_history.json').stat().st_size > 5_000_000
            or overview.get('model_comparison_archive_published') is not True):
        raise ValueError('Invalid bounded multi-model forecast archive')

    stations = json.loads((data / "stations.json").read_text(encoding="utf-8"))
    alerts = json.loads((data / "alerts.json").read_text(encoding="utf-8"))
    observations = json.loads((data / "observations.json").read_text(encoding="utf-8"))
    rain = json.loads((data / "rain_gauges.json").read_text(encoding="utf-8"))
    nasa = json.loads((data / "nasa_power.json").read_text(encoding="utf-8"))
    cemaden = json.loads((data / "cemaden.json").read_text(encoding="utf-8"))
    cemaden_sensors = json.loads((data / "cemaden_sensors.json").read_text(encoding="utf-8"))
    cptec = json.loads((data / "cptec.json").read_text(encoding="utf-8"))
    defesa_sc = json.loads((data / "defesa_civil_sc.json").read_text(encoding="utf-8"))
    archive = json.loads((data / "inmet_archive.json").read_text(encoding="utf-8"))
    epagri_geo = json.loads((data / "epagri_geo.json").read_text(encoding="utf-8"))
    epagri_notices = json.loads((data / "epagri_notices.json").read_text(encoding="utf-8"))
    epagri_bulletins = json.loads((data / "epagri_bulletins.json").read_text(encoding="utf-8"))
    regional_quality = json.loads((data / "regional_quality.json").read_text(encoding="utf-8"))
    notices_archive = json.loads((data / "notice_history.json").read_text(encoding="utf-8"))
    dashboard = json.loads((data / "dashboard.json").read_text(encoding="utf-8"))
    observed_history = json.loads((data / "observation_history.json").read_text(encoding="utf-8"))
    if (dashboard.get("kind") != "araquari_weather_dashboard_not_official_decision"
            or dashboard.get("schema_version") != 1 or dashboard.get("location_id") != "araquari"
            or dashboard.get("generated_at") != overview.get("generated_at")
            or dashboard.get("fixture_mode", False) is not fixture or dashboard.get("decision_automated") is not False):
        raise ValueError("Invalid primary Araquari dashboard")
    policy = dashboard.get("assessment", {})
    allowed_levels = ("verde", "azul", "amarelo", "laranja", "vermelho", "roxo")
    if (policy.get("suggested_level") not in (None, *allowed_levels)
            or policy.get("official_level") is not None
            or dashboard.get("protocol", {}).get("automatic_numeric_thresholds") is not False
            or [r.get("id") for r in dashboard.get("protocol", {}).get("levels", [])] != list(allowed_levels)):
        raise ValueError("Dashboard must preserve six qualitative reference levels")
    if policy.get("suggested_level"):
        primary_support = any(e.get("status") == "eligible" and e.get("supports_level") == policy["suggested_level"]
                           and e.get("matched_cue") and e.get("valid_from") and e.get("valid_until")
                           for e in policy.get("evidence", []))
        numeric = policy.get("numeric_support", {})
        numeric_support = (policy.get("basis_kind") == "complementary_numeric_evidence"
                           and policy["suggested_level"] in ("amarelo", "laranja")
                           and numeric.get("method_version") == "numeric-support-v1"
                           and numeric.get("proposed_level") == policy["suggested_level"]
                           and any(s.get("band", 0) > 0 for s in numeric.get("signals", [])))
        if policy.get("suggested_level") in ("verde", "roxo") or not (primary_support or numeric_support):
            raise ValueError("Level suggestion requires explicit primary or auxiliary evidence")
    gauge = dashboard.get("gauge_distribution", {})
    if gauge.get("station_count", 0) < 3 and gauge.get("median_mm") is not None:
        raise ValueError("Station median requires at least three comparable gauges")
    if gauge.get("status") == "available" and (gauge.get("station_count") != len(gauge.get("stations", []))
            or gauge.get("minimum_mm") is None or gauge.get("maximum_mm") is None):
        raise ValueError("Invalid gauge distribution traceability")
    if (observed_history.get("kind") != "araquari_point_observation_history_not_climatology"
            or observed_history.get("schema_version") != 1 or observed_history.get("location_id") != "araquari"
            or observed_history.get("generated_at") != overview.get("generated_at")
            or observed_history.get("fixture_mode", False) is not fixture
            or not isinstance(observed_history.get("records"), list) or len(observed_history["records"]) > 6000
            or (data / "observation_history.json").stat().st_size > 3_000_000
            or overview.get("observation_history_published") is not True):
        raise ValueError("Invalid bounded station observation history")
    assessment_history = json.loads((data / "assessment_history.json").read_text(encoding="utf-8"))
    if (assessment_history.get("kind") != "araquari_assessment_episodes_and_epagri_notice_history"
            or assessment_history.get("location_id") != "araquari"
            or assessment_history.get("generated_at") != overview.get("generated_at")
            or assessment_history.get("fixture_mode", False) is not fixture
            or len(assessment_history.get("episodes", [])) > 3000 or len(assessment_history.get("notices", [])) > 500
            or overview.get("assessment_history_published") is not True):
        raise ValueError("Invalid bounded assessment history")
    for record in observed_history["records"]:
        if record.get("source") not in ("cemaden-rain", "metar", "cemaden-temperature") or not record.get("observed_at"):
            raise ValueError("Observation history cannot contain model snapshots")
    for required in ("index.html", "dashboard.js", "dashboard.css", "essential.css", "chart-interaction.js", "icons.svg", "dados.html", "references/pn-13-2026.pdf", "references/pn-14-2026.pdf"):
        if not (output / required).is_file():
            raise ValueError(f"Missing dashboard asset: {required}")

    if epagri_bulletins.get("kind") != "epagri_ciram_editorial_forecast_bulletins_not_emergency_alerts" or epagri_bulletins.get("status") not in ("available", "cached", "stale", "no_recent_bulletins", "unavailable"):
        raise ValueError("Invalid Epagri editorial forecast product")
    for bulletin in epagri_bulletins.get("bulletins", []):
        if (not isinstance(bulletin, dict) or bulletin.get("data_kind") != "editorial_regional_forecast_not_station_observation_or_civil_defense_alert"
                or not bulletin.get("published_at") or not bulletin.get("title")):
            raise ValueError("Epagri editorial forecast mislabeled")
    if regional_quality.get("kind") != "regional_gauge_coverage_and_spatial_model_context_not_live_alert" or regional_quality.get("status") not in ("available", "unavailable", "no_complete_gauge_data"):
        raise ValueError("Invalid regional observation coverage dataset")
    if {row.get("location_id") for row in regional_quality.get("locations", [])} != {row["id"] for row in overview.get("locations", [])}:
        raise ValueError("Regional gauge analysis missing locations")
    for row in regional_quality["locations"]:
        selected = row.get("selected_station")
        if row.get("status") == "available":
            if (not isinstance(selected, dict) or selected.get("status") != "has_complete_observations"
                    or selected.get("last_complete_rain_mm") is None or selected.get("last_complete_day_utc") is None):
                raise ValueError("Regional gauge analysis has no complete dated measurement")
        elif selected is not None:
            raise ValueError("Regional gauge analysis must not invent observations")
        if row.get("epagri_catalog_is_measurement") is not False:
            raise ValueError("Epagri registry cannot be presented as sensor readings")
    if epagri_geo.get("kind") != "epagri_arcgis_station_registry_not_live_measurements":
        raise ValueError("Epagri station registry incorrectly classified")
    if epagri_notices.get("kind") != "epagri_ciram_official_advisories_not_civil_defense_alerts":
        raise ValueError("Epagri notices incorrectly classified")
    if epagri_geo.get("status") in ("available", "cached", "stale"):
        if {row.get("location_id") for row in epagri_geo.get("locations", [])} != {loc.get("id") for loc in overview.get("locations", [])}:
            raise ValueError("Incomplete Epagri registry geographical coverage")
    for advisory in epagri_notices.get("notices", []):
        if not isinstance(advisory, dict) or advisory.get("notice_kind") != "epagri_meteorological_advisory_not_civil_defense_alert":
            raise ValueError("Invalid Epagri advisory classification")
    if overview.get("schema_version") != 1 or overview.get("fixture_mode", False) is not fixture:
        raise ValueError("Unexpected manifest schema or fixture mode")
    available = sum(row.get("status") == "available" for row in overview.get("locations", []))
    if not overview.get("locations") or overview.get("available_locations") != available:
        raise ValueError("Manifest availability count inconsistent")
    if not available and not any(feed.get("status") in ("available", "partial", "no_recent_notices", "no_recent_bulletins")
                                 for feed in (alerts, observations, rain, cemaden, cemaden_sensors, cptec,
                                              epagri_notices, epagri_bulletins)):
        raise ValueError("Manifest has no available operational source")
    if not available and overview.get("publication_status") != "partial":
        raise ValueError("Model outage must be marked as a partial publication")
    coverage = json.loads((data / "coverage.json").read_text(encoding="utf-8"))
    expected_coverage = {row["id"] for row in overview["locations"]}
    if (coverage.get("schema_version") != 1 or coverage.get("kind") != "local_source_coverage_not_municipal_weather_measurement"
            or {row.get("location_id") for row in coverage.get("locations", [])} != expected_coverage):
        raise ValueError("Invalid locality coverage summary")
    for row in cemaden.get("locations", []):
        if row.get("status") not in ("available", "no_recent_data", "unavailable", "not_configured", "access_restricted", "rate_limited"):
            raise ValueError("Missing or invalid per-municipality Cemaden state")
        if row["status"] != "available" and row.get("stations"):
            raise ValueError("Failed municipality cannot contain Cemaden measurements")
    for place in overview["locations"]:
        if place.get("status") != "available":
            continue
        window = place.get("rain_window", {})
        hours = window.get("valid_hours")
        total = place.get("rain_next_24h_mm")
        if not isinstance(hours, int) or isinstance(hours, bool) or not 0 <= hours <= 24 or window.get("expected_hours") != 24:
            raise ValueError("Invalid forecast rain coverage")
        if hours != 24 and (total is not None or window.get("total_mm") is not None):
            raise ValueError("Partial forecast rain cannot be a full 24h total")
        if hours == 24 and (window.get("status") != "complete" or not isinstance(total, (int, float))
                            or isinstance(total, bool) or not math.isfinite(total) or total < 0 or total != window.get("total_mm")):
            raise ValueError("Invalid complete forecast rain total")
    if history.get("kind") != "daily_last_model_publication_not_station_observation":
        raise ValueError("History source classification invalid")
    if stations.get("kind") != "station_catalog_metadata_not_measurements":
        raise ValueError("INMET catalog source classification invalid")
    if alerts.get("kind") != "inmet_official_notices_by_municipality" or alerts.get("status") not in ("available", "unavailable"):
        raise ValueError("INMET alerts classification or status invalid")
    if observations.get("kind") != "aerodrome_metar_observations_not_municipal_measurements" or observations.get("status") not in ("available", "no_recent_reports", "unavailable"):
        raise ValueError("METAR observations classification or status invalid")
    alignment = json.loads((data / "territorial_alignment.json").read_text(encoding="utf-8"))
    if (alignment.get("kind") != "territorial_source_alignment_not_model_validation"
            or alignment.get("schema_version") != 1
            or {row.get("location_id") for row in alignment.get("locations", [])} != {row["id"] for row in overview["locations"]}):
        raise ValueError("Invalid common territorial coverage")
    for local in alignment["locations"]:
        sensors = {row["code"] for row in local.get("cemaden_candidates", [])}
        aerodromes = {row["code"] for row in local.get("metar_candidates", [])}
        for triad in local.get("candidate_triads", []):
            if (triad.get("cemaden_code") not in sensors or triad.get("metar_code") not in aerodromes
                    or triad.get("comparison_ready") is not False
                    or not isinstance(triad.get("station_distance_km"), (int,float))
                    or not 0 <= triad["station_distance_km"] <= 25.01):
                raise ValueError("Territorial candidate cannot claim scientific comparison readiness")
    metar_codes = {row["icao"] for row in observations.get("stations", [])}
    for local in observations.get("locations", []):
        refs = local.get("stations", [])
        if not isinstance(refs, list) or len(refs) > 6 or len({r.get("icao") for r in refs}) != len(refs):
            raise ValueError("Invalid regional METAR station references")
        for ref in refs:
            distance = ref.get("distance_km")
            if (ref.get("icao") not in metar_codes or ref.get("scope") not in ("nearby_aerodrome", "regional_context_only")
                    or not isinstance(distance, (int, float)) or isinstance(distance, bool)
                    or not math.isfinite(distance) or not 0 <= distance <= 180.05):
                raise ValueError("Invalid regional METAR station distance or scope")
        if local.get("observation") and (local.get("distance_km") is None or local["distance_km"] > 100.05):
            raise ValueError("Distant METAR cannot be primary local observation")
    if rain.get("kind") != "inmet_automatic_station_hourly_observed_rain_unvalidated" or rain.get("status") not in ("available", "unavailable", "not_configured", "no_nearby_catalog_stations", "access_restricted", "no_recent_data", "fixture_mode"):
        raise ValueError("INMET measured precipitation classification invalid")
    if rain["status"] == "fixture_mode" and not fixture:
        raise ValueError("Synthetic INMET rainfall forbidden in production")
    if rain["status"] != "available" and rain.get("stations"):
        raise ValueError("Unavailable rainfall source cannot include measured values")
    if nasa.get("schema_version") != 1 or nasa.get("kind") != "nasa_power_daily_gridded_estimate_not_station_observation" or nasa.get("status") not in ("available", "cached", "stale", "unavailable", "fixture_mode"):
        raise ValueError("Invalid NASA POWER source classification")
    if nasa["status"] in ("available", "cached", "stale") and not nasa.get("daily"):
        raise ValueError("NASA available state has no daily records")
    if nasa["status"] == "fixture_mode" and not fixture:
        raise ValueError("Synthetic NASA dataset forbidden in production")
    if cemaden.get("schema_version") != 1 or cemaden.get("kind") != "cemaden_recent_observed_station_rainfall_raw" or cemaden.get("status") not in ("available", "no_recent_data", "unavailable", "not_configured", "access_restricted", "fixture_mode"):
        raise ValueError("Invalid Cemaden source classification")
    if cemaden["status"] == "fixture_mode" and not fixture:
        raise ValueError("Synthetic Cemaden data forbidden in production")
    if cemaden["status"] not in ("available",) and any(row.get("stations") for row in cemaden.get("locations", [])):
        raise ValueError("Unavailable Cemaden data contains measured values")
    CEMADEN_SENSORS_KIND = "cemaden_recent_instrumental_sensor_readings_not_model_forecast"
    if (cemaden_sensors.get("schema_version") != 1 or cemaden_sensors.get("kind") != CEMADEN_SENSORS_KIND
            or cemaden_sensors.get("status") not in ("available", "no_recent_data", "unavailable", "not_configured", "access_restricted", "fixture_mode")):
        raise ValueError("Invalid Cemaden multi-sensor source")
    if cemaden_sensors["status"] == "fixture_mode" and not fixture:
        raise ValueError("Synthetic Cemaden readings forbidden in production")
    if cemaden_sensors["status"] != "available" and cemaden_sensors.get("stations"):
        raise ValueError("Unavailable Cemaden sensors cannot contain measurements")
    if (not isinstance(cemaden_sensors.get("locations"), list) or
            {row.get("location_id") for row in cemaden_sensors["locations"]} !=
            {row["id"] for row in overview.get("locations", [])}):
        raise ValueError("Cemaden sensor geographical coverage incomplete")
    sensor_codes = {row["code"] for row in cemaden_sensors.get("stations", [])}
    for local in cemaden_sensors["locations"]:
        refs = local.get("stations", [])
        if len(refs) > 24 or len({r.get("code") for r in refs}) != len(refs):
            raise ValueError("Cemaden station selection exceeds regional limit")
        for ref in refs:
            distance = ref.get("distance_km")
            if (ref.get("code") not in sensor_codes or not isinstance(distance, (int, float))
                    or isinstance(distance, bool) or not math.isfinite(distance) or not 0 <= distance <= 130.05):
                raise ValueError("Invalid regional Cemaden station distance")
    for station in cemaden_sensors.get("stations", []):
        if not isinstance(station.get("readings"), list) or not station.get("readings"):
            raise ValueError("Cemaden station has no readings")
        for reading in station["readings"]:
            if (not isinstance(reading.get("sensor_id"), int) or
                    not isinstance(reading.get("value"), (int, float)) or
                    not reading.get("observed_at") or
                    not isinstance(reading.get("sensor_name"), str)):
                raise ValueError("Invalid Cemaden sensor value")
    if cptec.get("schema_version") != 1 or cptec.get("kind") != "cptec_inpe_daily_forecast_nearest_locality_not_station_measurements" or cptec.get("status") not in ("available", "partial", "unavailable"):
        raise ValueError("Invalid CPTEC product or source status")
    if {x.get("location_id") for x in cptec.get("locations", [])} != {x["id"] for x in overview["locations"]}:
        raise ValueError("Invalid CPTEC municipality coverage")
    for row in cptec["locations"]:
        if row.get("status") not in ("available", "stale", "unavailable") or (row["status"] == "unavailable" and row.get("days")):
            raise ValueError("Invalid CPTEC local forecast state")
    if defesa_sc.get("schema_version") != 1 or defesa_sc.get("kind") != "defesa_civil_sc_publications_not_verified_active_alerts" or defesa_sc.get("status") not in ("available", "partial", "unavailable", "no_recent_publications", "stale"):
        raise ValueError("Invalid civil defense publications status")
    if len(defesa_sc.get("publications", [])) > 35 or (defesa_sc["status"] == "unavailable" and defesa_sc.get("publications")):
        raise ValueError("Invalid civil defense publication list")
    if defesa_sc.get("status") == "stale" and (not defesa_sc.get("publications") or defesa_sc.get("retrieval_method") != "previously_published_publications"):
        raise ValueError("Stale civil defense data must have previously validated publications")
    for post in defesa_sc["publications"]:
        address = urlparse(post.get("url", ""))
        if (post.get("validity_status") != "not_verified_from_publication_date" or
                address.scheme != "https" or address.hostname not in ("www.defesacivil.sc.gov.br", "defesacivil.sc.gov.br") or
                address.username or address.password):
            raise ValueError("Civil defense publication cannot claim a verified active alert")
    if archive.get("schema_version") != 1 or archive.get("kind") != "inmet_annual_zip_delayed_station_measurements_not_real_time" or archive.get("status") not in (
            "available", "cached", "stale", "unavailable", "no_nearby_stations", "fixture_mode"):
        raise ValueError("INMET annual delayed archive has invalid source schema")
    if archive["status"] == "fixture_mode" and not fixture:
        raise ValueError("Synthetic INMET annual archive cannot be published")
    archive_stations = archive.get("stations")
    if not isinstance(archive_stations, list) or len(archive_stations) > 12:
        raise ValueError("INMET annual station count invalid")
    if archive["status"] in ("available", "cached", "stale") and (not archive_stations or not archive.get("latest_observation_at")):
        raise ValueError("INMET archive claims availability without dated measurements")
    if archive["status"] in ("unavailable", "no_nearby_stations", "fixture_mode") and archive_stations:
        raise ValueError("INMET archive source unavailable but contains measurements")
    for station in archive_stations:
        if not isinstance(station, dict) or not isinstance(station.get("days"), list) or len(station["days"]) > 14:
            raise ValueError("Invalid INMET annual station days")
        for day in station["days"]:
            count = day.get("rain_measured_hours")
            if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= 24:
                raise ValueError("Invalid INMET annual hourly completeness")
            if count != 24 and day.get("rain_total_complete_mm") is not None:
                raise ValueError("Incomplete daily INMET rainfall wrongly presented as a full total")
    if overview.get("notice_archive_published") is not True:
        raise ValueError("Published archive marker is missing")
    if notices_archive.get("kind") != "archive_of_inmet_notices_not_confirmed_weather_events" or notices_archive.get("schema_version") != 1 or notices_archive.get("feed_status") != alerts["status"]:
        raise ValueError("Notice archive source classification invalid")
    if not isinstance(notices_archive.get("records"), list) or len(notices_archive["records"]) > 2000:
        raise ValueError("Invalid notice archive records")
    expected = {loc["id"] for loc in overview["locations"]}
    for dataset in (alerts, observations, rain, cemaden):
        if not isinstance(dataset.get("locations"), list) or {row.get("location_id") for row in dataset["locations"]} != expected:
            raise ValueError("Incomplete or invalid regional provider coverage")
    if alerts["status"] == "unavailable" and any(x.get("alerts") for x in alerts["locations"]):
        raise ValueError("Cannot show official warnings from an unavailable source")
    if observations["status"] == "unavailable" and any(x.get("observation") for x in observations["locations"]):
        raise ValueError("Cannot show observations from an unavailable source")
    if overview.get("official_alerts_integrated") is not (alerts["status"] == "available"):
        raise ValueError("Overview official alert integration status mismatched")
    for loc in overview["locations"]:
        if loc["status"] == "available":
            detail = json.loads((data / "places" / (loc["id"] + ".json")).read_text(encoding="utf-8"))
            if detail.get("measurement_status") != "estimated_model_not_station_observation":
                raise ValueError(f"Source classification changed for {loc['id']}")
    if not (output / "index.html").is_file():
        raise ValueError("Missing application index")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    validate(args.output, fixture=args.fixture)
    print(f"Site validated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

