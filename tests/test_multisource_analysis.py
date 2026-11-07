"""Auxiliary objective references, explicit periods and sampled alert history."""
import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from observatorio.objective_analysis import band,summarize,integrate
from observatorio.assessment_history import merge,KIND
from observatorio.alerts import normalize_alerts
from observatorio.notice_archive import merge_notice_archive
from observatorio.protocol import assess
from observatorio.analysis import forecast_analysis
NOW=datetime(2026,11,7,12,30,tzinfo=timezone.utc);STAMP=NOW.isoformat().replace('+00:00','Z')
PLACE={'id':'araquari','name':'Araquari','ibge_code':'4201307','latitude':-26.375,'longitude':-48.721}

def detail(rain=1,gust=20):
    start=NOW.replace(minute=0)
    return {'location':PLACE,'collected_at':STAMP,'current':{'time':start.isoformat()},'hourly':[
        {'time':(start+timedelta(hours=i)).isoformat(),'precipitation_mm':rain,'wind_kmh':10,'gust_kmh':gust,'temperature_c':25}
        for i in range(25)]}

def primary(d=None):
    d=d or detail()
    return {'forecast':forecast_analysis(d,NOW),'observed_rain':{'status':'available','stations':[
        {'code':'420130701A','observed_at':STAMP,'rain_1h_mm':0,'rain_24h_mm':0}]},
        'recent_observations':[],'official_notices':{'status':'available','notices':[]}}

def epagri():return {'kind':'epagri_ciram_official_advisories_not_civil_defense_alerts','status':'available','retrieved_at':STAMP,'notices':[]}

def dashboard(state='routine'):
    return {'assessment':{'monitoring_state':state,'title':'Monitoramento de rotina','suggested_level':None,'rule_version':'v2','evidence':[]}}


class NumericSupportTests(unittest.TestCase):
    def test_boundaries_are_explicit_and_not_temperature_thresholds(self):
        for field,values in {'rain_1h_mm':[(0,0),(20,1),(30,2),(60,2),(60.1,3)],'gust_kmh':[(0,0),(40,1),(60,2),(100,2),(100.1,3)],'rain_24h_mm':[(10,0),(49.9,0),(50,2),(100,2),(101,3)]}.items():
            for value,expected in values:self.assertEqual(band(value,field),expected)
        for value in (None,True,float('nan'),-1,10000):self.assertIsNone(band(value,'rain_1h_mm'))

    def test_single_potential_forecast_is_context_not_institutional_alert(self):
        d=detail(gust=44);r=summarize(primary(d),d,epagri(),STAMP)
        self.assertEqual(r['maximum_band'],1);self.assertIsNone(r['proposed_level'])
        p=integrate(assess(epagri(),{},STAMP),r)
        self.assertEqual(p['monitoring_label'],'Referências de atenção');self.assertIsNone(p['suggested_level'])

    def test_higher_direct_signal_can_support_attention_without_claiming_inmet_alert(self):
        d=detail(gust=70);r=summarize(primary(d),d,epagri(),STAMP)
        self.assertEqual(r['proposed_level'],'amarelo');self.assertFalse(r['coincidences'])

    def test_orange_numeric_support_requires_matching_strong_observation_nearby(self):
        d=detail(gust=70);p=primary(d)
        p['recent_observations']=[{'source':'NOAA/METAR','code':'SBJV','observed_at':STAMP,'distance_km':21,'gust_kmh':75,'wind_kmh':10}]
        r=summarize(p,d,epagri(),STAMP)
        self.assertEqual(r['proposed_level'],'laranja');self.assertTrue(r['coincidences'][0]['spatial_match_verified'])

    def test_future_peak_is_not_confirmation_of_old_observation(self):
        d=detail(gust=10);d['hourly'][20]['gust_kmh']=80;p=primary(d)
        p['recent_observations']=[{'source':'NOAA/METAR','code':'SBJV','observed_at':STAMP,'distance_km':21,'gust_kmh':80}]
        r=summarize(p,d,epagri(),STAMP)
        self.assertFalse(r['coincidences']);self.assertEqual(r['proposed_level'],'amarelo')

    def test_distant_or_stale_metar_cannot_raise_level(self):
        for changes in ({'distance_km':100},{'observed_at':(NOW-timedelta(hours=3)).isoformat()}):
            d=detail(gust=70);p=primary(d);p['recent_observations']=[{'source':'NOAA/METAR','code':'X','observed_at':STAMP,'distance_km':21,'gust_kmh':80,**changes}]
            self.assertEqual(summarize(p,d,epagri(),STAMP)['proposed_level'],'amarelo')

    def test_24h_proxy_does_not_alone_raise_institutional_level(self):
        d=detail(rain=5);r=summarize(primary(d),d,epagri(),STAMP)
        self.assertEqual(r['maximum_band'],3);self.assertIsNone(r['proposed_level'])
        self.assertTrue(any(s['period_proxy'] for s in r['signals'] if s['band']))

    def test_rain_pair_needs_verified_location_for_orange(self):
        d=detail(rain=35);p=primary(d);p['observed_rain']['stations'][0]['rain_1h_mm']=35
        self.assertEqual(summarize(p,d,epagri(),STAMP)['proposed_level'],'amarelo')
        sensors={'stations':[{'code':'420130701A','latitude':-26.375,'longitude':-48.721}]}
        self.assertEqual(summarize(p,d,epagri(),STAMP,sensors)['proposed_level'],'laranja')

    def test_primary_red_cannot_be_downgraded_by_lower_numeric_signals(self):
        p=assess(epagri(),{},STAMP);p['suggested_level']='vermelho';p['title']='Vermelho'
        r=integrate(p,summarize(primary(),detail(),epagri(),STAMP))
        self.assertEqual(r['suggested_level'],'vermelho')

    def test_routine_partial_and_official_context_are_distinct(self):
        r=summarize(primary(),detail(),epagri(),STAMP);p=assess(epagri(),{},STAMP)
        self.assertEqual(integrate(p,r)['monitoring_state'],'routine')
        self.assertEqual(integrate(p,{**r,'core_complete':False})['monitoring_state'],'partial')
        self.assertEqual(integrate(p,{**r,'has_complementary_notices':True})['monitoring_state'],'official_context')
        self.assertIsNone(integrate(p,r)['official_level'])

    def test_numeric_support_expires_with_its_observation(self):
        d=detail(rain=35);p=primary(d);p['observed_rain']['stations'][0].update(observed_at=(NOW-timedelta(minutes=50)).isoformat(),rain_1h_mm=35)
        r=summarize(p,d,epagri(),STAMP)
        self.assertLessEqual(datetime.fromisoformat(r['valid_until'].replace('Z','+00:00')),NOW+timedelta(minutes=10))


