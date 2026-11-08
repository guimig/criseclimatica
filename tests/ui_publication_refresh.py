"""Real browser regression for automatic refresh and transient outages."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from ui_dashboard import fixture, server
from ui_details import datasets
from ui_forecasts import comparison_fixture


def main():
    from playwright.sync_api import sync_playwright
    data=fixture();offline=False;counts={}
    def route(request):
        name=request.request.url.split('/')[-1].split('?')[0]
        counts[name]=counts.get(name,0)+1
        if offline and name=='latest.json':
            request.abort('internetdisconnected');return
        request.fulfill(content_type='application/json',body=json.dumps(data[name]))
    with server() as url,sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':390,'height':844})
        page.clock.install(time=datetime.now(timezone.utc))
        page.route('**/data/*.json*',route)
        page.goto(url)
        page.wait_for_function("document.getElementById('forecast-value').textContent.includes('18,0')")
        initial=counts.get('dashboard.json',0)
        page.clock.fast_forward(61000)
        page.wait_for_function('!panel.loading')
        assert counts.get('dashboard.json',0)==initial
        stamp=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat().replace('+00:00','Z')
        for name in data:data[name]['generated_at']=stamp
        data['dashboard.json']['forecast']['rain']['total_mm']=23
        page.locator('#chart-range').select_option('72')
        page.clock.fast_forward(61000)
        page.wait_for_function("document.getElementById('forecast-value').textContent.includes('23,0')")
        assert page.locator('#chart-range').input_value()=='72'
        offline=True
        page.clock.fast_forward(61000)
        page.wait_for_function("document.getElementById('publication-status').textContent.includes('Falha')")
        assert '23,0' in page.locator('#forecast-value').inner_text()
        # Manual refresh also preserves the previous publication during failure.
        page.locator('#refresh').click()
        page.wait_for_function('!panel.loading')
        assert '23,0' in page.locator('#forecast-value').inner_text()
        offline=False
        page.clock.fast_forward(61000)
        page.wait_for_function("document.getElementById('publication-status').hidden")
        # The detailed multi-model comparison has an independent loader. It
        # must follow publication changes too, retaining the chosen controls.
        details=datasets();comp=comparison_fixture(details['data/latest.json']['generated_at'])
        details['data/forecast_comparison.json']=comp
        context=browser.new_context(viewport={'width':1440,'height':1000})
        def detailed_route(request):
            key='data/'+request.request.url.split('/data/')[-1].split('?')[0]
            request.fulfill(content_type='application/json',body=json.dumps(details.get(key,{})))
        context.route('**/data/**',detailed_route)
        detail=context.new_page();detail.clock.install(time=datetime.now(timezone.utc))
        detail.goto(url+'dados.html#model-comparison');detail.locator('#model-comparison svg').wait_for()
        detail.get_by_label('Variável da comparação',exact=True).select_option('gust_kmh')
        detail.get_by_label('Período da comparação',exact=True).select_option('72')
        newer=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat().replace('+00:00','Z')
        details['data/latest.json']['generated_at']=newer
        replacement=comparison_fixture(newer);replacement['cptec']['locality']='Araquari · nova publicação'
        details['data/forecast_comparison.json']=replacement
        detail.clock.fast_forward(61000)
        detail.wait_for_function("document.getElementById('model-comparison').textContent.includes('Araquari · nova publicação')")
        assert detail.get_by_label('Variável da comparação',exact=True).input_value()=='gust_kmh'
        assert detail.get_by_label('Período da comparação',exact=True).input_value()=='72'
        # A malformed comparison response cannot erase the valid comparison.
        details['data/latest.json']['generated_at']=(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat().replace('+00:00','Z')
        details['data/forecast_comparison.json']={**replacement,'windows':None}
        detail.clock.fast_forward(61000)
        detail.wait_for_function("document.getElementById('model-comparison').textContent.includes('última leitura preservada')")
        assert detail.locator('#model-comparison svg').count()==1
        assert detail.get_by_label('Período da comparação',exact=True).input_value()=='72'
        context.close()
        browser.close()
    print('Automatic publication refresh passed: minute polling, home and detailed comparison versions, stable selections, failed/malformed request preservation and reconnection.')


if __name__=='__main__':main()
