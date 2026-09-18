# Conector HTTP FNRH v2 isolado

Preparado em 18/09/2026. `fnrh_connector.py` não é importado pelo app, não lê ambiente, banco, credenciais ou reservas e não foi executado com transporte real. Os testes injetam respostas fictícias. O painel local não permite transmissão.

## Fontes e contrato

- [Swagger oficial v2](https://fnrh.turismo.serpro.gov.br/FNRH_API/rest/v2/swagger.json), consultado em 18/09/2026: propriedades dos pedidos/respostas e Basic Authentication.
- [Manual disponibilizado como v2.4.2](https://www.gov.br/turismo/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/ficha-nacional-de-registro-de-hospedes/modulo-meio-de-hospedagem/meios-de-hospedagem-com-pms/documentacao-api-v2-4-2.pdf), baixado e lido nesta entrega: páginas humanas 36–38 confirmam PATCH individual com timestamp UTC como texto puro e resposta `dados.hospede_id/situacao_id/data_hora`; páginas 49–51 confirmam estruturas consolidadas `reserva/dados_hospede` e resposta `dados.reserva/dados_hospedes`; páginas 53–54 descrevem status HTTP.

Os nomes internos em `required` do Swagger divergem das propriedades JSON. A implementação usa propriedades esclarecidas pelos exemplos do PDF, sem interpretar `required` automaticamente. O host confirmado por documentação acessível e exemplo do manual (p. 35) é `fnrh.turismo.serpro.gov.br`; somente o endpoint HTTPS exato `/FNRH_API/rest/v2` é aceito. Outros hosts de exemplos e homologação ficam fora da lista até confirmação.

## Interface para futura integração

`HotelConfig(hotel_id, base_url, timeout)` é obrigatório. `FnrhConnector(config, username=..., token=..., transport=...)` recebe a credencial do hotel explicitamente, usando Basic com identificador e token. Não registra credenciais, payload ou corpo remoto em logs/resultados. Não persiste nenhum dado. Uma chamada exige novamente `hotel_id`, e divergência bloqueia antes do transporte.

- `register(hotel_id, payload, cpf_solicitante=...)`: POST consolidado; somente payload oficial previamente revisado. Verifica estrutura reserva/hóspedes, datas, contagens, origem e CPF do solicitante. **Não certifica completude das informações pessoais, domínios, condições de menores ou elegibilidade.** Não transforma a reserva simplificada do sistema em ficha oficial.
- `event(hotel_id, operation, guest_id, occurred_at)`: PATCH `checkin` ou `checkout`; exige UUID remoto e timestamp UTC explícito. Nunca usa `updated_at` ou inventa o horário.

O transporte padrão usa verificação TLS, timeout por operação de socket (não prazo global da operação), limite de resposta de 1 MiB, sem redirecionamento e sem repetição automática. Nenhuma configuração de proxy ou `.netrc` é consultada. Transporte injetado é componente confiável apenas para testes e deve respeitar a mesma proteção se substituído.

## Interpretação do resultado

`confirmed` exige HTTP 200 e resposta coerente. Em evento: mesmo UUID, estado específico esperado e instante correspondente. No registro: número/datas/origem/quantidade adulta correspondentes, UUID de reserva, quantidade esperada de hóspedes, UUIDs únicos e vínculos à reserva/pessoa. Essa confirmação significa resposta de registro recebida; não implica aprovação regulatória da ficha. A lista remota de hóspedes não é mapeada automaticamente para pessoas locais pela ordem.

`rejected` cobre apenas os status documentados 400, 401, 403 e 404. `uncertain` cobre timeout, erro de transporte, 5xx, redirecionamento, outros status e JSON/schema/identidade incompatíveis. Não há repetição automática em nenhum caso, inclusive 408, 409 e 429. Corpo de erro remoto nunca é apresentado diretamente ao operador.

O consumidor ainda deve persistir tentativa antes do envio, controlar exclusão concorrente, reconciliar resultados incertos, validar domínios/campos condicionais, autorizar o hotel/operador e conferir documentos. O adaptador isolado não fornece idempotência durável. Credenciais reais, ambiente de homologação, testes oficiais e ativação por hotel continuam pendentes.

## Verificação

`python -m unittest discover -s tests -p test_fnrh_connector.py -v`

11 testes sem rede aprovados: contrato de eventos, correlação de registro, falhas parciais, isolamento entre hotéis, configuração HTTPS, segredo ausente nos resultados, timeout sem retry e ausência de redirecionamento no transporte padrão. Nenhuma transmissão FNRH foi realizada.
