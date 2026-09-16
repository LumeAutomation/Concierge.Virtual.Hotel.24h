# AURA — Concierge Virtual Hotel 24h

Piloto local do Aurora Grand Resort & Spa, um resort **fictício**. Interface em português, respostas determinísticas com referência às políticas, encaminhamentos persistidos e fila da recepção.

## Executar

A aplicação requer Python 3.10+; não precisa instalar pacotes. O supervisor Windows
usa a dependência de `requirements-operations.txt`.

```powershell
python app.py
```

Abra http://127.0.0.1:8787. A recepção está em http://127.0.0.1:8787/recepcao.
Também pode executar `scripts/start.ps1`. Os dados ficam em `runtime/aura.sqlite3`; fechar o navegador não os apaga. Para parar o servidor, Ctrl+C no terminal.

## Testar

```powershell
python -m unittest discover -s tests -v
```

Experimente o horário do café, um pedido de toalhas e um cancelamento. Na recepção, altere o status e atualize a página. Emergências simuladas devem aparecer como urgentes; o piloto não notifica pessoas nem serviços reais.

## O que está conectado

- Chat → regras conservadoras → SQLite → fila local.
- Respostas de horários/check-in/Wi-Fi usam trechos revisados de `knowledge/policies.json`.
- Pedidos, reservas, dúvidas sem resposta suportada e emergências geram encaminhamento local.
- O protocolo só é devolvido depois do commit. Reenvios com o mesmo `request_id` não duplicam registros.

**Integração do modelo:** WAHA → n8n → base local AURA → WhatsApp.
Sem chamada ao ChatGPT/OpenAI e sem pesquisa externa. Respostas factuais copiam
conteúdo cadastrado; dúvidas sem correspondência segura vão para o responsável.
As políticas demonstrativas foram mantidas por escolha do usuário, único operador.

Em `/politicas`, **Nova política** cria o próximo código e ordena numericamente.
**Criar e colocar em uso** publica imediatamente para Administrador/Gestor;
rascunhos não entram na base. `POL-00` contém a apresentação da primeira interação.

O WhatsApp aceita texto normal, sem `[AURA TESTE]`. A lista de contatos autorizados
continua obrigatória; lista vazia bloqueia entradas. Login da equipe em `/login`.

Próximas etapas: trocar o pareamento para o número próprio confirmado pelo usuário,
testes reais posteriores pelo usuário, observar estabilidade, revisar segurança,
backup/recuperação e operações diárias, nessa ordem.

## Arquivos

- `app.py`: API e armazenamento local; `web/index.html`: chat e recepção.
- `prompts/aura-system.txt`: prompt preparado para futura integração de IA; não usado pelo motor local.
- `database/001_schema.sql` e `002_seed.sql`: base PostgreSQL, ainda não aplicada.
- `workflows/WF-01-aura-local.json`: template legado da ponte local; a integração atual usa o WF-03.
- `docs/n8n.md`: configuração e limites da ponte.
- `docs/retomada.md`: estado e próximos passos.

Os arquivos locais de acesso/instalação estão ignorados pelo Git; não são necessários para executar o piloto.

