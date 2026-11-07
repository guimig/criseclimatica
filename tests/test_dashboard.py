"""Normative priorities, robust station summaries and real observation continuity."""
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from observatorio.protocol import assess, reference, qualitative_match
from observatorio.dashboard import gauge_distribution, merge_observations, summarize, HISTORY_KIND, station_catalog, regional_rain_context
from build_site import build
from validate_site import validate

NOW=datetime(2026,11,6,20,tzinfo=timezone.utc)
STAMP='2026-11-06T20:00:00Z'


def notice(text='Previsão de temporais, com risco de alagamentos.',**extra):
    return {'title':'Temporais no Litoral Norte','url':'https://ciram.epagri.sc.gov.br/index.php/2026/11/06/aviso/',
            'notice_kind':'epagri_meteorological_advisory_not_civil_defense_alert',
            'published_at':'2026-11-06T18:00:00Z','valid_from':'2026-11-06T18:00:00Z','valid_until':'2026-11-07T23:00:00Z',
            'regions_text':'Litoral Norte','assessment_text':text,**extra}


def feed(notices=None,**extra):
    return {'kind':'epagri_ciram_official_advisories_not_civil_defense_alerts','status':'available',
            'retrieved_at':STAMP,'notices':[notice()] if notices is None else notices,**extra}


def primary(stations=None):
    return {'location_id':'araquari','valid_until':'2026-11-06T23:00:00Z',
            'forecast':{'status':'unavailable'},'observed_rain':{'status':'available','stations':stations or []},
            'recent_observations':[]}


class ProtocolTests(unittest.TestCase):
    def test_current_reference_replaces_previous_event_letters(self):
        ref=reference()
        self.assertEqual([r['id'] for r in ref['levels']],['verde','azul','amarelo','laranja','vermelho','roxo'])
        self.assertFalse(ref['automatic_numeric_thresholds'])
        self.assertEqual(len(ref['documents']),2)
        self.assertNotIn('events',ref)

    def test_qualitative_impact_suggests_attention_with_evidence(self):
        r=assess(feed(),{},STAMP)
        self.assertEqual(r['suggested_level'],'amarelo')
        self.assertIsNone(r['official_level'])
        self.assertEqual(r['evidence'][0]['matched_cue'],'alagamento')
        self.assertEqual(r['status'],'suggested_for_review')

    def test_primary_explicit_high_risk_supports_orange(self):
        r=assess(feed([notice('Alta probabilidade de tempestades com risco alto para a mobilidade.')]),{},STAMP)
        self.assertEqual(r['suggested_level'],'laranja')

    def test_severe_imminent_danger_supports_red_not_numeric_peak(self):
        r=assess(feed([notice('Tempestade severa iminente com ameaça à vida.')]),{},STAMP)
        self.assertEqual(r['suggested_level'],'vermelho')
        r=assess(feed([notice('Chuva 150 mm e vento 120 km/h.')]),{},STAMP)
        self.assertIsNone(r['suggested_level'])

    def test_blue_requires_seven_days_and_an_event(self):
        r=assess(feed([notice(valid_from='2026-11-13T20:00:00Z',valid_until='2026-11-14T20:00:00Z')]),{},STAMP)
        self.assertEqual(r['suggested_level'],'azul')
        r=assess(feed([notice(text='Previsão de tempo estável.',valid_from='2026-11-13T20:00:00Z')]),{},STAMP)
        self.assertIsNone(r['suggested_level'])

    def test_no_notice_is_not_green_and_no_decree_is_not_purple(self):
        for f in (feed([]),feed(status='unavailable'),feed([notice('Desastre prolongado e calamidade pública.')])):
            r=assess(f,{},STAMP)
            self.assertNotIn(r['suggested_level'],('verde','roxo'))

    def test_missing_timezone_or_territory_prevents_level(self):
        for override in ({'valid_from':None},{'valid_from':'2026-11-06T18:00:00'},
                         {'regions_text':'Oeste'},{'regions_text':'Todo o estado, exceto Litoral Norte'}):
            with self.subTest(override=override):
                self.assertIsNone(assess(feed([notice(**override)]),{},STAMP)['suggested_level'])

    def test_stale_expired_and_unsafe_sources_cannot_support_level(self):
        for f in (feed(status='stale'),feed(retrieved_at='2026-11-06T10:00:00Z'),
                  feed([notice(valid_until='2026-11-06T19:00:00Z')]),
                  feed([notice(url='https://example.com/')]),feed(kind='editorial_forecast')):
            self.assertIsNone(assess(f,{},STAMP)['suggested_level'])

    def test_inmet_color_is_not_a_level_conversion(self):
        analysis={'locations':[{'location_id':'araquari','official_notices':{'notices':[{'severity':'Grande Perigo'}]}}]}
        self.assertIsNone(assess(feed([]),analysis,STAMP)['suggested_level'])

    def test_negation_does_not_create_positive_danger(self):
        for text in ('Não há risco de tempestades ou alagamentos.', 'Sem risco alto de tempestades.'):
            self.assertIsNone(assess(feed([notice(text)]),{},STAMP)['suggested_level'])

    def test_high_risk_in_another_region_does_not_escalate_araquari(self):
        text='Temporais com risco alto no Oeste. No Litoral Norte, possibilidade de alagamentos.'
        self.assertEqual(assess(feed([notice(text)]),{},STAMP)['suggested_level'],'amarelo')
        self.assertIsNone(assess(feed([notice('Temporais com risco alto no Oeste.')]),{},STAMP)['suggested_level'])

    def test_higher_supported_level_does_not_average_away(self):
        r=assess(feed([notice(),notice('Alta probabilidade de tempestades.',url='https://ciram.epagri.sc.gov.br/b')]),{},STAMP)
        self.assertEqual(r['suggested_level'],'laranja')
        self.assertEqual(len(r['evidence']),2)

    def test_normative_conflict_is_exposed_not_resolved_by_code(self):
        text=' '.join(reference()['academic_rules'])
        self.assertIn('Divergência textual',text)
        self.assertIn('10 dias',text)
        self.assertEqual(reference()['communication_deadlines'][0]['deadline'],'22h do dia anterior')


