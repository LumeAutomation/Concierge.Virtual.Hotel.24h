# AURA — Guia de comandos e uso

Guia para executar o Concierge Virtual Hotel 24h no Windows pelo terminal PowerShell do VS Code. Para abrir o terminal, use **Terminal → Novo Terminal**. Execute os comandos abaixo um por vez.

## 1. Entrar na pasta do projeto

```powershell
Set-Location -LiteralPath 'C:\Users\willa\Desktop\Lume Ai & Automation\Concierge.Virtual.Hotel.24h'
```

Se o terminal já estiver nessa pasta, pule este comando.

## 2. Conferir o Python

```powershell
python --version
```

O sistema requer **Python 3.10 ou superior** e usa apenas a biblioteca padrão: não precisa de `pip install`, `npm install` nem banco externo para rodar o piloto.

Se `python` não for reconhecido, tente `py --version`. Se funcionar, use `py` no lugar de `python` nos comandos deste guia. Se nenhum funcionar, instale o Python 3.10 ou superior com a opção de adicionar ao PATH e reabra o terminal.

## 3. Iniciar o sistema

```powershell
python app.py
```

Mantenha esse terminal aberto enquanto usa o sistema. O servidor fica ocupado atendendo as páginas; isso é normal.

Alternativa disponível no projeto:

```powershell
.\scripts\start.ps1
```

Se o Windows bloquear a execução do script, use `python app.py` diretamente.

## 4. Abrir e utilizar

Com o servidor rodando, abra estes endereços no navegador:

| Tela | Endereço | Uso |
| --- | --- | --- |
| Chat do hóspede | http://127.0.0.1:8787 | Fazer perguntas e registrar pedidos |
| Recepção | http://127.0.0.1:8787/recepcao | Consultar encaminhamentos e alterar o status |
| Saúde da API | http://127.0.0.1:8787/api/health | Conferir se o servidor está respondendo |

Para abrir pelo PowerShell, use **outro terminal**:

```powershell
Start-Process 'http://127.0.0.1:8787'
Start-Process 'http://127.0.0.1:8787/recepcao'
```

Experimente no chat:

- `Qual é o horário do café da manhã?`
- `Quero toalhas no quarto de teste.`
- `Quero cancelar minha reserva fictícia.`

Perguntas sobre políticas podem receber resposta direta. Pedidos que precisam da equipe geram protocolo e aparecem na recepção. Abra a recepção, confira o pedido, altere seu status e atualize a página para verificar que foi salvo.

## 5. Parar e reiniciar

No terminal onde executou `python app.py`, pressione **Ctrl+C** para parar.

Para reiniciar, execute novamente:

```powershell
python app.py
```

Fechar apenas a aba do navegador não para o servidor. Os atendimentos ficam salvos em `runtime/aura.sqlite3` e continuam disponíveis depois de reiniciar.

## 6. Verificar se já está rodando

