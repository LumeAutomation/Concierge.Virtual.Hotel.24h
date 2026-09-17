"""Per-installation hotel identity and portable templates; never guest/runtime data."""
import operating_mode
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent
CONNECTION=None
LIMITS={'hotel_name':80,'assistant_name':40,'tagline':160,'primary_color':7,'address':240,
        'contact_email':160,'website':240,'reception_contact':400,'demo_notice':400}
class Conflict(ValueError):pass

def defaults():return json.loads((ROOT/'knowledge/hotel-profile.json').read_text(encoding='utf-8-sig'))

def validate(value):
    if not isinstance(value,dict) or set(value)!=set(LIMITS)|{'accommodation_count'}:raise ValueError('Campos de identificação inválidos.')
    for key,limit in LIMITS.items():
        if not isinstance(value[key],str) or not 1<=len(value[key].strip())<=limit:raise ValueError('Preencha corretamente: '+key)
        if any(ord(c)<32 for c in value[key]) or re.search(r'[<>]|\{\{|\}\}',value[key]):raise ValueError('Use texto simples em '+key)
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',value['primary_color']):raise ValueError('Informe uma cor hexadecimal válida.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value['contact_email']):raise ValueError('E-mail inválido.')
    url=urlsplit(value['website'])
    if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Informe um site HTTPS válido, sem credenciais.')
    if type(value['accommodation_count']) is not int or not 1<=value['accommodation_count']<=10000:raise ValueError('Quantidade de acomodações inválida.')
    return {k:v.strip() if isinstance(v,str) else v for k,v in value.items()}

def init_schema(connection):
    with connection() as db:db.executescript('''
    CREATE TABLE IF NOT EXISTS hotel_profile (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS hotel_profile_history (id INTEGER PRIMARY KEY, revision INTEGER NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL);
    ''')

def get(connection=None):
    connection=connection or CONNECTION
    if connection:
        with connection() as db:row=db.execute('SELECT revision,data FROM hotel_profile WHERE id=1').fetchone()
        if row:return {'revision':row[0],'profile':json.loads(row[1])}
    return {'revision':0,'profile':defaults()}

def save(connection,body,actor):
    profile=validate(body.get('profile'));revision=body.get('revision')
    if type(revision) is not int:raise ValueError('Revisão inválida.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT revision FROM hotel_profile WHERE id=1').fetchone()
        if revision!=(row[0] if row else 0):raise Conflict('Outra pessoa alterou a configuração. Recarregue antes de salvar.')
        raw=json.dumps(profile,ensure_ascii=False);revision+=1
        db.execute('INSERT INTO hotel_profile VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data',(revision,raw))
        db.execute('INSERT INTO hotel_profile_history(revision,actor,created_at,data) VALUES (?,?,?,?)',(revision,actor,datetime.now(timezone.utc).isoformat(),raw))
    return {'updated':True,'revision':revision,'profile':profile}

def render(text,profile=None):
    profile=profile or get()['profile']
    return re.sub(r'\{\{([a-z_]+)\}\}',lambda m:str(profile[m[1]]) if m[1] in profile else m[0],text)

def brand(text):
    profile=guest_profile()
    replacements={'Hotel Aura':profile['hotel_name'],'Hostess':profile['assistant_name']}
    for value in profile['hotel_name'],profile['assistant_name']:replacements.setdefault(value,value)
    pattern='|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True))
    return re.sub(pattern,lambda m:replacements[m[0]],render(text,profile))

def export_template(connection,base):
    import policy_review
    policies=policy_review.overlay(connection,base)
    keys=('id','title','content','department','example_question','audience')
    return {'format':'aura-hotel-template','version':1,'profile':get(connection)['profile'],
            'policies':[{k:p[k] for k in keys} for p in sorted(policies.values(),key=lambda p:policy_review.policy_order(p['id']))],
            'scope':'Identidade e políticas. Não contém reservas, hóspedes, conversas, acessos ou credenciais.',
            'activation':'Importar em instalação nova como rascunhos; revisar e publicar antes do uso real.'}

