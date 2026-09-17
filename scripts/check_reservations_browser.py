"""Jornada de reservas no navegador e banco isolados; sem envio WhatsApp."""
import json
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import auth
import reservations
import conversation_state
import policy_review
from scripts.http_fixture import ServerFixture
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]

def main():
    original=app.DB
    errors=[]
    with tempfile.TemporaryDirectory() as tmp:
        app.DB=Path(tmp)/'browser.sqlite3';app.init_db()
        auth.create_user(app.connection,dict(username='front',name='Recepcao Teste',role='recepcao',password='Reservation-browser-123'))
        with app.connection() as db:db.execute('UPDATE staff_users SET must_change=0')
        server=ServerFixture(app.application)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with patch.object(reservations,'bot_phone',return_value='5524999999999'),patch.object(conversation_state,'send_waha',return_value='browser-fake-welcome'),sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                context=browser.new_context(viewport={'width':1440,'height':1000},locale='en-US',permissions=['clipboard-read','clipboard-write'])
                page=context.new_page()
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base+'/reservas');page.wait_for_url('**/login')
                page.locator('#username').fill('front');page.locator('#password').fill('Reservation-browser-123')
                page.get_by_role('button',name='Entrar',exact=True).click();page.wait_for_url('**/recepcao')
                page.get_by_role('link',name='Reservas',exact=True).click()
                for name,value in dict(external_id='BROWSER-001',guest_name='Hospede Ficticio',phone='5511000000000',cpf='52998224725',arrival='01/10/2026',departure='03/10/2026',room='101').items():
                    page.locator('[name='+name+']').fill(value)
                page.get_by_role('button',name='Salvar reserva',exact=True).click()
                expect(page.locator('#success')).to_contain_text('Reserva salva')
                expect(page.locator('#statuses')).to_contain_text('Não enviada')
                conversation_state.send_waha.assert_not_called()
                assert page.locator('[name=arrival]').input_value()=='01/10/2026'
                with app.connection() as db:assert db.execute('SELECT arrival FROM reservations').fetchone()[0]=='2026-10-01'
                # Delay a periodic request, then click the same button while it is pending.
                page.evaluate("""() => {window.reservationFetches=0;const original=window.fetch;window.fetch=async(...args)=>{if(args[0]==='/api/reservations'&&!args[1]?.method){window.reservationFetches++;await new Promise(r=>setTimeout(r,300));}return original(...args)};void refresh();}""")
                page.locator('#refresh').click()
                expect(page.locator('#success')).to_contain_text('Lista atualizada')
                assert page.evaluate('window.reservationFetches')>=2
                assert page.url==base+'/reservas'
                page.locator('[name=guest_name]').fill('Edicao ainda nao salva')
                page.locator('#refresh').click()
                expect(page.locator('#refresh')).to_have_text('Atualizar lista')
                assert page.locator('[name=guest_name]').input_value()=='Edicao ainda nao salva'
                page.get_by_role('button',name='Visualizar / editar',exact=True).click()
                expect(page.locator('[name=guest_name]')).to_have_value('Hospede Ficticio')
                page.get_by_role('button',name='Enviar boas-vindas',exact=True).click()
                expect(page.locator('#success')).to_contain_text('Boas-vindas enviadas')
                expect(page.locator('#statuses')).to_contain_text('Aceita pelo WhatsApp')
                conversation_state.send_waha.assert_called_once()
                expect(page.locator('#generate')).to_be_disabled()
                assert page.locator('#guestLink').count()==0
                assert page.locator('#checkin').is_disabled()
                for i,text in enumerate(['INICIAR','SIM','CONFIRMAR NOME','CONFIRMAR DADOS','CONCLUIR']):
                    app.handle_message(dict(message=text,request_id='browser-reservation-'+str(i),session_id='waha_5511000000000_c_us'))
                page.get_by_role('button',name='Atualizar lista',exact=True).click()
                expect(page.locator('#list tbody')).to_contain_text('Concluído')
                page.get_by_role('button',name='Visualizar / editar',exact=True).click()
                expect(page.locator('#statuses')).to_contain_text('Pré-check-in: Concluído')
                assert page.locator('#checkin').is_disabled()
                page.locator('#documentChecked').check()
                page.get_by_role('button',name='Confirmar check-in',exact=True).click()
                expect(page.locator('#statuses')).to_contain_text('Check-in realizado')
                assert page.locator('#save').is_disabled()
                result=app.handle_message(dict(message='Quero fazer checkout',request_id='browser-checkout-pending',session_id='waha_5511000000000_c_us'))
                assert result['route']=='HUMAN_HANDOFF'
                page.get_by_role('button',name='Atualizar lista',exact=True).click()
                expect(page.locator('#list tbody')).to_contain_text('Aguardando recepção')
                page.get_by_role('button',name='Visualizar / editar',exact=True).click()
                expect(page.locator('#statuses')).to_contain_text('Aguardando recepção')
                assert page.locator('#checkout').is_disabled()
                page.locator('#paymentsReviewed').check();page.locator('#pendingReviewed').check()
                page.get_by_role('button',name='Liberar checkout',exact=True).click()
                expect(page.locator('#statuses')).to_contain_text('confirmada pela recepção')
                page.get_by_role('button',name='Confirmar checkout',exact=True).click()
                expect(page.locator('#statuses')).to_contain_text('Checkout realizado')
                assert page.locator('#generate').is_disabled()
                page.screenshot(path=str(ROOT/'runtime/reservations-browser.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(ROOT/'runtime/reservations-mobile.png'),full_page=True)
                # Policy branding is a view: saving an unchanged field preserves its source.
                auth.create_user(app.connection,dict(username='editor',name='Editor Teste',role='editor',password='Hostess-browser-123'))
                with app.connection() as db:db.execute("UPDATE staff_users SET must_change=0 WHERE username='editor'")
                session=auth.login(app.connection,'editor','Hostess-browser-123')
                context.add_cookies([{'url':base,'name':auth.COOKIE,'value':session}])
                original_policy=next(r for r in policy_review.catalog(app.connection,app.POLICIES) if r['id']=='POL-00')['draft']['content']
                page.goto(base+'/politicas')
                page.locator('.item').filter(has_text='POL-00').click()
                expect(page.locator('#effective-content')).to_contain_text('Hostess, assistente de Hotel Aura')
                assert 'Sou a AURA' not in page.locator('#content').input_value()
                page.get_by_role('button',name='Salvar rascunho',exact=True).click()
                expect(page.locator('#feedback')).to_contain_text('Rascunho salvo', timeout=30000)
                saved=next(r for r in policy_review.catalog(app.connection,app.POLICIES) if r['id']=='POL-00')['draft']['content']
                assert saved==original_policy
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown();thread.join();server.server_close();app.DB=original
    report=dict(passed=True,isolated_database=True,real_browser=True,welcome_button_precheckin_checkin_checkout=True,role='recepcao',mobile_overflow=False,whatsapp_sent=False,console_errors=errors,brazilian_dates_in_american_browser=True,refresh_queued_and_draft_preserved=True,direct_welcome_on_click_simulated=True,policy_source_preserved=True)
    (ROOT/'runtime/reservations-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
