"""Rascunhos e publicacao de politicas, com revisoes e controle de concorrencia."""
import json
import sqlite3
from datetime import datetime, timezone

FIELDS={'title':160,'content':6000,'department':80,'example_question':300}
class Conflict(ValueError): pass


def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS policy_reviews (
          id TEXT PRIMARY KEY, revision INTEGER NOT NULL, draft TEXT NOT NULL,
          editor TEXT NOT NULL, updated_at TEXT NOT NULL,
          published TEXT, approved_by TEXT, approved_at TEXT, published_revision INTEGER);
        CREATE TABLE IF NOT EXISTS policy_review_history (
          id INTEGER PRIMARY KEY, policy_id TEXT NOT NULL, revision INTEGER NOT NULL,
          action TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL, snapshot TEXT NOT NULL);
        ''')


def overlay(connection, policies):
    with connection() as db:
        rows=db.execute('SELECT id,published FROM policy_reviews WHERE published IS NOT NULL').fetchall()
    for pid, raw in rows:
        if pid in policies:
            policies[pid]={**policies[pid],**json.loads(raw),'real_hotel_approval':'aprovada_localmente'}
    return policies


def catalog(connection, policies):
    with connection() as db:
        db.row_factory=sqlite3.Row
        saved={r['id']:dict(r) for r in db.execute('SELECT * FROM policy_reviews')}
    out=[]
    for pid,p in policies.items():
        row=saved.get(pid,{})
        draft=json.loads(row['draft']) if row else {k:p[k] for k in FIELDS}
        published=json.loads(row['published']) if row.get('published') else None
        out.append({'id':pid,'audience':p['audience'],'revision':row.get('revision',0),
                    'draft':draft,'effective':published or {k:p[k] for k in FIELDS},
                    'approved_by':row.get('approved_by'),'approved_at':row.get('approved_at'),
                    'editor':row.get('editor'),'updated_at':row.get('updated_at'),
                    'published_revision':row.get('published_revision'),
                    'state':'approved' if published and row['revision']==row['published_revision'] else 'draft' if row else 'pending'})
    return out


def change(connection, policies, body):
    if not isinstance(body,dict): raise ValueError('Dados invalidos.')
    pid,action,actor,revision=body.get('id'),body.get('action'),body.get('actor'),body.get('revision')
    if not isinstance(pid,str) or pid not in policies or action not in ('save','approve'): raise ValueError('Politica ou acao invalida.')
    if not isinstance(actor,str) or not 2<=len(actor.strip())<=80: raise ValueError('Informe seu nome (2 a 80 caracteres).')
    if type(revision) is not int or revision<0: raise ValueError('Revisao invalida.')
    actor=actor.strip();now=datetime.now(timezone.utc).isoformat()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT revision,draft,published_revision FROM policy_reviews WHERE id=?',(pid,)).fetchone()
        if revision != (row[0] if row else 0): raise Conflict('Outra pessoa alterou esta politica. Recarregue antes de editar.')
        if action=='save':
            draft=body.get('draft')
            if not isinstance(draft,dict) or set(draft)!=set(FIELDS): raise ValueError('Campos de rascunho invalidos.')
            for key,limit in FIELDS.items():
                if not isinstance(draft[key],str) or not 1<=len(draft[key].strip())<=limit:
                    raise ValueError('Preencha '+key+' dentro do limite permitido.')
            draft={k:v.strip() for k,v in draft.items()};raw=json.dumps(draft,ensure_ascii=False);revision+=1
            db.execute('''INSERT INTO policy_reviews(id,revision,draft,editor,updated_at) VALUES (?,?,?,?,?)
                          ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,draft=excluded.draft,editor=excluded.editor,updated_at=excluded.updated_at''',(pid,revision,raw,actor,now))
        else:
            if not row: raise ValueError('Salve o rascunho antes de aprovar.')
            if row[2]==revision: return {'updated':True,'revision':revision,'duplicate':True}
            raw=row[1]
            db.execute('UPDATE policy_reviews SET published=?,approved_by=?,approved_at=?,published_revision=? WHERE id=?',(raw,actor,now,revision,pid))
        db.execute('INSERT INTO policy_review_history(policy_id,revision,action,actor,created_at,snapshot) VALUES (?,?,?,?,?,?)',(pid,revision,action,actor,now,raw))
    return {'updated':True,'revision':revision}
