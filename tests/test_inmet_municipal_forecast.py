"""INMET municipality, period/day compatibility and outage regression tests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/"src")]
from observatorio.inmet_forecast import normalize, collect, compare_daily, validate_product, TZ, iso, unavailable
from observatorio.alerts import normalize_alerts, retain_valid_notices, fetch_alerts, AlertSourceError
from observatorio.analysis import notice_analysis
from observatorio.dashboard import regional_notice_context

NOW = datetime(2026, 11, 10, 16, tzinfo=timezone.utc)
STAMP = iso(NOW)
LOCATIONS = [{"id":"araquari", "ibge_code":"4201307", "name":"Araquari"}]


def payload():
    entry = {"uf":"SC", "entidade":"Araquari", "resumo":"Possibilidade de chuva isolada", "temp_min":16, "temp_max":25,
             "umidade_min":50, "umidade_max":100, "int_vento":"Fracos", "dir_vento":"NE", "hora":"13", "icone":"data:image/png;base64,not_needed"}
    return {"4201307":{"10/11/2026":{period:deepcopy(entry) for period in ("manha","tarde","noite")}, "11/11/2026":deepcopy(entry)}}


class MunicipalForecastTests(unittest.TestCase):
    def test_normalized_periods_deduplicate_daily_extremes_without_numeric_inference(self):
        feed = normalize(payload(), STAMP);validate_product(feed)
        self.assertEqual(feed["days"][0]["minimum_c"],16)
        self.assertEqual(len(feed["days"][0]["periods"]),3)
        self.assertIsNone(feed["issued_at"])
        self.assertFalse(feed["risk_criteria"])
        self.assertNotIn("base64",json.dumps(feed));self.assertNotIn("rain_mm",json.dumps(feed))
        self.assertEqual(feed["days"][0]["periods"][0]["wind_intensity_text"],"Fracos")

    def test_bad_scope_and_structure_rejected_and_conflicts_preserved_only_by_period(self):
        for wrong in ({}, {"4209102":payload()["4201307"]}, {"4201307":[]}, {"4201307":{"invalid":{}}}):
            with self.assertRaises(ValueError):normalize(wrong,STAMP)
        for key,value in (("entidade","Joinville"),("uf","PR")):
            bad=payload();bad["4201307"]["10/11/2026"]["manha"][key]=value
            with self.assertRaises(ValueError):normalize(bad,STAMP)
        bad=payload();bad["4201307"]["10/11/2026"]["tarde"]["temp_max"]=27
        feed=normalize(bad,STAMP)
        self.assertIsNone(feed["days"][0]["maximum_c"])
        self.assertEqual(feed["days"][0]["periods"][1]["maximum_c"],27)

    def test_same_civil_day_requires_all_24_model_hours_and_does_not_use_utc_daily_values(self):
        feed=normalize(payload(),STAMP)
        start=datetime(2026,11,10,tzinfo=TZ)
        rows=[{"time":iso(start+timedelta(hours=i)),"temperature_c":i} for i in range(24)]
        detail={"collected_at":STAMP,"hourly":rows,"daily":[{"temperature_min_c":-40,"temperature_max_c":60}]}
        pair=compare_daily(feed,detail)["daily_comparison"][0]
        self.assertEqual(pair["start_at"],"2026-11-10T03:00:00Z")
        self.assertEqual(pair["status"],"comparable_context")
        self.assertEqual(pair["model_minimum_c"],0);self.assertEqual(pair["model_maximum_c"],23)
        for missing in (rows[:-1],rows+[dict(rows[0],temperature_c=44)]):
            detail["hourly"]=missing
            pair=compare_daily(feed,detail)["daily_comparison"][0]
            self.assertEqual(pair["status"],"incomplete");self.assertIsNone(pair["model_maximum_c"])

    def test_cached_data_never_renews_original_time_or_extends_validity(self):
        prior=normalize(payload(),STAMP)
        with patch("observatorio.inmet_forecast.fetch_payload",side_effect=TimeoutError):
            saved=collect(iso(NOW+timedelta(hours=1)),previous=prior)
            self.assertEqual(saved["status"],"cached");self.assertEqual(saved["retrieved_at"],STAMP)
            self.assertEqual(saved["valid_until"],prior["valid_until"])
            stale=collect(iso(NOW+timedelta(hours=7)),previous=saved)
            self.assertEqual(stale["status"],"stale")
            self.assertEqual(collect(iso(NOW+timedelta(hours=37)),previous=prior)["status"],"unavailable")
        validate_product(saved);validate_product(stale)
        refreshed=collect(iso(NOW+timedelta(minutes=30)),previous=prior,fixture=payload())
        self.assertEqual(refreshed["content_first_seen_at"],STAMP)
        self.assertNotEqual(refreshed["retrieved_at"],STAMP)
        self.assertEqual(collect(STAMP,fixture={})["status"],"unavailable")

    def test_fixture_and_risk_guards(self):
        validate_product(unavailable(STAMP,"fixture_mode"),fixture=True)
        with self.assertRaises(ValueError):validate_product(unavailable(STAMP,"fixture_mode"))
        bad=normalize(payload(),STAMP);bad["risk_criteria"]=True
        with self.assertRaises(ValueError):validate_product(bad)


class NoticeRecoveryTests(unittest.TestCase):
    def prior(self):
        return normalize_alerts({"hoje":[{"id_aviso":1,"geocodes":"4201307","descricao":"Tempestade", "severidade":"Perigo",
                               "data_inicio":"2026-11-10T12:00:00Z","data_fim":"2026-11-10T20:00:00Z"}],"futuro":[]},LOCATIONS,STAMP)

    def test_one_retry_then_success_without_rss(self):
        with patch("observatorio.alerts._fetch_alerts_once",side_effect=[AlertSourceError("offline"),{"hoje":[]}]) as request,patch("observatorio.alerts.time.sleep") as sleep:
            self.assertEqual(fetch_alerts(),{"hoje":[]});self.assertEqual(request.call_count,2);sleep.assert_called_once_with(1)
        with patch("observatorio.alerts._fetch_alerts_once",side_effect=AlertSourceError("offline")) as request,patch("observatorio.alerts.time.sleep"):
            with self.assertRaises(AlertSourceError):fetch_alerts()
            self.assertEqual(request.call_count,2)

    def test_failed_query_preserves_only_positive_explicit_unexpired_notices(self):
        saved=retain_valid_notices(self.prior(),LOCATIONS,iso(NOW+timedelta(hours=1)))
        self.assertEqual(saved["status"],"unavailable");self.assertIsNone(saved["retrieved_at"])
        self.assertEqual(saved["locations"][0]["alerts"],[])
        self.assertTrue(saved["retained_previous"]);self.assertEqual(saved["last_success_at"],STAMP)
        repeated=retain_valid_notices(saved,LOCATIONS,iso(NOW+timedelta(hours=2)))
        self.assertEqual(repeated["last_success_at"],STAMP)
        self.assertFalse(retain_valid_notices(repeated,LOCATIONS,iso(NOW+timedelta(hours=4)))["retained_previous"])
        unknown=self.prior();unknown["locations"][0]["alerts"][0]["end_at"]=None
        self.assertFalse(retain_valid_notices(unknown,LOCATIONS,STAMP)["retained_previous"])
        empty=normalize_alerts({"hoje":[],"futuro":[]},LOCATIONS,STAMP)
        self.assertFalse(retain_valid_notices(empty,LOCATIONS,STAMP)["retained_previous"])

    def test_retained_notices_are_context_not_successful_query(self):
        stamp=iso(NOW+timedelta(hours=1));saved=retain_valid_notices(self.prior(),LOCATIONS,stamp)
        result=notice_analysis(saved,"araquari",{"status":"unavailable"},NOW+timedelta(hours=1))
        self.assertEqual(result["status"],"unavailable");self.assertTrue(result["notices"][0]["retained_previous"])
        context=regional_notice_context({"locations":[{"location_id":"araquari","official_notices":result}]},{},stamp)
        self.assertEqual(context["status"],"unavailable");self.assertTrue(context["retained_previous"])
        self.assertEqual(len(context["notices"]),1)

if __name__=="__main__":unittest.main()
