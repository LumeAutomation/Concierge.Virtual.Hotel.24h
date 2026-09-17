"""Update the existing WF-03 using installed n8n CLI; preserve account credentials."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'runtime/auth'

def main():
    STATE.mkdir(parents=True,exist_ok=True)
    database=Path(os.environ['USERPROFILE'])/'.n8n/database.sqlite'
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT * FROM workflow_entity WHERE id=?',('auraWahaInput03',)).fetchone()
        if not row:raise RuntimeError('Workflow existente nao encontrado.')
        previous=dict(row)
    from datetime import datetime,timezone
    backup=STATE/('workflow-before-update-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    if not backup.exists():backup.write_text(json.dumps(previous,indent=2),encoding='utf-8')
    original=json.loads(previous['nodes'])
    credentials={node['name']:node.get('credentials') for node in original if node.get('credentials')}
    template=json.loads((ROOT/'workflows/WF-03-waha-entrada.json').read_text(encoding='utf-8'))
    for node in template['nodes']:
        if not node.get('parameters',{}).get('url','').startswith('http://127.0.0.1:8787/') and node['name'] in credentials:
            node['credentials']=credentials[node['name']]
    for name in ['WAHA - entrada']:
        node=next(n for n in template['nodes'] if n['name']==name)
        if not node.get('credentials'):
            # Recupera somente o vinculo local conhecido, sem criar outro segredo.
            saved=json.loads((ROOT/'runtime/waha/n8n-header-credential.json').read_text(encoding='utf-8-sig'))[0]
            with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
                found=db.execute('SELECT name FROM credentials_entity WHERE id=? AND type=?',(saved['id'],'httpHeaderAuth')).fetchone()
            if not found:raise RuntimeError('Credencial local do webhook ausente.')
            node['credentials']={'httpHeaderAuth':{'id':saved['id'],'name':found[0]}}
    token=(STATE/'service-token.txt').read_text(encoding='utf-8').strip()
    credential=[dict(id='auraLocalService',name='AURA - servico local',type='httpHeaderAuth',data=dict(name='Authorization',value='Bearer '+token))]
    secret=STATE/'service-credential.json'
    secret.write_text(json.dumps(credential),encoding='utf-8')
    workflow=STATE/'workflow-access.json';workflow.write_text(json.dumps([template]),encoding='utf-8')
    node=Path(os.environ['ProgramFiles'])/'nodejs/node.exe'
    cli=Path(os.environ['APPDATA'])/'npm/node_modules/n8n/bin/n8n'
    commands=[['import:credentials','--input='+str(secret)],['import:workflow','--input='+str(workflow)],['publish:workflow','--id=auraWahaInput03']]
    try:
        for i,args in enumerate(commands):
            with (STATE/('install-'+str(i)+'.log')).open('wb') as out:
                result=subprocess.run([str(node),str(cli),*args],stdout=out,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:raise RuntimeError('CLI falhou na etapa '+str(i)+'; consulte o log local sem divulgar credenciais.')
            print('Etapa '+str(i+1)+' de 3 concluida.',flush=True)
    finally:
        secret.unlink(missing_ok=True)
    print('Workflow atualizado e publicado. Reinicie o n8n para carregar a nova versao.')

if __name__=='__main__':main()