Execute em outro terminal:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8787/api/health'
```

O resultado esperado inclui `status: ok`, `mode: local_demo` e `storage: sqlite`. Se houver erro de conexão, confira se o servidor foi iniciado e qual porta está usando.

Se aparecer erro de porta ocupada ao iniciar, faça esta verificação antes de abrir outra instância. Se a API responder normalmente, acesse o sistema que já está rodando.

## 7. Usar outra porta, se necessário

No terminal que vai iniciar o servidor:

```powershell
$env:AURA_PORT = '8788'
python app.py
```

Nesse caso, acesse http://127.0.0.1:8788 e http://127.0.0.1:8788/recepcao. Use também `8788` no comando de saúde da API.

Para voltar à porta padrão, pare com **Ctrl+C** e execute:

```powershell
$env:AURA_PORT = '8787'
python app.py
```

## 8. Executar as verificações do projeto

Testes do aplicativo, sem precisar iniciar o servidor:

```powershell
python -m unittest discover -s tests -v
```

O resultado esperado é `OK` ao final.

Verificação opcional da preparação de mensagens do WhatsApp, caso tenha Node.js instalado:

```powershell
node scripts/check_whatsapp_input.cjs
```

Esse comando verifica o processamento local; não conecta o WhatsApp nem envia mensagens.

## 9. Fazer uma cópia dos atendimentos

Primeiro pare o servidor com **Ctrl+C**. Depois execute na pasta do projeto:

```powershell
$auraBackup = 'runtime/aura-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.sqlite3'
Copy-Item -LiteralPath 'runtime/aura.sqlite3' -Destination $auraBackup
```

A cópia fica na pasta `runtime`, com data e hora no nome. O banco original é criado no primeiro uso do sistema. Este comando considera o caminho padrão do banco.

## 10. Integrações e arquivos úteis

O sistema atual é um **piloto local com regras**, sem IA conectada e sem envio de notificações reais. Use dados fictícios. O chat e a recepção devem permanecer no acesso local configurado pelo projeto.

Os fluxos n8n estão preparados em arquivos, mas sua importação, autenticação e conexão externa ainda precisam de configuração. Iniciar `app.py` não inicia o n8n nem conecta o WhatsApp automaticamente.

| Arquivo | Para que serve |
| --- | --- |
| [README.md](README.md) | Visão geral do projeto |
| [docs/n8n.md](docs/n8n.md) | Configurar a ponte local com n8n |
| [docs/whatsapp-entrada.md](docs/whatsapp-entrada.md) | Configurar a entrada de mensagens do WhatsApp e consultar limitações |
| [docs/retomada.md](docs/retomada.md) | Estado registrado e próximos passos |
| [knowledge/policies.json](knowledge/policies.json) | Políticas usadas nas respostas do piloto |

## 11. Executar o n8n

O n8n já está instalado neste computador. Para usar o n8n junto com a AURA, mantenha **dois terminais abertos** no VS Code. Use **Terminal → Novo Terminal** para abrir o segundo.

**Terminal 1 — iniciar a AURA**, na pasta do projeto:

```powershell
python app.py
```

**Terminal 2 — iniciar o n8n:**

```powershell
n8n.cmd start
```

Use `n8n.cmd` no PowerShell para evitar o bloqueio de execução do arquivo `n8n.ps1`. Aguarde o terminal informar que o editor está disponível e acesse **http://localhost:5678** no navegador. Entre com a conta local que você configurou no n8n.

Se o comando não for reconhecido, use o caminho da instalação encontrada neste computador:

```powershell
& "$env:APPDATA\npm\n8n.cmd" start
```

Se a porta `5678` estiver ocupada, abra http://localhost:5678 antes de tentar iniciar outra instância: o n8n pode já estar em execução.

### Usar os fluxos do projeto

1. Abra o editor do n8n em http://localhost:5678.
2. Abra um workflow existente ou importe o JSON desejado pelo menu do editor, na opção de importar arquivo.
3. Para a ponte local, escolha `workflows/WF-01-aura-local.json` e siga [docs/n8n.md](docs/n8n.md), incluindo a credencial Header Auth.
4. Para a entrada WhatsApp, escolha `workflows/WF-02-whatsapp-entrada.json` e siga [docs/whatsapp-entrada.md](docs/whatsapp-entrada.md), incluindo credenciais e HTTPS.
5. Para n8n executando diretamente neste Windows, o nó HTTP Request deve apontar para `http://127.0.0.1:8787/api/chat`. Se mudar a porta da AURA, ajuste esse endereço no fluxo.

Abrir o editor não ativa automaticamente os workflows nem conclui a integração WhatsApp. O fluxo de entrada preparado não envia respostas ao celular.

### Parar e reiniciar o n8n

No terminal do n8n, pressione **Ctrl+C**. Caso o Windows peça confirmação para encerrar o arquivo em lotes, confirme. Para iniciar novamente:

```powershell
n8n.cmd start
```

Para encerrar tudo, pare também a AURA com **Ctrl+C** no terminal 1. Fechar o navegador não encerra esses processos.

## Rotina rápida

1. Abra o terminal na pasta do projeto.
2. Execute `python app.py`.
3. Acesse http://127.0.0.1:8787 para conversar.
4. Acesse http://127.0.0.1:8787/recepcao para acompanhar os pedidos.
5. Ao terminar, pressione **Ctrl+C** no terminal do servidor.
