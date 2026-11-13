"""Original-clock recovery and qualitative INMET participation regression."""
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from observatorio.analysis import iso
from observatorio.forecast_comparison import ARCHIVE_KIND, merge_archive, summarize
from observatorio.multisource import select_forecast, evidence, build
from observatorio.inmet_periods import assess
from observatorio.risk_classification import classify, evaluate, validate_product

NOW = datetime(2026, 11, 13, 9, 37, tzinfo=timezone.utc)
STAMP = iso(NOW)


def model(at=NOW-timedelta(hours=1), identifier='best_match'):
    start = at.replace(minute=0, second=0, microsecond=0)
    return {'id': identifier, 'name': identifier, 'location_id': 'araquari', 'status': 'available',
            'collected_at': iso(at), 'reference_at': iso(start),
            'hourly': [{'time': iso(start+timedelta(hours=i)), 'precipitation_mm': 0,
                        'wind_kmh': 10, 'gust_kmh': 20, 'temperature_c': 22} for i in range(73)]}


def archive(record=None):
    return {'schema_version': 1, 'kind': ARCHIVE_KIND, 'location_id': 'araquari',
            'publications': [{'saved_at': iso(NOW-timedelta(hours=1)), 'records': [record or model()]}]}


def context():
    return {'days': [{'source': 'INMET', 'location_id': 'araquari', 'day': day,
                     'collected_at': STAMP, 'valid_until': iso(NOW+timedelta(hours=6)),
                     'periods': [{'period': p, 'summary': 'Muitas nuvens com possibilidade de chuva isolada',
                                  'wind_intensity_text': 'Fracos'} for p in ('manha', 'tarde', 'noite')]}
                    for day in ('2026-11-13', '2026-11-14')]}


def dashboard():
    observations = [evidence('cemaden', '420130701A', field, 0, STAMP, hours=h, unit='mm', ttl=1 if h==1 else 6)
                    for h, field in ((1, 'rain_1h_mm'), (24, 'rain_24h_mm'))]
    observations += [evidence('ifc', 'ifc-araquari', field, 10, STAMP, unit='km/h') for field in ('wind_kmh', 'gust_kmh')]
    return {'synthesis': {'observations': observations, 'signals': [{**r, 'band': 0} for r in observations],
                         'notices': [], 'selected_forecast': {}, 'forecast_context': context()},
            'source_status': [{'source': 'INMET · avisos', 'status': 'available', 'reference_at': STAMP}]}


