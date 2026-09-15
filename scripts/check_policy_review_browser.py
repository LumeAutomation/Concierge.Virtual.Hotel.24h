import sys,tempfile,threading,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,knowledge_engine
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright

with tempfile.TemporaryDirectory() as tmp:
    app.DB=Path(tmp)/'review.sqlite3';app.init_db()
    before=knowledge_engine.load_base()[1]
    server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1366,'height':950});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            base=f'http://127.0.0.1:{server.server_port}'
            page.goto(base+'/politicas');page.locator('#summary').filter(has_text='100 políticas').wait_for()
            page.locator('#search').fill('POL-08');page.locator('#list button').click()
            page.locator('#actor').fill('Revisor QA')
            original=page.locator('#effective-content').inner_text()
            text='Cafe da manha de teste: aos domingos das 07h as 12h. A inclusao depende da tarifa.'
            page.locator('#content').fill(text)
            assert page.locator('#approve').is_disabled()
            page.locator('#save').click();page.locator('#feedback').filter(has_text='Rascunho salvo').wait_for()
            assert page.locator('#effective-content').inner_text()==original
            assert knowledge_engine.load_base()[1]==before
            page.reload();page.locator('#search').fill('POL-08');page.locator('#list button').click()
            assert page.locator('#content').input_value()==text
            page.locator('#approve').click();page.locator('#feedback').filter(has_text='Política aprovada').wait_for()
            assert page.locator('#effective-content').inner_text()==text
            response=page.request.post(base+'/api/chat',data={'message':'Qual horario do cafe da manha?','request_id':'policy-browser-test','session_id':'review-test'}).json()
            assert response['reply']==text
            page.locator('#content').fill('Outro rascunho pendente de aprovacao.')
            page.locator('#save').click();page.locator('#feedback').filter(has_text='Rascunho salvo').wait_for()
            assert page.locator('#effective-content').inner_text()==text
            page.screenshot(path='runtime/policy-review-browser.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.request.post(base+'/api/policies',data={},headers={'Origin':'https://example.com'}).status==403
            assert not errors,errors
            browser.close()
    finally:server.shutdown();server.server_close()
Path('runtime/policy-review-browser-results.json').write_text(json.dumps({'passed':True,'isolated_database':True,'policies':100,'flow':['edit','save_draft','reload','approve','answer_uses_approved','new_draft_preserves_live'],'real_policies_approved':False}),encoding='utf-8')
print('Politicas: edicao, rascunho, aprovacao e resposta validados no navegador.')