class StatisticsTests(unittest.TestCase):
    def rows(self,values):
        return {'status':'available','stations':[{'code':str(i),'observed_at':STAMP,'rain_24h_mm':v} for i,v in enumerate(values)]}

    def test_median_does_not_hide_maximum(self):
        r=gauge_distribution(self.rows([0,2,100]))
        self.assertEqual(r['median_mm'],2)
        self.assertEqual(r['maximum_mm'],100)
        self.assertEqual(r['minimum_mm'],0)
        self.assertEqual(r['station_count'],3)

    def test_small_sample_and_missing_are_not_fabricated_medians(self):
        for values in ([0],[0,5],[],[None]):
            r=gauge_distribution(self.rows(values))
            self.assertIsNone(r['median_mm'])
        self.assertEqual(gauge_distribution(self.rows([0]))['maximum_mm'],0)

    def test_noncontemporaneous_station_is_excluded(self):
        d=self.rows([1,2,500]);d['stations'][2]['observed_at']='2026-11-06T19:00:00Z'
        r=gauge_distribution(d)
        self.assertEqual(r['station_count'],2)
        self.assertEqual(r['maximum_mm'],2)
        self.assertIsNone(r['median_mm'])
        self.assertEqual(r['excluded_time_count'],1)

    def test_latest_station_value_wins_without_calling_time_evolution_a_conflict(self):
        d=self.rows([1,2,3]);d['stations'].append({'code':'0','observed_at':'2026-11-06T19:55:00Z','rain_24h_mm':0})
        r=gauge_distribution(d)
        self.assertEqual(r['station_count'],3)
        self.assertEqual(r['minimum_mm'],1)

    def test_identical_duplicate_station_does_not_inflate_sample(self):
        d=self.rows([0,2]);d['stations'].append(deepcopy(d['stations'][0]))
        r=gauge_distribution(d)
        self.assertEqual(r['station_count'],2)
        self.assertIsNone(r['median_mm'])

    def test_conflicting_duplicate_is_removed(self):
        d=self.rows([0,2,3]);d['stations'].append({**d['stations'][0],'rain_24h_mm':200})
        r=gauge_distribution(d)
        self.assertEqual(r['station_count'],2)
        self.assertEqual(r['maximum_mm'],3)


