"""Smoke real de navegador: cria apenas atendimentos ficticios identificados."""
import json
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
out = Path("runtime")
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE)
    page.get_by_role("button", name="Qual o horário do café da manhã?", exact=True).click()
    page.get_by_role("button", name="Enviar", exact=True).click()
    page.locator(".source").filter(has_text="POL-08").wait_for()
    text = "Quero toalhas para teste QA " + uuid.uuid4().hex[:8]
    page.get_by_role("textbox", name="Sua mensagem").fill(text)
    page.get_by_role("button", name="Enviar", exact=True).click()
    page.locator(".bubble").filter(has_text="registrado na fila local").wait_for()
    page.screenshot(path=str(out / "chat.png"), full_page=True)
    page.get_by_role("link", name="Recepção", exact=True).click()
    ticket = page.locator("article").filter(has_text=text)
    ticket.wait_for()
    page.locator('#operator').fill('QA local')
    ticket.get_by_role('button',name='Assumir atendimento').click()
    ticket.get_by_text('Responsável: QA local',exact=True).wait_for()
    page.reload()
    ticket=page.locator('article').filter(has_text=text)
    ticket.get_by_text('Responsável: QA local',exact=True).wait_for()
    page.screenshot(path=str(out / 'recepcao.png'),full_page=True)
    ticket.get_by_role('button',name='Concluir atendimento',exact=True).click()
    ticket.get_by_text('Pedido do painel local: sem aviso pelo WhatsApp.',exact=True).wait_for()
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(out / "mobile.png"), full_page=True)
    assert not errors, errors
    health = page.request.get(BASE + "/api/health").json()
    assert health["mode"] == "local_demo"
    assert page.request.post(BASE + "/api/chat", data=[], headers={"Content-Type":"application/json"}).status == 400
    assert page.request.post(BASE + "/api/chat", data={}, headers={"Content-Type":"application/json","Origin":"https://example.com"}).status == 403
    report = {"passed":True, "flow":"chat FAQ > handoff > recepcao > status persistido > resolved", "mobile_overflow":False,"console_errors":errors, "health":health}
    (out / "browser-check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report))
    browser.close()

