# Retomada — 11/09/2026

## Concluído e verificado

- Recuperado o escopo da conversa interrompida: piloto AURA local, banco e ponte n8n.
- Chat e fila de recepção em http://127.0.0.1:8787 e /recepcao.
- SQLite em runtime/aura.sqlite3 com protocolos idempotentes e status persistidos.
- 10 testes passaram: fontes de FAQ, emergência, reserva, pergunta desconhecida, conteúdo sensível, concorrência, conflito de protocolo, falha de armazenamento, entrada inválida e persistência.
- Teste Playwright passou no servidor real: clique em pergunta, envio, resposta com fonte, pedido fictício, navegação para recepção, alteração de status, recarga e confirmação. Atendimento QA encerrado como resolvido.
- Viewport móvel 390x844 sem overflow horizontal; nenhum erro JavaScript observado.
- Evidências locais: runtime/browser-check.json, chat.png, recepcao.png e mobile.png.
- POST inválido devolveu 400; origem externa devolveu 403.

## Preparado, ainda não executado

- database/001_schema.sql: 11 tabelas PostgreSQL, relações e RLS sem acesso público.
- database/002_seed.sql: hotel fictício e 39 políticas existentes.
- workflows/WF-01-aura-local.json: workflow desativado, com Header Auth a configurar. Importação e execução no n8n ainda não verificadas.

## Próximo bloco

Conectar o n8n ao piloto conforme docs/n8n.md e testar a ponte ponta a ponta. Confirmar infraestrutura PostgreSQL/Supabase e disponibilidade de conta/provedor de IA e WhatsApp antes das integrações correspondentes. Não há chaves configuradas pelo piloto.

O prompt em prompts/aura-system.txt está preservado para a futura IA. A aplicação atual usa regras em português, não IA ou RAG, e não envia notificações externas.

## Reiniciar

Na pasta do projeto: python app.py. O servidor pode estar em segundo plano; conferir /api/health antes de iniciar outro. AURA_PORT e AURA_DB permitem escolher porta e arquivo de dados.

As alterações estão locais, sem commit ou push nesta retomada. As anotações de acesso estão ignoradas pelo Git.

## Entrada WhatsApp preparada

WF-02-whatsapp-entrada.json recebe mensagens via WhatsApp Trigger, filtra status e normaliza eventos para a API local. Ainda requer importacao, credencial e URL HTTPS publica do n8n; nao houve teste real Meta -> n8n. Nao envia respostas ao celular. Veja docs/whatsapp-entrada.md. Validacao: 11 testes Python e 10 verificacoes Node passaram. O bloqueio Meta 130497 de saida permanece pendente apos configurar BRL.
