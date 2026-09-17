"""Observe local health and blocked webhooks; never send WhatsApp messages."""
import json,os,sqlite3,time,uuid
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
import psutil
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT))
from waha_config import session_name
STATE=ROOT/'runtime'
OPENER=build_opener(ProxyHandler({}))

def request(url,body=None,headers=None,timeout=8):
    start=time.monotonic()
    try:
        req=Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
        with OPENER.open(req,timeout=timeout) as r:r.read();status=r.status
        return {'status':status,'seconds':round(time.monotonic()-start,3)}
    except HTTPError as error:
        error.close();return {'status':error.code,'seconds':round(time.monotonic()-start,3)}
    except Exception as error:return {'status':0,'error':type(error).__name__,'seconds':round(time.monotonic()-start,3)}

def main():
    credential=json.loads((STATE/'waha/n8n-header-credential.json').read_text(encoding='utf-8-sig'))[0]['data']
    headers={credential['name']:credential['value']}
    start=time.monotonic();warmup=[]
    while time.monotonic()-start<180:
        result=request('http://127.0.0.1:5678/healthz/readiness');warmup.append(result)
        if result['status']==200:
            webhook=request('http://127.0.0.1:5678/webhook/aura-waha-entrada',{'event':'aura.warmup'},headers,timeout=15)
            if webhook['status']==200:break
        time.sleep(5)
    else:
        report={'passed':False,'stage':'warmup','samples':warmup,'whatsapp_sent':False}
        (STATE/'stability-results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));raise SystemExit(1)
    print('n8n pronto; iniciando observacao de 3 minutos.',flush=True)
    credential=json.loads((STATE/'waha/n8n-header-credential.json').read_text(encoding='utf-8-sig'))[0]['data']
    headers={credential['name']:credential['value']}
    dbpath=ROOT/'runtime/aura.sqlite3'
    with sqlite3.connect(dbpath) as db:
        assert not db.execute("SELECT 1 FROM pilot_contacts WHERE session_id='waha_000000000000_c_us' AND active=1").fetchone()
    log=Path(os.environ['LOCALAPPDATA'])/'AURA/logs/n8n.log';offset=log.stat().st_size
    rows=[];measure_start=time.monotonic()
    for i in range(19):
        row={'sample':i+1,'elapsed':round(time.monotonic()-measure_start,1),'ram_percent':psutil.virtual_memory().percent,
             'aura':request('http://127.0.0.1:8787/api/health'),
             'n8n':request('http://127.0.0.1:5678/healthz/readiness')}
        if i%6==0:
            # No prefix, and an explicitly unauthorized synthetic sender.
            mid='stability-'+str(uuid.uuid4())
            event={'event':'message','session':session_name(ROOT),'payload':{'id':mid,'from':'000000000000@c.us','fromMe':False,'hasMedia':False,'body':'Qual o horario do cafe da manha?'}}
            row['blocked_webhook']=request('http://127.0.0.1:5678/webhook/aura-waha-entrada',event,headers,timeout=20)
        rows.append(row)
        print(json.dumps(row),flush=True)
        if i<18:time.sleep(max(0,10-(time.monotonic()-measure_start-10*i)))
    with log.open('rb') as f:f.seek(offset);delta=f.read().decode('utf-8',errors='replace')
    errors={term:delta.count(term) for term in ['Database ping failed','SqliteWriteConnectionMutex','Offer expired']}
    with sqlite3.connect(dbpath) as db:
        saved=db.execute("SELECT count(*) FROM interactions WHERE session_id='waha_000000000000_c_us'").fetchone()[0]
    passed=all(row['aura']['status']==200 and row['n8n']['status']==200 and row.get('blocked_webhook',{'status':200})['status']==200 for row in rows) and not any(errors.values()) and saved==0
    report={'passed':passed,'duration_seconds':round(time.monotonic()-measure_start,1),'samples':rows,'new_log_errors':errors,'unauthorized_interactions':saved,'whatsapp_sent':False,'warmup_seconds':round(measure_start-start,1)}
    (STATE/'stability-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('STABILITY_PASSED='+str(passed),flush=True)
    if not passed:raise SystemExit(1)

if __name__=='__main__':main()
