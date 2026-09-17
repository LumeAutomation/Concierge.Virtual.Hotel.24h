"""Gera o workflow sem segredos; credencial vinculada durante instalacao local."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from waha_config import session_name
names = ['WAHA - entrada', 'Filtrar teste e preparar', 'Identificador SHA256', 'AURA - processar', 'Preparar resposta WhatsApp', 'WAHA - enviar resposta']
nodes = [
    dict(parameters=dict(httpMethod='POST', path='aura-waha-entrada', authentication='headerAuth', responseMode='lastNode', responseData='allEntries', options={}), id='waha-webhook', name=names[0], type='n8n-nodes-base.webhook', typeVersion=2, position=[0,0], webhookId='aura-waha-entrada'),
    dict(parameters=dict(jsCode=(ROOT/'scripts/waha-input.js').read_text(encoding='utf-8-sig').replace("const expectedSession = 'default';", 'const expectedSession = '+json.dumps(session_name(ROOT))+';')), id='waha-normalize', name=names[1], type='n8n-nodes-base.code', typeVersion=2, position=[260,0]),
    dict(parameters=dict(action='hash', type='SHA256', value='={{ $json.request_id }}', dataPropertyName='request_id', encoding='hex'), id='waha-hash', name=names[2], type='n8n-nodes-base.crypto', typeVersion=2, position=[520,0]),
    dict(parameters=dict(method='POST', url='http://127.0.0.1:8787/api/chat', sendBody=True, specifyBody='json', jsonBody='={{ JSON.stringify({message: $json.message, request_id: $json.request_id, session_id: $json.session_id}) }}', options=dict(timeout=15000)), id='waha-aura', name=names[3], type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[780,0]),
    dict(parameters=dict(mode='runOnceForEachItem', jsCode=(ROOT/'scripts/waha-reply.js').read_text(encoding='utf-8-sig')), id='waha-reply', name=names[4], type='n8n-nodes-base.code', typeVersion=2, position=[1040,0]),
    dict(parameters=dict(method='POST', url='http://127.0.0.1:8787/api/whatsapp/reply', sendBody=True, specifyBody='json', jsonBody='={{ JSON.stringify($json) }}', options=dict(timeout=30000)), id='waha-send', name=names[5], type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[1300,0], retryOnFail=False),
]
workflow = dict(id='auraWahaInput03', name='WF-03 | WAHA - AURA | Conversa de teste', active=False, nodes=nodes,
    connections={a:dict(main=[[dict(node=b, type='main', index=0)]]) for a,b in zip(names,names[1:])},
    settings=dict(executionOrder='v1', saveDataSuccessExecution='none', saveDataErrorExecution='none', saveManualExecutions=False))

def link(name): return [dict(node=name,type='main',index=0)]

# Gate before context/model: unapproved participants produce no persisted interaction.
gate = dict(parameters=dict(method='POST', url='http://127.0.0.1:8787/api/pilot/check', sendBody=True, specifyBody='json', jsonBody='={{ JSON.stringify($json) }}', options=dict(timeout=15000)), id='aura-pilot-check', name='Verificar contato autorizado', type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[650,-250])
allowed = dict(parameters=dict(conditions=dict(boolean=[dict(value1='={{ $json.allowed }}', operation='equal', value2=True)])), id='aura-pilot-condition', name='Contato autorizado?', type='n8n-nodes-base.if', typeVersion=1, position=[900,-250])
nodes.extend([gate,allowed])
workflow['connections']['Identificador SHA256']={'main':[link(gate['name'])]}
workflow['connections'][gate['name']]={'main':[link(allowed['name'])]}
workflow['connections'][allowed['name']]={'main':[link('AURA - processar'),[]]}
for node in nodes:
    if node.get('parameters',{}).get('url','').startswith('http://127.0.0.1:8787/'):
        node['parameters'].update(authentication='genericCredentialType',genericAuthType='httpHeaderAuth')
        node['credentials']={'httpHeaderAuth':{'id':'auraLocalService','name':'AURA - servico local'}}

(ROOT/'workflows/WF-03-waha-entrada.json').write_text(json.dumps(workflow, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
