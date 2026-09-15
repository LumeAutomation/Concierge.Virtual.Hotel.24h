# Revisao e aprovacao de politicas

Abra http://localhost:8787/politicas. Informe seu nome, encontre uma politica,
edite os campos e clique em **Salvar rascunho**. Compare a versao para revisao
com o **Texto em uso**. Depois de validar as regras com a equipe do hotel,
clique em **Aprovar e colocar em uso**.

Salvar nao muda a base usada nas respostas. Aprovacao passa a valer nas novas
consultas, sem reiniciar a AURA nem republicar o n8n. Mensagens ja processadas
mantem a resposta persistida. Uma consulta de IA com versao desatualizada e
rejeitada pelo validador existente.

As 100 politicas originais continuam sendo uma base demonstrativa de hotel
ficticio. Inicialmente todas aparecem como nao revisadas. A falta de aprovacao
nao desliga o piloto: o texto demonstrativo continua sendo usado ate haver uma
versao aprovada daquela politica. Isto nao habilita operacao real por si so.

## Armazenamento

- `knowledge/policies.json` e `knowledge/aurora-source.md`: fonte demonstrativa
  original, preservada. Nao refletem automaticamente as edicoes feitas na tela.
- `runtime/aura.sqlite3`, tabela `policy_reviews`: rascunho e versao aprovada.
- `policy_review_history`: historico de salvamentos/aprovacoes, autor, data e
  copia do texto daquela revisao. Inclua o SQLite no backup do projeto.

A consulta da IA e as FAQs locais leem as sobreposicoes aprovadas. A visibilidade
publica/interna permanece definida no catalogo original e nao pode ser ampliada
pelo formulario. As regras de seguranca e encaminhamento para equipe continuam
prevalecendo sobre o texto aprovado.

Uma nova edicao de politica aprovada cria rascunho e preserva a versao em uso.
O numero da revisao impede sobrescrita silenciosa por outro navegador. Em
conflito, copie suas alteracoes antes de recarregar e revisar a versao atual.
O nome informado e um registro operacional local, nao um login autenticado nem
prova de aprovacao institucional. A tela permanece restrita ao servico local.

## Validacao

35 testes Python passaram. O teste `scripts/check_policy_review_browser.py`
usa SQLite temporario e navegador real: edita, salva, recarrega, aprova,
confere resposta usando a nova regra e salva nova revisao sem alterar a vigente.
Tambem confere a tela em tamanho de celular e bloqueio de origem externa.
Evidencias locais: `runtime/policy-review-browser-results.json` e
`runtime/policy-review-browser.png`. Nenhuma politica operacional foi aprovada
pelos testes e nenhuma mensagem foi enviada ao WhatsApp.
