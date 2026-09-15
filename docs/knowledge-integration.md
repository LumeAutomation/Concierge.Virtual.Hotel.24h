# Base do hotel - edicao 2, 100 politicas

## Entrega
- knowledge/aurora-source.md: manual completo com indice, regras, excecoes, setor e exemplo.
- knowledge/policies.json: 100 politicas, 88 guest e 12 internal, versao 2.
- knowledge/policies-authoring.txt: texto editorial usado pelo gerador.
- knowledge/references.json: referencias primarias verificadas e alcance de cada referencia.
- scripts/build_hotel_policies.py: gera manual, JSON, referencias e database/002_seed.sql.
- runtime/knowledge-backup: copia da base anterior, ignorada pelo Git.

As politicas sao propostas autorais para o hotel ficticio Aurora. Referencias de Hilton, Hyatt, Iberostar e Ministerio do Turismo demonstram temas operacionais reais; nao tornam os valores ou regras do Aurora politicas oficiais dessas redes. Parametros do piloto precisam de homologacao antes de uso real. Cada politica indica se ha referencia especifica do tema.

## Integracao
A API relê as 100 politicas em cada POST /api/knowledge/context. A IA recebe pergunta e conteudo das politicas; telefone, session_id e request_id nao entram na chamada ao modelo. O texto da pergunta pode conter dados pessoais nao detectados pelo filtro, portanto manter testes ficticios.
knowledge_engine.py verifica a versao, a visibilidade guest e a presenca literal dos trechos escolhidos. O modelo gpt-4.1-mini retorna evidencias estruturadas; nao escreve livremente a resposta. Erro de modelo, recusa, trecho inventado ou fonte interna usam o atendimento local. A pertinencia da escolha e a cobertura das excecoes ainda exigem avaliacao de conteudo.
Emergencias, dados sensiveis reconhecidos, pedidos de acao e saudacoes seguem o caminho local.

## Estado verificado apos atualizar a credencial
- A nova chave OpenAi account foi salva no n8n e funcionou nas chamadas reais.
- 20 testes Python passaram; testes Node de filtros de entrada e resposta ja passaram.
- Base completa de 100 politicas enviada como contexto ao gpt-4.1-mini.
- Quatro testes reais sem envio ao WhatsApp passaram: horario do spa (POL-14), fumo na acomodacao (POL-57), profundidade nao documentada (encaminhamento) e varanda da categoria nao identificada (encaminhamento).
- Foi corrigida a resposta por mera afinidade de assunto: o prompt exige a informacao pedida, e medidas necessitam de evidencia com medida na validacao local.
- Registros ficticios de encaminhamento encerrados. Evidencia: runtime/waha/knowledge-live-results.json e knowledge-validation.json.
- Versao validada enviada para importacao no WF-03. A publicacao no editor e um novo teste real de WhatsApp ainda estao pendentes. O workflow deve terminar em WAHA - enviar resposta e incluir Carregar base do hotel e IA - consultar politicas.
- A base e enviada a cada consulta; nao houve upload persistente em OpenAI Files ou Vector Store.

## Proximo passo
Abrir http://localhost:5678/workflow/auraWahaInput03, atualizar com F5 e publicar/ativar a nova versao. Depois enviar de outro celular [AURA TESTE] Qual e o horario do spa? e conferir a resposta no remetente. Perguntas sem informacao suficiente geram encaminhamento local. A cobertura dos quatro testes nao garante acerto em todas as perguntas; novas falhas devem virar casos de teste.

## Atualizacoes
Editar o arquivo editorial e executar python scripts/build_hotel_policies.py. Os IDs POL-01 a POL-39 foram preservados; a base estende ate POL-100. A carga SQL preserva o historico, inativa versoes anteriores e insere/atualiza a versao 2; foi gerada, nao executada em PostgreSQL. Alteracoes de parametros tambem precisam revisar o fallback em app.py.

Documentacao da API: https://developers.openai.com/api/docs/models/gpt-4.1-mini e https://developers.openai.com/api/docs/guides/structured-outputs.

## Validacao real pelo WhatsApp concluida
Em 15/09/2026, o workflow ativo com IA recebeu os tres testes do usuario: spa respondeu com POL-14; toalhas e varanda geraram encaminhamentos abertos. As tres respostas foram encontradas na conversa WAHA com ack 3. Evidencia: runtime/waha/knowledge-whatsapp-check.json. A pendencia de publicacao e teste ponta a ponta descrita anteriormente esta concluida. Nao foram encerrados os atendimentos criados pelo usuario.


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

## Respostas curtas (2026-09-15)

O prompt prioriza trechos literais menores e condicoes diretamente relevantes.
Perguntas de continuacao nao repetem detalhes de outros dias ou servicos.
A validacao das citacoes permanece obrigatoria; nao ha reescrita livre de fatos.
O prompt e lido a cada requisicao, dispensando republicacao do workflow principal.

Teste real aprovado: resposta de 93 caracteres com horario de fim de semana
e condicao da tarifa. Evidencia: `runtime/waha/concise-live-results.json`.
Os 27 testes locais tambem passaram. Nenhuma mensagem WhatsApp foi enviada
por este teste; a proxima mensagem nova usa a instrucao atualizada.
