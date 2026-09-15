"""Confere os testes reais de conhecimento sem exibir chaves ou dados de hospedes."""
import json
import re
import sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
state=ROOT/'runtime/waha'
cases=json.loads((state/'knowledge-v2-cases.json').read_text(encoding='utf-8'))
b=(state/'knowledge-v2-output.log').read_bytes()
s=b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8',errors='replace')
runs={}
for match in re.finditer(r'\{',s):
    try: d,end=json.JSONDecoder().raw_decode(s[match.start():])
    except ValueError: continue
    if isinstance(d,dict) and isinstance(d.get('data'),dict):
        runs=d['data'].get('resultData',{}).get('runData',{})
        if runs: break
c=sqlite3.connect(str(ROOT/'runtime/aura.sqlite3'))
results=[]
for case in cases:
    row=c.execute('SELECT response FROM interactions WHERE id=?',(case['request_id'],)).fetchone()
    result=json.loads(row[0]) if row else {}
    model=[]
    for run in runs.get('IA '+case['tag'],[]):
        for branch in run.get('data',{}).get('main',[]):
            model.extend(item.get('json',{}) for item in branch)
    model_ok=any(v.get('choices') for v in model)
    expected=case['expected_policy']
    passed=model_ok and result.get('persisted') is True and ((result.get('answer_mode')=='knowledge_extract' and expected in result.get('policy_ids',[])) if expected else result.get('route')=='HUMAN_HANDOFF')
    summary={'case':case['tag'],'model_returned':model_ok,'route':result.get('route'),'answer_mode':result.get('answer_mode'),'policy_ids':result.get('policy_ids'),'passed':bool(passed)}
    results.append(summary)
    print(json.dumps(summary,ensure_ascii=True))
report={'policy_count':100,'passed':all(x['passed'] for x in results),'cases':results}
(state/'knowledge-live-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['passed']: raise SystemExit(1)
