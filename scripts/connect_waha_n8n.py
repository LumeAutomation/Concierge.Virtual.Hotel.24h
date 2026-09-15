"""Conecta o WAHA somente depois de o workflow estar publicado no n8n."""
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT/'runtime/waha'

def request(url, method='GET', data=None, headers=None):
    body = None if data is None else json.dumps(data).encode()
    req = Request(url, data=body, method=method, headers={'Content-Type':'application/json', **(headers or {})})
    with urlopen(req, timeout=25) as response:
        raw = response.read()
        return json.loads(raw) if raw else None

def main():
    credential = json.loads((STATE/'n8n-header-credential.json').read_text(encoding='utf-8-sig'))[0]['data']
    headers = {credential['name']: credential['value']}
    # Evento ficticio ignorado pelo filtro: verifica registro e autenticacao.
    request('http://127.0.0.1:5678/webhook/aura-waha-entrada', 'POST', {'event':'aura.connection.check'}, headers)
    settings = dict(line.split('=',1) for line in (STATE/'.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
    waha_headers = {'X-Api-Key':settings['WAHA_API_KEY']}
    session = request('http://127.0.0.1:3000/api/sessions/default', headers=waha_headers)
    config = session.get('config') or {}
    backup = STATE/'session-before-n8n.json'
    if not backup.exists():
        backup.write_text(json.dumps({'name':'default','config':config},indent=2),encoding='utf-8')
    target = 'http://host.docker.internal:5678/webhook/aura-waha-entrada'
    hooks = [hook for hook in config.get('webhooks',[]) if hook.get('url') != target]
    hooks.append({'url':target,'events':['message'],'customHeaders':[{'name':credential['name'],'value':credential['value']}], 'retries':{'policy':'constant','delaySeconds':3,'attempts':3}})
    config['webhooks'] = hooks
    request('http://127.0.0.1:3000/api/sessions/default','PUT',{'name':'default','config':config},waha_headers)
    verified = request('http://127.0.0.1:3000/api/sessions/default',headers=waha_headers)
    if not any(h.get('url') == target for h in (verified.get('config') or {}).get('webhooks',[])):
        raise ValueError('O WAHA nao confirmou o webhook.')
    print('Webhook WAHA -> n8n configurado. Status da sessao: '+str(verified.get('status')))
    print('Pendente: enviar [AURA TESTE] Qual o horario do cafe? de outro celular e validar a execucao.')

if __name__ == '__main__':
    try:
        main()
    except HTTPError as error:
        print('Configuracao interrompida: HTTP '+str(error.code)+'. Confirme a publicacao no n8n e as credenciais locais.',file=sys.stderr)
        sys.exit(1)
    except (URLError, ValueError, OSError, KeyError):
        print('Configuracao interrompida; confira os servicos e arquivos locais. Nenhum segredo foi exibido.',file=sys.stderr)
        sys.exit(1)
