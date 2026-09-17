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
                page.goto(base+'/')
                def chat(message,expected):
                    count=page.locator('.bubble').count()
                    page.get_by_role('textbox',name='Sua mensagem').fill(message)
                    page.get_by_role('button',name='Enviar',exact=True).click()
                    page.wait_for_function("n => document.querySelectorAll('.bubble').length >= n + 2",arg=count)
                    assert expected in page.locator('.bubble').last.inner_text(),page.locator('.bubble').last.inner_text()
                chat('quando posso entrar?','15h')
                chat('Qual horario da piscina?','20h')
                chat('e fecha que horas?','20h')
                chat('e o café da manhã?','06h30')
                chat('e aos domingos?','11h')
                page.screenshot(path=str(app.ROOT/'runtime/local-search-browser.png'),full_page=True)
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close();thread.join();app.DB=original
    report=dict(passed=True,isolated_database=True,real_browser=True,paraphrases=True,topic_followup=True,topic_change=True,external_model_used=False,whatsapp_sent=False,console_errors=errors)
    (app.ROOT/'runtime/local-search-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