class ObservationHistoryTests(unittest.TestCase):
    def test_only_actual_station_samples_are_retained_and_idempotent(self):
        p=primary([{'code':'12345','observed_at':STAMP,'rain_24h_mm':15,'rain_1h_mm':1}])
        first=merge_observations(None,p,STAMP)
        second=merge_observations(first,p,STAMP)
        self.assertEqual(first['records'],second['records'])
        self.assertEqual(len(first['records']),1)
        self.assertEqual(first['records'][0]['rain_24h_mm'],15)
        self.assertEqual(first['kind'],HISTORY_KIND)

    def test_far_metar_is_not_local_history(self):
        p=primary();p['recent_observations']=[{'source':'NOAA/METAR','code':'SBFL','observed_at':STAMP,'distance_km':149,'temperature_c':30}]
        self.assertFalse(merge_observations(None,p,STAMP)['records'])

    def test_history_is_retained_during_collection_failure(self):
        p=primary([{'code':'12345','observed_at':STAMP,'rain_24h_mm':15}])
        old=merge_observations(None,p,STAMP)
        new=merge_observations(old,primary(),'2026-11-06T23:00:00Z')
        self.assertEqual(new['records'],old['records'])

    def test_old_samples_expire_without_backfilling(self):
        p=primary([{'code':'12345','observed_at':STAMP,'rain_24h_mm':15}])
        old=merge_observations(None,p,STAMP)
        self.assertFalse(merge_observations(old,primary(),'2026-11-14T20:00:00Z')['records'])

    def test_conflicting_values_are_discarded_not_averaged(self):
        p=primary([{'code':'12345','observed_at':STAMP,'rain_24h_mm':15}])
        old=merge_observations(None,p,STAMP)
        p['observed_rain']['stations'][0]['rain_24h_mm']=30
        r=merge_observations(old,p,STAMP)
        self.assertFalse(r['records'])
        self.assertEqual(r['conflicting_records_discarded'],1)
        again=merge_observations(r,p,STAMP)
        self.assertEqual(again['records'],r['records'])
        self.assertEqual(again['conflicts'],r['conflicts'])

    def test_wrong_previous_kind_is_not_model_history_substitute(self):
        with self.assertRaisesRegex(ValueError,'refusing loss'):
            merge_observations({'kind':'daily_last_model_publication_not_station_observation'},primary(),STAMP)


class StationCatalogTests(unittest.TestCase):
    def test_exact_code_metadata_and_municipal_distance(self):
        history={'records':[{'source':'cemaden-rain','station':'12345'}]}
        sensors={'stations':[{'code':'12345','name':'Centro','municipality':'Araquari',
                             'latitude':-26.37,'longitude':-48.72}]}
        detail={'location':{'latitude':-26.37,'longitude':-48.72}}
        row=station_catalog(history,primary(),detail,sensors)[0]
        self.assertEqual(row['name'],'Centro')
        self.assertEqual(row['distance_km'],0)
        self.assertEqual(row['distance_reference'],'municipal_model_point_not_campus')
        self.assertEqual(row['metadata_status'],'coordinates_matched_by_station_code')

    def test_missing_metadata_does_not_invent_station_position(self):
        history={'records':[{'source':'cemaden-rain','station':'12345'}]}
        row=station_catalog(history,primary(),{}, {'stations':[{'code':'other','latitude':0,'longitude':0}]})[0]
        self.assertEqual(row['name'],'12345')
        self.assertIsNone(row['latitude'])
        self.assertIsNone(row['distance_km'])
        self.assertEqual(row['metadata_status'],'partial')

    def test_invalid_coordinates_and_metar_metadata(self):
        history={'records':[{'source':'cemaden-rain','station':'A'}, {'source':'metar','station':'SBJV'}]}
        p=primary();p['recent_observations']=[{'source':'NOAA/METAR','code':'SBJV','name':'Joinville','distance_km':21}]
        rows=station_catalog(history,p,{'location':{'latitude':-26,'longitude':-48}},
                             {'stations':[{'code':'A','latitude':100,'longitude':0}]})
        self.assertIsNone(rows[0]['latitude'])
        self.assertEqual(rows[1]['name'],'Joinville')
        self.assertEqual(rows[1]['distance_km'],21)
        self.assertIsNone(rows[1]['latitude'])


