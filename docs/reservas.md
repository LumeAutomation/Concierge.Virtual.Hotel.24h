# Reservas e jornada WhatsApp

Tela: http://localhost:8787/reservas — perfis Recepção, Gestor e Administrador.

1. Cadastre ID, nome completo, telefone, CPF e datas em DD/MM/AAAA.
   Salve a reserva e clique em Enviar boas-vindas. A Hostess do Hotel Aura
   envia diretamente ao WhatsApp cadastrado; salvar sozinho não envia.
   O painel mostra se o WhatsApp aceitou o envio. Não há reenvio automático.
2. O hóspede responde INICIAR pelo telefone cadastrado e SIM para o pré-check-in.
   O hóspede recebe a primeira mensagem sem abrir link nem iniciar a conversa.
3. O hóspede responde CONFIRMAR NOME, CONFIRMAR DADOS e CONCLUIR.
   O painel mostra Pré-check-in concluído. CORRIGIR encaminha à recepção.
4. Na chegada, confira o documento presencialmente, abra a reserva e marque
   a conferência antes de Confirmar check-in.
5. “Quero fazer checkout” registra solicitação para a recepção. Após conferir
   pagamentos e pendências, marque as duas confirmações e Liberar checkout.
   A recepção pode Confirmar checkout, ou o hóspede pedir novamente pelo WhatsApp.

Links valem 72 horas, não contêm CPF/nome/ID da reserva e ficam armazenados
somente como hash. Novo link revoga o anterior. Editar antes do check-in revoga
links, desfaz o vínculo e exige novo envio pelo botão e nova confirmação. Reserva encerrada não é editável.
O remetente deve corresponder ao telefone cadastrado; LID é resolvido pelo WAHA.
Conversa já vinculada a outra reserva aberta exige conferência da recepção.

Sem configuração adicional: destino obtido da conta WAHA conectada, sessão
configurada em runtime/waha/session.json. Não há integração PMS/pagamentos;
source, hotel_id e external_id separam a origem manual para futura integração.

Banco existente: reservations, reservation_links, reservation_conversations,
reservation_events. APIs autenticadas: GET /api/reservations,
GET /api/reservations/{id}, POST /api/reservations (save, link, checkin,
clear_checkout, checkout, welcome). Reutiliza /api/pilot/check, /api/chat e /api/whatsapp/reply.

Validação: python -m unittest discover -s tests -v
Navegador isolado, sem envio: python scripts/check_reservations_browser.py

Atualização Hostess: migração aditiva automática em public_protocols e
reservation_invitations. Não envia boas-vindas para reservas antigas.
Protocolo HA é apenas referência pública; os tokens de acesso continuam seguros.
INICIAR com mais de uma reserva elegível exige orientação da recepção.
Envio desconhecido exige conferir a conversa antes de uma ação manual.
