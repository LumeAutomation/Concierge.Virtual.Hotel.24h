# Correcao de recebimento e resposta ? 17/09/2026

A sessao WAHA pode ter nome diferente de `default`. Configure o nome em
`runtime/waha/session.json`, por exemplo `{"name":"Lume"}`. Sem o arquivo,
o padrao continua `default`. Entrada gerada, envio e monitoramento usam essa
configuracao. Ao alterar o nome, gere e publique novamente o WF-03, reinicie
AURA/n8n e execute `scripts/connect_waha_n8n.py`.

O webhook permanente e `/webhook/aura-waha-entrada`. O conector remove a
variante `/webhook-test/` desta integracao, preserva outros webhooks e salva
backup da configuracao anterior. A credencial de entrada deve estar vinculada.
O instalador recupera o vinculo local existente se ele foi removido no editor.

Contatos precisam estar ativos em `/equipe`; uma lista vazia bloqueia todas
as entradas. Mensagens enviadas pela propria conta do robo sao ignoradas.
A validacao tecnica nao substitui a confirmacao da resposta no celular.

---

# Atualização do modelo — 16/09/2026

Texto normal de contatos autorizados é aceito sem prefixo. O WF-03 publicado
consulta somente a base local e não contém nós OpenAI. A primeira interação de
cada conversa recebe POL-00; respostas e boas-vindas são persistidas juntas para
não repetir em reentregas. A criação/publicação de políticas ocorre pela tela.

As seções seguintes são histórico das versões anteriores, não o fluxo atual.

---

# Estado atual — 16/09/2026

O WF-03 agora verifica contatos autorizados antes de consultar a IA. As chamadas
à AURA usam a credencial `AURA - servico local`; o envio passa pelo controle de
idempotência da AURA. Prefixo `[AURA TESTE] ` mantido. Lista vazia bloqueia entradas.
Configuração e reinstalação: [access.md](access.md).

As seções abaixo registram etapas anteriores, inclusive o envio direto que foi
substituído. Para o estado atual, consulte também [retomada.md](retomada.md).

---

# WAHA -> n8n -> AURA -> WhatsApp

Workflow: workflows/WF-03-waha-entrada.json.
Editor: http://localhost:5678/workflow/auraWahaInput03
Nome: WF-03 | WAHA - AURA | Conversa de teste.

## Comportamento
WAHA - entrada -> Filtrar teste e preparar -> Identificador SHA256 -> AURA - processar -> Preparar resposta WhatsApp -> WAHA - enviar resposta.

- Aceita somente texto de outra conta, em conversa individual da sessao default, com prefixo `[AURA TESTE] ` seguido de uma mensagem.
- Ignora mensagens proprias, grupos, midia e eventos diferentes de message. Isso evita responder a propria resposta.
- O destinatario da resposta vem do remetente validado do evento. O no de envio usa POST /api/sendText com a credencial WAHA - envio local.
- So envia quando a AURA confirma persisted=true e devolve texto de resposta. A resposta se identifica como demonstracao.
- AURA e um motor de regras de hotel ficticio, sem IA conectada. Pedidos ficam na fila local; a resposta nao confirma execucao do servico pelo hotel.
- O Webhook usa responseData=allEntries, inclusive para responder sem erro quando um evento e ignorado.
- O salvamento automatico de dados das execucoes permanece desabilitado. Testes manuais podem exibir dados no editor.

## Validacao em 15/09/2026
- Recebimento real WAHA -> n8n -> AURA confirmado por pedidos de toalhas na recepcao.
- Filtros de entrada, destino da resposta e exigencia de persistencia testados com Node.
- Resposta ao ultimo pedido de teste enviada uma vez diretamente pela API usando o mesmo codigo de preparacao do workflow. WAHA retornou HTTP 201 e ID da mensagem. Isso confirma aceitacao pela API, nao leitura no celular.
- Versao com resposta publicada pelo usuario. Confirmados workflow ativo, no WAHA - enviar resposta presente, webhook HTTP 200 e sessao WORKING. Falta confirmar uma NOVA mensagem real pelo fluxo automatico completo.
- Evidencias locais: runtime/waha/integration-check.json e runtime/waha/outbound-validation.json.

