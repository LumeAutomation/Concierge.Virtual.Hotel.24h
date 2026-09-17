"""Explicit operating mode and revision-bound production policy approval."""
import json,re,unicodedata
from datetime import datetime,timezone
CONNECTION=None
class Conflict(ValueError):pass

def now():return datetime.now(timezone.utc).isoformat()
def init_schema(connection):
    with connection() as db:db.executescript('''
    CREATE TABLE IF NOT EXISTS operating_mode (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, mode TEXT NOT NULL, identity_revision INTEGER);
    CREATE TABLE IF NOT EXISTS operating_mode_history (id INTEGER PRIMARY KEY, actor TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS production_policy_approvals (policy_id TEXT PRIMARY KEY, published_revision INTEGER NOT NULL, actor TEXT NOT NULL, approved_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS production_policy_history (id INTEGER PRIMARY KEY, policy_id TEXT NOT NULL, published_revision INTEGER NOT NULL, actor TEXT NOT NULL, approved_at TEXT NOT NULL);
    ''')
def get(db=None):
    if db is None:
        if CONNECTION is None:return dict(mode='demonstration',revision=0,identity_revision=None)
        with CONNECTION() as conn:return get(conn)
    row=db.execute('SELECT mode,revision,identity_revision FROM operating_mode WHERE id=1').fetchone()
    return dict(zip(('mode','revision','identity_revision'),row)) if row else dict(mode='demonstration',revision=0,identity_revision=None)
def production():return get()['mode']=='production'
def demo_text(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
    return bool(re.search(r'fictici|demonstr|\.example\b',text))
def save(connection,body,actor):
    target=body.get('mode');revision=body.get('revision')
    if target not in ('demonstration','production') or type(revision) is not int:raise ValueError('Modo ou revisão inválida.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');current=get(db)
        if revision!=current['revision']:raise Conflict('Modo alterado por outra pessoa. Recarregue.')
        identity=None
        if body.get('confirm_identity') is True:
            row=db.execute('SELECT revision,data FROM hotel_profile WHERE id=1').fetchone()
            if not row or body.get('identity_revision')!=row[0]:raise Conflict('Salve e confira a identidade atual antes de validá-la.')
            if demo_text(row[1]):raise ValueError('Substitua os dados demonstrativos da identidade antes de validar para produção.')
            identity=row[0]
        db.execute('INSERT INTO operating_mode VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,mode=excluded.mode,identity_revision=excluded.identity_revision',(revision+1,target,identity))
        db.execute('INSERT INTO operating_mode_history(actor,created_at,data) VALUES (?,?,?)',(actor,now(),json.dumps(dict(mode=target,revision=revision+1,identity_revision=identity))))
    return dict(updated=True,mode=target,revision=revision+1,identity_revision=identity)
def approve(connection,body,actor):
    if body.get('confirm_real_content') is not True:raise ValueError('Confirme a conferência do conteúdo real do hotel.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT published_revision,published,revision FROM policy_reviews WHERE id=?',(body.get('id'),)).fetchone()
        if not row or not row[1] or row[0]!=body.get('published_revision') or row[0]!=row[2]:raise Conflict('Publique a revisão atual antes de validar para produção.')
        if demo_text(row[1]):raise ValueError('O texto ainda contém indicação demonstrativa. Revise antes de validar.')
        stamp=now()
        db.execute('INSERT INTO production_policy_approvals VALUES (?,?,?,?) ON CONFLICT(policy_id) DO UPDATE SET published_revision=excluded.published_revision,actor=excluded.actor,approved_at=excluded.approved_at',(body['id'],row[0],actor,stamp))
        db.execute('INSERT INTO production_policy_history(policy_id,published_revision,actor,approved_at) VALUES (?,?,?,?)',(body['id'],row[0],actor,stamp))
    return dict(updated=True,production_approved=True)
def approved_ids(connection=None):
    connection=connection or CONNECTION
    if not connection:return set()
    with connection() as db:
        return {r[0] for r in db.execute('SELECT a.policy_id FROM production_policy_approvals a JOIN policy_reviews r ON r.id=a.policy_id WHERE a.published_revision=r.published_revision AND r.published IS NOT NULL')}
def stamp(result):
    result['mode']='production' if production() else 'local_demo'
    result['mode_revision']=get()['revision']
    return result
