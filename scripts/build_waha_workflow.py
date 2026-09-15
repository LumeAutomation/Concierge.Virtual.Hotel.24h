"""Gera o workflow sem segredos; credencial vinculada durante instalacao local."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
names = ['WAHA - entrada', 'Filtrar teste e preparar', 'Identificador SHA256', 'AURA - processar', 'Preparar resposta WhatsApp', 'WAHA - enviar resposta']
nodes = [
    dict(parameters=dict(httpMethod='POST', path='aura-waha-entrada', authentication='headerAuth', responseMode='lastNode', responseData='allEntries', options={}), id='waha-webhook', name=names[0], type='n8n-nodes-base.webhook', typeVersion=2, position=[0,0], webhookId='aura-waha-entrada'),
    dict(parameters=dict(jsCode=(ROOT/'scripts/waha-input.js').read_text(encoding='utf-8-sig')), id='waha-normalize', name=names[1], type='n8n-nodes-base.code', typeVersion=2, position=[260,0]),
    dict(parameters=dict(action='hash', type='SHA256', value='={{ $json.request_id }}', dataPropertyName='request_id', encoding='hex'), id='waha-hash', name=names[2], type='n8n-nodes-base.crypto', typeVersion=2, position=[520,0]),
    dict(parameters=dict(method='POST', url='http://127.0.0.1:8787/api/chat', sendBody=True, specifyBody='json', jsonBody='={{ JSON.stringify({message: $json.message, request_id: $json.request_id, session_id: $json.session_id}) }}', options=dict(timeout=15000)), id='waha-aura', name=names[3], type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[780,0]),
    dict(parameters=dict(mode='runOnceForEachItem', jsCode=(ROOT/'scripts/waha-reply.js').read_text(encoding='utf-8-sig')), id='waha-reply', name=names[4], type='n8n-nodes-base.code', typeVersion=2, position=[1040,0]),
    dict(parameters=dict(method='POST', url='http://127.0.0.1:8787/api/whatsapp/reply', sendBody=True, specifyBody='json', jsonBody='={{ JSON.stringify($json) }}', options=dict(timeout=30000)), id='waha-send', name=names[5], type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[1300,0], retryOnFail=False),
]
workflow = dict(id='auraWahaInput03', name='WF-03 | WAHA - AURA | Conversa de teste', active=False, nodes=nodes,
    connections={a:dict(main=[[dict(node=b, type='main', index=0)]]) for a,b in zip(names,names[1:])},
    settings=dict(executionOrder='v1', saveDataSuccessExecution='none', saveDataErrorExecution='none', saveManualExecutions=False))

# Consulta a base atual a cada mensagem, sem incluir telefone na chamada ao modelo.
context = dict(parameters=dict(method='POST', url='http://127.0.0.1:8787/api/knowledge/context', sendBody=True, specifyBody='json', jsonBody='={{ JSON.stringify({message: $json.message, request_id: $json.request_id, session_id: $json.session_id}) }}', options=dict(timeout=15000)), id='aura-knowledge', name='Carregar base do hotel', type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[780,0])
condition = dict(parameters=dict(conditions=dict(boolean=[dict(value1='={{ $json.use_ai }}', operation='equal', value2=True)])), id='aura-ai-condition', name='Consultar IA?', type='n8n-nodes-base.if', typeVersion=1, position=[1040,0])
model = dict(parameters=dict(method='POST', url='https://api.openai.com/v1/chat/completions', authentication='predefinedCredentialType', nodeCredentialType='openAiApi', sendBody=True, specifyBody='json', jsonBody='={{ JSON.stringify($json.model_request) }}', options=dict(timeout=25000)), id='aura-openai', name='IA - consultar politicas', type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[1300,-160], onError='continueRegularOutput', retryOnFail=False)
commit = dict(parameters=dict(method='POST', url='http://127.0.0.1:8787/api/chat/knowledge', sendBody=True, specifyBody='json', jsonBody="={{ JSON.stringify({message: $('Carregar base do hotel').item.json.message, request_id: $('Carregar base do hotel').item.json.request_id, session_id: $('Carregar base do hotel').item.json.session_id, knowledge_version: $('Carregar base do hotel').item.json.knowledge_version, model_output: $json}) }}", options=dict(timeout=15000)), id='aura-knowledge-save', name='Validar fonte e registrar', type='n8n-nodes-base.httpRequest', typeVersion=4.2, position=[1560,-160])
nodes.extend([context,condition,model,commit])
workflow['name']='WF-03 | AURA - Base do hotel e WhatsApp'
def link(name): return [dict(node=name,type='main',index=0)]
workflow['connections']['Identificador SHA256']={'main':[link(context['name'])]}
workflow['connections'][context['name']]={'main':[link(condition['name'])]}
workflow['connections'][condition['name']]={'main':[link(model['name']),link('AURA - processar')]}
workflow['connections'][model['name']]={'main':[link(commit['name'])]}
workflow['connections'][commit['name']]={'main':[link('Preparar resposta WhatsApp')]}
for n in nodes:
    if n['name']=='AURA - processar': n['position']=[1300,180]
    if n['name']=='Preparar resposta WhatsApp': n['position']=[1820,0]
    if n['name']=='WAHA - enviar resposta': n['position']=[2080,0]

(ROOT/'workflows/WF-03-waha-entrada.json').write_text(json.dumps(workflow, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
