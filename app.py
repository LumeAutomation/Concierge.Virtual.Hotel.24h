"""AURA: piloto local deterministico. Somente dados ficticios."""
import json
import knowledge_engine
import conversation_state
import reception
import policy_review
import operations
import auth
import hmac
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

    auth.init_schema(connection)
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
        base,_=knowledge_engine.load_base()
        return {"route":"AUTO_REPLY","reply":base['POL-00']['content'],"policy_ids":["POL-00"],"ai_used":False,"answer_mode":"welcome"}
    if not re.search(ACTION,t):
        answer=knowledge_engine.local_answer(message)
        if answer:return answer
        matches=[row for row in FAQ if re.search(row[0],t)]
        if len(matches)==1 and len(t)<=180 and re.search(r"horario|que horas|quando.*(?:abre|fecha)|como.*(?:acess|conect)|nome da rede|^wi.?fi[?!. ]*$",t):
            pid=matches[0][1];base,version=knowledge_engine.load_base()
            return {"route":"AUTO_REPLY","reply":base[pid]['content'],"policy_ids":[pid],"ai_used":False,"answer_mode":"local_knowledge","knowledge_version":version}
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
    return False


def knowledge_context(body):
    message,request_id,session_id=validate_message(body)
    with connection() as db:
        previous=db.execute('SELECT session_id,message FROM interactions WHERE id=?',(request_id,)).fetchone()
    stored="[conteúdo sensível omitido]" if re.search(SENSITIVE,normalize(message)) else message.strip()
    if previous and (previous[0]!=session_id or previous[1]!=stored):raise ValueError('Protocolo ja utilizado por outra mensagem.')
    result=knowledge_engine.build_context(message,request_id,session_id,False)
    result['answer_mode']='local_knowledge_only'
    if previous:result['cached_response']=True
    return result


def handle_knowledge_message(body):
    # Model output supplied by legacy integrations is never used in this mode.
    return handle_message(body)


