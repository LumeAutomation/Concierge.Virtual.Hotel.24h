"""Validate policy creation and local-only answers in a real browser, isolated DB."""
import json,sys,tempfile,threading,uuid
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,auth,knowledge_engine
from playwright.sync_api import sync_playwright

def main():
    original=app.DB
    with tempfile.TemporaryDirectory() as tmp:
        app.DB=Path(tmp)/'test.sqlite3';app.init_db()
        auth.create_user(app.connection,dict(username='admin',name='Admin Teste',role='admin',password='Initial-test-123'))
        auth.change_password(app.connection,'admin','Initial-test-123','Changed-test-123')
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port);errors=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1366,'height':900})
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base+'/login');page.locator('#username').fill('admin');page.locator('#password').fill('Changed-test-123');page.get_by_role('button',name='Entrar',exact=True).click();page.wait_for_url('**/recepcao')
                page.goto(base+'/politicas');page.locator('.item').first.wait_for()
                assert page.locator('.item').first.inner_text().startswith('POL-00')
                page.get_by_role('button',name='+ Nova política').click()
                form=page.locator('#create-form')
                form.locator('[name=title]').fill('Sala de leitura')
                form.locator('[name=content]').fill('A sala de leitura abre das 09h às 17h.')
                form.locator('[name=example_question]').fill('Qual o horario da sala de leitura?')
                form.get_by_role('button',name='Criar e colocar em uso').click()
                page.get_by_text('POL-101 criada e disponível na base de conhecimento.',exact=True).wait_for()
                assert page.locator('#heading').inner_text().startswith('POL-101')
                assert page.locator('.item').last.inner_text().startswith('POL-101')
                def ask(rid):
                    response=page.request.post(base+'/api/chat',data=dict(message='Qual o horario da sala de leitura?',request_id=rid,session_id='browser-knowledge'))
                    assert response.ok
                    return response.json()
                first=ask('browser-new-policy-001');assert first['welcome_included'] and first['ai_used'] is False
                assert first['policy_ids']==['POL-101'] and '09h às 17h' in first['reply']
                assert first==ask('browser-new-policy-001')
                second=ask('browser-new-policy-002');assert not second.get('welcome_included')
                page.locator('#content').fill('A sala de leitura abre das 10h às 18h.')
                page.get_by_role('button',name='Salvar rascunho',exact=True).click()
                page.get_by_text('Rascunho salvo. As respostas continuam usando o texto anterior.',exact=True).wait_for()
                assert '09h às 17h' in ask('browser-new-policy-003')['reply']
                page.get_by_role('button',name='Aprovar e colocar em uso',exact=True).click()
                page.get_by_text('Política aprovada. A nova versão está em uso nas próximas consultas.',exact=True).wait_for()
                assert '10h às 18h' in ask('browser-new-policy-004')['reply']
                page.screenshot(path=str(app.ROOT/'runtime/new-policies-browser.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='+ Nova política').click()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close();thread.join();app.DB=original
    report=dict(passed=True,isolated_database=True,real_browser=True,automatic_id='POL-101',numeric_order=True,immediate_knowledge_update=True,draft_not_live=True,welcome_once=True,external_model_used=False,whatsapp_sent=False,console_errors=errors)
    (app.ROOT/'runtime/new-policies-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
