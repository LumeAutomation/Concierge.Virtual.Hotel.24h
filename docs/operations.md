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
