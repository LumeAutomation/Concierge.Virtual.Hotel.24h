# Servidor HTTP — AURA

Implementado em 17/09/2026. Responsável pela implementação e validação técnica: Codex, sob autorização do operador. O aceite operacional do hotel permanece no checklist geral.

`python app.py` inicia Waitress 3.0.2, com rotas WSGI em `web_server.py`. O supervisor mantém o mesmo comando e interpretador. `app.Handler` é apenas compatibilidade para testes antigos; não atende a instância em execução.

## Instalação e execução

No diretório do projeto, com o Python utilizado pelo supervisor:

```powershell
python -m pip install -r requirements-operations.txt
python app.py
```

Não iniciar uma segunda instância quando o supervisor já estiver executando a aplicação. O instalador do supervisor verifica tanto `psutil` quanto `waitress`. Ausência da dependência impede a inicialização; não existe retorno automático ao servidor de demonstração.

| Controle | Configuração atual |
| --- | --- |
| Endereço | Apenas `127.0.0.1` |
| Porta | `AURA_PORT`, padrão 8787 |
| Trabalhadores | 8 threads |
| Conexões ativas / backlog | 100 / 100 |
| Corpo / cabeçalhos | 16 KiB cada |
| Conexão inativa | 30 segundos, limpeza a cada 5 segundos |
| Proxy | Sem proxy confiável; cabeçalhos encaminhados não confiáveis removidos |
| Métodos | GET, HEAD, POST; demais recebem 405 |
| Erro inesperado da aplicação | JSON 500 genérico; log apenas da classe do erro |

Login, cookies, permissões e validação de Host/Origin continuam ativos. A resposta HEAD preserva os cabeçalhos de GET sem corpo. Rejeições do parser (413/431) podem retornar texto e encerrar a conexão antes de consumir os dados excedentes; não dependem das rotas JSON. O limite de inatividade não interrompe uma operação Python em andamento.

Configuração baseada na [documentação oficial do Waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html). Publicação HTTPS, política de rede e revisão do chat local sem autenticação continuam no próximo bloqueio do checklist. Esta configuração não autoriza exposição pública direta.

## Evidências e reprodução

```powershell
python -m unittest discover -s tests
python scripts/check_production_mode_browser.py
python scripts/check_guest_service_browser.py
python scripts/check_reservations_browser.py
```

- Suíte: 121 testes aprovados, incluindo transporte Waitress real, login e permissões, Host/Origin, credencial de integração, métodos, tamanho de corpo/cabeçalhos e erro interno sem exposição da mensagem da exceção.
- Carga isolada: 120 requisições, 12 clientes concorrentes, alternando saúde, FAQ e repetição do mesmo pedido. Critério previamente definido: zero erros, p95 inferior a 5 segundos e exatamente um pedido/uma interação para o identificador repetido.
- Resultado da execução na suíte: zero erros, p95 de 4.309 segundos e máximo de 10.612 segundos; sem duplicações. Relatório local: `runtime/http-load-results.json` (sobrescrito a cada execução).
- O critério dessa carga local foi atendido. A latência máxima e a fila observada exigem dimensionamento e observação prolongada no equipamento definitivo; este ensaio não comprova capacidade comercial nem disponibilidade contínua.
- Navegadores usam Waitress e bancos temporários. Relatórios em `runtime/production-mode-browser-results.json`, `runtime/guest-service-browser-results.json` e `runtime/reservations-browser-results.json`. Nenhum envio real de WhatsApp nesses testes.
- Backup local verificado antes da ativação. Retomada pelo supervisor confirmada com `Server: waitress` e `/api/health` em `local_demo`; AURA, n8n, workflow e sessão WhatsApp saudáveis na consulta posterior.

O teste de reservas também verifica salvar uma política sem alterar o texto original com marcadores de personalização. O prazo de espera dessa gravação é de 30 segundos no ambiente de arquivos em rede.

## Recuperação

Antes de atualizar, guardar o código conhecido e executar o backup operacional verificado. Em falha de atualização, recuperar os arquivos de código da versão anterior e reiniciar somente a aplicação pelo procedimento do supervisor. Este ajuste não introduz migração de banco. O backup operacional não é um pacote completo do código nem das integrações; restauração integral continua pendente no checklist.
