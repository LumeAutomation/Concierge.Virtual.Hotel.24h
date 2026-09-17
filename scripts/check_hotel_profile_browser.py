"""Validate hotel setup and portable template in a real browser, isolated database."""
import json,sys,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,auth
from playwright.sync_api import sync_playwright

def main():
    original=app.DB
    with tempfile.TemporaryDirectory() as tmp:
        app.DB=Path(tmp)/'hotel.sqlite3';app.init_db()
        for username,role in [('admin','admin'),('front','recepcao')]:
            auth.create_user(app.connection,dict(username=username,name='Teste '+username,role=role,password='Initial-test-123'))
            auth.change_password(app.connection,username,'Initial-test-123','Changed-test-123')
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port);errors=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
                page.on('pageerror',lambda error:errors.append(str(error)))
                assert page.request.get(base+'/api/hotel/template').status==401
                public=page.request.get(base+'/api/hotel/public').json();assert public['hotel_name']=='Hotel Aura'
                page.goto(base+'/login');page.locator('#username').fill('front');page.locator('#password').fill('Changed-test-123');page.get_by_role('button',name='Entrar',exact=True).click();page.wait_for_url('**/recepcao')
                assert page.request.get(base+'/api/hotel').status==403
                assert page.request.post(base+'/api/hotel',data={}).status==403
                page.request.post(base+'/api/auth/logout',data={})
                page.goto(base+'/login');page.locator('#username').fill('admin');page.locator('#password').fill('Changed-test-123');page.get_by_role('button',name='Entrar',exact=True).click();page.wait_for_url('**/recepcao')
                page.get_by_role('link',name='Meu hotel',exact=True).click();page.locator('#catalog details').first.wait_for()
                assert page.locator('#catalog details').count()==9
                page.locator('#hotel_name').fill('Resort Mar & Sol');page.locator('#assistant_name').fill('Lia');page.locator('#primary_color').fill('#204a70')
                page.get_by_role('button',name='Salvar identidade',exact=True).click()
                page.get_by_text('Identidade salva.',exact=False).wait_for()
                page.reload();page.locator('#hero-name').get_by_text('Resort Mar & Sol',exact=True).wait_for()
                assert page.locator('header b').inner_text()=='Resort Mar & Sol'
                reply=page.request.post(base+'/api/chat',data=dict(message='oi',request_id='hotel-browser-001',session_id='hotel-browser')).json()
                assert 'Lia' in reply['reply'] and 'Resort Mar & Sol' in reply['reply'] and '{{' not in reply['reply']
                with page.expect_download() as info:page.locator('#export-template').click()
                download=info.value;path=Path(tmp)/'modelo.json';download.save_as(path)
                package=json.loads(path.read_text(encoding='utf-8'));assert package['profile']['hotel_name']=='Resort Mar & Sol'
                assert len(package['policies'])==101 and 'hotel-browser-001' not in path.read_text(encoding='utf-8')
                page.screenshot(path=str(app.ROOT/'runtime/hotel-profile-browser.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors,errors;browser.close()
        finally:server.shutdown();server.server_close();thread.join();app.DB=original
    report=dict(passed=True,isolated_database=True,real_browser=True,role_permissions=True,branding=True,chat_identity=True,template_download=True,policy_count=101,mobile_overflow=False,whatsapp_sent=False,console_errors=errors)
    (app.ROOT/'runtime/hotel-profile-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
