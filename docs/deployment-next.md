# Pendências para operação fora deste computador

Nenhum provedor foi contratado e nenhum dado foi enviado a armazenamento externo.
A configuração atual atende apenas o piloto local do hotel fictício.

## Revisão pelo hotel

`runtime/policy-review-checklist.csv` reúne as 100 políticas, texto, revisão,
departamento e campos para responsável, decisão e observações. Regenere com
`python scripts/export_policy_review.py`. O CSV é material de revisão; editar
esse arquivo não publica alterações. Um Editor salva os rascunhos na tela
Políticas e um Gestor/Administrador aprova o conteúdo confirmado pelo hotel.
Não houve aprovação automática da base demonstrativa.

## Hospedagem contínua

Antes de provisionar, definir provedor/conta, orçamento, domínio, responsável,
hotel real, participantes e disponibilidade esperada. A migração precisa
incluir execução persistente da AURA e n8n, volume WAHA, HTTPS e controle de
acesso à equipe. Não basta expor a porta local ou abrir um túnel. As verificações
de Host/Origin da AURA são locais e exigem projeto específico para implantação
remota. Não alterar esses controles para aceitar qualquer origem.

## Backup externo

O backup local já inclui SQLite (atendimentos, políticas, contas com hashes,
contatos e controle de envios), knowledge, prompts e templates. Não inclui
credenciais n8n, sua chave de criptografia/banco, .env, Bearer token local ou
volume de sessão WAHA. Uma migração completa exige preservar esses componentes
separadamente e de forma cifrada.

Para executar a cópia externa faltam destino aprovado, credenciais e política
de retenção. Definir armazenamento privado com criptografia, acesso restrito,
monitoramento e teste de restauração em ambiente isolado. Não copiar senhas ou
arquivos de sessão para repositório Git. Proteger os backups do SQLite: contêm
dados de atendimento e hashes de senha. Ao restaurar uma cópia, invalidar sessões
anteriores antes de liberar o acesso, preservando o controle de idempotência.

## Novo login Windows

A tarefa `AURA - Supervisor local` continua configurada para o login do usuário.
Reiniciar a tarefa verifica o mecanismo de execução/recuperação, mas não substitui
um teste após sair e entrar novamente no Windows. Esse teste fica para o próximo
login normal, sem encerrar a sessão atual nem reiniciar a máquina durante o trabalho.
