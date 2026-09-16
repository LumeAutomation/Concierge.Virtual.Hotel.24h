# Atualização de escopo e implementação — 16/09/2026

O usuário definiu que este sistema é um modelo: manter a base demonstrativa e
somente sua conta de equipe. Testes no celular serão feitos posteriormente.

Implementado nesta continuação:
- Nova política com código sequencial transacional e ordenação numérica.
- Criar e colocar em uso atualiza a base imediatamente; rascunho fica fora.
- POL-00: identificação e boas-vindas na primeira interação registrada.
- Prefixo AURA TESTE opcional; contatos autorizados continuam exigidos.
- Workflow sem ChatGPT/OpenAI; atendimento factual extrai texto local.
- n8n compactado de 773,55 MB para 10,15 MB, sem perda de registros/credenciais,
  após backup SQLite verificado em %LOCALAPPDATA%/AURA/maintenance.
- Supervisor configura uma execução por vez, um runner JS e pool SQLite de 1;
  diagnósticos remotos e notificações de versão desabilitados.

Inicialização automática corrigida: prioridade 4 (normal) no Agendador,
substituindo a prioridade 7 que colocava os serviços abaixo do normal.
Após a correção: 19 verificações em 180 segundos, todas HTTP 200 para AURA
e n8n; quatro eventos sintéticos bloqueados, sem envio WhatsApp, sem
interação persistida e sem novos erros de ping SQLite, mutex ou runner.
A RAM ainda ficou entre 86,3% e 97,4%; esta janela curta não comprova
estabilidade prolongada nem prontidão para produção.

Verificação final de acesso aprovada: AURA, n8n, workflow e WhatsApp WORKING.
Uma consulta anterior ao WAHA falhou transitoriamente; nova consulta direta e
a repetição completa passaram. Acompanhar também o WAHA nas próximas medições.

Evidências novas: runtime/new-policies-browser-results.json,
runtime/stability-results.json e %LOCALAPPDATA%/AURA/maintenance/compact-results.json.
Não confundir a janela de observação registrada com garantia de disponibilidade.

Pendente: usuário informar o novo número e confirmar se será a conta pareada do
robô ou o participante autorizado. Nenhuma sessão WhatsApp foi desconectada.
Depois da estabilidade: segurança → backup/recuperação → operação diária.

O restante deste arquivo documenta a etapa anterior.

---

# Retomada do projeto - 16/09/2026

## Implementado nesta etapa

- Login individual e perfis Administrador, Recepção, Editor de políticas e Gestor.
- Troca obrigatória de senha temporária, expiração/revogação de sessões,
  proteção de APIs e identidade da sessão nos atendimentos e políticas.
- Administração de usuários e contatos em http://localhost:8787/equipe.
- WF-03 atualizado e publicado com credencial local e verificação de contato
  antes de consultar IA ou persistir atendimento. Prefixo [AURA TESTE] mantido.
- Lista de contatos inicia vazia: entradas WhatsApp ficam bloqueadas até
  o administrador cadastrar participantes confirmados.
- Supervisor corrigido para consultar processos diretamente via psutil e usar
  diretório de trabalho local; tarefa de login reinstalada.
- CSV das 100 políticas exportado para revisão humana.

## Acessos

- Login: http://localhost:8787/login
- Conta inicial: uiliam. Senha temporária somente no arquivo local
  `%LOCALAPPDATA%\AURA\initial-access.txt`. Trocar no primeiro acesso.
- Recepção: http://localhost:8787/recepcao
- Políticas: http://localhost:8787/politicas
- Operação: http://localhost:8787/operacao
- n8n: http://localhost:5678/workflow/auraWahaInput03
- WAHA: http://localhost:3000/dashboard/

## Validação

44 testes Python da aplicação/acesso passaram; outros três testes da correção
do supervisor passaram. Filtros JavaScript de entrada e resposta passaram.
Navegador real validou primeiro login, troca de senha, identidade da recepção,
conclusão de pedido local, criação de usuário, restrição de aprovação, contatos,
logout e telas em largura de celular, com banco isolado e sem envio WhatsApp.

Verificação instalada concluída em 16/09/2026 às 09h46 (Brasília): AURA,
n8n, workflow e WhatsApp saudáveis; supervisor ativo; credencial exigida;
contato fictício não autorizado retornou HTTP 200 no webhook sem persistir
atendimento nem enviar mensagem. Essa prova valida o bloqueio, não uma conversa
real com participante autorizado.

Durante o trabalho houve oscilações do n8n e 94,3% da memória física estava em
uso (aproximadamente 450 MB disponíveis). Não foram encerrados aplicativos do
usuário. A verificação final saudável não garante disponibilidade contínua
nesse computador sob pressão de memória.

Evidências: `runtime/access-browser-results.json` e
`runtime/access-live-results.json` (esta última registra a verificação instalada).
Backups SQLite verificados são mantidos em `%LOCALAPPDATA%\AURA\backups`.

## Ainda depende de informação ou ação humana

1. Informar/cadastrar os números autorizados. Depois, testar uma nova conversa
   real e confirmar recebimento no celular do participante.
2. A equipe do hotel deve revisar as políticas demonstrativas. Material:
   `runtime/policy-review-checklist.csv`; aprovação pelo perfil Gestor/Admin.
3. Validar a inicialização após o próximo login Windows. A tarefa foi executada,
   mas não houve logout nem reinicialização do computador nesta etapa.
4. Definir provedor/conta, orçamento e destino de backup externo para hospedagem
   contínua. Nenhum serviço contratado ou dado enviado a um provedor.

Procedimentos: docs/access.md, docs/operations.md e docs/deployment-next.md.
Runtime, segredos e conversas continuam fora do Git. O backup AURA não substitui
backup separado das credenciais/banco n8n, Bearer token e volume de sessão WAHA.
