# WF-01 — ponte local de demonstração

O arquivo ../workflows/WF-01-aura-local.json contém:
Webhook POST → HTTP Request para o piloto → Respond to Webhook.

É uma ponte para o motor determinístico, não um AI Agent, RAG ou integração WhatsApp.
O workflow fica desativado. Nenhuma mensagem externa é enviada.

1. Inicie `python app.py`.
2. Importe o JSON no editor n8n.
3. No Webhook, selecione uma credencial **Header Auth** criada por você para o piloto.
4. Com n8n executando nativamente no mesmo Windows, mantenha o endereço HTTP Request em `http://127.0.0.1:8787/api/chat`.
5. Clique em Listen for test event e use a Test URL exibida, incluindo o header configurado.
6. Envie JSON com `message`, `request_id` único e `session_id`.
7. Confira resposta e protocolo na recepção local. Repetir request_id com o mesmo corpo deve manter um único registro.

Exemplo de corpo, sem credenciais:
```json
{"message":"Quero toalhas no quarto de teste","request_id":"n8n-demo-0001","session_id":"n8n-demo"}
```

O header de autenticação não é salvo neste repositório. Em falha de API o workflow deve falhar, sem confirmar encaminhamento. Não há publicação, importação nem teste ponta a ponta do n8n confirmado nesta entrega.

Este endereço não atende n8n Cloud ou Docker em outra rede. Essa integração exige preparar autenticação e conectividade de backend antes de expor a API; não altere o bind para público neste piloto.

Referências oficiais consultadas:
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook/

