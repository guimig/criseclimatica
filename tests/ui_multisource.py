"""Real browser: equal local stations, daily INMET and hourly fallback."""
import json
import os
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from ui_dashboard import fixture, server, OUTPUT
from ui_details import datasets
from ui_forecasts import comparison_fixture
from observatorio.multisource import build, STATIONS


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
    dash.update(synthesis=synth,forecast=synth['selected_forecast'],forecast_series=detail['hourly'],forecast_comparison=comp,publication_at=stamp)
    ds=datasets();ds['data/dashboard.json']=dash;ds['data/latest.json']['generated_at']=stamp
    with sync_playwright() as p,server() as url:
        browser=p.chromium.launch(headless=True, executable_path=os.environ.get("WEATHER_BROWSER_PATH"))
        for width in (390,1440):
            context=browser.new_context(viewport={'width':width,'height':1000})
            for name,payload in home.items():context.route('**/data/'+name,lambda route,payload=payload:route.fulfill(json=payload))
            for name,payload in ds.items():
                if name not in ('data/dashboard.json','data/latest.json'):context.route('**/'+name,lambda route,payload=payload:route.fulfill(json=payload))
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url);page.locator('#weather-synthesis-home .synthesis-daily').wait_for()
            assert 'INMET' in page.locator('#weather-synthesis-home').inner_text()
            assert 'ECMWF' in page.locator('#forecast-note').inner_text()
            assert page.locator('#forecast-value').inner_text()!='—'
            assert page.locator('#weather-synthesis-home .synthesis-item').count()==3
            assert 'vento' in page.locator('#level-title').inner_text().lower()
            page.get_by_role('button',name='Por que esta leitura?').click()
            assert 'Pesos iguais' in page.get_by_role('dialog').inner_text()
            assert '4 estações' in page.get_by_role('dialog').inner_text()
            page.keyboard.press('Escape')
            for theme in ('light','dark'):
                if theme=='dark':page.locator('#theme-toggle').click()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(OUTPUT/f'multisource-home-{theme}-{width}.png'),full_page=True)
            page.goto(url+'dados.html');page.locator('#weather-synthesis-detail .synthesis-daily').wait_for()
            assert 'INMET' in page.locator('#weather-synthesis-detail').inner_text()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(OUTPUT/f'multisource-details-{width}.png'),full_page=True)
            assert not errors,errors;context.close()
        browser.close()
    print('Multisource browser checks passed: home/details, mobile/desktop, INMET, equal stations, fallback and themes.')


if __name__=='__main__':main()
