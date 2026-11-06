"""Validate public static artifact before publishing; avoids synthetic builds in Pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def validate(output: Path, *, fixture: bool = False) -> None:
    data = output / "data"
    overview = json.loads((data / "latest.json").read_text(encoding="utf-8"))
    history = json.loads((data / "history.json").read_text(encoding="utf-8"))
    stations = json.loads((data / "stations.json").read_text(encoding="utf-8"))
    alerts = json.loads((data / "alerts.json").read_text(encoding="utf-8"))
    observations = json.loads((data / "observations.json").read_text(encoding="utf-8"))
    rain = json.loads((data / "rain_gauges.json").read_text(encoding="utf-8"))
    nasa = json.loads((data / "nasa_power.json").read_text(encoding="utf-8"))
    cemaden = json.loads((data / "cemaden.json").read_text(encoding="utf-8"))
    cptec = json.loads((data / "cptec.json").read_text(encoding="utf-8"))
    defesa_sc = json.loads((data / "defesa_civil_sc.json").read_text(encoding="utf-8"))
    archive = json.loads((data / "inmet_archive.json").read_text(encoding="utf-8"))
    epagri_geo = json.loads((data / "epagri_geo.json").read_text(encoding="utf-8"))
    epagri_notices = json.loads((data / "epagri_notices.json").read_text(encoding="utf-8"))
    notices_archive = json.loads((data / "notice_history.json").read_text(encoding="utf-8"))
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
    if not overview.get("available_locations") or not overview.get("locations"):
        raise ValueError("Manifest has no available locations")
    if history.get("kind") != "daily_last_model_publication_not_station_observation":
        raise ValueError("History source classification invalid")
    if stations.get("kind") != "station_catalog_metadata_not_measurements":
        raise ValueError("INMET catalog source classification invalid")
    if alerts.get("kind") != "inmet_official_notices_by_municipality" or alerts.get("status") not in ("available", "unavailable"):
        raise ValueError("INMET alerts classification or status invalid")
    if observations.get("kind") != "aerodrome_metar_observations_not_municipal_measurements" or observations.get("status") not in ("available", "no_recent_reports", "unavailable"):
        raise ValueError("METAR observations classification or status invalid")
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
