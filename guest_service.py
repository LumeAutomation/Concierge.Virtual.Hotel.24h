"""Guest service requests, staff conversation ownership and local experience metrics."""
import operating_mode
import hashlib
import json
import re
import sqlite3
from datetime import timedelta
import conversation_state as state
import reservations


def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS service_requests (
          id TEXT PRIMARY KEY REFERENCES handoffs(id), reservation_id TEXT,
          room TEXT, kind TEXT NOT NULL, quantity INTEGER,
          guest_feedback TEXT, feedback_at TEXT, first_claimed_at TEXT);
        CREATE TABLE IF NOT EXISTS human_conversations (
          session_id TEXT PRIMARY KEY, handoff_id TEXT NOT NULL, operator TEXT NOT NULL,
          started_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS staff_messages (
          request_id TEXT PRIMARY KEY, handoff_id TEXT NOT NULL, operator TEXT NOT NULL,
          action TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        columns={r[1] for r in db.execute('PRAGMA table_info(service_requests)')}
        if 'first_claimed_at' not in columns:db.execute('ALTER TABLE service_requests ADD COLUMN first_claimed_at TEXT')


def answer(text,mode='service_status'):
    return dict(route='AUTO_REPLY',reply=text,policy_ids=[],answer_mode=mode,ai_used=False)


def capture(db,rid,session,message,department):
    reservation=reservations.bound_reservation(db,session)
    valid=reservation and reservation['status']=='CHECK_IN_REALIZADO'
    kind='toalhas' if re.search(r'\btoalhas?\b',message) else department
    match=re.search(r'\b(\d{1,2}|uma|duas|tres|quatro|cinco)\s+toalhas?\b',message)
    words={'uma':1,'duas':2,'tres':3,'quatro':4,'cinco':5}
    quantity=(words.get(match[1]) or int(match[1])) if match else None
    if quantity is not None and not 1<=quantity<=20:quantity=None
    db.execute('INSERT INTO service_requests(id,reservation_id,room,kind,quantity) VALUES (?,?,?,?,?)',
               (rid,reservation['id'] if valid else None,reservation['room'] if valid else None,kind,quantity))
    if kind=='toalhas':
        return 'Registrei seu pedido de '+(str(quantity)+' toalhas' if quantity else 'toalhas')+' para a governança. '+('A hospedagem está vinculada ao pedido.' if valid else 'A equipe precisa conferir sua hospedagem antes da entrega.')+' Você pode perguntar: como está meu pedido?'


def handle(db,session,message):
    active=db.execute('SELECT handoff_id FROM human_conversations WHERE session_id=?',(session,)).fetchone()
    if active:
        return dict(route='HUMAN_TAKEOVER',reply='Mensagem registrada para a equipe. A Hostess está pausada.',policy_ids=[],answer_mode='human_takeover',ai_used=False,suppress_response=True,handoff_id=active[0])
    if message.strip(' .!?') in ('obrigado','obrigada','muito obrigado','muito obrigada','valeu','ok','certo','entendi'):
        return answer('Por nada! Estou à disposição se precisar de mais alguma coisa.','courtesy')
    cancel=message.strip(' .!?') in ('cancelar meu pedido','desisti do pedido','cancelar pedido de toalhas','nao preciso mais das toalhas')
    status=bool(re.fullmatch(r'(?:como esta|qual (?:e )?o status (?:do)?|status (?:do)?|acompanhar)\s*(?:o )?(?:meu )?(?:pedido|atendimento)[ .!?]*',message))
    feedback=message.strip(' .!?') in ('recebi as toalhas','nao recebi as toalhas')
    if not status and not feedback and not cancel:return None
    rows=db.execute('''SELECT h.id,h.status,s.kind FROM handoffs h JOIN interactions i ON i.id=h.id
      LEFT JOIN service_requests s ON s.id=h.id WHERE i.session_id=?
      ORDER BY CASE WHEN h.status='resolved' THEN 1 ELSE 0 END,i.created_at DESC LIMIT 6''',(session,)).fetchall()
    if cancel:
        opened=[r for r in rows if r[1]!='resolved']
        if len(opened)!=1 or opened[0][2]!='toalhas':return answer('A recepção precisa conferir qual pedido pode ser cancelado.','clarification')
        rid,current,_=opened[0]
        if current!='open':return answer('Seu pedido já está em atendimento. Peça à equipe para conferir se ainda é possível cancelar.')
        db.execute("UPDATE handoffs SET status='resolved' WHERE id=?",(rid,))
        db.execute("UPDATE service_requests SET guest_feedback='cancelled',feedback_at=? WHERE id=?",(state.utcnow().isoformat(),rid))
        return answer('Seu pedido de toalhas foi cancelado antes de ser assumido pela equipe.','service_cancelled')
    if feedback:
        rows=[r for r in rows if r[2]=='toalhas']
        if len(rows)!=1:return answer('Informe à recepção qual pedido de toalhas precisa conferir.','clarification')
        rid,current,_=rows[0]
        value='not_received' if message.startswith('nao') else 'received'
        db.execute('UPDATE service_requests SET guest_feedback=?,feedback_at=? WHERE id=?',(value,state.utcnow().isoformat(),rid))
        if value=='not_received':
            # Reopen the same ticket without claiming a second delivery or repeating its notification.
            db.execute("UPDATE handoffs SET status='open' WHERE id=?",(rid,))
            db.execute('DELETE FROM handoff_work WHERE id=?',(rid,))
            return answer('Registrei que as toalhas não chegaram. Seu pedido está novamente na fila da governança para conferência.','service_feedback')
        return answer('Obrigado por confirmar o recebimento das toalhas!','service_feedback')
    if not rows:return answer('Não encontrei pedidos registrados nesta conversa. Como posso ajudar?')
    labels={'open':'aguardando atendimento','in_progress':'em atendimento','resolved':'concluído pela equipe'}
    lines=[]
    for rid,current,_ in rows:
        feedback_row=db.execute('SELECT guest_feedback FROM service_requests WHERE id=?',(rid,)).fetchone()
        label='cancelado pelo hóspede' if feedback_row and feedback_row[0]=='cancelled' else labels[current]
        lines.append(state.public_protocol(db,'interaction:'+rid)+': '+label+'.')
    return answer('\n'.join(lines))


def enrich(db,rows):
    for row in rows:
        item=db.execute('SELECT reservation_id,room,kind,quantity,guest_feedback FROM service_requests WHERE id=?',(row['id'],)).fetchone()
        row['service']=dict(zip(('reservation_id','room','kind','quantity','guest_feedback'),item)) if item else None
        row['human_operator']=None
        session=db.execute('SELECT session_id FROM interactions WHERE id=?',(row['id'],)).fetchone()[0]
        human=db.execute('SELECT operator FROM human_conversations WHERE session_id=?',(session,)).fetchone()
        if human:row['human_operator']=human[0]
        row['waiting_minutes']=max(0,int((state.utcnow()-state.utcnow().fromisoformat(row['created_at'])).total_seconds()/60))
    return rows


def thread(connection,rid):
    with connection() as db:
        row=db.execute('SELECT i.session_id FROM handoffs h JOIN interactions i ON i.id=h.id WHERE h.id=?',(rid,)).fetchone()
        if not row:raise ValueError('Atendimento não encontrado.')
        items=db.execute('SELECT id,message,response,created_at FROM interactions WHERE session_id=? ORDER BY created_at DESC,rowid DESC LIMIT 30',(row[0],)).fetchall()
        out=[]
        for mid,message,raw,created in reversed(items):
            response=json.loads(raw)
            staff=db.execute('SELECT operator FROM staff_messages WHERE request_id=?',(mid,)).fetchone()
            if not staff:out.append(dict(role='guest',text=message,created_at=created))
            if response.get('reply') and not response.get('suppress_response'):out.append(dict(role='staff' if staff else 'bot',operator=staff[0] if staff else None,text=response['reply'],created_at=created))
        return out


def staff_action(connection,body,operator,transport=None,allow_notification=None):
    rid,action=body.get('id'),body.get('action')
    if not isinstance(rid,str) or action not in ('takeover','release','message','notify_start'):raise ValueError('Ação inválida.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('''SELECT i.session_id,h.status,w.operator FROM handoffs h JOIN interactions i ON i.id=h.id
        LEFT JOIN handoff_work w ON w.id=h.id WHERE h.id=?''',(rid,)).fetchone()
        if not row or row[1]!='in_progress' or row[2]!=operator:raise ValueError('Assuma este atendimento antes de agir.')
        session=row[0]
        owner=db.execute('SELECT operator,handoff_id FROM human_conversations WHERE session_id=?',(session,)).fetchone()
        if owner and (owner[0]!=operator or owner[1]!=rid):raise ValueError('Esta conversa já está sob atendimento humano em outro protocolo.')
        if action=='takeover':
            db.execute('INSERT OR IGNORE INTO human_conversations VALUES (?,?,?,?)',(session,rid,operator,state.utcnow().isoformat()))
            return dict(updated=True,human_mode=True)
        if action=='release':
            db.execute('DELETE FROM human_conversations WHERE session_id=? AND handoff_id=?',(session,rid))
            return dict(updated=True,human_mode=False)
        text=body.get('text','').strip() if isinstance(body.get('text',''),str) else ''
        mid=body.get('request_id')
        if action=='notify_start':
            mid='staff-start-'+hashlib.sha256(rid.encode()).hexdigest()
            text='A equipe começou a atender seu pedido. Protocolo: '+state.public_protocol(db,'interaction:'+rid)+'.'
        if not isinstance(mid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,160}',mid) or not 1<=len(text)<=2000:raise ValueError('Informe mensagem e identificador válidos.')
        if re.fullmatch(r'waha_\d{6,20}_(c_us|lid)',session) and (allow_notification is None or not allow_notification(session)):
            raise ValueError('Contato sem acesso autorizado para envio.')
        previous=db.execute('SELECT session_id,response FROM interactions WHERE id=?',(mid,)).fetchone()
        if previous:
            recorded=db.execute('SELECT handoff_id,operator,action FROM staff_messages WHERE request_id=?',(mid,)).fetchone()
            if previous[0]!=session or json.loads(previous[1])['reply']!=text or recorded!=(rid,operator,action):raise ValueError('Identificador já utilizado.')
        else:
            result=dict(route='STAFF_REPLY',reply=text,policy_ids=[],ai_used=False,persisted=True,request_id=mid)
            operating_mode.stamp(result)
            db.execute('INSERT INTO interactions VALUES (?,?,?,?,?)',(mid,session,'[mensagem da equipe]',json.dumps(result,ensure_ascii=False),state.utcnow().isoformat()))
            db.execute('INSERT INTO staff_messages VALUES (?,?,?,?,?)',(mid,rid,operator,action,state.utcnow().isoformat()))
    if not session.startswith('waha_'):return dict(updated=True,delivery_status='local_only')
    return dict(updated=True,**state.deliver(connection,mid,session,transport))


def metrics(connection):
    with connection() as db:
        cutoff=(state.utcnow()-timedelta(minutes=15)).isoformat()
        counts=dict(db.execute('SELECT status,count(*) FROM handoffs GROUP BY status'))
        waiting=db.execute("SELECT count(*) FROM handoffs h JOIN interactions i ON i.id=h.id WHERE h.status='open' AND i.created_at<?",(cutoff,)).fetchone()[0]
        mean=db.execute('SELECT avg((julianday(COALESCE(s.first_claimed_at,w.claimed_at))-julianday(i.created_at))*1440) FROM handoffs h JOIN interactions i ON i.id=h.id LEFT JOIN handoff_work w ON w.id=h.id LEFT JOIN service_requests s ON s.id=h.id').fetchone()[0]
        stalled=(state.utcnow()-timedelta(minutes=2)).isoformat()
        unresolved=db.execute("SELECT count(*) FROM whatsapp_deliveries WHERE status='unknown' OR (status='sending' AND updated_at<?)",(stalled,)).fetchone()[0]
        unresolved+=db.execute("SELECT count(*) FROM handoff_work WHERE notification_status IN ('unknown','blocked') OR (notification_status='sending' AND completed_at<?)",(stalled,)).fetchone()[0]
        feedback=dict(db.execute('SELECT guest_feedback,count(*) FROM service_requests WHERE guest_feedback IS NOT NULL GROUP BY guest_feedback'))
        counts['cancelled']=feedback.get('cancelled',0)
        counts['resolved']=max(0,counts.get('resolved',0)-counts['cancelled'])
        unknown=[]
        for message,raw in db.execute('SELECT message,response FROM interactions ORDER BY created_at DESC LIMIT 500'):
            response=json.loads(raw)
            if response.get('answer_mode')=='knowledge_gap':unknown.append(message)
        return dict(counts=counts,waiting_over_15_minutes=waiting,mean_first_service_minutes=round(max(0,mean),1) if mean is not None else None,
                    delivery_attention=unresolved,feedback=feedback,knowledge_gaps=unknown[:10],knowledge_gaps_sample=len(unknown),sample_limit=500)
