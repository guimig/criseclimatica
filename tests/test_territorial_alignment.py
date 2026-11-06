"""Common geography does not imply model skill, shared units or climatic equivalence."""
import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src')]
from observatorio.config import load_locations
from observatorio.territorial_alignment import summarize
from observatorio.cemaden_sensors import collect, SensorSourceError
from observatorio.history import merge_daily_publications

STAMP='2026-11-06T12:00:00Z'
PLACE={'id':'curitiba','name':'Curitiba','state':'PR','latitude':-25.43,'longitude':-49.27,
       'territorial_group':'curitiba-planalto','ibge_code':'4106902'}


def sources():
    models={'curitiba':{'collected_at':STAMP,'current':{'time':STAMP,'temperature_c':25,'precipitation_mm':0},
                       'grid_point':{'latitude':-25.43,'longitude':-49.27,'elevation_m':900}}}
    rain={'status':'available','locations':[{'location_id':'curitiba','status':'available','stations':[{'code':'rain01'}]}]}
    sensors={'status':'available','stations':[{'code':'410690001A','name':'Estação teste','state':'PR',
              'municipality':'Curitiba','latitude':-25.44,'longitude':-49.27,
              'readings':[{'sensor_id':60,'unit':'°C','value':24,'observed_at':STAMP}]}]}
    metar={'status':'available','stations':[{'icao':'SBBI','name':'Bacacheri','latitude':-25.4,'longitude':-49.23,
             'observed_at':STAMP,'temperature_c':25}]}
    return models,rain,sensors,metar


class AlignmentTests(unittest.TestCase):
    def test_twenty_locations_four_groups_and_matching_ibge_states(self):
        places=load_locations(ROOT/'config/locations.json')
        self.assertEqual(len(places),20)
        self.assertEqual(len({p['territorial_group'] for p in places}),4)
        self.assertEqual({p['state'] for p in places},{'SC','PR'})
        for p in places:
            self.assertTrue(p['ibge_code'].startswith('42' if p['state']=='SC' else '41'))

    def test_close_sources_are_candidates_not_accuracy_comparison(self):
        result=summarize([PLACE],*sources(),STAMP)['locations'][0]
        self.assertEqual(result['coverage_status'],'three_sources_nearby')
        candidate=result['candidate_triads'][0]
        self.assertEqual(candidate['potential_common_variables'],['temperature_c'])
        self.assertTrue(candidate['model_grid_proximity_verified'])
        self.assertTrue(candidate['time_window_aligned'])
        self.assertFalse(candidate['comparison_ready'])
        self.assertFalse(candidate['elevation_match_verified'])
        self.assertFalse(result['cemaden_local_rain']['individual_station_positions_verified'])

    def test_metar_does_not_gain_fictional_rain_accumulation(self):
        model,rain,sensors,metar=sources()
        sensors['stations'][0]['readings'][0].update(sensor_id=10,unit='mm')
        out=summarize([PLACE],model,rain,sensors,metar,STAMP)['locations'][0]
        self.assertEqual(out['candidate_triads'][0]['potential_common_variables'],[])

    def test_mismatched_units_do_not_become_common_temperature(self):
        model,rain,sensors,metar=sources()
        sensors['stations'][0]['readings'][0]['unit']='°F'
        out=summarize([PLACE],model,rain,sensors,metar,STAMP)['locations'][0]
        self.assertEqual(out['candidate_triads'][0]['potential_common_variables'],[])

    def test_two_stations_in_radius_can_still_be_too_far_from_each_other(self):
        model,rain,sensors,metar=sources()
        sensors['stations'][0]['latitude']=-25.23
        metar['stations'][0]['latitude']=-25.63
        out=summarize([PLACE],model,rain,sensors,metar,STAMP)['locations'][0]
        self.assertEqual(out['cemaden_nearby_count'],1)
        self.assertEqual(out['metar_nearby_count'],1)
        self.assertFalse(out['candidate_triads'])

    def test_old_model_or_measurement_cannot_form_current_triad(self):
        for target in ('model','sensor','metar'):
            model,rain,sensors,metar=sources()
            old='2026-11-05T12:00:00Z'
            if target=='model': model['curitiba']['current']['time']=old
            if target=='sensor': sensors['stations'][0]['readings'][0]['observed_at']=old
            if target=='metar': metar['stations'][0]['observed_at']=old
            self.assertFalse(summarize([PLACE],model,rain,sensors,metar,STAMP)['locations'][0]['candidate_triads'])

    def test_timing_difference_is_reported_instead_of_hidden(self):
        model,rain,sensors,metar=sources()
        sensors['stations'][0]['readings'][0]['observed_at']='2026-11-06T10:00:00Z'
        candidate=summarize([PLACE],model,rain,sensors,metar,STAMP)['locations'][0]['candidate_triads'][0]
        self.assertEqual(candidate['time_gap_minutes'],120)
        self.assertFalse(candidate['time_window_aligned'])

    def test_returned_grid_can_be_far_from_requested_sample(self):
        model,rain,sensors,metar=sources()
        model['curitiba']['grid_point']['latitude']=-26
        candidate=summarize([PLACE],model,rain,sensors,metar,STAMP)['locations'][0]['candidate_triads'][0]
        self.assertFalse(candidate['model_grid_proximity_verified'])

    def test_missing_sources_do_not_fabricate_overlap(self):
        self.assertEqual(summarize([PLACE],{}, {}, {}, {}, STAMP)['locations'][0]['coverage_status'],'insufficient_overlap')

    def test_repeated_alignment_is_deterministic(self):
        self.assertEqual(summarize([PLACE],*sources(),STAMP),summarize([PLACE],*sources(),STAMP))


