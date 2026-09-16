"""Readiness and denied-event probe on the installed stack. Never sends WhatsApp."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import operations
ROOT=app.ROOT

def request(url,body=None,headers=None):
    data=None if body is None else json.dumps(body).encode()
    req=Request(url,data=data,headers={'Content-Type':'application/json',**(headers or {})})
    try:
        with urlopen(req,timeout=45) as r:return r.status,r.read()
    except HTTPError as error:
        with error:return error.code,error.read()

def main():
    state=operations.snapshot()
    report=dict(passed=False,checked_at=operations.now().isoformat(),services=state['services'],supervisor_active=state['supervisor']['status']=='ok',whatsapp_sent=False)
    report_path=ROOT/'runtime/access-live-results.json'
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert request('http://127.0.0.1:8787/api/handoffs')[0]==401
    assert request('http://127.0.0.1:8787/api/knowledge/context',{})[0]==401
    report.update(anonymous_admin_denied=True,service_token_required=True)
    token=(ROOT/'runtime/auth/service-token.txt').read_text(encoding='utf-8').strip()
    status,data=request('http://127.0.0.1:8787/api/pilot/check',dict(session_id='waha_000000000000_c_us'),{'Authorization':'Bearer '+token})
    assert status==200 and json.loads(data)['allowed'] is False
    report['local_pilot_gate_verified']=True
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    with sqlite3.connect(Path(os.environ['USERPROFILE'])/'.n8n/database.sqlite') as db:
        row=db.execute('SELECT active,versionId,activeVersionId,nodes FROM workflow_entity WHERE id=?',('auraWahaInput03',)).fetchone()
    assert row[0] and row[1]==row[2]
    report['workflow_published_current']=True
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    nodes=json.loads(row[3])
    assert any(n['name']=='Verificar contato autorizado' for n in nodes)
    assert all(n.get('credentials',{}).get('httpHeaderAuth',{}).get('id')=='auraLocalService' for n in nodes if n.get('parameters',{}).get('url','').startswith('http://127.0.0.1:8787/'))
    probe='aura-access-probe-'+str(uuid.uuid4())
    with app.connection() as db:
        assert not db.execute("SELECT 1 FROM pilot_contacts WHERE session_id='waha_000000000000_c_us' AND active=1").fetchone()
        before=db.execute('SELECT count(*) FROM interactions').fetchone()[0]
    credential=json.loads((ROOT/'runtime/waha/n8n-header-credential.json').read_text(encoding='utf-8-sig'))[0]['data']
    headers={credential['name']:credential['value']}
    ignored=request('http://127.0.0.1:5678/webhook/aura-waha-entrada',{'event':'aura.connection.check'},headers)
    assert ignored[0]==200,('ignored_event',ignored[0])
    denied=request('http://127.0.0.1:5678/webhook/aura-waha-entrada',dict(event='message',session='default',payload=dict(fromMe=False,**{'from':'000000000000@c.us'},hasMedia=False,body='Quero toalhas',id=probe)),headers)
    assert denied[0]==200,('denied_event',denied[0])
    with app.connection() as db:after=db.execute('SELECT count(*) FROM interactions').fetchone()[0]
    assert after==before,'A denied event must not create an interaction.'
    parsed=json.loads(denied[1])
    # An unconnected false branch returns no output in n8n allEntries mode.
    assert parsed==[] or (isinstance(parsed,list) and all(item.get('allowed') is False for item in parsed)), 'Unexpected response for a denied contact.'
    report=dict(passed=all(v['status']=='ok' for v in state['services'].values()) and state['supervisor']['status']=='ok',local_pilot_gate_verified=True,denied_branch_empty=parsed==[],checked_at=operations.now().isoformat(),services=state['services'],supervisor_active=True,workflow_published_current=True,anonymous_admin_denied=True,service_token_required=True,denied_contact_webhook_http=denied[0],denied_before_persistence=True,whatsapp_sent=False)
    (ROOT/'runtime/access-live-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    if not report['passed']: raise SystemExit(1)

if __name__=='__main__':
    try:main()
    except Exception as error:
        path=ROOT/'runtime/access-live-results.json'
        try:report=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):report={}
        report.update(passed=False,failure=type(error).__name__,failure_detail=str(error) if isinstance(error,AssertionError) else type(error).__name__,checked_at=operations.now().isoformat(),whatsapp_sent=False)
        path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        raise SystemExit(1)
