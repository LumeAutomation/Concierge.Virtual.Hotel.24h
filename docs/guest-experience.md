# Atendimento do hóspede

Sem API de IA ou novas dependências. O catálogo continua demonstrativo até a equipe confirmar e publicar os dados reais. Em /politicas, a faixa de revisão prioritária indica os assuntos que precisam de conferência. Não é uma aprovação automática para produção.

## Pedidos de toalhas

1. O hóspede pede toalhas. A Hostess registra protocolo e encaminha à governança, identificando quantidade explícita de 1 a 20 quando reconhecida. Sem quantidade, o painel pede confirmação pela equipe.
2. O pedido mostra reserva e acomodação somente se a conversa já estiver vinculada e o check-in estiver realizado. Um número de quarto digitado pelo hóspede não estabelece vínculo. Sem identificação, a equipe confere antes da entrega.
3. Na recepção, clique em **Assumir atendimento**. Em **Ver conversa**, o responsável pode clicar em **Avisar início**. É um envio explícito, com uma tentativa automática por protocolo; não informa prazo.
4. **Concluir atendimento** registra a conclusão pela equipe. Em WhatsApp, o aviso solicita `RECEBI AS TOALHAS` ou `NÃO RECEBI AS TOALHAS`. Apenas conclua após conferir o pedido.
5. A confirmação positiva registra recebimento separado da conclusão da equipe. A negativa reabre o mesmo pedido para conferência. Havendo vários pedidos de toalhas na conversa, a Hostess pede conferência pela recepção.

O hóspede pode perguntar `como está meu pedido?`. `Cancelar meu pedido` ou `não preciso mais das toalhas` cancela somente um pedido de toalhas ainda não assumido, sem alterar a reserva. Quando já está em atendimento, a equipe precisa avaliar a desistência.

## Conversa humana

Depois de assumir o atendimento, abra **Ver conversa** e clique em **Assumir conversa**. A Hostess pausa as respostas automáticas e registra as novas mensagens para o atendente; emergências e orientação sobre dados sensíveis continuam prioritárias. Os comandos de reserva também ficam aguardando enquanto a conversa está com a equipe.

Use **Atualizar conversa** para buscar novas mensagens. O rascunho da equipe permanece intacto durante atualizações da fila. **Enviar mensagem** envia ao WhatsApp autorizado ou registra a resposta quando o pedido vem do painel local. **Devolver à Hostess** ou concluir o protocolo libera o atendimento automático. O responsável precisa ser o mesmo usuário que assumiu o protocolo.

A pausa é explícita, sem expiração automática: confira conversas assumidas antes de encerrar o turno. Mensagens registradas durante a pausa não são respondidas retroativamente pelo bot.

## Indicadores e limites

A recepção mostra abertos, em atendimento, concluídos pela equipe, cancelados antes do atendimento, recebimentos confirmados, pedidos abertos há mais de 15 minutos e média até o primeiro atendimento. O limite de 15 minutos é um marcador operacional, não um prazo prometido ao hóspede. Dados anteriores à implantação podem não ter vínculo de reserva ou confirmação de recebimento.

Envios com falha, sem confirmação, bloqueados ou presos em envio há mais de dois minutos aparecem para conferência. Aceito pelo WhatsApp não significa lido ou entregue ao aparelho. Não há reenvio automático após resultado incerto. A página /operacao continua mostrando os serviços e a sessão WhatsApp.

As perguntas sem resposta segura são extraídas das últimas 500 interações; a lista mostra até dez exemplos. Não representa uma contagem de toda a história. A equipe pode usar esses exemplos para revisar políticas.

Políticas locais reconhecem alguns erros de uma letra em nomes de serviços. Não há modelo generativo, nem garantia de compreender qualquer frase. Emergências continuam com a orientação demonstrativa existente: esta versão não aciona socorro real.

Validação: testes em tests/test_guest_service.py, regressão de reservas e scripts/check_guest_service_browser.py. O navegador usa banco temporário e não envia WhatsApp real.
