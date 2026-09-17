"""Validate hotel setup and portable template in a real browser, isolated database."""
import json,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,auth
from scripts.http_fixture import ServerFixture
from playwright.sync_api import sync_playwright

def main():
    original=app.DB
    with tempfile.TemporaryDirectory() as tmp:
        app.DB=Path(tmp)/'hotel.sqlite3';app.init_db()
        for username,role in [('admin','admin'),('front','recepcao')]:
            auth.create_user(app.connection,dict(username=username,name='Teste '+username,role=role,password='Initial-test-123'))
            auth.change_password(app.connection,username,'Initial-test-123','Changed-test-123')
        server=ServerFixture(app.application)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port);errors=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
                page.on('pageerror',lambda error:errors.append(str(error)))
                assert page.request.get(base+'/api/operating-mode').status==401
                page.goto(base+'/login');page.locator('#username').fill('admin');page.locator('#password').fill('Changed-test-123');page.get_by_role('button',name='Entrar',exact=True).click();page.wait_for_url('**/recepcao')
                page.goto(base+'/hotel');page.locator('#mode-state').get_by_text('Demonstração',exact=False).wait_for()
                page.locator('#operating-mode').select_option('production');page.locator('#save-mode').click()
                page.get_by_text('Modo salvo.',exact=False).wait_for()
                page.reload();page.locator('#mode-state').get_by_text('Produção',exact=False).wait_for()
                result=page.request.post(base+'/api/chat',data=dict(message='Qual horario do cafe da manha?',request_id='browser-prod-before-01')).json()
                assert result['route']=='HUMAN_HANDOFF' and result['sources']==[] and '06h30' not in result['reply']
                rows=page.request.get(base+'/api/policies').json();row=next(r for r in rows if r['id']=='POL-08')
                saved=page.request.post(base+'/api/policies',data=dict(action='save',id='POL-08',revision=row['revision'],draft={**row['draft'],'content':'O café da manhã funciona das 07h às 10h.'})).json()
                assert page.request.post(base+'/api/policies',data=dict(action='approve',id='POL-08',revision=saved['revision'])).ok
                page.goto(base+'/politicas');page.locator('.item').filter(has_text='POL-08 ·').click()
                page.on('dialog',lambda d:d.accept())
                page.locator('#approve-production').click();page.get_by_text('Revisão validada para produção.',exact=False).wait_for()
                result=page.request.post(base+'/api/chat',data=dict(message='Qual horario do cafe da manha?',request_id='browser-prod-after-01')).json()
                assert result['policy_ids']==['POL-08'] and '07h' in result['reply'] and '06h30' not in result['reply']
                page.screenshot(path=str(app.ROOT/'runtime/production-mode-browser.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors,errors;browser.close()
        finally:server.shutdown();thread.join();server.server_close();app.DB=original
    report=dict(passed=True,isolated_database=True,real_browser=True,mode_persisted=True,empty_production_handoff=True,explicit_revision_approval=True,approved_content_answered=True,mobile_overflow=False,whatsapp_sent=False,console_errors=errors)
    (app.ROOT/'runtime/production-mode-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
