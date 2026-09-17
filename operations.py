"""Backup consistente do SQLite e monitoramento local, sem enviar mensagens."""
from contextlib import closing
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from waha_config import session_name

ROOT=Path(os.environ.get('AURA_PROJECT_ROOT', str(Path(__file__).resolve().parent)))
LOCAL=Path(os.environ.get('LOCALAPPDATA',str(ROOT/'runtime')))/'AURA'
BACKUPS=LOCAL/'backups'
STATE=LOCAL/'operations.json'
BACKUP_STATE=LOCAL/'backup.json'


def now(): return datetime.now(timezone.utc)
def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,path)

def read_json(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def backup(root=ROOT, destination=BACKUPS):
    root=Path(root);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    stamp=now().strftime('%Y%m%dT%H%M%S%fZ')
    archive=destination/('aura-'+stamp+'.zip')
    partial=archive.with_suffix('.partial')
    entries={}
    try:
        with tempfile.TemporaryDirectory(dir=destination) as temporary:
            copy=Path(temporary)/'aura.sqlite3'
            source_path=root/'runtime/aura.sqlite3'
            if not source_path.is_file():raise FileNotFoundError('Banco AURA ausente')
            with closing(sqlite3.connect(str(source_path))) as source,closing(sqlite3.connect(str(copy))) as target:
                source.backup(target)
                if target.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Backup SQLite invalido')
            with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED) as out:
                def add(path,name):
                    data=path.read_bytes();out.writestr(name,data);entries[name]=hashlib.sha256(data).hexdigest()
                add(copy,'runtime/aura.sqlite3')
                for folder,extensions in [('knowledge',{'.json','.md','.txt'}),('prompts',{'.txt','.md'}),('workflows',{'.json'})]:
                    for path in sorted((root/folder).glob('*')):
                        if path.is_file() and path.suffix in extensions:add(path,folder+'/'+path.name)
                manifest={'created_at':now().isoformat(),'sha256':entries,'scope':'AURA database, knowledge, prompts, workflow templates'}
                out.writestr('manifest.json',json.dumps(manifest))
            verify_archive(partial)
            os.replace(partial,archive)
        # Apenas arquivos de backup com nome controlado, nunca diretorios recursivos.
        import re
        archives=sorted(p for p in destination.iterdir() if p.is_file() and re.fullmatch(r'aura-\d{8}T\d{12}Z\.zip',p.name))
        for old in archives[:-14]:
            if old.resolve().parent != destination.resolve():raise ValueError('Destino de retencao invalido')
            old.unlink()
        result={'status':'ok','created_at':manifest['created_at'],'file':str(archive),'files':len(entries),'verified':True}
        return result
    finally:
        if partial.exists():partial.unlink()


def verify_archive(path):
    with zipfile.ZipFile(path) as source:
        if source.testzip() is not None:raise ValueError('Arquivo corrompido')
        manifest=json.loads(source.read('manifest.json'))
        for name,digest in manifest['sha256'].items():
            if hashlib.sha256(source.read(name)).hexdigest()!=digest:raise ValueError('Checksum invalido')
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'verify.sqlite3';db.write_bytes(source.read('runtime/aura.sqlite3'))
            with closing(sqlite3.connect(str(db))) as conn:
                if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Banco invalido')
    return manifest


def get_json(url,headers=None):
    with urlopen(Request(url,headers=headers or {}),timeout=3) as response:return json.load(response)


def snapshot():
    result={'checked_at':now().isoformat(),'services':{}}
    try:
        healthy=get_json('http://127.0.0.1:8787/api/health').get('status')=='ok'
        result['services']['aura']={'status':'ok' if healthy else 'error'}
    except Exception:result['services']['aura']={'status':'error'}
    try:
        get_json('http://127.0.0.1:5678/healthz/readiness')
        result['services']['n8n']={'status':'ok'}
    except Exception:result['services']['n8n']={'status':'error'}
    try:
        db=Path(os.environ['USERPROFILE'])/'.n8n/database.sqlite'
        if not db.is_file():raise FileNotFoundError()
        with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=2)) as conn:
            row=conn.execute('SELECT active FROM workflow_entity WHERE id=?',('auraWahaInput03',)).fetchone()
        result['services']['workflow']={'status':'ok' if row and row[0] else 'error'}
    except Exception:result['services']['workflow']={'status':'unknown'}
    try:
        values=dict(line.split('=',1) for line in (ROOT/'runtime/waha/.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
        session=get_json('http://127.0.0.1:3000/api/sessions/'+quote(session_name(ROOT),safe=''),{'X-Api-Key':values['WAHA_API_KEY']})
        result['services']['whatsapp']={'status':'ok' if session.get('status')=='WORKING' else 'error','session_status':session.get('status','unknown')}
    except Exception:result['services']['whatsapp']={'status':'error'}
    monitor=read_json(STATE);last=monitor.get('heartbeat')
    try:running=(now()-datetime.fromisoformat(last)).total_seconds()<120
    except (TypeError,ValueError):running=False
    result['supervisor']={'status':'ok' if running else 'error','heartbeat':last,'last_errors':monitor.get('errors',[])}
    latest=read_json(BACKUP_STATE)
    try:fresh=(now()-datetime.fromisoformat(latest['created_at'])).total_seconds()<26*3600 and Path(latest['file']).is_file()
    except (KeyError,TypeError,ValueError):fresh=False
    result['backup']={**latest,'fresh':fresh,'status':'ok' if fresh and latest.get('status')=='ok' else 'error'}
    return result
