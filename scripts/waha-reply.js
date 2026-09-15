const original = $('Filtrar teste e preparar').item.json;
const result = $json;
if (result.persisted !== true || typeof result.reply !== 'string' || !result.reply.trim()) {
  throw new Error('AURA nao confirmou uma resposta persistida; envio cancelado.');
}
if (typeof original.chat_id !== 'string' || !/^\d{6,20}@(c\.us|lid)$/.test(original.chat_id)) {
  throw new Error('Destino de resposta invalido; envio cancelado.');
}
if (result.session_id && result.session_id !== original.session_id) throw new Error('Sessao de resposta divergente.');
if (typeof result.request_id !== 'string' || !result.request_id) throw new Error('Protocolo ausente.');
return {json: {request_id: result.request_id, session_id: original.session_id}};
