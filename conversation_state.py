"""Estado local de conversa e envio: uma tentativa automatica por mensagem."""
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent

def utcnow(): return datetime.now(timezone.utc)

def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS conversation_contexts (
          request_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, message TEXT NOT NULL,
          history TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS whatsapp_deliveries (
          request_id TEXT PRIMARY KEY REFERENCES interactions(id), status TEXT NOT NULL,
          provider_id TEXT, updated_at TEXT NOT NULL, error_code TEXT);
        CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY);
        CREATE INDEX IF NOT EXISTS interactions_session_created ON interactions(session_id,created_at);
        ''')
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM schema_migrations WHERE name='whatsapp_deliveries_v1'").fetchone():
            # Antigas interacoes podem ja ter sido respondidas pelo no anterior.
            db.execute("INSERT OR IGNORE INTO whatsapp_deliveries(request_id,status,updated_at) SELECT id,'legacy_unverified',? FROM interactions WHERE session_id LIKE 'waha_%'",(utcnow().isoformat(),))
            db.execute("INSERT INTO schema_migrations(name) VALUES ('whatsapp_deliveries_v1')")

def is_followup(message):
    return bool(re.match(r'^(?:e\b|aos domingos\b|no domingo\b|nesse caso\b|e nesse\b)',message.strip().lower()))

def snapshot(connection,request_id,session_id,message,is_sensitive):
    now=utcnow(); cutoff=now-timedelta(minutes=30)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT session_id,message,history FROM conversation_contexts WHERE request_id=?',(request_id,)).fetchone()
        if previous:
            if previous[0]!=session_id or previous[1]!=message:
                raise ValueError('Protocolo de contexto ja utilizado.')
            return json.loads(previous[2])
        recent=db.execute('SELECT message,response,created_at FROM interactions WHERE session_id=? AND id!=? ORDER BY created_at DESC,rowid DESC LIMIT 3',(session_id,request_id)).fetchall()
        pairs=[]
        for text,raw,created in recent:
            result=json.loads(raw)
            if datetime.fromisoformat(created)<cutoff: break
            if is_sensitive(text) or text=='[conteúdo sensível omitido]': break
            if result.get('route')!='AUTO_REPLY' or not result.get('policy_ids'): break
            # Contexto e apenas para identificar o assunto; politicas atuais prevalecem.
            pairs.append([{'role':'user','content':text[:2000]},{'role':'assistant','content':result['reply'][:2200]}])
        history=[item for pair in reversed(pairs) for item in pair]
        db.execute('DELETE FROM conversation_contexts WHERE created_at<?',(cutoff.isoformat(),))
        db.execute('INSERT INTO conversation_contexts VALUES (?,?,?,?,?)',(request_id,session_id,message,json.dumps(history,ensure_ascii=False),now.isoformat()))
    return history

def send_waha(payload):
    values=dict(line.split('=',1) for line in (ROOT/'runtime/waha/.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
    key=values.get('WAHA_API_KEY')
    if not key: raise ValueError('Credencial WAHA ausente.')
    request=Request('http://127.0.0.1:3000/api/sendText',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Api-Key':key})
    with urlopen(request,timeout=20) as response:
        result=json.load(response)
    if not isinstance(result,dict) or not result.get('id'):
        raise ValueError('WAHA nao retornou identificador.')
    return result['id']

def deliver(connection,request_id,session_id,transport=None):
    if not isinstance(request_id,str) or not isinstance(session_id,str): raise ValueError('Identificacao invalida.')
    now=utcnow()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT session_id,response FROM interactions WHERE id=?',(request_id,)).fetchone()
        if not row or row[0]!=session_id: raise ValueError('Resposta persistida nao pertence a conversa.')
        match=re.fullmatch(r'waha_(\d{6,20})_(c_us|lid)',session_id)
        result=json.loads(row[1])
        if not match or result.get('persisted') is not True or not isinstance(result.get('reply'),str) or not result['reply'].strip():
            raise ValueError('Resposta ou destino invalido.')
        existing=db.execute('SELECT status,updated_at FROM whatsapp_deliveries WHERE request_id=?',(request_id,)).fetchone()
        if existing:
            status,updated=existing
            if status=='sending' and now-datetime.fromisoformat(updated)>timedelta(minutes=2):
                status='unknown'
                db.execute("UPDATE whatsapp_deliveries SET status='unknown',error_code='interrupted',updated_at=? WHERE request_id=?",(now.isoformat(),request_id))
            return {'request_id':request_id,'delivery_status':status,'duplicate':True,'needs_review':status=='unknown'}
        db.execute("INSERT INTO whatsapp_deliveries(request_id,status,updated_at) VALUES (?,'sending',?)",(request_id,now.isoformat()))
    chat_id=match[1]+('@c.us' if match[2]=='c_us' else '@lid')
    payload={'session':'default','chatId':chat_id,'text':'AURA | Demonstracao\n\n'+result['reply'],'linkPreview':False}
    try:
        provider_id=(transport or send_waha)(payload)
        if not provider_id: raise ValueError('Identificador de envio vazio.')
    except Exception as error:
        # Timeout/queda pode acontecer depois da entrega. Nunca reenviar automaticamente.
        with connection() as db:
            db.execute("UPDATE whatsapp_deliveries SET status='unknown',error_code=?,updated_at=? WHERE request_id=?",(type(error).__name__,utcnow().isoformat(),request_id))
        return {'request_id':request_id,'delivery_status':'unknown','duplicate':False,'needs_review':True}
    with connection() as db:
        db.execute("UPDATE whatsapp_deliveries SET status='sent',provider_id=?,updated_at=? WHERE request_id=?",(json.dumps(provider_id),utcnow().isoformat(),request_id))
    return {'request_id':request_id,'delivery_status':'sent','duplicate':False,'needs_review':False}

def list_deliveries(connection):
    with connection() as db:
        db.row_factory=sqlite3.Row
        return [dict(r) for r in db.execute('SELECT request_id,status,updated_at,error_code FROM whatsapp_deliveries ORDER BY updated_at DESC LIMIT 50')]