def handle_message(body, _decision=None):
    message, request_id, session_id = validate_message(body)
    result = classify(message)
    result.setdefault("ai_used",False)
    if conversation_state.is_followup(message):
        result={"route":"AUTO_REPLY","reply":"Sobre qual serviço do hotel você está perguntando?", "policy_ids":[], "answer_mode":"clarification", "ai_used":False}
    # Nao reter conteudo identificado como sensivel.
    stored_message = "[conteúdo sensível omitido]" if re.search(SENSITIVE, normalize(message)) else message.strip()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT session_id,message,response FROM interactions WHERE id=?", (request_id,)).fetchone()
        if previous:
            if previous[0] != session_id or previous[1] != stored_message:
                raise ValueError("request_id já utilizado por outra mensagem.")
            return json.loads(previous[2])
        first = not db.execute('SELECT 1 FROM interactions WHERE session_id=? LIMIT 1',(session_id,)).fetchone()
        if first and result.get('priority')!='urgent' and result.get('route')!='SAFE_REPLY':
            welcome=knowledge_engine.load_base()[0]['POL-00']['content']
            if result.get('answer_mode')!='welcome':result['reply']=welcome+'\n\n'+result['reply']
            result['welcome_included']=True
            result['welcome_policy_id']='POL-00'
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

    def respond(self, status, data, cookie=None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def local_request(self):
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return host in hosts and (origin is None or origin in {"http://" + h for h in hosts})

    def staff(self):
        return auth.current(connection, auth.cookie_token(self.headers.get('Cookie')))

    def require_staff(self, permission=None, page=False, allow_change=False):
        user = self.staff()
        if not user or (user['must_change'] and not allow_change):
            if page:
                self.send_response(303)
                self.send_header('Location', '/login')
                self.send_header('Content-Length', '0')
                self.end_headers()
            else:
                self.respond(401, {'error': 'Entre com sua conta e atualize a senha temporaria.'})
            return None
        if permission and permission not in user['permissions']:
            self.respond(403, {'error': 'Seu perfil nao permite esta acao.'})
            return None
        return user

    def service(self):
        try:
            token = (ROOT/'runtime/auth/service-token.txt').read_text(encoding='utf-8').strip()
            return bool(token) and hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+token)
        except OSError:
            return False

    def serve_page(self, name):
        payload = (ROOT/'web'/name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript; charset=utf-8' if name.endswith('.js') else 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.local_request():
            return self.respond(403, {'error': 'Acesso somente local.'})
        if self.path == '/api/health':
            return self.respond(200, {'status':'ok','mode':'local_demo','channel':'local_rules','storage':'sqlite','staff_auth':True})
        if self.path == '/api/auth/me':
            user = self.require_staff(allow_change=True)
            if user: return self.respond(200, user)
            return
        public = {'/':'index.html','/login':'login.html','/staff.js':'staff.js'}
        if self.path in public:
            return self.serve_page(public[self.path])
        pages = {'/recepcao':('reception','index.html'), '/politicas':('policies','policies.html'),
                 '/operacao':('operations','operations.html'), '/equipe':('users','team.html')}
        if self.path in pages:
            permission, name = pages[self.path]
            if self.require_staff(permission, page=True): return self.serve_page(name)
            return
        routes = {'/api/whatsapp/deliveries':('operations',lambda:conversation_state.list_deliveries(connection)),
                  '/api/operations':('operations',operations.snapshot),
                  '/api/policies':('policies',lambda:policy_review.catalog(connection,POLICIES)),
                  '/api/handoffs':('reception',list_handoffs),
                  '/api/users':('users',lambda:auth.list_users(connection)),
                  '/api/pilot/contacts':('users',lambda:auth.contacts(connection))}
        if self.path in routes:
            permission, action = routes[self.path]
            if self.require_staff(permission): return self.respond(200,action())
            return
        return self.respond(404, {'error':'Nao encontrado.'})

    def do_POST(self):
        try:
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                return self.respond(415, {'error':'Use application/json.'})
            size = int(self.headers.get('Content-Length','0'))
            if not 0 < size <= 16384:
                return self.respond(413, {'error':'Tamanho invalido.'})
            body = json.loads(self.rfile.read(size))
            if not self.local_request():
                return self.respond(403, {'error':'Acesso somente local.'})
            if not isinstance(body, dict): raise ValueError('Envie um objeto JSON.')
            if self.path == '/api/auth/login':
                token = auth.login(connection,body.get('username'),body.get('password'))
                if not token: return self.respond(401,{'error':'Login ou senha invalidos. Apos varias tentativas, aguarde 15 minutos.'})
                return self.respond(200,auth.current(connection,token),
                    f'{auth.COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={auth.TTL}')
            if self.path == '/api/auth/logout':
                auth.logout(connection,auth.cookie_token(self.headers.get('Cookie')))
                return self.respond(200,{'ok':True},f'{auth.COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if self.path == '/api/auth/password':
                user = self.require_staff(allow_change=True)
                if not user: return
                result = auth.change_password(connection,user['username'],body.get('old_password'),body.get('password'))
                return self.respond(200,result,f'{auth.COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            permissions = {'/api/policies':'approve' if body.get('action')=='approve' or (body.get('action')=='create' and body.get('publish') is True) else 'edit',
                           '/api/handoffs/status':'reception','/api/users':'users',
                           '/api/users/update':'users','/api/pilot/contacts':'users'}
            if self.path in permissions:
                user = self.require_staff(permissions[self.path])
                if not user: return
                # Identity is derived from the session, never from the submitted name.
                body['actor'] = user['username']
                body['operator'] = user['username']
                if self.path == '/api/policies': result=policy_review.change(connection,POLICIES,body)
                elif self.path == '/api/handoffs/status': result=reception.update(connection,body,allow_notification=lambda sid:auth.allowed_contact(connection,sid))
                elif self.path == '/api/users': result=auth.create_user(connection,body,user['username'])
                elif self.path == '/api/users/update': result=auth.update_user(connection,body,user['username'])
                else: result=auth.save_contact(connection,body,user['username'])
                return self.respond(200 if result.get('updated',True) else 404,result)
            internal = self.path in ('/api/knowledge/context','/api/chat/knowledge','/api/whatsapp/reply','/api/pilot/check')
            whatsapp = str(body.get('session_id','')).startswith(('waha_','wa_'))
            if internal or whatsapp:
                if not self.service(): return self.respond(401,{'error':'Credencial de integracao necessaria.'})
                allowed = auth.allowed_contact(connection,body.get('session_id',''))
                if self.path == '/api/pilot/check': return self.respond(200,{'allowed':allowed,**{k:body[k] for k in ('message','request_id','session_id') if k in body}})
                if whatsapp and not allowed: return self.respond(403,{'error':'Contato fora do piloto autorizado.'})
            if self.path == '/api/whatsapp/reply':
                result=conversation_state.deliver(connection,body.get('request_id'),body.get('session_id'))
                return self.respond(503 if result['needs_review'] else 200,result)
            if self.path == '/api/knowledge/context': return self.respond(200,knowledge_context(body))
            if self.path == '/api/chat/knowledge': return self.respond(200,handle_knowledge_message(body))
            if self.path == '/api/chat': return self.respond(200,handle_message(body))
            return self.respond(404,{'error':'Nao encontrado.'})
        except policy_review.Conflict as error:
            return self.respond(409,{'error':str(error)})
        except (ValueError, UnicodeError) as error:
            return self.respond(400,{'error':str(error) if isinstance(error,ValueError) else 'Dados invalidos.'})
        except sqlite3.Error:
            return self.respond(503,{'error':'Nao foi possivel registrar. Tente novamente.'})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("AURA_PORT", "8787"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AURA piloto local: http://127.0.0.1:{port}", flush=True)
    server.serve_forever()

