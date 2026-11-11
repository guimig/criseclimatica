"""Real Chromium tests for the isolated campus source on both pages."""
from datetime import datetime, timedelta, timezone
import json
from ui_dashboard import fixture, server, OUTPUT
from ui_details import datasets
from ui_style_system import check_style_system


def campus_feed(stamp):
    now = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    iso = lambda t:t.isoformat().replace('+00:00','Z')
    definitions = {'temperature':('°C',20,'AVG'), 'humidity':('%',75,'AVG'), 'pressure':('hPa',1005,'AVG'),
                   'rain_daily':('mm',31.01,'MAX'), 'rain_intensity':('mm/h',0,'MAX'),
                   'wind_avg':('km/h',2,'AVG'), 'wind_gust':('km/h',5,'MAX'), 'wind_direction_deg':('°',337,None)}
    metrics = {key:{'unit':unit,'latest':{'time':stamp,'value':value},'aggregation':agg,
                    'series':[{'time':iso(now-timedelta(minutes=i*5)),'value':value+i/10} for i in reversed(range(12))] if agg else []}
               for key,(unit,value,agg) in definitions.items()}
    return {'schema_version':1,'kind':'ifc_araquari_campus_observations_not_risk_criteria','risk_criteria':False,'location_id':'araquari',
            'publication_at':stamp,'checked_at':stamp,'window_start':iso(now-timedelta(days=1)),'window_end':stamp,'status':'available','metrics':metrics}


def main():
    from playwright.sync_api import sync_playwright
    home=fixture();detail=datasets();stamp=home['latest.json']['generated_at'];feed=campus_feed(stamp)
    # Keep one identity for the campus artifact and the detail manifest.
    with server() as url,sync_playwright() as playwright:
        browser=playwright.chromium.launch();OUTPUT.mkdir(exist_ok=True)
        for page_name in ('dados.html',):
            for width,height,theme in [(1440,1100,'light'),(390,844,'dark'),(320,900,'light')]:
                context=browser.new_context(viewport={'width':width,'height':height},color_scheme=theme)
                data=home.copy() if page_name=='index.html' else {k.removeprefix('data/'):v for k,v in detail.items()}
                version=data['latest.json']['generated_at'];data['campus_station.json']=campus_feed(version)
                context.route('**/data/**',lambda route:route.fulfill(content_type='application/json',body=json.dumps(data.get(route.request.url.split('/data/')[-1].split('?')[0],{}))))
                page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url+page_name)
                if page_name=='dados.html':page.get_by_role('tab',name='Medições',exact=True).click()
                page.locator('#campus-values strong').first.wait_for()
                page.locator('#campus-station').scroll_into_view_if_needed()
                assert '31,01 mm' in page.locator('#campus-values').inner_text()
                assert page.locator('#campus-plot svg').is_visible()
                page.locator('#campus-variable').select_option('rain_daily')
                assert 'Não é chuva das últimas 24 h' in page.locator('#campus-chart-note').inner_text()
                plot=page.locator('#campus-plot svg');plot.focus();page.keyboard.press('Home')
                first=page.locator('#campus-readout').inner_text();page.keyboard.press('End')
                assert first != page.locator('#campus-readout').inner_text()
                assert '31,01 mm' in page.locator('#campus-readout').inner_text()
                plot.hover();assert len(page.locator('#campus-readout').inner_text())<90
                check_style_system(page)
                assert not errors,errors
                page.screenshot(path=str(OUTPUT/f'campus-{page_name}-{width}-{theme}.png'))
                # Expired observations retain their original time and are explicit.
                old=campus_feed(version)
                for metric in old['metrics'].values():metric['latest']['time']=(datetime.now(timezone.utc)-timedelta(hours=4)).isoformat()
                data['campus_station.json']=old
                page.evaluate("document.getElementById('refresh')?.click() || document.getElementById('reload')?.click()")
                page.wait_for_function("document.getElementById('campus-values').textContent.includes('leitura antiga')")
                context.close()
        browser.close()
    print('Campus station: both pages, three viewports, themes, graph keyboard/hover and stale readings passed.')

if __name__=='__main__':main()
