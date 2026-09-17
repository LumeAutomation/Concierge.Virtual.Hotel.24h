# Respostas locais das políticas

A busca não usa API nem modelo externo. Ela reconhece vocabulário equivalente para entrada/saída, Wi-Fi, café da manhã, piscinas, academia, pets e estacionamento. As demais políticas usam correspondência das palavras da pergunta com título, pergunta de exemplo e conteúdo vigente.

Exemplos para testar no chat:
- `quando posso entrar?`
- `que horas abre a musculação?`
- `Qual horário da piscina?`, seguido de `e fecha que horas?`
- `e o café da manhã?`, seguido de `e aos domingos?`

O contexto usa somente a última resposta local da mesma conversa por até 30 minutos. A resposta é sempre reconstruída com a política atual; o texto anterior não é tratado como fonte. Mudança explícita de assunto prevalece. Emergências, dados sensíveis, ações e o fluxo de reservas mantêm prioridade.

Em /politicas, use um título específico, uma pergunta de exemplo natural e conteúdo completo com horários, condições e exceções. Salvar rascunho não muda as respostas. Aprovar e colocar em uso atualiza a busca imediatamente. Políticas internas e novas políticas não publicadas não entram na busca. O catálogo demonstrativo original continua disponível; esta mudança não aprova nem altera seu conteúdo.

Quando assuntos diferentes empatam, o chat pede esclarecimento. Políticas com o mesmo título e a mesma pergunta vão para atendimento humano para evitar escolher entre regras conflitantes. Informação ausente também exige atendimento humano. Perguntas sobre medidas e temperatura permanecem conservadoramente com a equipe, até existir um cadastro estruturado desses dados.

É uma busca determinística com contexto, não uma IA generativa nem compreensão irrestrita da linguagem. Sinônimos explícitos estão em knowledge_engine.py; novas políticas também participam automaticamente pela correspondência de palavras. Nenhuma dependência foi adicionada.

Validação: `python -m unittest discover -s tests` e `python scripts/check_local_search_browser.py`. O navegador usa banco temporário e não envia WhatsApp.
