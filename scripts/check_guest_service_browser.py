"""Reception experience with real browser and isolated DB; no WhatsApp sending."""
import json,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,auth,guest_service
from scripts.http_fixture import ServerFixture
from playwright.sync_api import sync_playwright

def main():
    original=app.DB
    with tempfile.TemporaryDirectory() as tmp:
        app.DB=Path(tmp)/'test.sqlite3';app.init_db()
        auth.create_user(app.connection,dict(username='admin',name='Teste',role='admin',password='Initial-test-123'))
        auth.change_password(app.connection,'admin','Initial-test-123','Changed-test-123')
        app.handle_message(dict(message='Preciso de duas toalhas',session_id='browser-service',request_id='browser-service-001'))
        server=ServerFixture(app.application)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port);errors=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1366,'height':900})
                page.on('pageerror',lambda error:errors.append(str(error)))
                assert page.request.get(base+'/api/experience').status==401
                assert page.request.get(base+'/api/handoffs/thread/browser-service-001').status==401
                page.goto(base+'/login');page.locator('#username').fill('admin');page.locator('#password').fill('Changed-test-123')
                page.get_by_role('button',name='Entrar',exact=True).click();page.wait_for_url('**/recepcao')
                card=page.locator('article').filter(has_text='Preciso de duas toalhas');card.wait_for()
                assert 'Toalhas: 2' in card.inner_text()
                card.get_by_role('button',name='Assumir atendimento',exact=True).click()
                card.get_by_text('Responsável: admin',exact=True).wait_for()
                card.get_by_role('button',name='Ver conversa',exact=True).click()
                page.locator('#takeover').click();page.get_by_text('Conversa assumida. Hostess pausada.',exact=True).wait_for()
                reply=app.handle_message(dict(message='Pode conferir meu pedido?',session_id='browser-service',request_id='browser-service-002'))
                assert reply['suppress_response']
                page.locator('#thread-refresh').click();page.locator('#conversation-log').get_by_text('Hóspede: Pode conferir meu pedido?',exact=True).wait_for()
                page.locator('#staff-text').fill('Estou conferindo seu pedido com a governança.')
                page.wait_for_timeout(5500)
                assert page.locator('#staff-text').input_value()=='Estou conferindo seu pedido com a governança.'
                page.locator('#staff-send').click();page.get_by_text('Mensagem registrada no painel local.',exact=True).wait_for()
                assert guest_service.thread(app.connection,'browser-service-001')[-1]['role']=='staff'
                page.locator('#release-bot').click();page.get_by_text('Hostess liberada.',exact=True).wait_for()
                page.locator('#thread-close').click()
                card.get_by_role('button',name='Concluir atendimento',exact=True).click()
                card.get_by_text('Pedido do painel local: sem aviso pelo WhatsApp.',exact=True).wait_for()
                page.locator('#experience-metrics').get_by_text('Concluídos pela equipe: 1',exact=False).wait_for()
                page.screenshot(path=str(app.ROOT/'runtime/guest-service-browser.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.goto(base+'/politicas');page.locator('#readiness').get_by_text('Revisão prioritária para uso real:',exact=False).wait_for()
                assert not errors,errors
                browser.close()
        finally:server.shutdown();thread.join();server.server_close();app.DB=original
    report=dict(passed=True,isolated_database=True,real_browser=True,towel_quantity=True,human_takeover=True,staff_reply=True,draft_preserved=True,release=True,completion=True,metrics=True,mobile_overflow=False,whatsapp_sent=False,console_errors=errors)
    (app.ROOT/'runtime/guest-service-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
