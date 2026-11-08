"""Analytical safety: incomplete evidence must never imply improvement or safety."""
import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from observatorio.analysis import (KIND, forecast_analysis, forecast_snapshot, hourly_bins,
    iso, notice_analysis, observed_rain, recent_observations, revision_analysis, summarize,
    temperature_context)
from observatorio.alerts import normalize_alerts
from observatorio.open_meteo import normalize, ProviderError

NOW = datetime(2026, 11, 6, 12, 30, tzinfo=timezone.utc)
STAMP = iso(NOW)
PLACE = {'id':'araquari', 'name':'Araquari', 'state':'SC', 'latitude':-26.375,
         'longitude':-48.721, 'ibge_code':'4201307', 'featured':True}
OTHER = {**PLACE, 'id':'joinville', 'name':'Joinville', 'latitude':-26.3044, 'longitude':-48.8487, 'ibge_code':'4209102'}


def detail(place=PLACE, now=NOW, rain=1):
    start = now.replace(minute=0, second=0, microsecond=0)
    return {'location':place, 'grid_point':{'latitude':place['latitude'], 'longitude':place['longitude'], 'elevation_m':10},
            'collected_at':iso(now), 'current':{'time':iso(start), 'temperature_c':30},
            'hourly':[{'time':iso(start+timedelta(hours=i)), 'precipitation_mm':rain,
                       'wind_kmh':10+i, 'gust_kmh':20+i, 'temperature_c':31 if 3 <= i <= 7 else 29,
                       'humidity_pct':80} for i in range(49)]}


def feed(**extra):
    return {'status':'available', 'retrieved_at':STAMP, 'checked_at':STAMP, 'locations':[], **extra}


def synthesis(details=None, cemaden=None, metars=None, alerts=None, previous=None, sensors=None):
    return summarize([PLACE, OTHER], details if details is not None else {'araquari':detail()},
                     cemaden or {}, metars or {}, alerts or {}, {}, STAMP, previous=previous, sensors=sensors)


class ForecastAnalysisTests(unittest.TestCase):
    def test_complete_rain_peaks_have_preceding_hour_boundaries(self):
        result = forecast_analysis(detail(), NOW)
        self.assertEqual(result['rain']['total_mm'], 24)
        self.assertEqual(result['rain_peaks'][0], {'hours':3, 'total_mm':3,
            'start_at':'2026-11-06T12:00:00Z', 'end_at':'2026-11-06T15:00:00Z'})
        self.assertEqual(result['wind']['gust_kmh']['maximum'], 43)
        self.assertEqual(result['heat']['hours_at_or_above'], 5)
        self.assertEqual(result['heat']['longest_sequence_hours'], 5)
        self.assertEqual(result['heat']['start_at'], '2026-11-06T15:00:00Z')

    def test_partial_rain_does_not_establish_peak_or_zero(self):
        d = detail(); d['hourly'][4]['precipitation_mm'] = None
        result = forecast_analysis(d, NOW)
        self.assertEqual(result['rain']['status'], 'partial')
        self.assertIsNone(result['rain']['total_mm'])
        self.assertFalse(result['rain_peaks'])
        self.assertIsNone(result['rain_wind_overlap'])

    def test_zero_rain_is_valid_and_distinct_from_missing(self):
        result = synthesis(details={'araquari':detail(rain=0)})['locations'][0]
        self.assertEqual(result['forecast']['rain']['total_mm'], 0)
        self.assertNotIn('rain_timing', {s['id'] for s in result['suggestions']})

    def test_conflicting_duplicate_invalidates_only_its_variable(self):
        d = detail(); row = deepcopy(d['hourly'][4]); row['gust_kmh'] = 100; d['hourly'].append(row)
        r = forecast_analysis(d, NOW)
        self.assertIsNone(r['wind']['gust_kmh']['maximum'])
        self.assertEqual(r['rain']['status'], 'complete')

    def test_identical_duplicates_are_idempotent(self):
        d=detail(); original=forecast_analysis(d,NOW); d['hourly'] += deepcopy(d['hourly'])
        self.assertEqual(forecast_analysis(d,NOW), original)

    def test_invalid_numeric_values_never_create_peaks(self):
        for val in (True, float('nan'), -2, 5000):
            with self.subTest(value=val):
                d=detail(); d['hourly'][3]['gust_kmh']=val
                self.assertIsNone(forecast_analysis(d,NOW)['wind']['gust_kmh']['maximum'])

    def test_stale_or_future_models_do_not_support_suggestions(self):
        for offset in (-10, 1):
            d=detail(now=NOW+timedelta(hours=offset))
            row=synthesis(details={'araquari':d})['locations'][0]
            self.assertEqual(row['forecast']['status'], 'stale')
            self.assertFalse(row['suggestions'])

    def test_missing_temperature_prevents_duration_claim(self):
        d=detail(); d['hourly'][4]['temperature_c']=None
        r=forecast_analysis(d,NOW)
        self.assertIsNone(r['heat']['hours_at_or_above'])
        self.assertIsNone(r['heat']['longest_sequence_hours'])

    def test_rain_at_gust_time_uses_following_rain_endpoint(self):
        d=detail(); d['hourly'][23]['precipitation_mm']=2; d['hourly'][24]['precipitation_mm']=7
        r=forecast_analysis(d,NOW)['rain_wind_overlap']
        self.assertEqual(r['gust_at'], '2026-11-07T11:00:00Z')
        self.assertEqual(r['rain_mm'], 7)

    def test_empty_or_malformed_series_never_creates_values(self):
        self.assertEqual(hourly_bins(None,'temperature_c'), {})
        self.assertEqual(hourly_bins([None, {}, {'time':'invalid'}], 'temperature_c'), {})
        d=detail();d['hourly']=[]
        r=forecast_analysis(d,NOW)
        self.assertFalse(r['rain_peaks'])
        self.assertEqual(r['heat']['status'], 'unavailable')


