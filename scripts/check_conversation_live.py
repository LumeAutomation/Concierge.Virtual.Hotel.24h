"""Verifica o teste de contexto pela execucao n8n, sem exibir dados privados."""
import json
import re
import sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
state=ROOT/'runtime/waha'
case=json.loads((state/'context-test-case.json').read_text(encoding='utf-8'))
b=(state/'context-test-output.log').read_bytes()
s=b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8',errors='replace')
runs={}
for match in re.finditer(r'\{',s):
    try: d,_=json.JSONDecoder().raw_decode(s[match.start():])
    except ValueError: continue
    if isinstance(d,dict) and isinstance(d.get('data'),dict):
        runs=d['data'].get('resultData',{}).get('runData',{})
        if runs: break

def outputs(name):
    return [item.get('json',{}) for run in runs.get(name,[]) for branch in run.get('data',{}).get('main',[]) for item in branch]

with sqlite3.connect(str(ROOT/'runtime/aura.sqlite3')) as db:
    row=db.execute('SELECT response FROM interactions WHERE id=?',(case['request_id'],)).fetchone()
result=json.loads(row[0]) if row else {}
contexts=outputs('Carregar base do hotel')
models=outputs('IA - consultar politicas')
passed=(any(1 <= c.get('context_turns',0) <= 3 for c in contexts)
        and any(m.get('choices') for m in models)
        and result.get('answer_mode')=='knowledge_extract'
        and result.get('policy_ids')==['POL-08']
        and '11h' in result.get('reply',''))
report={'passed':passed,'context_turns':[c.get('context_turns') for c in contexts],
        'answer_mode':result.get('answer_mode'),'policy_ids':result.get('policy_ids'),
        'question':case['message'],'whatsapp_sent':False}
(state/'context-live-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
if not passed: raise SystemExit(1)
