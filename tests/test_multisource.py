"""Comparable evidence, outages, equal weights and independent validity."""
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from observatorio.multisource import (STATIONS, build, statistics, evidence, merge_history,
    counter_window, local_observations, select_forecast, notices, validate_product, forecast_context)
from observatorio.unit_inference import annotate
from observatorio.analysis import iso

NOW = datetime(2026, 11, 11, 15, tzinfo=timezone.utc)
STAMP = iso(NOW)


def model(identifier='best_match', missing=None):
    rows = [{'time': iso(NOW+timedelta(hours=i)), 'precipitation_mm': 1,
             'temperature_c': 20, 'wind_kmh': 10, 'gust_kmh': 15} for i in range(49)]
    if missing: rows[3][missing] = None
    return {'id': identifier, 'name': identifier, 'provider': 'Open-Meteo', 'status': 'available',
            'collected_at': STAMP, 'hourly': rows}


def campus():
    return {'status':'available','checked_at':STAMP, 'metrics': {
        'temperature':{'latest':{'time':STAMP,'value':20}},
        'humidity':{'latest':{'time':STAMP,'value':80}},
        'wind_avg':{'latest':{'time':STAMP,'value':10}},
        'wind_gust':{'latest':{'time':STAMP,'value':50}},
        'rain_daily':{'latest':{'time':STAMP,'value':10},'series':[]}}}