class EvidenceTests(unittest.TestCase):
    def test_araquari_is_primary_even_when_only_joinville_forecast_exists(self):
        result=synthesis(details={'joinville':detail(OTHER)})
        self.assertEqual(result['primary_location_id'],'araquari')
        self.assertEqual(result['locations'][0]['forecast']['status'],'unavailable')
        self.assertEqual(result['locations'][1]['role'],'complementary_regional_context')
        self.assertFalse(result['locations'][0]['suggestions'])

    def test_only_exact_municipal_observed_accumulations_are_used(self):
        cemaden=feed(locations=[{'location_id':'joinville','status':'available','stations':[
            {'code':'X','observed_at':STAMP,'rain_24h_mm':50}]}])
        self.assertFalse(observed_rain(cemaden,'araquari',NOW)['stations'])

    def test_accumulations_are_not_added_or_compared_to_future(self):
        cemaden=feed(locations=[{'location_id':'araquari','status':'available','stations':[
            {'code':'X','observed_at':STAMP,'rain_24h_mm':10,'rain_48h_mm':30,'rain_72h_mm':50}]}])
        r=synthesis(cemaden=cemaden)['locations'][0]
        self.assertEqual(r['observed_rain']['stations'][0]['rain_24h_mm'],10)
        self.assertNotIn('total_mm',r['observed_rain'])
        self.assertNotIn('rain_error_mm',r)

    def test_stale_observation_is_not_zero(self):
        cemaden=feed(locations=[{'location_id':'araquari','status':'available','stations':[
            {'code':'X','observed_at':iso(NOW-timedelta(hours=7)),'rain_24h_mm':0}]}])
        r=observed_rain(cemaden,'araquari',NOW)
        self.assertEqual(r['status'],'no_valid_recent_readings')
        self.assertFalse(r['stations'])

    def test_notice_without_explicit_timezone_does_not_claim_overlap(self):
        raw={'hoje':[{'id_aviso':'1','descricao':'Chuvas intensas','geocodes':'4201307',
                      'data_inicio':'2026-11-06','hora_inicio':'12:00','data_fim':'2026-11-07','hora_fim':'12:00'}]}
        alerts=normalize_alerts(raw,[PLACE],STAMP)
        r=notice_analysis(alerts,'araquari',forecast_analysis(detail(),NOW),NOW)
        self.assertEqual(r['notices'][0]['temporal_relation'],'unverified_timezone_or_window')

    def test_notice_with_offsets_can_match_window(self):
        alerts=feed(locations=[{'location_id':'araquari','alerts':[{'id':'1','type':'Vento',
            'start_at':'2026-11-06T10:00:00-03:00','end_at':'2026-11-06T15:00:00-03:00'}]}])
        r=notice_analysis(alerts,'araquari',forecast_analysis(detail(),NOW),NOW)
        self.assertEqual(r['notices'][0]['temporal_relation'],'overlaps_forecast')

    def test_warning_is_used_without_model_agreement(self):
        alerts=feed(locations=[{'location_id':'araquari','alerts':[{'id':'1','type':'Tempestade'}]}])
        r=synthesis(details={},alerts=alerts)['locations'][0]
        self.assertIn('official_notice',{s['id'] for s in r['suggestions']})
        self.assertNotIn('rain_timing',{s['id'] for s in r['suggestions']})

    def test_expired_verified_notice_does_not_support_suggestion(self):
        alerts=feed(locations=[{'location_id':'araquari','alerts':[{'id':'1','type':'Vento',
            'start_at':iso(NOW-timedelta(hours=4)), 'end_at':iso(NOW-timedelta(hours=1))}]}])
        row=synthesis(details={},alerts=alerts)['locations'][0]
        self.assertEqual(row['official_notices']['notices'][0]['lifecycle'],'expired')
        self.assertFalse(row['suggestions'])

    def test_notice_end_does_not_expire_unrelated_data(self):
        end=iso(NOW+timedelta(minutes=10))
        alerts=feed(locations=[{'location_id':'araquari','alerts':[{'id':'1','type':'Vento',
            'start_at':iso(NOW-timedelta(hours=1)), 'end_at':end}]}])
        row=synthesis(alerts=alerts)['locations'][0]
        self.assertEqual(row['valid_until'],end)
        self.assertEqual(row['data_valid_until'],iso(NOW+timedelta(hours=3)))

    def test_stale_notice_does_not_generate_advisory(self):
        alerts=feed(retrieved_at=iso(NOW-timedelta(hours=7)),locations=[{'location_id':'araquari','alerts':[{'id':'1'}]}])
        self.assertFalse(synthesis(details={},alerts=alerts)['locations'][0]['suggestions'])

    def test_pairwise_context_needs_distance_and_time(self):
        base={'icao':'SBJV','name':'Joinville','latitude':PLACE['latitude'],'longitude':PLACE['longitude'],
              'observed_at':STAMP,'temperature_c':27}
        for changes, count in (({},1),({'latitude':-28},0),({'observed_at':iso(NOW-timedelta(hours=2))},0)):
            with self.subTest(changes=changes):
                r=temperature_context(detail(),PLACE,feed(stations=[{**base,**changes}]),NOW)
                self.assertEqual(len(r['pairs']),count)
                if count:self.assertIsNone(r['pairs'][0]['difference_c'])

    def test_recent_metar_remains_visible_without_forecast(self):
        metars=feed(stations=[{'icao':'SBJV','observed_at':STAMP,'temperature_c':27}],
            locations=[{'location_id':'araquari','stations':[{'icao':'SBJV','distance_km':20}]}])
        r=synthesis(details={},metars=metars)['locations'][0]
        self.assertEqual(r['recent_observations'][0]['temperature_c'],27)

    def test_suggestions_have_traceability_and_expire(self):
        r=synthesis()['locations'][0]
        self.assertEqual(r['valid_until'],iso(NOW+timedelta(hours=3)))
        for s in r['suggestions']:
            self.assertTrue(all(s.get(k) for k in ('text','evidence','scope','limitation')))
        text=json.dumps(r,ensure_ascii=False).lower()
        for forbidden in ('suspenda as aulas','o campus está seguro','não há risco'):
            self.assertNotIn(forbidden,text)


