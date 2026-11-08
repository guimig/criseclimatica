"""Real browser regression for automatic refresh and transient outages."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from ui_dashboard import fixture, server


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
        browser.close()
    print('Automatic publication refresh passed: minute polling, new publication, stable chart selection, failed request preservation and reconnection.')


if __name__=='__main__':main()