## Operacao
1. Abrir o editor, atualizar com F5 e publicar/ativar a versao que termina em WAHA - enviar resposta.
2. De outro celular, enviar `[AURA TESTE] Quero toalhas no quarto de teste` ao numero pareado.
3. Conferir resposta no celular remetente e registro em http://127.0.0.1:8787/recepcao.
4. Para parar respostas automaticas, desativar o WF-03 no n8n.

A configuracao de webhook da sessao ja existe. scripts/connect_waha_n8n.py serve para reinstala-la se necessario, preservando os demais ajustes e o backup local.
Credenciais ficam no cofre n8n e em runtime, ignorado pelo Git.

## Limite de reenvio
O registro AURA e idempotente por identificador da mensagem. O envio WAHA ainda nao tem controle persistente de duplicidade: uma reentrega do webhook ou reexecucao manual pode repetir a resposta, embora nao duplique o atendimento. O no HTTP de envio nao repete automaticamente por conta propria. Uma falha de rede apos o WAHA aceitar o envio exige conferir a conversa antes de reexecutar.

## Verificar localmente
- node scripts/check_waha_input.cjs
- node scripts/check_waha_reply.cjs
- python -m unittest discover -s tests -v
- python scripts/build_waha_workflow.py (gera JSON sem segredos; ao importar em outra instancia, vincular credenciais nos dois nos HTTP/Webhook correspondentes).

Referencia do envio: https://waha.devlike.pro/docs/how-to/send-messages/


## Contexto e protecao contra duplicidade (2026-09-15)

O WF-03 passa a enviar a resposta por `POST /api/whatsapp/reply` no servico
local AURA. O destino e o texto sao reconstruidos a partir da interacao ja
persistida. O n8n fornece somente `request_id` e `session_id`.

A tabela `whatsapp_deliveries` reserva a tentativa em uma transacao SQLite
antes de chamar o WAHA. Repeticoes, inclusive simultaneas e apos reinicio,
nao iniciam outro envio para o mesmo protocolo. Isto garante no maximo uma
tentativa automatica, nao entrega garantida. Timeout ou falha deixa o envio
como `unknown`: confira o WhatsApp antes de qualquer acao manual. Uma tentativa
interrompida por mais de dois minutos tambem vira `unknown` quando consultada
por nova tentativa. `sent` significa que o WAHA retornou um identificador,
nao que o destinatario leu a mensagem.

`GET /api/whatsapp/deliveries` lista os ultimos 50 registros, sem numero de
telefone nem texto. Interacoes WhatsApp anteriores a esta migracao recebem
`legacy_unverified`, evitando reenviar historico cuja entrega nao e conhecida.
Nao apague o banco nem a tabela de controle para tentar corrigir um timeout.

O contexto utiliza ate tres trocas informativas anteriores da mesma conversa,
dentro dos ultimos 30 minutos. Um pedido encaminhado para equipe, saudacao ou
mensagem sensivel interrompe a sequencia. O historico serve para identificar
o assunto; a resposta continua exigindo citacao validada da base atual.
A pergunta curta "e aos domingos?" sem contexto pede esclarecimento.
Perguntas anteriores e respostas entram na chamada da IA; os identificadores
da conversa nao entram no corpo enviado ao modelo. O filtro de dados sensiveis
e conservador e baseado em padroes, nao um anonimizado geral de texto livre.
O contexto e fixado por protocolo para manter a mesma entrada nas repeticoes.
Uma mensagem ja registrada pula a chamada da IA. Mensagens diferentes que
cheguem simultaneamente podem ainda nao enxergar a resposta em andamento.

Validacao: 27 testes Python e verificacoes JavaScript de entrada/saida.
Inclui oito chamadas simultaneas com apenas uma chamada ao transporte,
timeout sem reenvio, reinicio, migracao, isolamento e expiracao de contexto.
O teste com IA real e o estado da publicacao devem ser conferidos nos
artefatos locais `runtime/waha/context-live-results.json` e no n8n.

Teste real de contexto aprovado: depois de uma pergunta sobre o cafe da manha,
"e aos domingos?" usou uma troca anterior e retornou `knowledge_extract`
com POL-08 e horario ate 11h. Executado pelo n8n com a credencial OpenAI
existente, sem etapa de envio WhatsApp. Evidencia: `context-live-results.json`.
A ativacao desta revisao no webhook depende de publicar a versao importada
no workflow `auraWahaInput03`; a publicacao ainda nao foi verificada.
