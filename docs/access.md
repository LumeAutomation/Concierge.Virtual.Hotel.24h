# Acesso individual e piloto restrito

Entrada: http://localhost:8787/login. Use sempre o mesmo host no navegador;
o cookie de localhost é diferente do cookie de 127.0.0.1.

## Primeiro acesso

O instalador `python scripts/setup_access.py` cria uma única conta inicial,
`uiliam`, e grava a senha temporária em
`%LOCALAPPDATA%\AURA\initial-access.txt`. Não copia a senha para documentação,
Git ou console. A senha precisa ser trocada no primeiro acesso. Apague esse
arquivo depois da troca. Executar o instalador novamente preserva as contas.

Em **Equipe e piloto**, o administrador cria contas individuais com senha
temporária, altera perfis, redefine senhas e desativa acessos. Redefinição,
alteração de perfil, desativação, logout e troca de senha revogam sessões.
Não é permitido remover o último administrador ativo nem rebaixar o próprio
acesso administrativo. A tela **Minha senha** permite a troca posterior.

| Perfil | Permissões |
| --- | --- |
| Recepção | Consultar, assumir e concluir atendimentos |
| Editor de políticas | Consultar políticas e salvar rascunhos |
| Gestor | Recepção, rascunhos, aprovação de políticas e operação |
| Administrador | Todas, inclusive usuários e contatos do piloto |

A identidade de editor, aprovador e atendente vem da sessão no servidor.
Enviar outro nome no JSON não muda essa identidade. Atendimentos já assumidos
continuam pertencendo à pessoa que os assumiu. Não reutilize logins de pessoas
que saíram da equipe.

Senhas têm de 12 a 128 caracteres, salt aleatório e PBKDF2-SHA256 com 600 mil
iterações. Cookies são HttpOnly e SameSite=Strict, com duração máxima de oito
horas; o banco guarda apenas o hash do token de sessão. Cinco falhas por login
bloqueiam novas tentativas por até 15 minutos; há também limite global de 30
falhas na janela. O serviço continua restrito a loopback HTTP. Isso não é uma
implantação pública: HTTPS, autenticação de hóspedes e segregação por hotel
não foram implantados.

## Contatos autorizados

Em **Equipe e piloto**, cadastre somente participantes confirmados. O número
usa apenas dígitos, incluindo DDI e DDD. Alguns eventos do WAHA usam LID em vez
de telefone: nesse caso, confirme a identidade do LID antes de cadastrá-lo;
telefone e LID não são intercambiáveis nem autorizados automaticamente.

Lista vazia bloqueia todas as entradas WhatsApp. Não é necessário escrever `[AURA TESTE]`; o prefixo antigo é aceito opcionalmente. O workflow verifica a lista antes de consultar a base local ou
registrar atendimento. As APIs repetem a verificação, inclusive no envio.
Concluir um atendimento de contato revogado registra a conclusão local com
aviso `blocked`, sem mensagem. Não há importação automática dos números antigos.

## Integração n8n

As APIs de contexto, resposta com IA e envio exigem Bearer token. O arquivo
`runtime/auth/service-token.txt` e a credencial n8n `AURA - servico local`
contêm o mesmo segredo. O template versionado contém apenas o vínculo da
credencial, nunca seu valor. Usuários da equipe não podem usar a sessão web
como credencial de integração.

Para reinstalar o WF-03 nesta mesma instância: gere o template com
`python scripts/build_waha_workflow.py` e execute
`python scripts/install_access_workflow.py`. Esse procedimento preserva os
vínculos existentes de WAHA e OpenAI, publica pelo CLI e exige reiniciar o n8n.
O arquivo temporário de importação da credencial é removido ao final; os
artefatos autenticados ficam em runtime, ignorado pelo Git.

WF-01/WF-02 são templates legados, sem migração/validação nesta etapa. Não os
ative para contornar as restrições do WF-03.

## Verificação

- `python -m unittest discover -s tests -v`
- `python scripts/check_access_browser.py`: navegador com banco temporário.
- `python scripts/verify_access_live.py`: serviços e webhook real com evento
  fictício de contato não autorizado; não envia WhatsApp.

Evidências locais: `runtime/access-browser-results.json` e
`runtime/access-live-results.json`. Um novo teste de conversa autorizada e de
recebimento no celular continua dependendo de participante confirmado.


## Novas políticas e modo restrito

A política POL-00 aparece primeiro e define as boas-vindas da primeira interação
registrada de cada conversa. O texto é editável pela tela de políticas. Emergências
e mensagens sensíveis mantêm a resposta prioritária, sem a abertura de boas-vindas.

**Nova política** reserva o próximo POL-N dentro de uma transação, inclusive se
houver duas criações simultâneas. Os códigos existentes não mudam. A lista é
ordenada pelo número: POL-99, POL-100, POL-101. Administrador/Gestor pode usar
**Criar e colocar em uso**; Editor só cria rascunho. A publicação atualiza a base
SQLite e as próximas consultas, sem reiniciar a AURA ou reimportar o n8n.

O workflow atual não possui nó OpenAI. As perguntas de referência/títulos são
comparados de forma normalizada; intenções conhecidas de horários e acesso
consultam a política correspondente. O texto factual é copiado da fonte, sem
paráfrase gerada. Pergunta ambígua ou sem correspondência vai para o responsável;
seguimentos sem assunto explícito pedem esclarecimento. Políticas internas não
são usadas como resposta factual ao hóspede. Isso elimina geração livre, mas não
valida a veracidade do texto que o administrador cadastra nem garante toda
interpretação possível. Os módulos de validação extrativa antigos permanecem
como código/testes legados, sem uso pelo fluxo publicado.