class StateCollectionTests(unittest.TestCase):
    def test_sc_and_pr_requests_use_the_shared_limiter_and_keep_partial_results(self):
        places=[PLACE,{'id':'araquari','state':'SC','latitude':-26.375,'longitude':-48.721}]
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        row={'codestacao':'420130701A','uf':'SC','latitude':-26.375,'longitude':-48.721,
             'nome':'Teste','cidade':'Araquari','id_sensor':60,'valor':25,'datahora':now}
        states=[]; requests=[]
        def fetch(jwt,*,uf):
            states.append(uf)
            if uf=='PR': raise SensorSourceError('service_unavailable')
            return [row]
        with patch('observatorio.cemaden_sensors.fetch_recent',side_effect=fetch):
            out=collect(places,now,token='test-only',sensor_fetcher=lambda _:[],on_request=lambda:requests.append(1))
        self.assertEqual(set(states),{'SC','PR'})
        self.assertEqual(len(requests),3)  # catalog + both state queries
        self.assertEqual(out['status'],'available')
        self.assertEqual(out['diagnostic'],'partial_state_coverage')
        self.assertEqual(out['state_queries']['PR'],'service_unavailable')

    def test_legitimate_pr_reading_is_kept_and_other_state_is_not(self):
        from observatorio.cemaden_sensors import normalize_recent
        row={'codestacao':'410690001A','uf':'PR','latitude':PLACE['latitude'],'longitude':PLACE['longitude'],
             'nome':'Teste','cidade':'Curitiba','id_sensor':60,'valor':25,'datahora':STAMP}
        out=normalize_recent([row,{**row,'uf':'RS','codestacao':'430000001A'}],{},[PLACE],STAMP,
                             now=datetime.fromisoformat(STAMP.replace('Z','+00:00')))
        self.assertEqual([r['code'] for r in out['stations']],['410690001A'])

    def test_one_year_history_accepts_twenty_municipalities_with_bounded_size(self):
        now=datetime(2026,11,6,12,tzinfo=timezone.utc)
        records=[]
        for place in load_locations(ROOT/'config/locations.json'):
            for day in range(366):
                time=(now-timedelta(days=day)).isoformat().replace('+00:00','Z')
                records.append({'location_id':place['id'],'day_local':time[:10],
                  'collected_at':time,'model_reference_at':time,'source':'open-meteo','kind':'model_snapshot_not_observation',
                  'temperature_c':25,'wind_kmh':10,'gust_kmh':20,'rain_next_24h_mm':0})
        previous={'schema_version':1,'kind':'daily_last_model_publication_not_station_observation','records':records}
        out=merge_daily_publications(previous,{'locations':load_locations(ROOT/'config/locations.json')},{},now=now)
        self.assertEqual(len(out['records']),7320)
        self.assertLess(len(json.dumps(out,ensure_ascii=False,separators=(',',':')).encode()),3_000_000)


if __name__=='__main__':unittest.main()
