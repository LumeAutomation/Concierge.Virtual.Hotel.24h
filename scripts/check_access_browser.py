"""Real browser checks on an isolated database; no WhatsApp sends."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import auth
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def main():
    original=app.DB
    with tempfile.TemporaryDirectory() as tmp:
        app.DB=Path(tmp)/'browser.sqlite3';app.init_db()
        auth.create_user(app.connection,dict(username='admin',name='Admin Teste',role='admin',password='Initial-browser-123'))
        app.handle_message(dict(message='Quero toalhas',request_id='browser-ticket-123'))
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port);errors=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1366,'height':900})
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/recepcao');page.wait_for_url('**/login')
                page.locator('#username').fill('admin');page.locator('#password').fill('Initial-browser-123')
                page.get_by_role('button',name='Entrar',exact=True).click()
                page.locator('#change').wait_for(state='visible')
                page.locator('#old').fill('Initial-browser-123');page.locator('#new').fill('Changed-browser-456');page.locator('#confirm').fill('Changed-browser-456')
                page.get_by_role('button',name='Salvar nova senha').click()
                page.locator('#login').wait_for(state='visible')
                page.locator('#password').fill('Changed-browser-456');page.get_by_role('button',name='Entrar',exact=True).click()
                page.wait_for_url('**/recepcao');page.locator('.ticket').wait_for()
                assert page.locator('#operator').input_value()=='admin'
                assert page.locator('#operator').get_attribute('readonly') is not None
                page.get_by_role('button',name='Assumir atendimento').click()
                page.get_by_role('button',name='Concluir atendimento').click()
                page.get_by_text('Pedido do painel local: sem aviso pelo WhatsApp.',exact=True).wait_for()
                page.get_by_role('link',name='Equipe e piloto').click()
                page.locator('#userform [name=username]').fill('editor')
                page.locator('#userform [name=name]').fill('Editor Teste')
                page.locator('#userform [name=role]').select_option('editor')
                page.locator('#userform [name=password]').fill('Editor-initial-123')
                page.get_by_role('button',name='Criar acesso').click()
                page.locator('#users').get_by_text('Editor Teste',exact=False).wait_for()
                page.locator('#contactform [name=label]').fill('Participante ficticio')
                page.locator('#contactform [name=identifier]').fill('5511000000000')
                page.get_by_role('button',name='Autorizar contato').click()
                page.locator('#contacts').get_by_role('button',name='Desativar').wait_for()
                page.locator('#contacts').get_by_role('button',name='Desativar').click()
                page.locator('#contacts').get_by_role('button',name='Reativar').wait_for()
                page.screenshot(path=str(ROOT/'runtime/access-team-browser.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                for route in ['/equipe','/recepcao','/politicas','/login']:
                    page.goto(base+route)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),route
                page.goto(base+'/equipe');page.get_by_role('button',name='Sair',exact=True).click();page.wait_for_url('**/login')
                page.locator('#username').fill('editor');page.locator('#password').fill('Editor-initial-123');page.get_by_role('button',name='Entrar',exact=True).click()
                page.locator('#change').wait_for(state='visible')
                page.locator('#old').fill('Editor-initial-123');page.locator('#new').fill('Editor-changed-456');page.locator('#confirm').fill('Editor-changed-456')
                page.get_by_role('button',name='Salvar nova senha').click();page.locator('#login').wait_for(state='visible')
                page.locator('#password').fill('Editor-changed-456');page.get_by_role('button',name='Entrar',exact=True).click();page.wait_for_url('**/politicas')
                page.locator('#editor').wait_for(state='visible')
                assert not page.locator('#approve').is_visible()
                assert not page.get_by_role('link',name='Recepção',exact=True).is_visible()
                page.locator('#content').fill('Politica ficticia revisada no teste isolado.')
                page.get_by_role('button',name='Salvar rascunho').click()
                page.get_by_text('Rascunho salvo. As respostas continuam usando o texto anterior.',exact=True).wait_for()
                assert page.request.get(base+'/api/users').status==403
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join();app.DB=original
    report=dict(passed=True,real_browser=True,isolated_database=True,first_password_change=True,staff_identity=True,role_permissions=True,pilot_contacts=True,mobile_overflow=False,whatsapp_sent=False,console_errors=errors)
    (ROOT/'runtime/access-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
