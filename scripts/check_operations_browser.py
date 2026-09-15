import json
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1366,'height':900});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    base='http://127.0.0.1:8787'
    page.goto(base+'/operacao');page.get_by_text('Todos os sinais estão normais.',exact=True).wait_for(timeout=30000)
    assert page.locator('.card').count()==6
    state=page.request.get(base+'/api/operations').json()
    assert all(item['status']=='ok' for item in state['services'].values())
    assert state['backup']['verified'] and state['backup']['fresh']
    page.screenshot(path='runtime/operations-dashboard.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    for route in ['/operacao','/politicas','/recepcao']:
        page.goto(base+route)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),route
    assert not errors,errors
    browser.close()
Path('runtime/operations-live-results.json').write_text(json.dumps({'passed':True,'real_browser':True,'all_services_healthy':True,'backup_verified':True,'mobile_overflow':False,'console_errors':errors},indent=2),encoding='utf-8')
print('Painel real validado: seis sinais normais, backup verificado e tela adaptada ao celular.')
