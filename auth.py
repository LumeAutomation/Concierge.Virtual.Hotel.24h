"""Staff accounts, revocable sessions and explicit pilot contacts."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie

ROLES = {'admin': {'reception','policies','edit','approve','operations','users','settings'},
         'recepcao': {'reception'}, 'editor': {'policies','edit'},
         'gestor': {'reception','policies','edit','approve','operations','settings'}}
COOKIE = 'aura_session'
TTL = 8 * 3600


def init_schema(connection):
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS staff_users (
          username TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
          password TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          must_change INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS staff_sessions (
          token TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (
          key TEXT PRIMARY KEY, failures INTEGER NOT NULL, until REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS access_audit (
          id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
          target TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS pilot_contacts (
          session_id TEXT PRIMARY KEY, label TEXT NOT NULL, active INTEGER NOT NULL);
        ''')


def password_hash(password):
    if not isinstance(password,str) or not 12 <= len(password) <= 128:
        raise ValueError('Use uma senha de 12 a 128 caracteres.')
    salt=secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()


def verify(password,encoded):
    if not isinstance(password,str) or len(password)>128: return False
    salt,digest=encoded.split(':')
    actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()
    return hmac.compare_digest(actual,digest)


def audit(db,actor,action,target):
    db.execute('INSERT INTO access_audit(actor,action,target,created_at) VALUES (?,?,?,?)',
               (actor,action,target,time.time()))


def create_user(connection,body,actor='setup'):
    username=str(body.get('username','')).strip().lower()
    name,role=body.get('name'),body.get('role')
    if not re.fullmatch(r'[a-z0-9_.-]{3,40}',username):
        raise ValueError('Login: 3 a 40 letras, numeros, ponto, traco ou sublinhado.')
    if not isinstance(name,str) or not 2<=len(name.strip())<=60 or not isinstance(role,str) or role not in ROLES:
        raise ValueError('Nome ou perfil invalido.')
    encoded=password_hash(body.get('password'))
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM staff_users WHERE username=?',(username,)).fetchone():
            raise ValueError('Login ja cadastrado.')
        db.execute('INSERT INTO staff_users(username,name,role,password) VALUES (?,?,?,?)',(username,name.strip(),role,encoded))
        audit(db,actor,'create_user',username)
    return {'created':True}


def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()


def login(connection,username,password):
    username=str(username or '').lower().strip()[:40]; now=time.time()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for key in ('all','user:'+username):
            row=db.execute('SELECT failures,until FROM login_attempts WHERE key=?',(key,)).fetchone()
            if row and row[1]>now and row[0]>=(30 if key=='all' else 5): return None
        row=db.execute('SELECT password,active FROM staff_users WHERE username=?',(username,)).fetchone()
        valid=verify(password,row[0] if row else 'aura-dummy:'+'0'*64)
        if not valid or not row or not row[1]:
            for key in ('all','user:'+username):
                db.execute('''INSERT INTO login_attempts VALUES (?,1,?) ON CONFLICT(key)
                  DO UPDATE SET failures=CASE WHEN until<? THEN 1 ELSE failures+1 END,
                  until=CASE WHEN until<? THEN excluded.until ELSE until END''',(key,now+900,now,now))
            db.execute('DELETE FROM login_attempts WHERE until<?',(now,))
            return None
        db.execute('DELETE FROM login_attempts WHERE key=?',('user:'+username,))
        token=secrets.token_urlsafe(32)
        db.execute('DELETE FROM staff_sessions WHERE expires<?',(now,))
        db.execute('INSERT INTO staff_sessions VALUES (?,?,?)',(token_hash(token),username,now+TTL))
        audit(db,username,'login',username)
        return token


def cookie_token(header):
    try:
        cookies=SimpleCookie(); cookies.load(header or '')
        return cookies[COOKIE].value if COOKIE in cookies else ''
    except Exception: return ''


def current(connection,token):
    with connection() as db:
        row=db.execute('''SELECT u.username,u.name,u.role,u.must_change
          FROM staff_sessions s JOIN staff_users u ON u.username=s.username
          WHERE s.token=? AND s.expires>? AND u.active=1''',(token_hash(token),time.time())).fetchone()
    if not row: return None
    return dict(username=row[0],name=row[1],role=row[2],must_change=bool(row[3]),permissions=sorted(ROLES[row[2]]))


def logout(connection,token):
    with connection() as db: db.execute('DELETE FROM staff_sessions WHERE token=?',(token_hash(token),))


def change_password(connection,user,old,new):
    encoded=password_hash(new)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT password FROM staff_users WHERE username=?',(user,)).fetchone()
        if not row or not verify(old,row[0]) or old==new:
            raise ValueError('Senha atual incorreta ou nova senha igual a atual.')
        db.execute('UPDATE staff_users SET password=?,must_change=0 WHERE username=?',(encoded,user))
        db.execute('DELETE FROM staff_sessions WHERE username=?',(user,))
        audit(db,user,'change_password',user)
    return {'changed':True}


def list_users(connection):
    with connection() as db:
        db.row_factory=sqlite3.Row
        return [dict(row) for row in db.execute('SELECT username,name,role,active,must_change FROM staff_users ORDER BY username')]


def update_user(connection,body,actor):
    username,role,active=body.get('username'),body.get('role'),body.get('active')
    if not isinstance(username,str) or not isinstance(role,str) or role not in ROLES or type(active) is not bool:
        raise ValueError('Perfil ou situacao invalida.')
    encoded=password_hash(body['password']) if body.get('password') else None
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT role,active FROM staff_users WHERE username=?',(username,)).fetchone()
        if not row: raise ValueError('Usuario nao encontrado.')
        if username==actor and (not active or role!='admin'):
            raise ValueError('Nao remova seu proprio acesso administrativo.')
        if row==('admin',1) and (not active or role!='admin'):
            if db.execute("SELECT count(*) FROM staff_users WHERE role='admin' AND active=1").fetchone()[0]<=1:
                raise ValueError('Mantenha pelo menos um administrador ativo.')
        db.execute('UPDATE staff_users SET role=?,active=? WHERE username=?',(role,int(active),username))
        if encoded: db.execute('UPDATE staff_users SET password=?,must_change=1 WHERE username=?',(encoded,username))
        db.execute('DELETE FROM staff_sessions WHERE username=?',(username,))
        audit(db,actor,'update_user',username)
    return {'updated':True}


def allowed_contact(connection,session):
    with connection() as db:
        return bool(db.execute('SELECT 1 FROM pilot_contacts WHERE session_id=? AND active=1',(session,)).fetchone())


def contacts(connection):
    with connection() as db:
        db.row_factory=sqlite3.Row
        return [dict(r) for r in db.execute('SELECT * FROM pilot_contacts ORDER BY label')]


def save_contact(connection,body,actor):
    identifier,kind=body.get('identifier',''),body.get('kind','c_us')
    label,active=body.get('label',''),body.get('active',True)
    if not isinstance(identifier,str) or not re.fullmatch(r'\d{6,20}',identifier) or kind not in ('c_us','lid'):
        raise ValueError('Use somente digitos do numero com DDI/DDD ou do LID confirmado.')
    if not isinstance(label,str) or not 2<=len(label.strip())<=60 or type(active) is not bool:
        raise ValueError('Nome ou situacao invalida.')
    session='waha_'+identifier+'_'+kind
    with connection() as db:
        db.execute('INSERT INTO pilot_contacts VALUES (?,?,?) ON CONFLICT(session_id) DO UPDATE SET label=excluded.label,active=excluded.active',(session,label.strip(),int(active)))
        audit(db,actor,'pilot_contact',session)
    return {'saved':True}
