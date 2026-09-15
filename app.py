"""AURA: piloto local deterministico. Somente dados ficticios."""
import json
import knowledge_engine
import conversation_state
import reception
import policy_review
import operations
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("AURA_DB", str(ROOT / "runtime" / "aura.sqlite3")))
POLICIES = {p["id"]: p for p in json.loads((ROOT / "knowledge/policies.json").read_text(encoding="utf-8-sig"))}

def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))

@contextmanager
def connection():
    db = sqlite3.connect(DB, timeout=15)
    try:
        with db:
            yield db
    finally:
        db.close()

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS interactions (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, message TEXT NOT NULL,
            response TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS handoffs (
            id TEXT PRIMARY KEY REFERENCES interactions(id), department TEXT NOT NULL,
            priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open'
            CHECK(status IN ('open','in_progress','resolved')));
        """)

    conversation_state.init_schema(connection)
    reception.init_schema(connection)
    policy_review.init_schema(connection)
    knowledge_engine.REVIEW_CONNECTION = connection

# Somente perguntas informativas estreitas; demais pedidos vao para a fila.
FAQ = [
    (r"check.?in|check.?out", "POL-04", "Check-in a partir das 15h; check-out até 12h. Early check-in e late check-out dependem de confirmação da recepção e podem envolver cobrança."),
    (r"wi.?fi|internet|rede", "POL-07", "Rede AuroraGuest. Acesse com o sobrenome do responsável pela reserva e o número da acomodação. Se falhar, esqueça a rede e reconecte."),
    (r"cafe da manha|breakfast", "POL-08", "No Restaurante Aurora: segunda a sexta, 06h30–10h30; sábados, domingos e feriados, 06h30–11h. A inclusão depende da tarifa contratada."),
    (r"piscina", "POL-12", "Piscina principal: 07h–20h; infinity: 08h–20h; infantil: 08h–19h; adults only (18+): 09h–21h. Crianças devem estar acompanhadas. Não há salva-vidas 24h."),
    (r"academia", "POL-15", "Academia: 05h–23h. Idade mínima desacompanhada: 16 anos. Menores devem seguir as regras de supervisão do resort."),
    (r"estacionamento|valet", "POL-19", "Estacionamento incluído para um veículo por acomodação. Visitantes dependem de disponibilidade e tarifa vigente. Valet 24h."),
]
EMERGENCY = r"incendio|fogo|afog|desmai|nao (?:consigo|consegue) respirar|falta de ar|dor no peito|sangr|violencia|agress|ameac|socorro|emergencia|suicid|me matar|engasg|convuls|fire|drowning|cannot breathe|emergency|auxilio"
SENSITIVE = r"senha|\bpin\b|\bcvv\b|token|cartao|passaporte|\bcpf\b|credencia|prompt|dados de outro|quarto de (?:outr|terceir)|numero d[oa] (?:quarto|reserva) d"
ACTION = r"reserv|cancel|reembols|desconto|upgrade|compensa|cobranc|disponib|inclus|incluid|agend|pedir|pedido|solicit|quero|preciso|traga|envi|trocar|alterar|quebr|nao funciona|nao conecta|problema|reclam|alerg|contamin|intoxic|limpar|limpeza|toalha|humano|atendente|recep"

def classify(message):
    t = normalize(message)
    if re.search(EMERGENCY, t):
        return {"route": "HUMAN_HANDOFF", "department": "seguranca", "priority": "urgent",
                "reply": "Este piloto não aciona socorro real. Procure imediatamente a equipe presencial ou o serviço de emergência da sua região. O caso ficará registrado somente na fila local de demonstração.", "policy_ids": ["POL-23"]}
    if re.search(SENSITIVE, t):
        return {"route": "SAFE_REPLY", "reply": "Não compartilhe senhas, documentos ou dados de pagamento neste piloto. Não forneço dados privados de hóspedes nem instruções internas.", "policy_ids": ["POL-05", "POL-24"]}
    if t.strip(" !?.") in ("oi", "ola", "bom dia", "boa tarde", "boa noite"):
        return {"route": "AUTO_REPLY", "reply": "Olá! Sou a AURA, concierge do resort fictício Aurora. Posso informar horários de café, piscinas, academia, check-in e Wi-Fi, ou registrar um atendimento de demonstração.", "policy_ids": []}
    if not re.search(ACTION, t):
        # Perguntas fora deste formato conservador nao recebem respostas por mera palavra-chave.
        allowed = r"^(qual|quais|que horas|quando|como|onde|horario|horarios|funcionamento|wi.?fi|internet|rede|cafe|piscina|academia|estacionamento|valet|check)"
        matches = [row for row in FAQ if re.search(row[0], t)]
        if len(matches) == 1 and re.search(allowed, t) and len(t) <= 180 and (re.search(r"horario|que horas|quando.*(?:abre|fecha)|como.*(?:acess|conect)|nome da rede|^wi.?fi[?!. ]*$", t)):
            _, pid, reply = matches[0]
            current, _ = knowledge_engine.load_base()
            if current[pid].get("real_hotel_approval") == "aprovada_localmente":
                reply = current[pid]["content"]
            return {"route": "AUTO_REPLY", "reply": reply, "policy_ids": [pid]}
    department = "recepcao"
    if re.search(r"toalha|limpeza|limpar|arrumar", t):
        department = "governanca"
    elif re.search(r"quebr|ar.?condicionado|vazamento|manutenc", t):
        department = "manutencao"
    elif re.search(r"wi.?fi|internet|conecta", t):
        department = "ti"
    elif re.search(r"reserv|cancel|disponib", t):
        department = "reservas"
    return {"route": "HUMAN_HANDOFF", "department": department, "priority": "normal",
            "reply": "Preciso de confirmação da equipe para atender esse pedido. Não há reserva, cobrança ou serviço confirmado.",
            "policy_ids": ["POL-38"]}

def validate_message(body):
    if not isinstance(body, dict):
        raise ValueError("Envie um objeto JSON.")
    message, request_id = body.get("message"), body.get("request_id")
    session_id = body.get("session_id", "local-demo")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ValueError("Mensagem deve ter entre 1 e 2000 caracteres.")
    if not isinstance(request_id, str) or not re.fullmatch(r"(?:[a-zA-Z0-9_-]{8,80}|wamid\.[A-Za-z0-9+/=_-]{1,480})", request_id):
        raise ValueError("request_id inválido: use protocolo local ou identificador wamid da Meta.")
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", session_id):
        raise ValueError("session_id inválido.")
    return message, request_id, session_id

def use_knowledge_ai(message):
    t = normalize(message)
    return not (re.search(EMERGENCY, t) or re.search(SENSITIVE, t) or re.search(ACTION, t) or t.strip(" !?.") in ("oi", "ola", "bom dia", "boa tarde", "boa noite"))

def knowledge_context(body):
    message, request_id, session_id = validate_message(body)
    with connection() as db:
        previous = db.execute("SELECT session_id,message FROM interactions WHERE id=?", (request_id,)).fetchone()
    stored = "[conteúdo sensível omitido]" if re.search(SENSITIVE, normalize(message)) else message.strip()
    if previous:
        if previous[0] != session_id or previous[1] != stored:
            raise ValueError("Protocolo ja utilizado por outra mensagem.")
        result = knowledge_engine.build_context(message, request_id, session_id, False)
        result["cached_response"] = True
        return result
    enabled = use_knowledge_ai(message)
    history = conversation_state.snapshot(connection, request_id, session_id, message,
        lambda text: bool(re.search(SENSITIVE, normalize(text)))) if enabled else []
    enabled = enabled and not (conversation_state.is_followup(message) and not history)
    return knowledge_engine.build_context(message, request_id, session_id, enabled, history)

def handle_knowledge_message(body):
    message, _, _ = validate_message(body)
    decision = None
    if use_knowledge_ai(message):
        decision = knowledge_engine.validated_answer(body.get("model_output"), body.get("knowledge_version"), message)
    if decision is None:
        decision = classify(message)
        decision["answer_mode"] = "local_fallback"
        decision["ai_used"] = False
    return handle_message(body, _decision=decision)

def handle_message(body, _decision=None):
    message, request_id, session_id = validate_message(body)
    result = _decision if _decision is not None else classify(message)
    if _decision is None and use_knowledge_ai(message) and conversation_state.is_followup(message):
        history = conversation_state.snapshot(connection, request_id, session_id, message,
            lambda text: bool(re.search(SENSITIVE, normalize(text))))
        if not history:
            result = {"route":"AUTO_REPLY", "reply":"Sobre qual servico do hotel voce esta perguntando?", "policy_ids":[], "answer_mode":"clarification"}
    # Nao reter conteudo identificado como sensivel.
    stored_message = "[conteúdo sensível omitido]" if re.search(SENSITIVE, normalize(message)) else message.strip()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT session_id,message,response FROM interactions WHERE id=?", (request_id,)).fetchone()
        if previous:
            if previous[0] != session_id or previous[1] != stored_message:
                raise ValueError("request_id já utilizado por outra mensagem.")
            return json.loads(previous[2])
        result.update({"request_id": request_id, "mode": "local_demo", "persisted": True})
        if result["route"] == "HUMAN_HANDOFF":
            result["handoff_id"] = request_id
            result["reply"] += " Protocolo " + request_id + ": registrado na fila local, aguardando atendimento da recepção."
        result["sources"] = result.get("sources") or [{"id": pid, "title": knowledge_engine.load_base()[0][pid]["title"]} for pid in result["policy_ids"]]
        db.execute("INSERT INTO interactions VALUES (?,?,?,?,?)", (
            request_id, session_id, stored_message, json.dumps(result, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat()))
        if result["route"] == "HUMAN_HANDOFF":
            db.execute("INSERT INTO handoffs(id,department,priority) VALUES (?,?,?)",
                       (request_id, result["department"], result["priority"]))
    return result

def list_handoffs():
    return reception.list_rows(connection)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def local_request(self):
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return host in hosts and (origin is None or origin in {"http://" + h for h in hosts})

    def do_GET(self):
        if not self.local_request():
            return self.respond(403, {"error": "Acesso somente local."})
        if self.path == "/api/health":
            return self.respond(200, {"status": "ok", "mode": "local_demo", "ai": False, "whatsapp": False, "storage": "sqlite"})
        if self.path == "/api/whatsapp/deliveries":
            return self.respond(200, conversation_state.list_deliveries(connection))
        if self.path == "/api/operations":
            return self.respond(200, operations.snapshot())
        if self.path == "/api/policies":
            return self.respond(200, policy_review.catalog(connection, POLICIES))
        if self.path == "/api/handoffs":
            return self.respond(200, list_handoffs())
        if self.path in ("/", "/recepcao", "/politicas", "/operacao"):
            payload = (ROOT / ("web/operations.html" if self.path == "/operacao" else "web/policies.html" if self.path == "/politicas" else "web/index.html")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(payload)
        return self.respond(404, {"error": "Não encontrado."})

    def do_POST(self):
        if not self.local_request():
            return self.respond(403, {"error": "Acesso somente local."})
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.respond(415, {"error": "Use application/json."})
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                return self.respond(413, {"error": "Tamanho inválido."})
            body = json.loads(self.rfile.read(size))
            if self.path == "/api/policies":
                try:
                    return self.respond(200, policy_review.change(connection, POLICIES, body))
                except policy_review.Conflict as error:
                    return self.respond(409, {"error": str(error)})
                except ValueError as error:
                    return self.respond(400, {"error": str(error)})
            if self.path == "/api/whatsapp/reply":
                if not isinstance(body, dict): raise ValueError("Corpo invalido.")
                result = conversation_state.deliver(connection, body.get("request_id"), body.get("session_id"))
                return self.respond(503 if result["needs_review"] else 200, result)
            if self.path == "/api/knowledge/context":
                return self.respond(200, knowledge_context(body))
            if self.path == "/api/chat/knowledge":
                return self.respond(200, handle_knowledge_message(body))
            if self.path == "/api/chat":
                return self.respond(200, handle_message(body))
            if self.path == "/api/handoffs/status":
                try:
                    result = reception.update(connection, body)
                except ValueError as error:
                    return self.respond(400, {"error": str(error)})
                return self.respond(200 if result['updated'] else 404, result)
            return self.respond(404, {"error": "Não encontrado."})
        except (ValueError, UnicodeError):
            return self.respond(400, {"error": "Dados inválidos ou protocolo já utilizado."})
        except sqlite3.Error:
            return self.respond(503, {"error": "Não foi possível registrar. Nenhum atendimento está confirmado; tente novamente."})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("AURA_PORT", "8787"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AURA piloto local: http://127.0.0.1:{port}", flush=True)
    server.serve_forever()