class HistoryTests(unittest.TestCase):
    def test_state_runs_are_idempotent_and_measure_sample_span_only(self):
        a=merge(None,dashboard(),STAMP);b=merge(a,dashboard(),STAMP)
        self.assertEqual(a,b)
        later=(NOW+timedelta(hours=3)).isoformat().replace('+00:00','Z');c=merge(b,dashboard(),later)
        self.assertEqual(c['episodes'][0]['samples'],2);self.assertEqual(c['episodes'][0]['sampled_span_hours'],3)
        self.assertIn('not continuous',c['duration_note'])

    def test_change_and_gap_start_separate_episodes(self):
        a=merge(None,dashboard(),STAMP)
        b=merge(a,dashboard('partial'),(NOW+timedelta(hours=3)).isoformat())
        self.assertEqual(len(b['episodes']),2);self.assertEqual(b['episodes'][0]['transition_kind'],'different_state_sampled')
        c=merge(b,dashboard('partial'),(NOW+timedelta(hours=12)).isoformat())
        self.assertEqual(len(c['episodes']),3);self.assertEqual(c['episodes'][1]['transition_kind'],'collection_gap')

    def test_epagri_validity_and_visibility_spans_are_separate(self):
        d=dashboard();d['assessment']['evidence']=[{'status':'eligible','url':'https://ciram.epagri.sc.gov.br/a','valid_from':STAMP,'valid_until':(NOW+timedelta(hours=24)).isoformat()}]
        a=merge(None,d,STAMP);self.assertEqual(a['notices'][0]['validity_hours'],24)
        self.assertEqual(a['episodes'][0]['sampled_span_hours'],0)
        b=merge(a,dashboard(),(NOW+timedelta(hours=3)).isoformat())
        self.assertEqual(len(b['notices']),1)

    def test_invalid_previous_state_is_not_silently_lost(self):
        with self.assertRaises(ValueError):merge({'kind':'other'},dashboard(),STAMP)

    def test_inmet_source_clock_duration_does_not_invent_timezone(self):
        raw={'hoje':[{'id_aviso':'1','geocodes':'4201307','data_inicio':'2026-11-07','hora_inicio':'00:00','data_fim':'2026-11-08','hora_fim':'00:00'}]}
        feed=normalize_alerts(raw,[PLACE],STAMP);n=feed['locations'][0]['alerts'][0]
        self.assertIsNone(n['start_at']);self.assertEqual(n['validity_hours'],24)
        self.assertEqual(n['duration_kind'],'nominal_source_clock_no_timezone')
        archive=merge_notice_archive(None,feed,now=NOW)
        self.assertEqual(archive['records'][0]['validity_hours'],24)

    def test_explicit_offset_supports_elapsed_validity(self):
        raw={'hoje':[{'id_aviso':'1','geocodes':'4201307','data_inicio':'2026-11-07T00:00:00-03:00','data_fim':'2026-11-07T06:00:00-03:00'}]}
        n=normalize_alerts(raw,[PLACE],STAMP)['locations'][0]['alerts'][0]
        self.assertEqual(n['validity_hours'],6);self.assertEqual(n['duration_kind'],'explicit_instants')

if __name__=='__main__':unittest.main()
