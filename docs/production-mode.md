# Demonstração e produção

O modo é persistido por instalação, com revisão e histórico do responsável. A instalação atual permanece em Demonstração. Este controle de conteúdo não substitui servidor, segurança, infraestrutura e demais exigências do checklist.

Em **Meu hotel**, use **Modo de operação**:

- **Demonstração:** permite o catálogo fictício original e as políticas publicadas localmente.
- **Produção:** permite somente a revisão publicada que também recebeu validação explícita para produção. Sem correspondência segura, encaminha à equipe. Rascunhos, catálogo original não validado e políticas internas não viram respostas ao hóspede.

## Validar uma política

1. Revise os dados reais em Políticas e salve o rascunho.
2. Publique com Aprovar e colocar em uso. Em produção, essa publicação sozinha ainda não libera a resposta.
3. Clique em **Validar para produção** e confirme a conferência dos dados do hotel.

A validação fica vinculada à revisão publicada. Salvar um novo rascunho preserva a publicação anterior; publicar nova revisão exige nova validação. Identificadores, responsável e data ficam registrados. O sistema recusa indicadores evidentes de demonstração (como fictício, demonstração e domínio .example); isso não substitui conferência humana nem verifica a veracidade de todos os dados.

## Identidade e contatos

Em Meu hotel, salve os dados reais e confirme a identidade na seção Modo de operação. Identidade padrão ou não validada resulta em apresentação neutra (Hotel / Assistente), sem endereço, e-mail ou site fictício nas respostas. Alterar a identidade salva invalida a validação anterior. Políticas que dependem de campos de identidade indisponíveis ficam fora das respostas.

## Proteções de envio

- Boas-vindas de reserva exigem política POL-00 validada e disponível em produção.
- Respostas antigas de demonstração ou de outra revisão de modo são bloqueadas no envio em produção.
- Respostas de conhecimento pendentes são bloqueadas se a versão da base tiver mudado.
- Pedidos, histórico e confirmações de ações persistidas continuam funcionando; o controle não transforma uma solicitação em serviço realizado.
- Orientações genéricas de proteção de dados e emergência continuam disponíveis sem citar políticas não validadas. Isso não implementa acionamento real de socorro.
- Mensagens da equipe são ações humanas explícitas, não geração automática de conteúdo a partir do catálogo.

O modo e a validação de produção não são transferidos no modelo exportado. Uma instalação nova precisa de configuração e validação próprias. A mudança de modo não apaga dados nem autoriza reenvio automático de mensagens bloqueadas.

## Evidências

- `tests/test_production_mode.py`: base vazia, publicação comum, revisão validada, rascunhos, nova publicação, importação, identidade, emergência, boas-vindas e mensagens antigas.
- `scripts/check_production_mode_browser.py`: persistência do modo, encaminhamento sem base validada e liberação de resposta após validação explícita, em banco temporário.
- `runtime/production-mode-browser-results.json`: resultado do navegador; sem WhatsApp real.

Critério técnico do primeiro item P0: cumprido pelos testes. Homologação do conteúdo de um hotel real: pendente no item seguinte.
