import operating_mode
import knowledge_engine
"""Reservas manuais e jornada do hospede no SQLite existente."""
import hashlib
import json
import re
import secrets
import sqlite3
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from waha_config import session_name
import conversation_state as delivery

ROOT = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r'\bAURA-RESERVA\s+([A-Za-z0-9_-]{43})(?![A-Za-z0-9_-])', re.I)
OPEN = ('RESERVA_CADASTRADA', 'LINK_GERADO', 'CHECK_IN_REALIZADO')

class Conflict(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS reservations (
          id TEXT PRIMARY KEY, hotel_id TEXT NOT NULL DEFAULT 'aurora',
          source TEXT NOT NULL DEFAULT 'manual', external_id TEXT NOT NULL UNIQUE,
          guest_name TEXT NOT NULL, phone TEXT NOT NULL, cpf TEXT NOT NULL,
          arrival TEXT, departure TEXT, room TEXT,
          status TEXT NOT NULL DEFAULT 'RESERVA_CADASTRADA',
          pre_status TEXT NOT NULL DEFAULT 'PRE_CHECKIN_PENDENTE',
          checkin_status TEXT NOT NULL DEFAULT 'PENDENTE',
          checkout_status TEXT NOT NULL DEFAULT 'PENDENTE',
          stage TEXT, checkout_cleared INTEGER NOT NULL DEFAULT 0,
          version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reservation_invitations (
          reservation_id TEXT PRIMARY KEY REFERENCES reservations(id), phone TEXT NOT NULL,
          welcome_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reservation_links (
          token_hash TEXT PRIMARY KEY, reservation_id TEXT NOT NULL REFERENCES reservations(id),
          expires REAL NOT NULL, consumed_session TEXT, revoked INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS reservation_conversations (
          session_id TEXT PRIMARY KEY, reservation_id TEXT NOT NULL REFERENCES reservations(id));
        CREATE TABLE IF NOT EXISTS reservation_events (
          id INTEGER PRIMARY KEY, reservation_id TEXT NOT NULL REFERENCES reservations(id),
          action TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS reservation_links_reservation ON reservation_links(reservation_id);
        CREATE INDEX IF NOT EXISTS reservation_conversations_reservation ON reservation_conversations(reservation_id);
        ''')

def event(db, rid, action, actor):
    db.execute('INSERT INTO reservation_events(reservation_id,action,actor,created_at) VALUES (?,?,?,?)',
               (rid, action, actor, now()))

def row(db, rid):
    cursor = db.execute('SELECT * FROM reservations WHERE id=?', (rid,))
    value = cursor.fetchone()
    if not value:
        raise ValueError('Reserva nao encontrada.')
    return dict(zip([c[0] for c in cursor.description], value))

def list_rows(connection):
    with connection() as db:
        db.row_factory = sqlite3.Row
        rows=[dict(r) for r in db.execute('SELECT * FROM reservations ORDER BY created_at DESC LIMIT 500')]
        for value in rows: add_metadata(db,value)
        return rows

def detail(connection, rid):
    with connection() as db:
        result = row(db, rid)
        add_metadata(db,result)
        db.row_factory = sqlite3.Row
        result['history'] = [dict(r) for r in db.execute(
            'SELECT action,actor,created_at FROM reservation_events WHERE reservation_id=? ORDER BY id', (rid,))]
        return result

def phone_number(value):
    if not isinstance(value, str) or re.search(r'[^0-9+().\s-]', value):
        raise ValueError('Informe telefone com DDI e DDD.')
    digits = re.sub(r'\D', '', value)
    if len(digits) in (10, 11):
        digits = '55' + digits
    if not re.fullmatch(r'[1-9]\d{10,14}', digits):
        raise ValueError('Informe telefone com DDI e DDD.')
    return digits

def cpf_number(value):
    if not isinstance(value, str) or re.search(r'[^0-9.\s-]', value):
        raise ValueError('CPF invalido.')
    digits = re.sub(r'\D', '', value)
    if len(digits) != 11 or len(set(digits)) == 1:
        raise ValueError('CPF invalido: confira os 11 digitos.')
    for length in (9, 10):
        check = (sum(int(digits[i]) * (length + 1 - i) for i in range(length)) * 10 % 11) % 10
        if check != int(digits[length]):
            raise ValueError('CPF invalido: confira os digitos verificadores.')
    return digits

def fields(body):
    result = {}
    for key, limit in [('external_id', 80), ('guest_name', 160)]:
        value = body.get(key)
        if not isinstance(value, str) or not 2 <= len(value.strip()) <= limit:
            raise ValueError('Informe ID da reserva e nome completo validos.')
        result[key] = value.strip()
    if len(result['guest_name'].split()) < 2:
        raise ValueError('Informe o nome completo do hospede.')
    result['phone'] = phone_number(body.get('phone'))
    result['cpf'] = cpf_number(body.get('cpf'))
    for key in ('arrival', 'departure'):
        value = body.get(key) or None
        if value:
            try:
                date.fromisoformat(value)
            except (ValueError, TypeError):
                raise ValueError('Data invalida.') from None
        result[key] = value
    if result['arrival'] and result['departure'] and result['arrival'] > result['departure']:
        raise ValueError('Saida anterior a chegada.')
    room = body.get('room') or None
    if room is not None and (not isinstance(room, str) or len(room.strip()) > 30):
        raise ValueError('Quarto invalido.')
    result['room'] = room.strip() if room else None
    return result

def waha_get(path):
    values = dict(line.split('=', 1) for line in (ROOT/'runtime/waha/.env').read_text(encoding='utf-8-sig').splitlines()
                  if '=' in line and not line.startswith('#'))
    with urlopen(Request('http://127.0.0.1:3000'+path, headers={'X-Api-Key': values['WAHA_API_KEY']}), timeout=8) as response:
        return json.load(response)

def bot_phone():
    try:
        session = waha_get('/api/sessions/'+quote(session_name(ROOT), safe=''))
        identifier = (session.get('me') or {}).get('id', '')
        number = identifier.split('@')[0].split(':')[0]
        if session.get('status') != 'WORKING' or not re.fullmatch(r'\d{11,15}', number):
            raise ValueError()
        return number
    except Exception:
        raise ValueError('WhatsApp indisponivel. Conecte a sessao antes de gerar o link.') from None

def sender_phone(session_id):
    match = re.fullmatch(r'waha_(\d{6,20})_(c_us|lid)', session_id or '')
    if not match:
        return None
    if match[2] == 'c_us':
        return match[1]
    try:
        data = waha_get('/api/'+quote(session_name(ROOT), safe='')+'/lids/'+match[1])
        if data.get('lid') != match[1]+'@lid':
            return None
        pn = data.get('pn', '')
        if re.fullmatch(r'\d{11,15}@c\.us', pn):
            return pn.split('@')[0]
    except Exception:
        pass
    return None

def token_hash(message):
    found = TOKEN_RE.search(message or '')
    return hashlib.sha256(found[1].encode()).hexdigest() if found else None

def token_reservation(db, digest, session):
    found = db.execute('''SELECT reservation_id FROM reservation_links
        WHERE token_hash=? AND revoked=0 AND expires>? AND (consumed_session IS NULL OR consumed_session=?)''',
        (digest, time.time(), session)).fetchone()
    if not found:
        return None
    result = row(db, found[0])
    return result if result['status'] in OPEN else None

def bound_reservation(db, session):
    found = db.execute('SELECT reservation_id FROM reservation_conversations WHERE session_id=?', (session,)).fetchone()
    return row(db, found[0]) if found else None

def access(connection, body):
    session = body.get('session_id', '')
    if not isinstance(session, str) or not re.fullmatch(r'waha_\d{6,20}_(c_us|lid)', session):
        return False
    message = body.get('message', '')
    if not isinstance(message, str):
        return False
    digest = token_hash(message)
    if message.strip(' .!?').upper()=='INICIAR':
        phone=sender_phone(session)
        with connection() as db:return bool(phone and invited(db,phone))
    with connection() as db:
        reservation = token_reservation(db, digest, session) if digest else bound_reservation(db, session)
    if not reservation:
        return False
    if reservation['status'] not in OPEN:
        # The final checkout reply must still be deliverable; no new messages are admitted.
        with connection() as db:
            sent = db.execute('SELECT response FROM interactions WHERE id=? AND session_id=?',
                              (body.get('request_id'),session)).fetchone()
        if not sent or json.loads(sent[0]).get('answer_mode') != 'reservation':
            return False
    return sender_phone(session) == reservation['phone']

def _change(connection, body, actor):
    action = body.get('action', 'save')
    destination = bot_phone() if action == 'link' else None
    values = fields(body) if action == 'save' else None
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        rid = body.get('id')
        if action == 'save' and not rid:
            rid = uuid.uuid4().hex
            try:
                db.execute('''INSERT INTO reservations(id,external_id,guest_name,phone,cpf,arrival,departure,room,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''', (rid, *[values[k] for k in ('external_id','guest_name','phone','cpf','arrival','departure','room')], now(), now()))
            except sqlite3.IntegrityError:
                raise ValueError('ID de reserva ja cadastrado.') from None
            event(db, rid, 'RESERVA_CADASTRADA', actor)
            return {'saved': True, 'reservation': row(db, rid)}
        reservation = row(db, rid)
        if body.get('version') != reservation['version']:
            raise Conflict('Reserva alterada por outro atendimento. Atualize a tela.')
        if reservation['status'] == 'CHECK_OUT_REALIZADO':
            raise ValueError('Reserva encerrada; alteracoes bloqueadas.')
        extra = {}
        if action == 'save':
            if reservation['checkin_status'] == 'CHECK_IN_REALIZADO':
                raise ValueError('Edicao bloqueada apos o check-in.')
            try:
                db.execute('''UPDATE reservations SET external_id=?,guest_name=?,phone=?,cpf=?,arrival=?,departure=?,room=?,
                    pre_status='PRE_CHECKIN_PENDENTE',stage=NULL,checkout_cleared=0 WHERE id=?''',
                    (*[values[k] for k in ('external_id','guest_name','phone','cpf','arrival','departure','room')], rid))
            except sqlite3.IntegrityError:
                raise ValueError('ID de reserva ja cadastrado.') from None
            db.execute('UPDATE reservation_links SET revoked=1 WHERE reservation_id=?', (rid,))
            db.execute('DELETE FROM reservation_conversations WHERE reservation_id=?', (rid,))
            db.execute('DELETE FROM reservation_invitations WHERE reservation_id=?', (rid,))
            db.execute("UPDATE reservations SET status='RESERVA_CADASTRADA' WHERE id=?", (rid,))
            label = 'RESERVA_EDITADA'
        elif action == 'link':
            token, expires = issue_token(db,rid)
            if reservation['status'] == 'RESERVA_CADASTRADA':
                db.execute("UPDATE reservations SET status='LINK_GERADO' WHERE id=?", (rid,))
            extra = {'url': 'https://wa.me/'+destination+'?'+urlencode({'text':'Olá! 👋 Vim iniciar meu atendimento com a Hostess do Hotel Aura. Quero acessar os serviços da minha hospedagem.\n\nReferência de acesso: AURA-RESERVA '+token}),
                     'expires_at': datetime.fromtimestamp(expires, timezone.utc).isoformat()}
            label = 'LINK_GERADO'
        elif action == 'checkin':
            if reservation['pre_status'] != 'PRE_CHECKIN_CONCLUIDO' or body.get('document_checked') is not True:
                raise ValueError('Conclua o pre-check-in e confirme a conferencia presencial do documento.')
            if reservation['checkin_status'] == 'CHECK_IN_REALIZADO':
                raise ValueError('Check-in ja realizado.')
            db.execute("UPDATE reservations SET status='CHECK_IN_REALIZADO',checkin_status='CHECK_IN_REALIZADO' WHERE id=?", (rid,))
            label = 'CHECK_IN_REALIZADO_DOCUMENTO_CONFERIDO'
        elif action in ('clear_checkout', 'checkout'):
            if reservation['checkin_status'] != 'CHECK_IN_REALIZADO':
                raise ValueError('Check-in ainda nao realizado.')
            if action == 'clear_checkout':
                if body.get('pending_reviewed') is not True or body.get('payments_reviewed') is not True:
                    raise ValueError('Confirme a conferencia de pagamentos e a ausencia de pendencias.')
                db.execute('UPDATE reservations SET checkout_cleared=1 WHERE id=?', (rid,))
                label = 'CHECKOUT_LIBERADO_PELA_RECEPCAO'
            else:
                if not reservation['checkout_cleared']:
                    raise ValueError('A recepcao deve liberar as pendencias antes de confirmar a saida.')
                close(db, rid)
                label = 'CHECK_OUT_REALIZADO'
        else:
            raise ValueError('Acao de reserva invalida.')
        db.execute('UPDATE reservations SET version=version+1,updated_at=? WHERE id=?', (now(), rid))
        event(db, rid, label, actor)
        return {'saved': True, 'reservation': row(db, rid), **extra}

def close(db, rid):
    db.execute("UPDATE reservations SET status='CHECK_OUT_REALIZADO',checkout_status='CHECK_OUT_REALIZADO',stage=NULL WHERE id=?", (rid,))
    db.execute('UPDATE reservation_links SET revoked=1 WHERE reservation_id=?', (rid,))

def reply(text, handoff=False):
    result = {'route':'HUMAN_HANDOFF' if handoff else 'TOOL_ACTION', 'reply':text,
              'policy_ids':[], 'answer_mode':'reservation', 'ai_used':False}
    if handoff:
        result.update(department='recepcao', priority='normal')
    return result

def operational(message, normalized):
    if 'AURA-RESERVA' in message.upper():
        return True
    if re.search(r'horario|que horas|early|late', normalized):
        return False
    return bool(re.search(r'pre[ -]?check[ -]?in|check[ -]?in|check[ -]?out|minha reserva|status da reserva', normalized))

def private_message(message):
    return '[reserva:'+hashlib.sha256(message.strip().encode()).hexdigest()+']'

def handle(db, message, session, normalized, verified_phone=None):
    digest = token_hash(message)
    reservation = bound_reservation(db, session)
    command = normalized.strip(' .!?')
    if command == 'iniciar':
        candidates=invited(db,verified_phone) if verified_phone else []
        if len(candidates)!=1:
            return reply('A recepção precisa conferir qual reserva corresponde ao seu telefone. Procure a recepção para identificar a hospedagem correta.',True)
        target=candidates[0]
        if reservation and reservation['id']!=target['id'] and reservation['status'] in OPEN:
            return reply('Há outra hospedagem vinculada a esta conversa. Procure a recepção para conferir.',True)
        reservation=target
        db.execute('INSERT INTO reservation_conversations VALUES (?,?) ON CONFLICT(session_id) DO UPDATE SET reservation_id=excluded.reservation_id',(session,target['id']))
        event(db,target['id'],'HOSPEDE_IDENTIFICADO','whatsapp')
        if target['pre_status']=='PRE_CHECKIN_CONCLUIDO':
            return reply('Bem-vindo(a) à Jornada do Hóspede do Hotel Aura. Seu pré-check-in está concluído. A Hostess está à disposição para ajudar durante sua hospedagem.')
        if target['stage']=='REVIEW':
            return reply('A recepção precisa corrigir seu cadastro antes de continuar.',True)
        db.execute("UPDATE reservations SET stage='OFFER',version=version+1,updated_at=? WHERE id=?",(now(),target['id']))
        return reply('Bem-vindo(a) à Jornada do Hóspede do Hotel Aura! Gostaria de realizar seu pré-check-in agora? Responda SIM para começar ou DEPOIS para continuar em outro momento.')
    if digest:
        target = token_reservation(db, digest, session)
        if not target or verified_phone != target['phone']:
            return reply('Nao foi possivel validar o link e o telefone desta reserva. Solicite ajuda a recepcao.', True)
        if reservation and reservation['id'] != target['id'] and reservation['status'] in OPEN:
            return reply('Ha outra reserva vinculada a esta conversa. A recepcao precisa conferir antes de trocar o atendimento.', True)
        reservation = target
        db.execute('UPDATE reservation_links SET consumed_session=? WHERE token_hash=?', (session, digest))
        db.execute('INSERT INTO reservation_conversations VALUES (?,?) ON CONFLICT(session_id) DO UPDATE SET reservation_id=excluded.reservation_id', (session, target['id']))
        event(db, target['id'], 'HOSPEDE_IDENTIFICADO', 'whatsapp')
    if not reservation:
        if operational(message, normalized):
            return reply('Peça à recepção para enviar as boas-vindas ao telefone cadastrado. Depois de receber a mensagem, responda INICIAR para consultar sua hospedagem.', True)
        return None
    if not re.fullmatch(r'waha_\d{6,20}_(c_us|lid)', session):
        return None
    rid = reservation['id']
    stage = reservation['stage']
    if reservation['status'] == 'CHECK_OUT_REALIZADO':
        return reply('O checkout desta hospedagem ja foi registrado. Para outra reserva, solicite novas boas-vindas à recepção.') if operational(message, normalized) else None
    action = None
    text = None
    if stage=='OFFER' and command in ('depois','nao'):
        return reply('Tudo bem! Quando desejar, envie PRÉ-CHECK-IN. A Hostess do Hotel Aura continua à disposição para suas dúvidas.')
    if (stage=='OFFER' and command in ('sim','agora')) or digest or (re.search(r'pre[ -]?check[ -]?in', normalized) and command != 'concluir pre-check-in' and operational(message,normalized)):
        if reservation['pre_status'] == 'PRE_CHECKIN_CONCLUIDO':
            return reply('Seu pre-check-in esta concluido. Na chegada, apresente o documento de identidade a recepcao para conferencia presencial.')
        if stage == 'REVIEW':
            return reply('A recepcao precisa corrigir seu cadastro e enviar novas boas-vindas antes de continuar.', True)
        db.execute("UPDATE reservations SET pre_status='PRE_CHECKIN_EM_ANDAMENTO',stage='NAME' WHERE id=?", (rid,))
        text = 'Vamos iniciar seu pre-check-in. O nome cadastrado e '+reservation['guest_name']+'. Esta correto? Responda CONFIRMAR NOME ou CORRIGIR. Voce pode perguntar sobre os servicos do hotel a qualquer momento.'
        action = 'PRE_CHECKIN_INICIADO'
    elif stage in ('NAME','DOCUMENT','REVIEW_FINAL') and command in ('nao','corrigir','dados incorretos'):
        db.execute("UPDATE reservations SET stage='REVIEW',pre_status='PRE_CHECKIN_PENDENTE' WHERE id=?", (rid,))
        event(db, rid, 'CADASTRO_REQUER_CORRECAO', 'whatsapp')
        db.execute('UPDATE reservations SET version=version+1,updated_at=? WHERE id=?', (now(), rid))
        return reply('A recepcao precisa corrigir o cadastro. Nao envie CPF completo nem foto do documento por aqui.', True)
    elif stage == 'NAME' and command in ('sim','confirmar nome'):
        db.execute("UPDATE reservations SET stage='DOCUMENT' WHERE id=?", (rid,))
        text = 'O CPF cadastrado termina em '+reservation['cpf'][-2:]+'. Confirme se corresponde ao documento informado na reserva: CONFIRMAR DADOS ou CORRIGIR. Nao envie o CPF completo. O documento sera conferido presencialmente.'
        action = 'NOME_CONFIRMADO'
    elif stage == 'DOCUMENT' and command in ('sim','confirmar dados'):
        db.execute("UPDATE reservations SET stage='REVIEW_FINAL' WHERE id=?", (rid,))
        dates = []
        if reservation['arrival']: dates.append('Chegada: '+date.fromisoformat(reservation['arrival']).strftime('%d/%m/%Y')+'.')
        if reservation['departure']: dates.append('Saida: '+date.fromisoformat(reservation['departure']).strftime('%d/%m/%Y')+'.')
        text = (' '.join(dates)+' ' if dates else '')+'Para concluir a confirmacao do cadastro, responda CONCLUIR. Isso nao libera o check-in: apresente seu documento na recepcao ao chegar.'
        action = 'DADOS_CONFIRMADOS'
    elif stage == 'REVIEW_FINAL' and command in ('concluir','concluir pre-check-in','sim'):
        db.execute("UPDATE reservations SET stage=NULL,pre_status='PRE_CHECKIN_CONCLUIDO' WHERE id=?", (rid,))
        text = 'Pre-check-in concluido e registrado. Ao chegar, apresente seu documento de identidade a recepcao para conferir e liberar o check-in.'
        action = 'PRE_CHECKIN_CONCLUIDO'
    elif re.search(r'check[ -]?out', normalized) and operational(message, normalized):
        if reservation['checkin_status'] != 'CHECK_IN_REALIZADO':
            return reply('Nao ha check-in realizado nesta reserva. A recepcao precisa conferir sua hospedagem.', True)
        if reservation['checkout_cleared']:
            close(db, rid)
            action = 'CHECK_OUT_REALIZADO'
            text = 'Checkout registrado. A recepcao havia liberado as pendencias desta hospedagem. Entregue as chaves a equipe presencial.'
        else:
            db.execute("UPDATE reservations SET checkout_status='PENDENTE_RECEPCAO' WHERE id=?", (rid,))
            event(db, rid, 'CHECKOUT_SOLICITADO', 'whatsapp')
            db.execute('UPDATE reservations SET version=version+1,updated_at=? WHERE id=?', (now(), rid))
            return reply('Solicitacao de checkout registrada. A recepcao precisa conferir pagamentos e pendencias antes de concluir sua saida.', True)
    elif re.search(r'check[ -]?in|minha reserva|status da reserva', normalized) and operational(message, normalized):
        if reservation['checkin_status'] == 'CHECK_IN_REALIZADO':
            return reply('Seu check-in foi realizado pela recepcao.'+(' Quarto registrado: '+reservation['room']+'.' if reservation['room'] else ' O quarto ainda nao foi informado no sistema.'))
        if reservation['pre_status'] == 'PRE_CHECKIN_CONCLUIDO':
            return reply('Sua reserva esta cadastrada e o pre-check-in foi concluido. Apresente o documento de identidade na recepcao para liberar o check-in.')
        return reply('Sua reserva esta cadastrada, mas o pre-check-in ainda nao foi concluido. Envie PRE-CHECK-IN para iniciar ou retomar.')
    if action:
        event(db, rid, action, 'whatsapp')
        db.execute('UPDATE reservations SET version=version+1,updated_at=? WHERE id=?', (now(), rid))
        return reply(text)
    return None


def issue_token(db, rid):
    token=secrets.token_urlsafe(32)
    expires=time.time()+72*3600
    db.execute('UPDATE reservation_links SET revoked=1 WHERE reservation_id=?',(rid,))
    db.execute('INSERT INTO reservation_links(token_hash,reservation_id,expires) VALUES (?,?,?)',
               (hashlib.sha256(token.encode()).hexdigest(),rid,expires))
    return token,expires


def invited(db, phone):
    ids=db.execute('''SELECT r.id FROM reservations r JOIN reservation_invitations i ON i.reservation_id=r.id
        WHERE r.phone=? AND i.phone=r.phone AND r.status IN ('RESERVA_CADASTRADA','LINK_GERADO','CHECK_IN_REALIZADO')
          AND EXISTS (SELECT 1 FROM reservation_links l WHERE l.reservation_id=r.id AND l.revoked=0 AND l.expires>?)''',
        (phone,time.time())).fetchall()
    return [row(db,found[0]) for found in ids]


def prepare_welcome(db, reservation):
    rid=reservation['id']
    welcome_id='reservation-welcome-'+rid+'-'+str(reservation['version'])
    protocol=delivery.public_protocol(db,'reservation:'+rid)
    first=reservation['guest_name'].split()[0]
    text=(f'Olá, {first}! 👋\n\nSeja muito bem-vindo(a) ao Hotel Aura. ✨\n\n'
          'Sua reserva foi registrada. Queremos tornar sua experiência simples e confortável.\n\n'
          'Você já tem acesso à nossa Hostess exclusiva pelo WhatsApp: faça seu pré-check-in antes de chegar, '
          'consulte informações da sua hospedagem e conte com nosso atendimento durante a estadia.\n\n'
          'Para começar, responda a esta mensagem com:\n\nINICIAR\n\nProtocolo: '+protocol)
    if operating_mode.production():
        welcome=knowledge_engine.load_base()[0].get('POL-00')
        if not welcome:raise ValueError('Valide a política de boas-vindas para produção antes de enviar.')
        text=welcome['content']+'\n\nSua reserva foi registrada. Para iniciar o atendimento, responda INICIAR. Protocolo: '+protocol
    text=delivery.display_text(text)
    response={'request_id':welcome_id,'persisted':True,'reply':text,'route':'TOOL_ACTION',
              'policy_ids':[],'sources':[],'ai_used':False,'answer_mode':'reservation_welcome','mode':'local_demo'}
    operating_mode.stamp(response)
    if operating_mode.production():response['knowledge_version']=knowledge_engine.load_base()[1]
    db.execute('INSERT INTO interactions VALUES (?,?,?,?,?)',
               (welcome_id,'waha_'+reservation['phone']+'_c_us','[boas-vindas da reserva]',json.dumps(response,ensure_ascii=False),now()))
    db.execute('INSERT INTO reservation_invitations VALUES (?,?,?,?)',
               (rid,reservation['phone'],welcome_id,now()))


def add_metadata(db, reservation):
    reservation['public_protocol']=delivery.public_protocol(db,'reservation:'+reservation['id'])
    found=db.execute('''SELECT d.status,d.updated_at FROM reservation_invitations i
        LEFT JOIN whatsapp_deliveries d ON d.request_id=i.welcome_id WHERE i.reservation_id=?''',
        (reservation['id'],)).fetchone()
    status=found[0] if found and found[0] else 'not_sent'
    if status=='sending' and time.time()-datetime.fromisoformat(found[1]).timestamp()>120:
        db.execute("UPDATE whatsapp_deliveries SET status='unknown',error_code='interrupted',updated_at=? WHERE request_id=(SELECT welcome_id FROM reservation_invitations WHERE reservation_id=?)",
                   (now(),reservation['id']))
        status='unknown'
    reservation['welcome_status']=status


def send_welcome(connection, body, actor, transport=None):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        reservation=row(db,body.get('id'))
        if reservation['status']=='CHECK_OUT_REALIZADO':
            raise ValueError('Reserva encerrada; envio bloqueado.')
        invitation=db.execute('SELECT welcome_id FROM reservation_invitations WHERE reservation_id=?',(reservation['id'],)).fetchone()
        if not invitation:
            if body.get('version')!=reservation['version']:
                raise Conflict('Reserva alterada. Atualize a tela antes de enviar.')
            issue_token(db,reservation['id'])
            prepare_welcome(db,reservation)
            event(db,reservation['id'],'BOAS_VINDAS_SOLICITADAS',actor)
            db.execute('UPDATE reservations SET version=version+1,updated_at=? WHERE id=?',(now(),reservation['id']))
            invitation=db.execute('SELECT welcome_id FROM reservation_invitations WHERE reservation_id=?',(reservation['id'],)).fetchone()
        welcome_id=invitation[0]
        session=db.execute('SELECT session_id FROM interactions WHERE id=?',(welcome_id,)).fetchone()[0]
        # Prepared records from the earlier version may not have been sent yet.
        if not db.execute('SELECT 1 FROM whatsapp_deliveries WHERE request_id=?',(welcome_id,)).fetchone():
            if not db.execute('SELECT 1 FROM reservation_links WHERE reservation_id=? AND revoked=0 AND expires>?',(reservation['id'],time.time())).fetchone():
                issue_token(db,reservation['id'])
    sent=delivery.deliver(connection,welcome_id,session,transport)
    return {'saved':True,'reservation':detail(connection,reservation['id']),
            'welcome_status':sent['delivery_status'],'duplicate':sent['duplicate']}


def change(connection, body, actor, transport=None):
    if body.get('action')=='welcome':
        return send_welcome(connection,body,actor,transport)
    result=_change(connection,body,actor)
    result['reservation']=detail(connection,result['reservation']['id'])
    return result
