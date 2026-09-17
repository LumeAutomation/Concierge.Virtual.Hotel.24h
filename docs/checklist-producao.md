# Checklist de produção — AURA

Revisão: 17/09/2026. Base: código e documentação atuais. Este documento é um plano de liberação, não uma certificação de segurança nem uma execução dos itens abaixo. Os relatórios anteriores de saúde e testes são evidências daquela validação, não prova de disponibilidade contínua.

**Situação atual:** modelo demonstrativo funcional, com personalização e replicação por instalações independentes. Ainda não liberar para operação comercial irrestrita com hóspedes reais.

**Já implementado na base local**

- [x] Identidade configurável por hotel e exportação de identidade/políticas sem copiar bancos operacionais.
- [x] Reservas, boas-vindas, pré-check-in e check-in/checkout com conferência da equipe.
- [x] Pedidos, histórico, atendimento humano com pausa da Hostess e indicadores locais.
- [x] Login individual, permissões e histórico de revisão/publicação de políticas.
- [x] Persistência, proteção contra repetições de envio, backup local com verificação de integridade e supervisor local.
- [x] Testes automatizados e validações de navegador em ambiente isolado.

Esses itens existem; precisam ser homologados na instalação real do cliente. A confirmação do provedor de WhatsApp não equivale a confirmação de recebimento ou leitura pelo hóspede.

**P0 — Bloqueios antes do primeiro hotel em produção**

