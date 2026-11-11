"""Six consultative stages, real coverage and expiry regression."""
import sys
import unittest
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from observatorio.risk_classification import classify,evaluate,validate_product
from observatorio.analysis import iso
from observatorio.multisource import evidence
NOW=datetime(2026,11,11,1,tzinfo=timezone.utc);STAMP=iso(NOW)


def fixture():
    sources={f:{'status':'available','name':'Modelo','valid_until':iso(NOW+timedelta(hours=8))} for f in ('precipitation_mm','wind_kmh','gust_kmh')}
    observations=[evidence('cemaden','420130701A',f,0,STAMP,hours=h,unit='mm',ttl=1 if h==1 else 6) for h,f in ((1,'rain_1h_mm'),(24,'rain_24h_mm'))]
    synthesis={'observations':observations,'signals':[{**r,'band':0} for r in observations], 'notices':[],
        'selected_forecast':{'sources_by_variable':sources}}
    return {'synthesis':synthesis,'assessment':{'base_assessment':{'evidence':[]}},
            'source_status':[{'source':'INMET · avisos','status':'available','reference_at':STAMP}],
            'inmet_context':{'status':'available','retrieved_at':STAMP,'notices':[]}}


class RiskTests(unittest.TestCase):
    def test_normality_requires_observations_forecast_and_warning_check(self):
        d=fixture();r=classify(d,{},STAMP);validate_product(r)
        self.assertEqual(r['level'],'verde');self.assertEqual(r['name'],'Normalidade')
        for mutate in (lambda d:d['synthesis']['observations'].clear(),
                       lambda d:d['synthesis']['selected_forecast']['sources_by_variable'].pop('gust_kmh'),
                       lambda d:d['source_status'].clear()):
            bad=fixture();mutate(bad);self.assertIsNone(classify(bad,{},STAMP)['level'])

    def test_normality_expires_with_shortest_required_measurement(self):
        r=classify(fixture(),{},STAMP)
        self.assertEqual(evaluate(r,iso(NOW+timedelta(minutes=30)))['level'],'verde')
        self.assertIsNone(evaluate(r,iso(NOW+timedelta(hours=2)))['level'])

    def test_any_equal_station_can_support_attention_without_average(self):
        for station in ('420130701A','420130702A','420130704A','ifc-araquari'):
            d=fixture();d['synthesis']['signals'].append({**evidence('source',station,'gust_kmh',50,STAMP,unit='km/h'),'band':1})
            r=classify(d,{},STAMP);self.assertEqual(r['level'],'amarelo');self.assertIn('50',r['reason'])

    def test_compatible_severe_observation_and_model_support_orange(self):
        d=fixture();d['synthesis']['signals'].append({**evidence('source','420130701A','rain_1h_mm',40,STAMP,hours=1,unit='mm'),'band':2})
        detail={'hourly':[{'time':STAMP,'precipitation_mm':45}]}
        self.assertEqual(classify(d,detail,STAMP)['level'],'laranja')
        self.assertEqual(classify(d,{'hourly':[{'time':iso(NOW+timedelta(hours=8)),'precipitation_mm':100}]},STAMP)['level'],'amarelo')

    def test_unknown_interval_is_not_used_as_a_false_coincidence(self):
        d=fixture();d['synthesis']['signals'].append({**evidence('ifc','ifc-araquari','gust_kmh',70,STAMP,unit='km/h',method='reported_interval_unverified'),'band':2})
        self.assertEqual(classify(d,{'hourly':[{'time':STAMP,'gust_kmh':80}]},STAMP)['level'],'amarelo')

    def test_inmet_and_epagri_use_same_qualitative_criteria(self):
        for source in ('INMET','Epagri/Ciram'):
            d=fixture();d['synthesis']['notices']=[{'source':source,'title':'Tempestade','assessment_text':'Tempestade severa iminente com ameaça à vida.',
                'start_at':STAMP,'end_at':iso(NOW+timedelta(hours=3)),'valid_until':iso(NOW+timedelta(hours=2))}]
            r=classify(d,{},STAMP);self.assertEqual(r['level'],'vermelho');self.assertIsNone(r['official_level'])
            d['synthesis']['notices'][0]['assessment_text']='Alta probabilidade de tempestades com risco alto.'
            self.assertEqual(classify(d,{},STAMP)['level'],'laranja')

    def test_future_event_seven_days_out_is_preparation(self):
        d=fixture();d['synthesis']['notices']=[{'source':'INMET','title':'Tempestade','start_at':iso(NOW+timedelta(days=8)),
            'end_at':iso(NOW+timedelta(days=9)),'valid_until':iso(NOW+timedelta(hours=6))}]
        self.assertEqual(classify(d,{},STAMP)['level'],'azul')

    def test_positive_inmet_notice_with_unverified_window_blocks_green(self):
        d=fixture();d['inmet_context']['notices']=[{'id':'28680','type':'Tempestade','lifecycle':'unverified',
            'start_at':iso(NOW+timedelta(days=1)),'end_at':iso(NOW+timedelta(days=1)),
            'severity':'Grande perigo','municipalities':[{'location_id':'araquari'}]}]
        r=classify(d,{},STAMP);self.assertEqual(r['level'],'amarelo');self.assertIn('validade a confirmar',r['reason'])
        d['inmet_context']['notices'][0]['municipalities']=[{'location_id':'joinville'}]
        self.assertEqual(classify(d,{},STAMP)['level'],'verde')

    def test_expired_or_failed_warning_query_cannot_create_notice_or_green(self):
        d=fixture();d['source_status'][0]['reference_at']=iso(NOW-timedelta(hours=7));d['inmet_context']['status']='unavailable'
        self.assertIsNone(classify(d,{},STAMP)['level'])

    def test_no_data_never_becomes_normality_and_numbers_never_calamity(self):
        d=fixture();d['synthesis']['observations']=[];d['synthesis']['signals']=[];d['synthesis']['selected_forecast']={}
        self.assertIsNone(classify(d,{},STAMP)['level'])
        d['synthesis']['signals']=[{**evidence('x','ifc-araquari','gust_kmh',200,STAMP,unit='km/h'),'band':3}]
        r=classify(d,{},STAMP);self.assertEqual(r['level'],'amarelo');validate_product(r)
        self.assertEqual(classify(d,{},STAMP),r)

    def test_approximate_high_rain_prevents_false_green_without_becoming_orange(self):
        d=fixture();d['synthesis']['observations'].append(evidence('ifc','ifc-araquari','rain_1h_mm',40,STAMP,hours=1,unit='mm',threshold_eligible=False))
        self.assertEqual(classify(d,{},STAMP)['level'],'amarelo')

    def test_past_reported_notice_date_does_not_leave_attention_permanently(self):
        d=fixture();d['inmet_context']['notices']=[{'id':'old','type':'Tempestade','lifecycle':'unverified','window_as_reported':'01/11/2026 00:00 — 01/11/2026 23:59','municipalities':[{'location_id':'araquari'}]}]
        self.assertEqual(classify(d,{},STAMP)['level'],'verde')

    def test_validator_refuses_unsubstantiated_level(self):
        r=classify(fixture(),{},STAMP);r['level']='vermelho'
        with self.assertRaises(ValueError):validate_product(r)


if __name__=='__main__':unittest.main()