class RegionalRainContextTests(unittest.TestCase):
    def fixture(self):
        p=primary([{'code':'local','observed_at':STAMP,'rain_1h_mm':1}]);p['name']='Araquari'
        neighbor={'location_id':'joinville','name':'Joinville','observed_rain':{'status':'available','stations':[
            {'code':'near','observed_at':STAMP,'rain_1h_mm':2,'rain_24h_mm':4},
            {'code':'far','observed_at':STAMP,'rain_1h_mm':3},
            {'code':'missing','observed_at':STAMP,'rain_1h_mm':4},
            {'code':'local','observed_at':STAMP,'rain_1h_mm':100}]}}
        sensors={'stations':[{'code':'near','name':'Centro','latitude':-26.3,'longitude':-48.8},
                             {'code':'far','name':'Distante','latitude':-27.5,'longitude':-48.8}]}
        details={'araquari':{'location':{'latitude':-26.375,'longitude':-48.721}}}
        return {'locations':[p,neighbor]},details,sensors

    def test_context_keeps_verified_neighbors_separate_from_local_history(self):
        analysis,details,sensors=self.fixture();r=regional_rain_context(analysis,details,sensors,STAMP)
        self.assertEqual([x['station'] for x in r['records']],['near'])
        self.assertEqual(r['stations'][0]['municipality'],'Joinville')
        self.assertEqual(r['excluded_unlocated'],1)
        self.assertEqual(r['records'][0]['scope'],'nearby_station_snapshot_not_araquari_measurement')
        self.assertEqual(len(analysis['locations'][0]['observed_rain']['stations']),1)
        self.assertEqual(analysis['locations'][0]['observed_rain']['stations'][0]['rain_1h_mm'],1)

    def test_no_point_or_stale_measurement_never_fabricates_regional_values(self):
        analysis,details,sensors=self.fixture()
        self.assertFalse(regional_rain_context(analysis,{},sensors,STAMP)['records'])
        analysis['locations'][1]['observed_rain']['stations'][0]['observed_at']='2026-11-05T20:00:00Z'
        self.assertFalse(regional_rain_context(analysis,details,sensors,STAMP)['records'])

    def test_duplicates_empty_and_repeated_calls(self):
        analysis,details,sensors=self.fixture()
        analysis['locations'].append(deepcopy(analysis['locations'][1]))
        a=regional_rain_context(analysis,details,sensors,STAMP)
        self.assertEqual(len(a['records']),1)
        self.assertEqual(a,regional_rain_context(analysis,details,sensors,STAMP))
        self.assertFalse(regional_rain_context({'locations':[]},details,{},STAMP)['records'])


class DeploymentTests(unittest.TestCase):
    def test_build_has_new_dashboard_and_preserved_detail_page(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'site';build(target,fixture=ROOT/'tests/fixtures/open_meteo.json');validate(target,fixture=True)
            data=json.loads((target/'data/dashboard.json').read_text())
            self.assertEqual(data['location_id'],'araquari')
            self.assertFalse(data['decision_automated'])
            home=(target/'index.html').read_text();detail=(target/'dados.html').read_text()
            self.assertIn('./dashboard.js',home)
            self.assertNotIn('id="territory-grid"',home)
            self.assertIn('id="territory-grid"',detail)
            self.assertLess(len(home),14000)  # Includes explicit shared-control labels and accessible grouping.
            self.assertTrue((target/'references/pn-13-2026.pdf').is_file())
            with self.assertRaises(ValueError):validate(target,fixture=False)

    def test_validator_rejects_fabricated_official_level(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'site';build(target,fixture=ROOT/'tests/fixtures/open_meteo.json')
            p=target/'data/dashboard.json';data=json.loads(p.read_text());data['assessment']['official_level']='verde';p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'qualitative reference levels'):validate(target,fixture=True)

    def test_already_published_observation_history_cannot_silently_disappear(self):
        with tempfile.TemporaryDirectory() as directory:
            responses={'data/history.json':{'kind':'existing'},'data/latest.json':{'observation_history_published':True},'data/notice_history.json':{'records':[]}}
            with patch('build_site.fetch_previous_json',side_effect=lambda base,path,**kwargs:responses.get(path)):
                with self.assertRaisesRegex(RuntimeError,'observation history is missing'):
                    build(Path(directory)/'site',previous_url='https://example.com/')

if __name__=='__main__':unittest.main()
