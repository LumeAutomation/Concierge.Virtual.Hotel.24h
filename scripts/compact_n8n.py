"""One-time offline SQLite maintenance with a verified backup, no record deletion."""
import hashlib,json,os,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
import psutil

def main():
    cli=Path(os.environ['APPDATA'])/'npm/node_modules/n8n/bin/n8n'
    for process in psutil.process_iter(['name']):
        if process.info['name']=='node.exe' and any(str(cli).casefold()==arg.casefold() for arg in process.cmdline()):
            raise RuntimeError('Pare o n8n antes da manutencao.')
    source=Path(os.environ['USERPROFILE'])/'.n8n/database.sqlite'
    target=Path(os.environ['LOCALAPPDATA'])/'AURA/maintenance';target.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=target/('n8n-before-compact-'+stamp+'.sqlite3')
    before=source.stat().st_size
    with closing(sqlite3.connect(source,timeout=15)) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Banco original invalido.')
        def signature():
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            counts={name:db.execute('SELECT count(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
            credentials=hashlib.sha256(repr(db.execute('SELECT id,data FROM credentials_entity ORDER BY id').fetchall()).encode()).hexdigest()
            return counts,credentials
        original=signature()
        with closing(sqlite3.connect(backup)) as copy:
            db.backup(copy)
            if copy.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Backup invalido.')
        db.execute('VACUUM');db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok' or signature()!=original:
            raise RuntimeError('Validacao apos manutencao falhou. Preserve o backup e mantenha n8n parado.')
    result=dict(before_mb=round(before/2**20,2),after_mb=round(source.stat().st_size/2**20,2),backup=str(backup),integrity='ok',record_counts_preserved=True,credential_bytes_preserved=True)
    (target/'compact-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