class RecoveryTests(unittest.TestCase):
    def test_failure_recovers_complete_original_product_and_clocks(self):
        comparison = {'records': [{'id': 'best_match', 'status': 'unavailable', 'hourly': [], 'diagnostic': 'URLError'}]}
        original = deepcopy(comparison); old = archive(); previous = deepcopy(old)
        f, detail = select_forecast(comparison, STAMP, old)
        for source in f['sources_by_variable'].values():
            self.assertEqual(source['status'], 'available'); self.assertTrue(source['retained_previous'])
            self.assertEqual(source['collected_at'], old['publications'][0]['records'][0]['collected_at'])
            self.assertEqual(source['valid_until'], '2026-11-13T16:00:00Z')
        self.assertEqual(comparison, original); self.assertEqual(old, previous)
        self.assertTrue(detail['hourly'])
        self.assertEqual(select_forecast(comparison, STAMP, old), (f, detail))

    def test_same_model_different_runs_do_not_create_rain_gust_overlap(self):
        current=model(NOW);current['hourly'][4]['precipitation_mm']=None
        f,_=select_forecast({'records':[current]},STAMP,archive())
        self.assertEqual(f['sources_by_variable']['precipitation_mm']['id'],f['sources_by_variable']['gust_kmh']['id'])
        self.assertNotEqual(f['sources_by_variable']['precipitation_mm']['collected_at'],f['sources_by_variable']['gust_kmh']['collected_at'])
        self.assertIsNone(f['rain_wind_overlap'])

    def test_current_complete_alternative_beats_cached_primary(self):
        f, _ = select_forecast({'records': [model(NOW, 'ecmwf_ifs025')]}, STAMP, archive())
        self.assertTrue(all(s['id']=='ecmwf_ifs025' and not s['retained_previous'] for s in f['sources_by_variable'].values()))

    def test_expiry_and_wrong_municipality_are_never_recovered(self):
        for changes in ({'collected_at': iso(NOW-timedelta(hours=9))},
                        {'reference_at': iso(NOW-timedelta(hours=9))}, {'location_id': 'joinville'}):
            record = {**model(), **changes}
            f, _ = select_forecast({'records': []}, STAMP, archive(record))
            self.assertEqual(f['status'], 'unavailable')
        f, _ = select_forecast({'records': []}, '2026-11-13T16:00:00Z', archive())
        self.assertEqual(f['status'], 'unavailable')

    def test_missing_or_conflicting_hour_not_spliced_from_other_runs(self):
        first=model(); first['hourly'][4]['gust_kmh']=None
        second=model(NOW-timedelta(hours=2)); second['hourly'][6]['gust_kmh']=None
        old=archive(first);old['publications'].append({'saved_at':iso(NOW-timedelta(hours=2)), 'records':[second]})
        f,_=select_forecast({'records':[]},STAMP,old)
        self.assertEqual(f['sources_by_variable']['gust_kmh']['status'],'unavailable')
        self.assertEqual(f['sources_by_variable']['precipitation_mm']['status'],'available')
        first=model();first['hourly'].append({**first['hourly'][4],'gust_kmh':400})
        f,_=select_forecast({'records':[]},STAMP,archive(first))
        self.assertEqual(f['sources_by_variable']['gust_kmh']['status'],'unavailable')

    def test_archive_keeps_current_hour_and_does_not_republish_cache_as_new_run(self):
        record=model(NOW);comparison=summarize({},[record],{},STAMP)
        old=merge_archive(None,comparison)
        self.assertIn('2026-11-13T09:00:00Z',[r['time'] for r in old['publications'][0]['records'][0]['hourly']])
        failed=summarize({},[],{},iso(NOW+timedelta(minutes=5)))
        again=merge_archive(old,failed)
        self.assertEqual(again['publications'][-1]['records'],[])
        f,_=select_forecast(failed,failed['generated_at'],again)
        self.assertTrue(f['sources_by_variable']['gust_kmh']['retained_previous'])

    def test_build_wires_archive_into_signals_and_history(self):
        result, history, detail=build({'assessment':{}},{},{},{},{'records':[]},{},{},STAMP,forecast_archive=archive())
        self.assertTrue(result['selected_forecast']['sources_by_variable']['gust_kmh']['retained_previous'])
        self.assertEqual(len(result['signals']),3)
        self.assertEqual(history['assessments'][0]['selected_forecasts'],result['selected_forecast']['sources_by_variable'])


