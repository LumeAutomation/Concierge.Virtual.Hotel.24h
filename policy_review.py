"""Rascunhos e publicacao de politicas, com revisoes e controle de concorrencia."""
import json
import sqlite3
import re
from datetime import datetime, timezone

FIELDS={'title':160,'content':6000,'department':80,'example_question':300}
class Conflict(ValueError): pass


def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS custom_policies (id TEXT PRIMARY KEY, audience TEXT NOT NULL, created_at TEXT NOT NULL);
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
    policies = include_custom(connection, policies, published_only=True)
    for pid, raw in rows:
        if pid in policies:
            policies[pid]={**policies[pid],**json.loads(raw),'real_hotel_approval':'aprovada_localmente'}
    return policies


def catalog(connection, policies):
    policies = include_custom(connection, policies)
    with connection() as db:
        db.row_factory=sqlite3.Row
        saved={r['id']:dict(r) for r in db.execute('SELECT * FROM policy_reviews')}
    out=[]
    for pid in sorted(policies, key=policy_order):
        p = policies[pid]
        row=saved.get(pid,{})
        draft=json.loads(row['draft']) if row else {k:p[k] for k in FIELDS}
        published=json.loads(row['published']) if row.get('published') else None
        out.append({'id':pid,'audience':p['audience'],'revision':row.get('revision',0),
                    'draft':draft,'effective':published or {k:p[k] for k in FIELDS},
                    'approved_by':row.get('approved_by'),'approved_at':row.get('approved_at'),
                    'editor':row.get('editor'),'updated_at':row.get('updated_at'),
                    'published_revision':row.get('published_revision'), 'custom':p.get('custom',False), 'in_use':bool(published) or not p.get('custom',False),
                    'state':'approved' if published and row['revision']==row['published_revision'] else 'draft' if row else 'pending'})
    return out


def change(connection, policies, body):
    if not isinstance(body,dict): raise ValueError('Dados invalidos.')
    if body.get('action') == 'create': return create(connection, policies, body)
    policies = include_custom(connection, policies)
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


def policy_order(pid):
    match=re.fullmatch(r'POL-(\d+)',pid)
    return (0,int(match[1])) if match else (1,pid)


def include_custom(connection, policies, published_only=False):
    policies=dict(policies)
    with connection() as db:
        rows=db.execute('SELECT c.id,c.audience,r.draft,r.published FROM custom_policies c JOIN policy_reviews r ON r.id=c.id').fetchall()
    for pid,audience,draft,published in rows:
        if published_only and not published: continue
        fields=json.loads(published if published_only else draft)
        policies[pid]={'id':pid,'audience':audience,'status':'active','hotel_id':'aurora_grand_resort','version':2,'deployment_scope':'hotel_ficticio','custom':True,**fields}
    return policies


def create(connection, policies, body):
    draft,actor=body.get('draft'),body.get('actor')
    audience,publish=body.get('audience','guest'),body.get('publish',False)
    if audience not in ('guest','internal') or type(publish) is not bool:raise ValueError('Visibilidade ou publicacao invalida.')
    if not isinstance(actor,str) or not 2<=len(actor.strip())<=80:raise ValueError('Responsavel invalido.')
    if not isinstance(draft,dict) or set(draft)!=set(FIELDS):raise ValueError('Preencha todos os campos da politica.')
    for key,limit in FIELDS.items():
        if not isinstance(draft[key],str) or not 1<=len(draft[key].strip())<=limit:raise ValueError('Campo invalido: '+key)
    draft={k:v.strip() for k,v in draft.items()};raw=json.dumps(draft,ensure_ascii=False)
    now=datetime.now(timezone.utc).isoformat()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        ids=set(policies)|{r[0] for r in db.execute('SELECT id FROM custom_policies')}
        number=max([int(pid[4:]) for pid in ids if re.fullmatch(r'POL-\d+',pid)],default=0)+1
        pid=f'POL-{number:02d}'
        db.execute('INSERT INTO custom_policies VALUES (?,?,?)',(pid,audience,now))
        db.execute('INSERT INTO policy_reviews(id,revision,draft,editor,updated_at,published,approved_by,approved_at,published_revision) VALUES (?,1,?,?,?,?,?,?,?)',
                   (pid,raw,actor,now,raw if publish else None,actor if publish else None,now if publish else None,1 if publish else None))
        db.execute('INSERT INTO policy_review_history(policy_id,revision,action,actor,created_at,snapshot) VALUES (?,1,?,?,?,?)',(pid,'create_and_approve' if publish else 'create',actor,now,raw))
    return {'updated':True,'id':pid,'revision':1,'published':publish}
