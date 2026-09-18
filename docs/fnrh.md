# Painel e persistência — entrega 2

Implementação local em 18/09/2026. Acesse `/fnrh` pelo menu **FNRH**, com perfil Recepção, Gestor ou Administrador. A tela usa as reservas cadastradas, sem copiar CPF/telefone para a resposta da API. As ações são explicitamente simulações e não alteram check-in/checkout da reserva.

- Confira a reserva, marque a conferência humana e escolha o resultado fictício para ensaiar check-in ou checkout.
- As tentativas e o histórico ficam em `fnrh_jobs` e `fnrh_events` no SQLite da instalação e sobrevivem ao reinício. Unicidade por hotel/reserva/operação e transação de escrita impedem execução duplicada concorrente.
- Resultado incerto bloqueia repetição. A reconciliação exige conferência, justificativa e decisão sobre o resultado **simulado**. Não escrever documentos, telefone ou outros dados pessoais na justificativa.
- O histórico mostra ator autenticado, ação, estado e horário. Alterações dos dados conferidos bloqueiam novos ensaios; divergências devem ser investigadas, sem apagar tentativas para forçar repetição.
- Nenhum resultado desta tela confirma envio à plataforma oficial. A avaliação de pendências cobre o cadastro local; não certifica completude do formulário oficial.

API local: GET `/api/fnrh` e POST `/api/fnrh`, protegidas pelas permissões de recepção e validação de Host/Origin. A identidade do autor vem da sessão, nunca do corpo enviado. Migração aditiva ocorre em `app.init_db()`; não remove dados existentes. O backup do SQLite passa a incluir essas tabelas.

O transporte HTTP oficial é um componente separado, documentado em [fnrh-connector.md](fnrh-connector.md), sem ligação às ações do painel. Antes de habilitar envio, ainda é preciso implementar cadastro complementar/acompanhantes, validar domínios e contratos em homologação e ligar o transporte à fila com reconciliação remota. As tabelas SIMULATED_* não podem ser reaproveitadas como comprovantes oficiais.

Teste do painel em banco temporário:

```powershell
python scripts/check_fnrh_browser.py
```

---
# FNRH Digital — preparação local

Entrega 1, 18/09/2026. Responsável técnico: equipe Codex. Mapeamento e simulação com dados fictícios, sem transmissão oficial, coleta adicional no WhatsApp ou alteração das reservas operacionais.

## Executar

```powershell
python scripts/simulate_fnrh.py
python -m unittest discover -s tests -p test_fnrh.py -v
```

O simulador usa uma reserva fictícia embutida e memória descartável. Estados SIMULATED_* não são confirmações oficiais. A saída resume estados e pendências sem CPF ou telefone. Não aceita credenciais nem acessa o banco da instalação. Reiniciar o processo apaga o controle de repetição; persistência durável será parte do conector antes de uso real. O contrato interno não deve ser enviado à API.

## Mapeamento

Consulta em 18/09/2026: [página oficial PMS](https://www.gov.br/turismo/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/ficha-nacional-de-registro-de-hospedes/modulo-meio-de-hospedagem/meios-de-hospedagem-com-pms) e [manual API disponibilizado como 2.4.2](https://www.gov.br/turismo/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/ficha-nacional-de-registro-de-hospedes/modulo-meio-de-hospedagem/meios-de-hospedagem-com-pms/documentacao-api-v2-4-2.pdf). A capa interna ainda identifica 2.4.

| Dado local | Campo documentado / tratamento futuro |
| --- | --- |
| external_id | reserva.numero_reserva |
| arrival / departure | reserva.data_entrada / data_saida; datas previstas |
| guest_name | dados_pessoais.nome |
| cpf | dados_pessoais.documento_id.numero_documento, tipo_documento_id CPF; não cobre estrangeiros |
| phone | dados_pessoais.contato.telefone |
| hotel_id | Identidade local; não equivale ao identificador/credencial oficial |
| room | Sem correspondência identificada no contrato consolidado consultado |
| pre_status | Controle local; pré-check-in concluído não confirma registro oficial |
| checkin_status / checkout_status | Estados locais; não comprovam confirmação da API |

Páginas humanas 19–20: reservas; 26–27: adicionar hóspede; 39–41: pessoa; 45–50: hospedagem consolidada. Faltam dados estruturados de adultos/menores, origem/OTA, nascimento, nacionalidade, residência, e-mail/endereço, gênero, raça, deficiência, motivo da viagem, transporte, responsável por menor e identificadores remotos. Não inferir nacionalidade pelo CPF ou DDI. Não usar updated_at como horário de entrada/saída: registrar o evento específico.

Condições expressas: descrição de gênero para OUTRO; tipo de deficiência para SIM; cidade IBGE e estado para residência no Brasil; logradouro/número/bairro quando CEP preenchido; responsável para menor de 18; número OTA para origem OTA. No fluxo de adicionar hóspede, motivo/transporte dependem do estado de check-in/checkout. A extração da tabela de obrigatoriedade é incompleta: esta lista não certifica todos os campos obrigatórios. Conferir schema e condições no ambiente de homologação.

## Fluxo e próximas entregas

O manual apresenta POST /hospedagem/registrar (reserva e hóspedes juntos), ou POST /reservas, POST /pessoas e POST /reservas/{reserva_id}/hospedes. Entrada/saída usam PATCH /hospedes/{hospede_id}/checkin e /checkout. Escolher e homologar um caminho antes do transporte. Há divergências de hosts nos exemplos, paginação e nomes de rota no manual; confirmar antes de usar.

1. **Preparação local:** contrato interno, pendências, conferência humana, ordem dos eventos e ensaios de repetição/erro/resultado incerto. Nenhum campo adicional é solicitado a hóspedes nesta entrega.
2. **Conector e painel:** persistir eventos e correlação local/remota por hotel e hóspede; validar schema e domínios; coletar campos necessários; registrar horários reais; guardar credenciais isoladas; apresentar pendências com permissões e auditoria. Reconciliar resultados incertos antes de repetir. Implementar acompanhantes, menores e documentos estrangeiros.
3. **Homologação e ativação:** hotel habilitado, credenciais próprias e aceite do responsável; conferir confirmação/erro real e ausência de duplicações. Manter conferência de identidade pela recepção. Nunca solicitar senha gov.br no chat.

O simulador não altera check-in/checkout reais. Erro, resultado incerto e sucesso simulado são distintos e nenhum confirma envio oficial. Os testes locais não substituem homologação da API.

## Validação desta entrega

Em 18/09/2026: suíte existente com 121 testes aprovada; 8 testes específicos do simulador aprovados em execução separada. CLI executada com sucesso: repetição manteve uma tentativa, erro explícito permitiu nova tentativa e resultado incerto bloqueou repetição. Revisão independente conferiu bloqueios para alteração de quarto e divergência de dados entre check-in e checkout. Nenhuma chamada à FNRH ou envio WhatsApp realizado.
