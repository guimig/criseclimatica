"""Real browser: equal local stations, daily INMET and hourly fallback."""
import json
import os
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from ui_dashboard import fixture, server, OUTPUT
from ui_details import datasets
from ui_forecasts import comparison_fixture
from observatorio.forecast_comparison import merge_archive
from observatorio.risk_classification import classify
from observatorio.multisource import build, STATIONS
from observatorio.dashboard import gauge_distribution
from ui_campus_station import campus_feed


def main():
    from playwright.sync_api import sync_playwright
    home=fixture();dash=home['dashboard.json'];stamp=dash['generated_at'];now=datetime.fromisoformat(stamp.replace('Z','+00:00'))
    iso=lambda t:t.isoformat().replace('+00:00','Z')
    comp=comparison_fixture(stamp)
    for row in comp['records'][0]['hourly']:row['precipitation_mm']=None
    c={'status':'available','checked_at':stamp,'metrics':{
        'temperature':{'latest':{'time':stamp,'value':23}},'humidity':{'latest':{'time':stamp,'value':75}},
        'wind_avg':{'latest':{'time':stamp,'value':15}},'wind_gust':{'latest':{'time':stamp,'value':50}},
        'rain_daily':{'latest':{'time':stamp,'value':12},'series':[{'time':iso(now-timedelta(minutes=60-5*i)),'value':i} for i in range(13)]}}}
    primary={'observed_rain':{'status':'available','stations':[{'code':s,'observed_at':stamp,'rain_1h_mm':i,'rain_24h_mm':i+2} for i,s in enumerate(list(STATIONS)[:3])]},'recent_observations':[]}
    synth,_,detail=build(dash,primary,c,{},comp,comp['inmet'],{},stamp)
    assert synth['statistics']['rain_1h_mm']['station_count']==4
    dash['gauge_distribution']=gauge_distribution(primary['observed_rain'])
    home['observation_history.json']['records']=[{'source':'cemaden-rain','station':r['code'],'observed_at':stamp,'rain_1h_mm':r['rain_1h_mm'],'rain_24h_mm':r['rain_24h_mm']} for r in primary['observed_rain']['stations']]
    raw=campus_feed(stamp)
    for key,metric in c['metrics'].items():raw['metrics'][key].update(metric)
    home['campus_station.json']=raw
    dash.update(synthesis=synth,forecast=synth['selected_forecast'],forecast_series=detail['hourly'],forecast_comparison=comp,publication_at=stamp)
    dash['risk_classification']=classify(dash,detail,stamp);synth['risk_classification']=dash['risk_classification']
    ds=datasets();ds['data/dashboard.json']=dash;ds['data/latest.json']['generated_at']=stamp
    original=deepcopy(dash)
    calm_comp=deepcopy(comp)
    for record in calm_comp['records']:
        for row in record['hourly']:row.update(gust_kmh=20,wind_kmh=10)
    calm_c=deepcopy(c);calm_c['metrics']['wind_gust']['latest']['value']=20
    calm_synth,_,calm_detail=build(original,primary,calm_c,{},calm_comp,comp['inmet'],{},stamp)
    calm=deepcopy(original);calm.update(synthesis=calm_synth,forecast=calm_synth['selected_forecast'],forecast_series=calm_detail['hourly'])
    calm['risk_classification']=classify(calm,calm_detail,stamp);calm_synth['risk_classification']=calm['risk_classification']
    assert calm['risk_classification']['level']=='verde'
    qualitative=deepcopy(calm)
    qs,_,qd=build(qualitative,primary,calm_c,{}, {'records':[]},comp['inmet'],{},stamp)
    qualitative.update(synthesis=qs,forecast=qs['selected_forecast'],forecast_series=qd['hourly'])
    qualitative['risk_classification']=classify(qualitative,qd,stamp);qs['risk_classification']=qualitative['risk_classification']
    assert qualitative['risk_classification']['level']=='verde'
    recovered=deepcopy(calm)
    rs,_,rd=build(recovered,primary,calm_c,{}, {'records':[]},comp['inmet'],{},stamp,
                  forecast_archive=merge_archive(None,calm_comp))
    recovered.update(synthesis=rs,forecast=rs['selected_forecast'],forecast_series=rd['hourly'])
    recovered['risk_classification']=classify(recovered,rd,stamp);rs['risk_classification']=recovered['risk_classification']
    assert recovered['risk_classification']['level']=='verde'
    with sync_playwright() as p,server() as url:
        browser=p.chromium.launch(headless=True, executable_path=os.environ.get("WEATHER_BROWSER_PATH"))
        for width in (320,390,1440):
            dash.clear();dash.update(deepcopy(original))
            context=browser.new_context(viewport={'width':width,'height':1000})
            for name,payload in home.items():context.route('**/data/'+name,lambda route,request,payload=payload:route.fulfill(json=payload))
            for name,payload in ds.items():
                if name.removeprefix('data/') not in home:context.route('**/'+name,lambda route,request,payload=payload:route.fulfill(json=payload))
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url);page.locator('#forecast-brief').wait_for()
            assert 'chuva' in page.locator('#forecast-brief').inner_text().lower()
            assert 'ECMWF' in page.locator('#forecast-source').inner_text()
            assert page.locator('#forecast-value').inner_text()!='—'
            assert '3,0' in page.locator('#observed-value').inner_text()
            page.locator('#plot .station-bar').first.wait_for()
            assert page.locator('#plot .station-bar').count()==3
            assert page.locator('#campus-values').count()==0
            assert page.locator('.comparison-metric').count()==3
            assert page.locator('#level-title').inner_text()=='Atenção'
            assert page.locator('#weather-synthesis-home,#campus-station,#forecast-comparison,#memory').count()==0
            assert len(page.locator('#level-reason').inner_text())<180
            page.locator('#level-explain').click();assert page.locator('#detail-dialog').is_visible()
            assert 'Critério utilizado' in page.locator('#dialog-content').inner_text()
            assert 'Evidências atuais' in page.locator('#dialog-content').inner_text()
            page.locator('.risk-explanation-levels > summary').click()
            assert page.locator('.risk-explanation-levels h4').count()==6
            page.keyboard.press('Escape');assert not page.locator('#detail-dialog').is_visible()
            for theme in ('light','dark'):
                if theme=='dark':page.locator('#theme-toggle').click()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(OUTPUT/f'multisource-home-{theme}-{width}.png'),full_page=True)
            page.goto(url+'dados.html');page.locator('#weather-synthesis-detail .synthesis-daily').wait_for()
            assert 'INMET' in page.locator('#weather-synthesis-detail').inner_text()
            assert 'Classificação de risco' in page.locator('#weather-synthesis-detail').inner_text()
            assert '4 estações' in page.locator('#weather-synthesis-detail').inner_text()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(OUTPUT/f'multisource-details-{width}.png'),full_page=True)
            dash.clear();dash.update(deepcopy(calm))
            page.goto(url);page.get_by_role('heading',name='Normalidade',exact=True).wait_for()
            assert page.locator('#level-card').get_attribute('data-risk')=='verde'
            assert 'acompanhamento das condições' not in page.locator('#level-card').inner_text().lower()
            page.screenshot(path=str(OUTPUT/f'clear-normality-{width}.png'),full_page=True)
            dash.clear();dash.update(deepcopy(qualitative))
            page.goto(url);page.get_by_role('heading',name='Normalidade',exact=True).wait_for()
            assert 'previsão por turnos' in page.locator('#level-kind').inner_text()
            assert page.locator('#forecast-value').inner_text()=='—'
            assert page.locator('#forecast-brief').is_visible()
            page.locator('#level-explain').click();assert page.locator('#detail-dialog').is_visible()
            assert 'qualitativa' in page.locator('#dialog-content').inner_text()
            page.keyboard.press('Escape')
            page.goto(url+'dados.html');page.locator('#weather-synthesis-detail').get_by_role('heading',name='Normalidade',exact=True).wait_for()
            assert 'INMET diário/por turno' in page.locator('#weather-synthesis-detail').inner_text()
            dash.clear();dash.update(deepcopy(recovered))
            page.goto(url);page.get_by_role('heading',name='Normalidade',exact=True).wait_for()
            assert 'consulta anterior' in page.locator('#forecast-source').inner_text()
            assert page.locator('#forecast-value').inner_text()!='—'
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert not errors,errors;context.close()
        browser.close()
    print('Multisource browser checks passed: home/details, mobile/desktop, INMET, equal stations, fallback and themes.')


if __name__=='__main__':main()