class MultisourceTests(unittest.TestCase):
    def test_four_stations_equal_mean_and_extreme_not_diluted(self):
        rows=[evidence('source',s,'rain_1h_mm',v,STAMP,hours=1,unit='mm') for s,v in zip(STATIONS,[0,0,0,80])]
        stat=statistics(rows,'rain_1h_mm',STAMP)
        self.assertEqual(stat['station_count'],4);self.assertEqual(stat['mean'],20)
        self.assertEqual(stat['median'],0);self.assertEqual(stat['maximum'],80)
        self.assertTrue(all(r['weight']==1 for r in stat['members']))

    def test_duplicate_station_is_not_two_votes_and_conflicts_excluded(self):
        r=evidence('cemaden','420130701A','rain_1h_mm',2,STAMP,hours=1,unit='mm')
        self.assertEqual(statistics([r,r],'rain_1h_mm',STAMP)['station_count'],1)
        self.assertEqual(statistics([r,{**r,'value':3}],'rain_1h_mm',STAMP)['station_count'],0)

    def test_unrelated_time_windows_do_not_enter_same_statistic(self):
        rows=[evidence('ifc','ifc-araquari','rain_daily_mm',80,STAMP,unit='mm'),
              evidence('cemaden','420130701A','rain_24h_mm',2,STAMP,hours=24,unit='mm')]
        self.assertEqual(statistics(rows,'rain_24h_mm',STAMP)['mean'],2)
        old={**rows[1], 'end_at':iso(NOW-timedelta(hours=1))}
        self.assertEqual(statistics([rows[1],old],'rain_24h_mm',STAMP)['station_count'],1)

    def test_failure_or_zero_signature_does_not_erase_other_variables(self):
        c=campus();c['metrics']['temperature']['latest']['value']=0;c['metrics']['humidity']['latest']['value']=0
        rows,rejected=local_observations({},c,{},STAMP)
        self.assertNotIn('temperature_c',[r['variable'] for r in rows]);self.assertIn('gust_kmh',[r['variable'] for r in rows])
        self.assertEqual(sum(r['reason']=='simultaneous_temperature_humidity_zero' for r in rejected),2)
        rows,_=local_observations({}, {}, {}, STAMP);self.assertEqual(rows,[])

    def test_partial_model_fallback_by_variable_without_hour_splicing(self):
        f,d=select_forecast({'records':[model(missing='precipitation_mm'),model('ecmwf_ifs025')]},STAMP)
        self.assertEqual(f['rain']['total_mm'],24)
        self.assertEqual(f['sources_by_variable']['precipitation_mm']['id'],'ecmwf_ifs025')
        self.assertEqual(f['sources_by_variable']['gust_kmh']['id'],'best_match')
        self.assertIsNone(f['rain_wind_overlap'])
        self.assertTrue(f['sources_by_variable']['precipitation_mm']['fallback'])
        f,_=select_forecast({'records':[]},STAMP);self.assertEqual(f['status'],'unavailable')

    def test_stale_models_and_conflicting_hour_cannot_be_selected(self):
        r=model();r['collected_at']=iso(NOW-timedelta(hours=9))
        f,_=select_forecast({'records':[r]},STAMP);self.assertEqual(f['status'],'unavailable')
        r=model();r['reference_at']=iso(NOW-timedelta(hours=9))
        f,_=select_forecast({'records':[r]},STAMP);self.assertEqual(f['status'],'unavailable')
        r=model();r['hourly'].append({**r['hourly'][3],'gust_kmh':200})
        f,_=select_forecast({'records':[r]},STAMP)
        self.assertEqual(f['sources_by_variable']['gust_kmh']['status'],'unavailable')
        self.assertEqual(f['sources_by_variable']['temperature_c']['status'],'available')

    def test_counter_difference_not_sum_and_gaps_or_resets_rejected(self):
        rows=[evidence('ifc','ifc-araquari','rain_daily_mm',i/10,iso(NOW-timedelta(minutes=60-5*i)),unit='mm',method='five_minute_counter_max') for i in range(13)]
        r=counter_window(rows,1,STAMP);self.assertAlmostEqual(r['value'],1.2);self.assertFalse(r['threshold_eligible'])
        self.assertIsNone(counter_window(rows[:3]+rows[7:],1,STAMP))
        rows[8]['value']=0;self.assertIsNone(counter_window(rows,1,STAMP))
        self.assertIsNone(counter_window(rows,24,STAMP))

    def test_history_repeat_conflicts_and_refusal_of_loss(self):
        row=evidence('ifc','ifc-araquari','temperature_c',20,STAMP,unit='°C')
        h=merge_history(None,[row],{},STAMP);self.assertEqual(h,merge_history(h,[row],{},STAMP))
        h=merge_history(h,[{**row,'value':21}],{},STAMP);self.assertEqual(h['records'],[])
        self.assertEqual(merge_history(h,[row],{},STAMP)['records'],[])
        with self.assertRaises(ValueError):merge_history({},[],{},STAMP)

    def test_inmet_daily_participates_without_hourly_or_quantitative_rain(self):
        feed={'status':'available','retrieved_at':STAMP,'valid_until':iso(NOW+timedelta(hours=6)),
              'days':[{'day':'2026-11-11','minimum_c':18,'maximum_c':25,'periods':[{'period':'tarde','summary':'Chuva','wind_intensity_text':'Fracos'}]}]}
        ctx=forecast_context({},feed,{},STAMP)
        self.assertEqual(ctx['days'][0]['source'],'INMET');self.assertNotIn('precipitation_mm',ctx['days'][0])
        self.assertEqual(forecast_context({},feed,{},iso(NOW+timedelta(hours=7)))['days'],[])

    def test_inmet_and_epagri_notice_weights_equal_and_do_not_set_formal_level(self):
        end=iso(NOW+timedelta(hours=4))
        dash={'assessment':{'base_assessment':{'evidence':[{'status':'eligible','checked_at':STAMP,'valid_from':STAMP,'valid_until':end,'url':'epagri','title':'Temporais'}]}},
              'inmet_context':{'status':'available','retrieved_at':STAMP,'notices':[{'id':'1','type':'Temporal','start_at':STAMP,'end_at':end,'municipalities':[{'location_id':'araquari'}]}]}}
        rows=notices(dash,STAMP);self.assertEqual({r['source']:r['weight'] for r in rows},{'Epagri/Ciram':1,'INMET':1})
        result,h,detail=build(dash,{},campus(),{},{'records':[model()]},{},{},STAMP)
        validate_product(result);self.assertIsNone(result['formal_level'])
        self.assertEqual(len(result['notices']),2)
        self.assertEqual(h['assessments'][0]['notices'], result['notices'])
        _,again,_=build(dash,{},campus(),{},{'records':[model()]},{},{},STAMP,h)
        self.assertEqual(len(again['assessments']),1)
        self.assertEqual(notices(dash,iso(NOW+timedelta(hours=7))),[])

    def test_unit_hypotheses_are_empirical_and_never_silently_confirmed(self):
        feed={'stations':[{'readings':[{'sensor_id':240,'value':0,'unit':None},{'sensor_id':330,'value':35,'unit':None},{'sensor_id':20,'value':15,'unit':None},{'sensor_id':10,'value':1,'unit':'mm'}]}]}
        annotate(feed);a,b,c,d=feed['stations'][0]['readings']
        self.assertEqual(a['unit_inference']['suggested_unit'],'mm/h');self.assertIsNone(a['unit'])
        self.assertEqual(b['unit_inference']['suggested_unit'],'%');self.assertIsNone(c['unit_inference']['suggested_unit'])
        self.assertEqual(d['unit_status'],'documented');self.assertFalse(a['unit_inference']['numeric_analysis_eligible'])

    def test_empty_build_is_partial_not_zero(self):
        data,h,_=build({'assessment':{}},{},{},{},{'records':[]},{},{},STAMP)
        validate_product(data)
        self.assertEqual(data['statistics']['rain_24h_mm']['status'],'unavailable')
        self.assertEqual(data['coverage']['wind']['status'],'unavailable');self.assertEqual(data['signals'],[])


if __name__=='__main__':unittest.main()
