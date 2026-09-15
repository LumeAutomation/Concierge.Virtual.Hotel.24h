import sys,tempfile,threading,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,conversation_state
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    app.DB=Path(tmp)/'ui.sqlite3';app.init_db()
    for tag in ['success','timeout']:
        app.handle_message(dict(message='Quero toalhas teste '+tag,request_id='reception-ui-'+tag,session_id='waha_5500000000000_c_us'))
    server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with patch.object(conversation_state,'send_waha',side_effect=['fake-provider-id',TimeoutError()]) as transport:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1280,'height':900});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/recepcao')
            page.locator('#operator').fill('QA recepcao')
            for tag,expected in [('success','Aviso aceito pelo WhatsApp.'),('timeout','Envio n')]:
                card=page.locator('article').filter(has_text='Quero toalhas teste '+tag)
                card.get_by_role('button',name='Assumir atendimento').click()
                card.get_by_role('button',name='Concluir e avisar no WhatsApp').click()
                card.get_by_text(expected,exact=tag=='success').wait_for()
            page.reload();page.locator('article').filter(has_text='Quero toalhas teste success').get_by_text('Aviso aceito pelo WhatsApp.',exact=True).wait_for()
            assert page.get_by_role('button',name='Concluir e avisar no WhatsApp').count()==0
            assert transport.call_count==2
            page.screenshot(path='runtime/reception-flow.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors,errors
            browser.close()
    server.shutdown();server.server_close()
Path('runtime/reception-browser-results.json').write_text(json.dumps({'passed':True,'real_browser':True,'transport':'simulated','real_whatsapp_sent':False,'tested':['claim','complete','success','timeout','reload','mobile']}),encoding='utf-8')
print('Recepcao: navegador real, conclusao, envio simulado e timeout validados.')
