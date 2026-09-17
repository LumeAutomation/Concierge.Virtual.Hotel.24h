# Conferência do modelo AURA e homologação por hotel

**Escopo desta etapa:** preparar e conferir o modelo fictício para apresentação e replicação. O usuário optou por continuar com o modelo AURA, sem identificar um hotel real. Nenhum dado foi declarado verdadeiro para um empreendimento real, nenhuma política foi validada para produção e o modo da instalação não foi alterado.

**Resultado da conferência técnica do modelo**

- 101 políticas catalogadas com título, departamento, conteúdo e pergunta de referência preenchidos.
- Referências a códigos de políticas conferidas: nenhuma referência inexistente encontrada.
- Campos de identidade renderizados: nenhum marcador de preenchimento pendente nas políticas carregadas.
- 11 cenários representativos aprovados em banco temporário: entrada, café, piscina, academia, spa, pets, informação ausente, toalhas, solicitação de reserva de spa, privacidade e emergência.
- As seis perguntas informativas desses cenários também foram testadas em produção sem validações: foram encaminhadas à equipe, sem fontes do catálogo fictício.
- Nenhuma mensagem enviada pelo WhatsApp. Nenhuma publicação ou reserva da instalação atual foi alterada.

Esta verificação cobre estrutura e comportamento nos cenários listados. Não significa teste conversacional individual das 101 políticas nem comprovação de ausência de todas as contradições possíveis.

**Matriz de conferência**

Arquivo: [homologacao-modelo-aura.csv](homologacao-modelo-aura.csv). Pode ser aberto no Excel; utiliza ponto e vírgula e codificação UTF-8. Contém uma linha por política, com campos para fonte do hotel, responsável, data, revisão publicada, resultado de teste real e observações. Os campos de aceite estão vazios e a confirmação de dados reais está marcada como NAO.

O script de conferência não sobrescreve uma matriz existente, para preservar preenchimentos manuais. Preencher a planilha também não publica nem valida políticas no sistema.

**Dados que cada hotel deverá fornecer**

| Área | Dados a confirmar | Evidência sugerida |
|---|---|---|
| Identidade e contatos | Nome, endereço, canais oficiais, recepção e responsável | Cadastro e confirmação da gestão |
| Acomodações | Categorias, capacidade, camas, itens garantidos e acessibilidade | Inventário e descritivo aprovado |
| Chegada e saída | Horários, documentos, conferência e exceções | Procedimento da recepção |
| Alimentação | Locais, horários por dia, planos e restrições | Cardápio e regras de alimentos e bebidas |
| Valores e inclusões | Preço, unidade, vigência, taxa, exceções e aceite | Tabela comercial vigente |
| Lazer e bem-estar | Horários, restrições de uso, supervisão e interrupções | Procedimentos dos setores |
| Pets e visitantes | Categorias autorizadas, limites, circulação e adicionais | Política aprovada do empreendimento |
| Governança e manutenção | O que pode ser pedido, responsável, confirmação e acompanhamento | Procedimento de execução |
| Reservas e pagamentos | Canal responsável, cancelamento, alterações, conferência de consumos | Procedimentos e condições comerciais |
| Privacidade e segurança | Verificação de identidade, acesso, responsáveis e atendimento de emergência | Procedimentos aprovados pela equipe competente |

Não inventar um prazo, uma taxa ou uma garantia para preencher campos ausentes. Registrar a pendência e encaminhar esse assunto à equipe até a confirmação.

**Roteiro de aceite por assunto**

1. Registrar a fonte, versão ou data de vigência e responsável pela informação.
2. Conferir a política com as demais que tratam do mesmo serviço: inclusões, valores, horários e exceções devem coincidir.
3. Salvar o conteúdo real como rascunho em Políticas e publicar a revisão após a revisão do responsável.
4. Perguntar de pelo menos duas formas diferentes; testar também uma exceção e uma informação ausente. Registrar pergunta, resultado esperado, resposta obtida, código e revisão.
5. Corrigir divergências e repetir somente os cenários afetados.
6. Validar a revisão para produção usando o controle específico do sistema, somente após confirmação humana. A identidade do hotel também precisa de validação própria.
7. Registrar o aceite da gestão para o escopo liberado. Repetir a conferência quando houver nova publicação ou mudança operacional relevante.

**Critérios para encerrar o item de produção**

- [ ] Hotel real identificado e ambiente separado da demonstração.
- [ ] Responsável pelo aceite identificado.
- [ ] Fontes vigentes dos assuntos prioritários registradas.
- [ ] Conteúdo real publicado e identidade conferida.
- [ ] Perguntas, variantes, exceções e ausência de informação testadas com evidências.
- [ ] Revisões aprovadas para produção e pendências restantes encaminhadas à equipe.
- [ ] Aceite do responsável registrado, sem tratar dados fictícios como dados reais.

Até isso ocorrer, o item **Homologar o conteúdo com o hotel** permanece pendente. A preparação do modelo está concluída e não impede avançar nas melhorias técnicas independentes do checklist.

**Reexecutar a conferência do modelo**

```powershell
python scripts/check_demo_catalog.py
```

Resultado detalhado: `runtime/demo-catalog-review-results.json`. O script usa catálogo base e banco temporário; não avalia a operação real de um cliente.
