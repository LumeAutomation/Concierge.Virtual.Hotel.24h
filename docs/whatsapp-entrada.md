# WhatsApp - entrada na AURA

Arquivo: workflows/WF-02-whatsapp-entrada.json. Importar como novo workflow.

## Estado
Preparado e testado localmente; ainda nao importado, autenticado ou publicado no n8n.
Fluxo: WhatsApp Trigger -> Preparar mensagem -> AURA local.
A resposta fica no OUTPUT do ultimo no. Este fluxo nao envia mensagens ao celular.
O erro Meta 130497 de saida permanece pendente.

## Configuracao
1. Reiniciar python app.py se o processo estiver usando a versao anterior.
2. Importar o arquivo e abrir WhatsApp - receber.
3. Criar credencial WhatsApp OAuth2: Client ID = App ID; Client Secret = App Secret, obtidos no aplicativo Aura-Bot, App settings > Basic. Inserir diretamente no n8n.
4. O n8n precisa de URL publica HTTPS para o webhook e callback OAuth. localhost nao e acessivel pela Meta. A publicacao HTTPS ainda precisa ser preparada; manter a API Python e a recepcao em loopback.
5. Trigger On deve conter Messages; atualizacoes de status estao desabilitadas.
6. Preparar mensagem limita a entrada ao Phone Number ID do numero de teste atual. Alterar esse filtro ao migrar para outro numero.
7. Depois de configurar credencial e HTTPS, executar o workflow e enviar uma mensagem ficticia ao numero de teste pelo celular cadastrado.
8. Conferir o OUTPUT final. Um pedido como 'Quero toalhas' deve gerar protocolo na recepcao. Uma FAQ pode responder sem gerar encaminhamento.

Ha apenas um webhook por app Meta. Trocar entre teste e producao pode substituir a assinatura usada no painel da Meta. Conferir isso antes da ativacao.
Para n8n rodando nativamente neste Windows, o HTTP Request usa http://127.0.0.1:8787/api/chat. Cloud e Docker exigem outra configuracao de conectividade/autenticacao.

## Comportamento e limites
- Wamid original preservado para idempotencia; nao truncar IDs.
- Audio, imagem e outros tipos viram encaminhamento humano sem download/processamento.
- Eventos statuses nao geram atendimento.
- Mensagens vazias, maiores que 2000 caracteres ou remetentes sem numero numerico falham explicitamente para revisao na execucao.
- Piloto de regras e dados ficticios. Nao conectar clientes reais nesta etapa.
- Ainda nao ha fila duravel entre o Trigger e o Python: se a API falhar depois do recebimento, revisar/reexecutar a execucao no n8n.
- Validacoes: python -m unittest discover -s tests -v; node scripts/check_whatsapp_input.cjs.

Referencias oficiais:
https://docs.n8n.io/integrations/builtin/credentials/whatsapp/
https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.whatsapptrigger/

