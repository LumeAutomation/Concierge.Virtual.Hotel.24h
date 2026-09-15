# Retomada do projeto - 15/09/2026

## Implementado

- WAHA e n8n: entrada [AURA TESTE] e resposta no WhatsApp.
- IA com citacoes verificadas, respostas curtas e contexto por conversa.
- Controle de duplicidade e tratamento de entrega incerta.
- Recepcao: assumir, concluir e avisar pelo WhatsApp.
- 100 politicas demonstrativas, rascunhos e aprovacao local.
- Supervisor no login Windows, recuperacao, backup diario e painel de saude.

## Acessos locais

Recepcao: http://localhost:8787/recepcao
Politicas: http://localhost:8787/politicas
Operacao: http://localhost:8787/operacao
n8n: http://localhost:5678/workflow/auraWahaInput03
WAHA: http://localhost:3000/dashboard/

## Verificacoes

38 testes Python passaram. Recepcao, politicas e operacao foram conferidas em
navegador real. O supervisor recuperou a AURA apos interrupcao controlada.
Backup SQLite criado, restaurado em ambiente de teste e verificado.

## Proximo trabalho

1. Login individual e permissoes por funcao.
2. Revisao das politicas pela equipe do hotel: a base ainda e demonstrativa.
3. Testar inicio depois de novo login Windows, sem reiniciar a maquina agora.
4. Piloto restrito a numeros autorizados antes de remover [AURA TESTE].
5. Hospedagem continua e backup externo para operacao real.

## Versionamento e dados locais

O Git recebe codigo, telas, scripts, testes, documentacao, politicas
demonstrativas e templates de workflow sem credenciais.
Runtime, .env, conversas, banco e exportacoes autenticadas ficam fora do Git.
O backup local em %LOCALAPPDATA%\AURA\backups preserva banco, atendimentos,
rascunhos, politicas aprovadas e controle dos envios.
Credenciais do n8n, arquivos .env e sessao WAHA continuam nos locais originais;
nao fazem parte do backup da AURA e exigem migracao separada.
Clonar o repositorio nao recria automaticamente as credenciais.

Procedimentos: docs/operations.md, docs/policy-review.md, docs/reception.md,
docs/knowledge-integration.md e docs/waha-n8n.md.
