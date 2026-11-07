"""Browser regression for multi-model attribution, controls and mobile text."""
import json
from datetime import datetime, timedelta, timezone
from ui_dashboard import fixture, server, OUTPUT
from ui_details import datasets
from observatorio.forecast_comparison import summarize


def comparison_fixture(stamp):
    now=datetime.fromisoformat(stamp.replace('Z','+00:00'));start=now.replace(minute=0,second=0,microsecond=0)
    iso=lambda t:t.isoformat().replace('+00:00','Z')
    def rows(multiplier):
        return [{'time':iso(start+timedelta(hours=i)),'precipitation_mm':round((i%5)*multiplier,1),
                 'temperature_c':22+i%8,'wind_kmh':15+i%7,'gust_kmh':30+i%20} for i in range(169)]
    detail={'location':{'id':'araquari','latitude':-26.37,'longitude':-48.72},'current':{'time':iso(start)},'collected_at':stamp,'hourly':rows(.3)}
    alternatives=[{'id':model,'name':name,'status':'available','collected_at':stamp,'hourly':rows(multiplier)}
                  for model,name,multiplier in [('ecmwf_ifs025','ECMWF IFS',.6),('ncep_gfs_global','NOAA GFS',.9)]]
    cp={'checked_at':stamp,'locations':[{'location_id':'araquari','status':'available','nearest_cptec_locality':'Araquari','updated_day':now.date().isoformat(),
                                      'days':[{'day':now.date().isoformat(),'minimum_c':21,'maximum_c':29}]}]}
    return summarize(detail,alternatives,cp,stamp)


def main():
    from playwright.sync_api import sync_playwright
    home=fixture();comp=comparison_fixture(home['dashboard.json']['generated_at']);home['dashboard.json']['forecast_comparison']=comp
    details=datasets();details['data/forecast_comparison.json']=comp
    details['data/latest.json']['generated_at']=comp['generated_at']
    OUTPUT.mkdir(exist_ok=True)
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width in (320,390,768,1440):
            context=browser.new_context(viewport={'width':width,'height':1000})
            def route(r):
                path=r.request.url.split('/data/')[-1].split('?')[0]
                data=home.get(path) if '/dados.html' not in (r.request.headers.get('referer') or '') else details.get('data/'+path)
                if path=='forecast_comparison.json':data=comp
                r.fulfill(content_type='application/json',body=json.dumps(data or {}))
            context.route('**/data/**',route)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(url);page.locator('.forecast-comparison-card summary').click();page.locator('.comparison-range').first.wait_for()
                page.locator('.station-filter summary').click()
                for theme in ('light','dark'):
                    if theme=='dark':page.locator('#theme-toggle').click()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Home overflow {width}'
                    for selector in ['#chart-range','#station-select','#rain-window','#observed-variable']:
                        box=page.locator(selector).bounding_box();assert box['height']>=44,(width,selector,box)
                    # Every common control belongs above both plot cards, not on top of a chart.
                    bottom=page.locator('.period-controls').bounding_box()
                    for selector in ['#observed-panel','#forecast-panel']:
                        box=page.locator(selector).bounding_box();assert box['y']>=bottom['y']+bottom['height']
                    assert page.locator('[data-mode]').count()==0
                    assert page.locator('#chart-range').is_visible()
                    if width<620:
                        for selector in ['.level-reason','.coverage-copy','.weather-panel .chart-caption']:
                            assert page.locator(selector).first.evaluate('el=>parseFloat(getComputedStyle(el).fontSize)')>=14,selector
                    page.screenshot(path=str(OUTPUT/f'comparison-home-{theme}-{width}.png'),full_page=True)
                page.goto(url+'dados.html#model-comparison');page.locator('#model-comparison svg').wait_for()
                if page.locator('html').get_attribute('data-theme')=='dark':page.locator('#theme-toggle').click()
                assert page.get_by_role('tab',name='Previsões',exact=True).get_attribute('aria-selected')=='true'
                assert 'principal provisória' in page.locator('#model-comparison').inner_text()
                assert 'fora das faixas numéricas' in page.locator('#model-comparison').inner_text()
                for field in ['temperature_c','gust_kmh','precipitation_mm']:
                    page.get_by_label('Variável da comparação',exact=True).select_option(field)
                    page.get_by_label('Período da comparação',exact=True).select_option('72')
                    page.locator('#model-comparison svg').focus();page.keyboard.press('Home')
                    assert page.locator('.comparison-tooltip').is_visible()
                    assert 'ECMWF' in page.locator('.comparison-tooltip').inner_text()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Details overflow {width}'
                page.screenshot(path=str(OUTPUT/f'comparison-details-light-{width}.png'),full_page=True)
                page.locator('#theme-toggle').click();page.screenshot(path=str(OUTPUT/f'comparison-details-dark-{width}.png'),full_page=True)
                assert not errors,errors
            except Exception:
                page.screenshot(path=str(OUTPUT/f'comparison-failure-{width}.png'),full_page=True);raise
            finally:context.close()
        browser.close()
    print('Forecast comparison UX passed: 320/390/768/1440px, models, hours, keyboard, themes, control placement and mobile text.')

if __name__=='__main__':main()