- [x] **Separar demonstração de produção.** Implementado modo persistido por instalação, com validação explícita da revisão publicada, identidade neutra enquanto não validada e bloqueio de respostas antigas da demonstração. Sem conteúdo aprovado para produção, o atendimento encaminha à equipe. Validado por testes automatizados e navegador em banco isolado; esta instalação permanece em Demonstração. Evidências e uso: [Modo de produção](production-mode.md). A homologação dos dados reais continua pendente no próximo item.
- [ ] **Homologar o conteúdo com o hotel.** Conferir acomodações, capacidade, horários, inclusões, valores, contatos e condições. Aceite: responsável identificado publica o catálogo real e valida perguntas de cada assunto prioritário. Conservar a instalação comercial de demonstração separada. Preparação do modelo fictício concluída: matriz de 101 políticas e 11 cenários representativos conferidos. [Roteiro e critérios de aceite](homologacao-conteudo.md). Homologação real permanece pendente até haver hotel e responsável; dados fictícios não foram aprovados para produção.
- [x] **Substituir o servidor HTTP de demonstração.** Instância local migrada para Waitress 3.0.2, com limites de requisição/conexões, tratamento de erros e controles de acesso preservados. Suíte de 121 testes e carga local de 120 requisições/12 clientes aprovadas, sem pedidos duplicados. Configuração, métricas e limites do aceite: [Servidor HTTP](servidor-http.md). Publicação HTTPS, dimensionamento definitivo e observação prolongada continuam nos itens seguintes.
- [ ] **Integrar a FNRH Digital — próxima etapa de desenvolvimento.** Reaproveitar os dados da reserva e do pré-check-in, solicitar os campos obrigatórios faltantes e integrar reservas, hóspedes, check-in e checkout pela API oficial. Dividir em entregas: (1) mapear campos e preparar simulação local com dados fictícios; (2) implementar conector, credenciais isoladas por hotel e painel de pendências, com proteção contra duplicações; (3) validar em homologação e ativar em produção somente com hotel habilitado, credenciais próprias e aceite. Manter a conferência da recepção e registrar confirmação ou erro retornado pela FNRH. Aceite: jornada homologada, sem fichas duplicadas e sem marcar envio incerto como confirmado. **Agendada; implementação não iniciada nesta atualização, a pedido do usuário para preservar os créditos disponíveis.** A preparação local será a primeira entrega quando o trabalho for retomado. [Documentação oficial de integração](https://www.gov.br/turismo/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/ficha-nacional-de-registro-de-hospedes/modulo-meio-de-hospedagem/meios-de-hospedagem-com-pms).
- [ ] **Definir e proteger o acesso.** Escolher rede privada/VPN ou publicação HTTPS, conforme o uso. Adaptar validação de Host/Origin, proxy, cookies, autenticação e limites de requisições. Revisar o chat local sem autenticação antes de qualquer exposição. Aceite: acessos indevidos às APIs e sessões de outros hóspedes são recusados; painéis de n8n/WAHA não ficam publicamente expostos por padrão.
- [ ] **Ter infraestrutura e inicialização adequadas.** Usar ambiente dedicado com recursos dimensionados. Eliminar dependência de login interativo para iniciar a operação e validar persistência após reinício completo. Aceite: retorno dos serviços após reboot, falha de processo e interrupção controlada de rede, sem perda ou duplicação de pedidos.
- [ ] **Operar 24 horas sem depender do computador pessoal.** Hospedar a aplicação, o banco, o n8n e o conector WhatsApp em ambiente dedicado na nuvem ou no hotel, com energia e internet adequadas à disponibilidade acordada. Eliminar dependências de arquivos, unidades de rede e processos do computador de desenvolvimento. Aceite: desligar o computador pessoal e confirmar, com contato autorizado, que o hóspede continua recebendo respostas e que a equipe consegue acessar o painel por outro dispositivo.
- [ ] **Conferir mensagens recebidas durante indisponibilidade.** Simular uma interrupção controlada do servidor ou da conexão WhatsApp e verificar quais mensagens são recuperadas pelo provedor na retomada. Definir reconciliação e atendimento manual para as pendências, sem presumir recuperação automática. Aceite: registrar o resultado de cada mensagem de teste e garantir que mensagens recuperadas não gerem respostas ou pedidos duplicados; documentar as limitações observadas.
- [ ] **Definir o canal WhatsApp comercial.** Decidir e validar o provedor do cliente, condições de uso, limites, forma de envio inicial e recuperação da conexão. Se o canal mudar, adaptar o conector; não tratar o pareamento WAHA atual como validação automática de outro provedor. Aceite: número e credenciais exclusivos e jornada real autorizada de envio/resposta/atendimento.
- [ ] **Fechar o controle de identidade.** Testar telefone/LID, reserva, acomodação, telefones compartilhados, hóspedes com várias reservas, troca de número e acesso após checkout. Aceite: nenhum hóspede consulta dados ou comandos de outra hospedagem. Aceitar CPF válido não prova identidade.
- [ ] **Proteger dados e credenciais.** Definir necessidade de cada dado, prazos de retenção, descarte, permissões de arquivos, proteção do disco/backups e política de logs. O cadastro atual guarda CPF no SQLite; reavaliar necessidade de armazenar o valor completo e as medidas de proteção. Revisar obrigações e avisos de privacidade com os responsáveis do cliente. Aceite: plano documentado, permissões testadas e nenhuma credencial ou dado operacional incluído no pacote de instalação.
- [ ] **Homologar o fluxo de emergência.** A resposta atual declara que não aciona socorro real. Definir texto, contatos, escala e encaminhamento aprovados pelo hotel; o sistema não pode afirmar acionamento sem evidência. Aceite: simulação com equipe autorizada, responsáveis e contingência documentados.
- [ ] **Validar restauração e contingência.** Completar a estratégia de backup da aplicação, dados, configuração n8n e material necessário para recuperação das integrações; proteger segredos separadamente. Manter cópia fora da máquina principal, com acesso restrito. Aceite: restauração em ambiente limpo e medição da perda de dados e do tempo de recuperação aceitáveis para o hotel. Um ZIP íntegro não prova recuperação completa da operação.
- [ ] **Criar alertas acionáveis.** Alertar um responsável sobre desconexão, serviço parado, falha de backup, disco insuficiente, fila parada e envio incerto. Aceite: cada falha simulada chega ao responsável definido; nenhuma repetição automática causa mensagem duplicada.

**P1 — Homologação da experiência e da operação**

- [ ] **Responder a formatos não suportados.** O filtro atual ignora mídia. Criar orientação para áudio, imagem e documento, ou implementar suporte específico. Aceite: hóspede recebe orientação útil em vez de silêncio, sem interpretar conteúdo que o sistema não processa.
- [ ] **Cobrir exceções da jornada.** Testar mais de um pedido aberto, várias reservas, quarto ainda não definido, reserva alterada, cadastro divergente, repetição de mensagem, desistência e reabertura. Aceite: protocolos e estados corretos, sem atribuição indevida de quarto ou execução duplicada.
- [ ] **Operar a troca de turno.** Definir transferência de responsável e tratamento de conversa humana abandonada; a pausa atual não expira automaticamente. Aceite: outro profissional autorizado consegue continuar o atendimento e nenhuma conversa fica esquecida por encerramento de turno.
- [ ] **Homologar permissões e auditoria.** Conferir recepção, governança, manutenção, gestão e administração conforme a organização real. Validar ações simultâneas, desligamento de usuário e revogação de acesso. Aceite: cada ação sensível tem autor, data e resultado verificáveis.
- [ ] **Validar desempenho e duração.** Medir volume esperado de conversas, latência, filas, consumo de memória e concorrência de gravações. Fazer observação prolongada e testes de falha. Aceite: metas acordadas antes dos testes atendidas, sem perda ou duplicação. Decidir manutenção ou evolução do SQLite a partir dessas medições; troca de banco não é requisito automático.
- [ ] **Executar ponta a ponta com o canal real.** Com contato autorizado, validar boas-vindas, identificação, pré-check-in, chegada, pedido de toalhas, humano, confirmação/negativa de recebimento e checkout. Aceite: registros no painel correspondem ao que chegou ao aparelho e ao que a equipe efetivamente realizou.
- [ ] **Treinar a equipe e definir contingência manual.** Documentar responsáveis, horários, acompanhamento, passagem de turno, tratamento de falhas e quando parar o bot. Aceite: equipe opera o roteiro e continua atendendo durante indisponibilidade do sistema.
- [ ] **Liberar inicialmente com acompanhamento.** Começar em escopo e volume limitados, com responsável e critérios para interromper/reverter. Aceite: registro dos problemas, correções verificadas e aprovação explícita do hotel antes de ampliar.

**P2 — Replicação comercial previsível**

- [ ] **Padronizar instalação e dependências.** Criar procedimento reproduzível com versões fixadas, validação prévia e instalação em máquina limpa. A importação de modelo atual prepara dados; não instala toda a infraestrutura.
- [ ] **Parametrizar todos os recursos por cliente.** Banco, diretórios, portas, endpoints, serviços, tarefas, volumes, logs, backups e credenciais. `AURA_DB` sozinho não isola o conjunto. Aceite: alterar/parar uma instalação não modifica dados nem serviços de outra.
- [ ] **Preparar um pacote de distribuição limpo.** Usar lista explícita de arquivos permitidos. Excluir `runtime`, `.env`, `Acessos`, bancos, históricos, sessões, credenciais e arquivos de senha inicial. Aceite: pacote inspecionado e instalação sem herdar dados ou acessos do modelo.
- [ ] **Versionar atualizações e migrações.** Registrar versão instalada, mudanças de banco, backup prévio e recuperação em caso de atualização malsucedida. Aceite: atualizar cópia representativa sem perda de dados; testar estratégia de retorno compatível com a versão do banco.
- [ ] **Definir suporte e responsabilidades.** Documentar implantação, manutenção, atualização, custo de infraestrutura/provedor, propriedade dos dados, canal de suporte e compromissos que serão vendidos. Revisar condições de licença e uso dos componentes para a forma de comercialização escolhida.
- [ ] **Ter aceite por cliente.** Separar a configuração do modelo da aprovação do hotel. Registrar ambiente, versão, número WhatsApp, responsáveis, testes e pendências aceitas antes da ativação.

**Evoluções que não são obrigatórias para a primeira instalação**

- [ ] Painel central para administrar vários hotéis.
- [ ] Integração PMS/motor de reservas, se a operação inicial puder trabalhar com cadastro e conferência manuais aprovados.
- [ ] Cobrança recorrente automática e gestão de planos comerciais.
- [ ] IA generativa, voz e outros idiomas, conforme demanda e validação.

**Regra de liberação:** concluir os bloqueios P0 e a homologação P1 aplicáveis, com evidências e responsável pelo aceite. Para repetir a venda com previsibilidade, concluir P2 antes de escalar instalações. Ter o modelo configurável e testes locais aprovados não substitui esse aceite.

**Responsabilidade por item:** antes de executar, registrar responsável, prazo, evidência de conclusão e impedimentos. Não marcar como concluído apenas porque uma funcionalidade existe no código.

Referências locais: `docs/hotel-commercial-template.md`, `docs/guest-experience.md`, `app.py`, `reservations.py`, `operations.py`, `scripts/supervise.py`, `scripts/waha-input.js`.

Para a configuração de segurança do n8n, revisar as opções oficiais de proteção da implantação: https://docs.n8n.io/hosting/securing/overview