def validate_template(package):
    import policy_review
    if not isinstance(package,dict) or package.get('format')!='aura-hotel-template' or package.get('version')!=1:raise ValueError('Modelo incompatível.')
    profile=validate(package.get('profile'));policies=package.get('policies')
    if not isinstance(policies,list) or not 1<=len(policies)<=250:raise ValueError('Catálogo inválido.')
    seen=set()
    for row in policies:
        if not isinstance(row,dict) or set(row)!=set(policy_review.FIELDS)|{'id','audience'}:raise ValueError('Política inválida.')
        pid=row['id']
        if not isinstance(pid,str) or not re.fullmatch(r'POL-\d{2,5}',pid) or pid in seen or row['audience'] not in ('guest','internal'):raise ValueError('Código ou visibilidade inválida.')
        seen.add(pid)
        for key,limit in policy_review.FIELDS.items():
            if not isinstance(row[key],str) or not 1<=len(row[key].strip())<=limit:raise ValueError('Campo de política inválido: '+key)
    if 'POL-00' not in seen:raise ValueError('Inclua a política de boas-vindas.')
    return profile,policies

def import_new(connection,package,actor):
    import policy_review
    profile,policies=validate_template(package)
    base=json.loads((ROOT/'knowledge/policies.json').read_text(encoding='utf-8-sig'));base={p['id']:p for p in base}
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for table in ('hotel_profile','policy_reviews','custom_policies','reservations','interactions'):
            if db.execute('SELECT 1 FROM '+table+' LIMIT 1').fetchone():raise Conflict('Importação disponível somente em uma instalação nova, sem configuração ou dados operacionais.')
        stamp=datetime.now(timezone.utc).isoformat();raw=json.dumps(profile,ensure_ascii=False)
        db.execute('INSERT INTO hotel_profile VALUES (1,1,?)',(raw,))
        db.execute('INSERT INTO hotel_profile_history(revision,actor,created_at,data) VALUES (1,?,?,?)',(actor,stamp,raw))
        for p in policies:
            pid=p['id'];raw=json.dumps({k:p[k] for k in policy_review.FIELDS},ensure_ascii=False)
            if pid in base and p['audience']!=base[pid]['audience']:raise ValueError('A visibilidade da política base não pode ser alterada pelo modelo.')
            if pid not in base:db.execute('INSERT INTO custom_policies VALUES (?,?,?)',(pid,p['audience'],stamp))
            db.execute('INSERT INTO policy_reviews(id,revision,draft,editor,updated_at) VALUES (?,1,?,?,?)',(pid,raw,actor,stamp))
            db.execute('INSERT INTO policy_review_history(policy_id,revision,action,actor,created_at,snapshot) VALUES (?,1,?,?,?,?)',(pid,'import_draft',actor,stamp,raw))
    return {'updated':True,'policies_imported':len(policies),'published':False}

# Only HTML text nodes are branded; scripts and style source are never interpolated.
def page(source):
    from html.parser import HTMLParser
    from html import escape
    profile=guest_profile()
    class Branding(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=False);self.out=[];self.raw=0
        def handle_starttag(self,tag,attrs):
            self.out.append(self.get_starttag_text())
            if tag in ('script','style'):self.raw+=1
        def handle_startendtag(self,tag,attrs):self.out.append(self.get_starttag_text())
        def handle_endtag(self,tag):
            self.out.append('</'+tag+'>')
            if tag in ('script','style'):self.raw=max(0,self.raw-1)
        def handle_data(self,data):
            if self.raw:self.out.append(data);return
            replacements={'Hotel Aura':profile['hotel_name'],'Hostess':profile['assistant_name']}
            self.out.append(escape(re.sub(r'Hotel Aura|Hostess',lambda m:replacements[m[0]],data),quote=False))
        def handle_entityref(self,name):self.out.append('&'+name+';')
        def handle_charref(self,name):self.out.append('&#'+name+';')
        def handle_decl(self,decl):self.out.append('<!'+decl+'>')
        def handle_comment(self,data):self.out.append('<!--'+data+'-->')
    parser=Branding();parser.feed(source);parser.close()
    style='<style>header,button:not(.example):not(.item){background:'+profile['primary_color']+'}header a,header button{color:white}</style>'
    result=''.join(parser.out)
    return result.replace('</head>',style+'</head>',1) if '</head>' in result else style+result


def guest_profile():
    current=get()
    mode=operating_mode.get()
    if mode['mode']!='production' or (mode['identity_revision'] is not None and mode['identity_revision']==current['revision']):return current['profile']
    return dict(hotel_name='Hotel',assistant_name='Assistente',tagline='Atendimento ao hóspede',primary_color='#123d3a',address='',contact_email='',website='',reception_contact='',accommodation_count=0,demo_notice='Informações sujeitas à confirmação da equipe.')
