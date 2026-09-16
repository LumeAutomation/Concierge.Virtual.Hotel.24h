# Operacao local: inicializacao, backup e saude

Painel: http://localhost:8787/operacao

## Inicializacao e recuperacao

A tarefa Windows `AURA - Supervisor local` inicia ao entrar no usuario atual,
sem janela. Ela roda `pythonw.exe` com um agente em `%LOCALAPPDATA%\AURA\agent`.
O agente guarda o caminho completo da pasta do projeto (UNC quando aplicavel),
verifica os servicos a cada 30 segundos e inicia processos que pararam:
AURA em 8787, n8n em 5678 e o container existente `aura-waha` em 3000.
Se necessario, inicia o Docker Desktop. Nao baixa imagens nem recria sessoes.

A tarefa nao exige senha armazenada nem privilegio administrativo. Foi criada
para a sessao interativa: antes de entrar no Windows, durante suspensao ou com
o computador desligado, nao ha atendimento garantido. A pasta do projeto deve
estar acessivel. O supervisor nao encerra processos travados ou processos que
ja estejam usando as portas; o painel indicara falhas observaveis.

Reinstalar/atualizar o agente depois de alterar seus scripts:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Install-AuraAutostart.ps1`
Para parar: encerre a tarefa no Agendador de Tarefas. Os servicos que ja estavam
rodando continuam ativos. Desabilite a tarefa para impedir o proximo login.

## Backup

Uma copia a cada 24 horas, enquanto o supervisor estiver em execucao. A primeira
copia acontece assim que ele inicia sem backup recente. Sao mantidas as ultimas
14 copias validas em `%LOCALAPPDATA%\AURA\backups`.

O banco SQLite e copiado pela API de backup, com suporte a banco em uso. O ZIP
inclui `runtime/aura.sqlite3` (atendimentos, politicas aprovadas, rascunhos e
controle dos envios), knowledge, prompts e templates de workflow. Cada arquivo
tem SHA-256 no manifesto, e a copia do banco passa por `PRAGMA quick_check`.
Somente depois dessas verificacoes a copia recebe status de sucesso.

Este backup e da aplicacao AURA. Nao inclui .env, credenciais/BD do n8n, volume
de sessao do WAHA nem instaladores. Nao equivale a uma copia completa da maquina.
A pasta esta no perfil local do Windows, separada da pasta de rede do projeto;
nao e backup externo ou em nuvem. Ela contem dados de atendimento.

Antes de restaurar, pare o supervisor e a AURA, preserve o banco atual e valide
o ZIP com `operations.verify_archive(caminho)`. Restaure em ambiente isolado
primeiro; o banco inclui o controle que impede reenvios de mensagens antigas.
Nao substitua o banco enquanto a AURA estiver rodando.

## Painel

Exibe disponibilidade da AURA e n8n, publicacao do fluxo `auraWahaInput03`,
sessao WhatsApp WORKING, sinal do supervisor e backup recente (ate 26 horas).
O painel atualiza a cada 15 segundos. Os alertas sao visuais locais, sem envio
por email/WhatsApp. Nao testa saldo da OpenAI nem envia mensagens de prova.
Saude dos servicos nao comprova entrega de uma conversa especifica.

## Validacao

38 testes Python, incluindo backup com banco WAL aberto, restauracao em banco
temporario, retencao de 14 copias, exclusao de .env e estados de indisponibilidade.
A recuperacao real da AURA e a tela de operacao sao verificadas separadamente
em `runtime/operations-live-results.json`.

Validacao ao vivo concluida: a AURA foi interrompida e recuperada pelo supervisor
com novo PID; o painel mostrou seis sinais normais e foi conferido no navegador
e em largura de celular. Uma segunda instancia do supervisor encerrou sem
iniciar servicos adicionais. A tarefa de login esta registrada e em execucao;
o computador nao foi reiniciado para testar um novo login.


## Atualização de 16/09/2026

As telas e a API de operação agora exigem perfil Gestor ou Administrador.
A consulta de processos do supervisor usa `psutil` diretamente, sem abrir
PowerShell por rodada. Instale `requirements-operations.txt` ao preparar outro
computador. O instalador verifica essa dependência antes de alterar a tarefa.
Os serviços iniciam com diretório de trabalho em `%LOCALAPPDATA%\AURA`, evitando
usar o compartilhamento de rede como diretório corrente. AURA ainda lê o código
e o banco na pasta original; acesso ao compartilhamento continua necessário.
O estado registra a etapa em andamento antes de cada serviço, além do resultado
final. A tarefa foi reinstalada e sua recuperação verificada; novo login Windows
continua pendente de um teste natural pelo usuário.


## Modelo local com um operador — continuação em 16/09

O banco n8n foi compactado offline de 773,55 MB para 10,15 MB. A manutenção
verificou o backup, a integridade, a contagem de registros de todas as tabelas
e os bytes cifrados das credenciais antes/depois. Artefato protegido no perfil
local: AURA/maintenance/compact-results.json. Não houve exclusão de registros.

O supervisor limita execução de produção e runner JS a 1, pool de leitura
SQLite a 1, heap do runner a 256 MB e token inicial do runner a 120 segundos.
Diagnósticos remotos e notificações de versão foram desativados. Na segunda
observação, os módulos opcionais mcp-registry e community-packages foram
retirados do carregamento do supervisor: o WF-03 usa apenas nós nativos.
Os pacotes instalados permanecem no disco e os workflows não foram apagados;
outros workflows que dependam de plugins comunitários exigem reabilitar esse
módulo em scripts/supervise.py e reinstalar/reiniciar o supervisor/n8n.

O monitor `python scripts/check_stability.py` aguarda prontidão e webhook,
observa requisições por pelo menos três minutos e registra timeouts e erros,
sem enviar WhatsApp. `runtime/stability-before-modules.json` preserva a primeira
observação, que falhou; `runtime/stability-results.json` é a mais recente.
A redução do banco e dos limites não é, sozinha, prova de estabilidade.


### Prioridade da tarefa Windows

Foi confirmado que o padrão 7 do Agendador iniciava supervisor, AURA e n8n
em BELOW_NORMAL_PRIORITY_CLASS. A tarefa passou a usar prioridade 4 (normal).
Além de CPU, o Agendador aplica prioridade de I/O e memória conforme a tabela
oficial: https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-priority-settingstype-element
Isso é especialmente relevante na máquina de 8 GB sob pressão de memória.
Não foi aplicada prioridade alta nem tempo real, e nenhum aplicativo do usuário
foi encerrado. `runtime/stability-before-normal-priority.json` preserva a medição
anterior; compare com o relatório final antes de concluir que a correção resolveu
as oscilações. A configuração persistente está em Install-AuraAutostart.ps1.