class RevisionTests(unittest.TestCase):
    def previous(self):
        old=NOW-timedelta(hours=3)
        return forecast_snapshot({'araquari':detail(now=old)},iso(old))

    def test_same_valid_hours_are_compared_not_shifted_windows(self):
        d=detail(rain=2); f=forecast_analysis(d,NOW)
        r=revision_analysis(self.previous(),d,'araquari',f,NOW)
        self.assertEqual(r['status'],'comparable_publications')
        self.assertEqual(r['previous_rain_mm'],24)
        self.assertEqual(r['current_rain_mm'],48)
        self.assertEqual(r['rain_change_mm'],24)

    def test_missing_current_data_is_not_improvement(self):
        d=detail(rain=None);f=forecast_analysis(d,NOW)
        r=revision_analysis(self.previous(),d,'araquari',f,NOW)
        self.assertIsNone(r['rain_change_mm'])

    def test_other_grid_or_incomplete_previous_is_not_comparable(self):
        for mutate in (lambda p:p['locations'][0]['grid_point'].update(latitude=-27),
                       lambda p:p['locations'][0]['hourly'].clear(),
                       lambda p:p.update(generated_at=STAMP),
                       lambda p:p.update(kind='observed_history')):
            p=self.previous();mutate(p);d=detail()
            self.assertIsNone(revision_analysis(p,d,'araquari',forecast_analysis(d,NOW),NOW)['rain_change_mm'])

    def test_malformed_previous_state_degrades_without_failure(self):
        for p in (None, {}, {'kind':'wrong'}, {**self.previous(),'locations':[None]}, {**self.previous(),'locations':42}, {**self.previous(),'locations':[{'location_id':'araquari','hourly':None}]}):
            d=detail();r=revision_analysis(p,d,'araquari',forecast_analysis(d,NOW),NOW)
            self.assertIsNone(r['rain_change_mm'])

    def test_snapshot_is_bounded_and_repeatable(self):
        d=detail();a=forecast_snapshot({'araquari':d},STAMP)
        self.assertEqual(a,forecast_snapshot({'araquari':d},STAMP))
        self.assertLessEqual(len(a['locations'][0]['hourly']),49)
        self.assertNotIn('observations',a)


class UnitTests(unittest.TestCase):
    def test_current_interval_is_preserved(self):
        raw=json.loads((ROOT/'tests/fixtures/open_meteo.json').read_text())
        r=normalize(PLACE,raw,STAMP)
        self.assertEqual(r['current']['interval_seconds'],900)
        self.assertEqual(r['time_basis']['timezone'],'UTC')

    def test_missing_or_wrong_hourly_and_daily_units_fail_closed(self):
        for section, field in (('hourly_units','precipitation'),('daily_units','temperature_2m_max')):
            for val in (None,'wrong'):
                raw=json.loads((ROOT/'tests/fixtures/open_meteo.json').read_text())
                raw[section][field]=val
                with self.assertRaises(ProviderError):normalize(PLACE,raw,STAMP)

if __name__ == '__main__':
    unittest.main()
