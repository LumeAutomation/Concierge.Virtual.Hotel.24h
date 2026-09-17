"""Conclusao pela recepcao com uma tentativa de notificacao por protocolo."""
import guest_service
import json
import re
import sqlite3
from datetime import timedelta
import conversation_state as state


def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS handoff_work (
          id TEXT PRIMARY KEY REFERENCES handoffs(id), operator TEXT NOT NULL,
          claimed_at TEXT NOT NULL, completed_at TEXT,
          notification_status TEXT NOT NULL DEFAULT 'not_requested',
          notification_text TEXT, provider_id TEXT, error_code TEXT);
        ''')


def update(connection, body, transport=None, allow_notification=None):
    if not isinstance(body, dict): raise ValueError('Dados invalidos.')
    rid, target, operator = body.get('id'), body.get('status'), body.get('operator')
    if not isinstance(rid,str) or target not in ('in_progress','resolved'):
        raise ValueError('Acao invalida.')
    if not isinstance(operator,str) or not 2 <= len(operator.strip()) <= 80:
        raise ValueError('Informe seu nome (2 a 80 caracteres).')
    operator=operator.strip()
    now=state.utcnow().isoformat()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT h.status,i.session_id FROM handoffs h JOIN interactions i ON i.id=h.id WHERE h.id=?',(rid,)).fetchone()
        if not row: return {'updated':False}
        work=db.execute('SELECT operator,notification_status FROM handoff_work WHERE id=?',(rid,)).fetchone()
        if row[0]=='resolved':
            if target!='resolved': raise ValueError('Atendimento ja concluido.')
            return {'updated':True,'duplicate':True,'notification_status':work[1] if work else 'not_requested'}
        if work and work[0]!=operator: raise ValueError('Atendimento assumido por outra pessoa.')
        if target=='in_progress':
            db.execute('INSERT OR IGNORE INTO handoff_work(id,operator,claimed_at) VALUES (?,?,?)',(rid,operator,now))
            db.execute("UPDATE handoffs SET status='in_progress' WHERE id=?",(rid,))
            db.execute('UPDATE service_requests SET first_claimed_at=COALESCE(first_claimed_at,?) WHERE id=?',(now,rid))
            return {'updated':True,'notification_status':'not_requested'}
        if row[0]!='in_progress' or not work: raise ValueError('Assuma o atendimento antes de concluir.')
        match=re.fullmatch(r'waha_(\d{6,20})_(c_us|lid)',row[1])
        authorized = not match or allow_notification is None or allow_notification(row[1])
        status='blocked' if not authorized else 'sending' if match else 'local_only'
        text='Hostess do Hotel Aura\n\nA recepcao marcou seu atendimento como concluido. Protocolo: '+state.public_protocol(db,'interaction:'+rid)+'. Se ainda precisar de ajuda, responda com sua mensagem.'
        db.execute("UPDATE handoffs SET status='resolved' WHERE id=?",(rid,))
        db.execute('DELETE FROM human_conversations WHERE handoff_id=?',(rid,))
        service=db.execute('SELECT kind FROM service_requests WHERE id=?',(rid,)).fetchone()
        if service and service[0]=='toalhas':text+=' As toalhas chegaram? Responda RECEBI AS TOALHAS ou NÃO RECEBI AS TOALHAS.'
        text=state.display_text(text)
        db.execute('UPDATE handoff_work SET completed_at=?,notification_status=?,notification_text=? WHERE id=?',(now,status,text,rid))
    if not match or not authorized: return {'updated':True,'notification_status':status}
    payload={'session':state.session_name(state.ROOT),'chatId':match[1]+('@c.us' if match[2]=='c_us' else '@lid'),'text':text,'linkPreview':False}
    try:
        provider=(transport or state.send_waha)(payload)
        if not provider: raise ValueError('Identificador ausente.')
        status,error='sent',None
    except Exception as exc:
        provider=None
        status,error='unknown',type(exc).__name__
    with connection() as db:
        db.execute('UPDATE handoff_work SET notification_status=?,provider_id=?,error_code=? WHERE id=?',(status,json.dumps(provider),error,rid))
    return {'updated':True,'notification_status':status}


def list_rows(connection):
    with connection() as db:
        cutoff=(state.utcnow()-timedelta(minutes=2)).isoformat()
        db.execute("UPDATE handoff_work SET notification_status='unknown',error_code='interrupted' WHERE notification_status='sending' AND completed_at<?",(cutoff,))
        db.row_factory=sqlite3.Row
        rows = [dict(r) for r in db.execute('''
          SELECT h.*,i.message,i.created_at,w.operator,w.claimed_at,w.completed_at,
            COALESCE(w.notification_status,'not_requested') notification_status,
            CASE WHEN i.session_id GLOB 'waha_*' THEN 'WhatsApp' ELSE 'Painel local' END channel
          FROM handoffs h JOIN interactions i ON h.id=i.id LEFT JOIN handoff_work w ON w.id=h.id
          ORDER BY CASE h.status WHEN 'resolved' THEN 1 ELSE 0 END,
            CASE h.priority WHEN 'urgent' THEN 0 ELSE 1 END,i.created_at DESC LIMIT 200
        ''')]

        for row in rows: row['public_protocol']=state.public_protocol(db,'interaction:'+row['id'])
        return guest_service.enrich(db,rows)
