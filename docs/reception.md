# Recepcao: assumir, concluir e avisar

Abra http://localhost:8787/recepcao e informe seu nome. Clique em **Assumir
atendimento** no pedido e, depois de conferir que ele foi atendido, em
**Concluir e avisar no WhatsApp**. Pedidos criados no painel local mostram
**Concluir atendimento** e nao geram mensagens externas.

O aviso informa que a recepcao marcou aquele protocolo como concluido.
Ele nao confirma automaticamente entrega de itens, reservas ou cobrancas.
Apenas a conclusao feita pelo operador dispara o aviso; assumir nao envia.
O modelo usa dados demonstrativos e contatos autorizados, sem prefixo obrigatório.

## Registro e envio

A tabela `handoff_work` guarda responsavel, inicio, conclusao e estado do aviso.
A conclusao e a reserva da tentativa sao persistidas juntas antes do envio.
Repetir o clique ou recarregar a pagina nao cria uma segunda tentativa.
Pedidos antigos ja resolvidos nao sao notificados retroativamente.

- `sent`: WAHA retornou identificador; nao significa leitura pelo destinatario.
- `unknown`: envio incerto ou falha. Conferir conversa; nao ha reenvio automatico.
- `sending`: tentativa em andamento; apos dois minutos vira `unknown` na consulta.
- `local_only`: sem destino WhatsApp.

O pedido continua concluido mesmo se o aviso falhar. O painel exibe os dois
estados separadamente. O nome e uma identificacao operacional local, nao login
nem prova de identidade. O servico permanece restrito ao computador local.
Nao ha reabertura nem transferencia entre operadores nesta etapa.

## Validacao

`python -m unittest discover -s tests -q`
`python scripts/check_reception_browser.py`

O teste de navegador usa SQLite temporario e transporte simulado: percorre
assumir, concluir, sucesso, timeout e recarga, sem enviar WhatsApp real.
Evidencia: runtime/reception-browser-results.json e runtime/reception-flow.png.
O teste real com o hospede deve usar um pedido novo de demonstracao e a
conclusao pelo operador. Nenhum pedido existente e concluido na implantacao.
