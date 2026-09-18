"""Validate local FNRH UI on temporary SQLite and isolated HTTP socket."""
import secrets
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import auth
import conversation_state
from scripts.http_fixture import ServerFixture
from playwright.sync_api import sync_playwright, expect


def main():
    original = app.DB
    errors = []
    with tempfile.TemporaryDirectory(prefix='aura-fnrh-browser-') as tmp:
        try:
            app.DB = Path(tmp) / 'isolated.sqlite3'
            app.init_db()
            password = secrets.token_urlsafe(24)
            auth.create_user(app.connection, dict(username='fnrh_test', name='FNRH Teste',
                             role='recepcao', password=password))
            with app.connection() as db:
                db.execute('UPDATE staff_users SET must_change=0')
                for rid, arrival, pre in [('ready', '2030-01-01', 'PRE_CHECKIN_CONCLUIDO'),
                                          ('pending', None, 'PRE_CHECKIN_PENDENTE')]:
                    db.execute('''INSERT INTO reservations
                        (id,external_id,guest_name,phone,cpf,arrival,departure,pre_status,
                         checkin_status,checkout_status,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (rid, 'FICTICIO-' + rid, '<img src=x onerror=alert(1)>',
                         '5511000000000', '52998224725', arrival, '2030-01-03', pre,
                         'CHECK_IN_REALIZADO', 'CHECK_OUT_REALIZADO',
                         '2030-01-01T12:00:00+00:00', '2030-01-01T12:00:00+00:00'))
            server = ServerFixture(app.application)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = 'http://127.0.0.1:' + str(server.server_port)
            try:
                with patch.object(conversation_state, 'send_waha', side_effect=AssertionError('Unexpected WhatsApp call')) as send, sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(base + '/fnrh')
                    page.wait_for_url('**/login')
                    page.locator('#username').fill('fnrh_test')
                    page.locator('#password').fill(password)
                    page.get_by_role('button', name='Entrar', exact=True).click()
                    page.wait_for_url('**/recepcao')
                    page.goto(base + '/fnrh')
                    expect(page.locator('.notice')).to_contain_text('Simulação local — nenhum envio oficial')
                    expect(page.locator('#rows tr')).to_have_count(2)
                    assert page.locator('#rows img').count() == 0
                    body = page.locator('body').inner_text()
                    assert '52998224725' not in body and '5511000000000' not in body
                    page.locator('#rows tr').filter(has_text='FICTICIO-pending').get_by_role('button').click()
                    expect(page.locator('#title')).to_be_focused()
                    expect(page.locator('#blocked')).to_contain_text('Simulação bloqueada:')
                    expect(page.get_by_role('link', name='Abrir Reservas para resolver pendências')).to_have_attribute('href', '/reservas')
                    page.locator('#humanChecked').check()
                    expect(page.locator('#simulate')).to_be_disabled()
                    page.locator('#rows tr').filter(has_text='FICTICIO-ready').get_by_role('button').click()
                    expect(page.locator('#simulate')).to_be_disabled()
                    page.locator('#humanChecked').check()
                    page.locator('#outcome').select_option('uncertain')
                    page.locator('#simulate').click()
                    expect(page.locator('#success')).to_contain_text('Simulação local registrada')
                    page.locator('#humanChecked').check()
                    expect(page.locator('#simulate')).to_be_disabled()
                    expect(page.locator('#reconciliation')).to_be_visible()
                    page.reload()
                    page.locator('#rows tr').filter(has_text='FICTICIO-ready').get_by_role('button').click()
                    expect(page.locator('#reconciliation')).to_be_visible()
                    page.locator('#resolution').select_option('not_sent')
                    page.locator('#reason').fill('Cenário fictício conferido no teste isolado.')
                    expect(page.locator('#reconcile')).to_be_disabled()
                    page.locator('#reconciledChecked').check()
                    page.locator('#reconcile').click()
                    expect(page.locator('#success')).to_contain_text('Reconciliação local registrada')
                    page.locator('#humanChecked').check()
                    page.locator('#outcome').select_option('error')
                    page.locator('#simulate').click()
                    expect(page.locator('#history')).to_contain_text('Erro fictício')
                    page.locator('#humanChecked').check()
                    page.locator('#outcome').select_option('ok')
                    page.locator('#simulate').click()
                    expect(page.locator('#history')).to_contain_text('Sucesso fictício')
                    page.locator('#humanChecked').check()
                    expect(page.locator('#simulate')).to_be_disabled()
                    page.locator('#operation').select_option('checkout')
                    expect(page.locator('#simulate')).to_be_disabled()
                    page.locator('#humanChecked').check()
                    page.locator('#simulate').click()
                    expect(page.locator('#history > li')).to_have_count(2)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    send.assert_not_called()
                    assert not errors, errors
                    browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
        finally:
            app.DB = original
    print('FNRH browser: passed (temporary DB, no official or WhatsApp transmission)')


if __name__ == '__main__':
    main()