class PeriodRiskTests(unittest.TestCase):
    def test_qualitative_route_with_measurements_and_warning_query_can_support_green(self):
        d=dashboard();r=classify(d,{},STAMP);validate_product(r)
        self.assertEqual(r['level'],'verde');self.assertEqual(r['basis'],'qualitative_monitored_coverage')
        self.assertEqual(r['coverage']['forecast_resolution'],'mixed_or_qualitative')
        self.assertEqual(evaluate(r,iso(NOW+timedelta(hours=2)))['level'],None)
        self.assertFalse(any('gust_kmh' in p for p in r['qualitative_forecast']['periods']))

    def test_missing_observation_or_query_or_period_prevents_false_green(self):
        for change in (lambda d:d['source_status'].clear(),
                       lambda d:d['synthesis']['observations'].clear(),
                       lambda d:d['synthesis']['observations'].pop(),
                       lambda d:d['synthesis']['forecast_context']['days'][1]['periods'].pop(0),
                       lambda d:d['synthesis']['forecast_context']['days'][0].update(location_id='joinville'),
                       lambda d:d['synthesis']['forecast_context']['days'][0].update(valid_until=STAMP),
                       lambda d:d['synthesis']['forecast_context']['days'][0].update(collected_at=iso(NOW+timedelta(hours=1)))):
            d=dashboard();change(d);self.assertIsNone(classify(d,{},STAMP)['level'])

    def test_hazards_support_attention_even_with_hourly_calm_and_without_measurements(self):
        for summary,wind in (('Nublado com pancadas de chuva e trovoadas','Fracos'),
                             ('Tempestade com granizo','Fortes'),('Sem chuva','Fortes'),('Chuva intensa','Fracos'),('Encoberto','Moderados a fortes')):
            d=dashboard();d['synthesis']['observations']=[]
            p=d['synthesis']['forecast_context']['days'][0]['periods'][1];p.update(summary=summary,wind_intensity_text=wind)
            r=classify(d,{},STAMP);self.assertEqual(r['level'],'amarelo')
            self.assertEqual(r['basis'],'inmet_qualitative_forecast_attention');self.assertIsNone(r['official_level'])
            self.assertFalse(any(c['level'] in ('laranja','vermelho','roxo') for c in r['candidates']))
        d=dashboard();d['synthesis']['selected_forecast'],detail=select_forecast({'records':[model(NOW)]},STAMP)
        d['synthesis']['forecast_context']['days'][0]['periods'][1]['summary']='Trovoadas'
        self.assertEqual(classify(d,detail,STAMP)['level'],'amarelo')

    def test_unknown_or_negated_description_does_not_certify_normality(self):
        for summary,wind in (('Fenômeno desconhecido','Fracos'),('Sem trovoadas','Fracos'),('Encoberto','Moderados'),('Encoberto','Fracos com rajadas')):
            d=dashboard();p=d['synthesis']['forecast_context']['days'][0]['periods'][1]
            p.update(summary=summary,wind_intensity_text=wind)
            self.assertIsNone(classify(d,{},STAMP)['level'])

    def test_expired_past_and_out_of_horizon_hazards_do_not_trigger_attention(self):
        for day,period in (('2026-11-12','noite'),('2026-11-14','tarde')):
            d=dashboard();ctx=d['synthesis']['forecast_context']
            ctx['days'].append({**deepcopy(ctx['days'][0]),'day':day,'periods':[{'period':period,'summary':'Trovoadas','wind_intensity_text':'Fortes'}]})
            self.assertEqual(classify(d,{},STAMP)['level'],'verde')
        d=dashboard()
        for day in d['synthesis']['forecast_context']['days']:day.update(valid_until=STAMP)
        self.assertIsNone(classify(d,{},STAMP)['level'])

    def test_day_only_and_turns_preserve_resolution_and_expiry(self):
        ctx=context();ctx['days'][1]['periods']=[{'period':'dia','summary':'Poucas nuvens','wind_intensity_text':'Fracos'}]
        r=assess(ctx,STAMP);self.assertTrue(r['coverage']['rain']['available'])
        self.assertEqual(r['coverage']['wind']['resolution'],'qualitative_daily_or_period')
        self.assertTrue(all(p['time_basis']=='operational_period_bucket_not_exact_event_time' for p in r['periods']))
        ctx['days'][0]['cached']=True
        r=assess(ctx,iso(NOW+timedelta(hours=1)))
        self.assertTrue(r['periods'][0]['cached'])
        self.assertEqual(r['periods'][0]['valid_until'],'2026-11-13T15:00:00Z')
        self.assertEqual(assess(ctx,iso(NOW+timedelta(hours=6)))['periods'],[])

    def test_duplicate_conflicting_period_is_rejected(self):
        d=dashboard();day=d['synthesis']['forecast_context']['days'][0]
        day['periods'].append(deepcopy(day['periods'][0]))
        self.assertIsNone(classify(d,{},STAMP)['level'])


if __name__=='__main__': unittest.main()
