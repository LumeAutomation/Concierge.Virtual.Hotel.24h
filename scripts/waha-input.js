const output = [];
for (const [index, item] of $input.all().entries()) {
  const event = item.json.body ?? item.json;
  const p = event.payload;
  if (event.event !== 'message' || event.session !== 'default' || !p) continue;
  if (p.fromMe !== false || typeof p.from !== 'string') continue;
  if (!/^\d{6,20}@(c\.us|lid)$/.test(p.from)) continue;
  if (p.hasMedia || typeof p.body !== 'string' || !p.body.startsWith('[AURA TESTE] ')) continue;
  const message = p.body.slice('[AURA TESTE] '.length).trim();
  if (!message || message.length > 2000) throw new Error('Texto de teste vazio ou acima de 2000 caracteres.');
  if (typeof p.id !== 'string' || !p.id.trim() || p.id.length > 512) throw new Error('ID de mensagem WAHA invalido.');
  output.push({json: {
    message,
    chat_id: p.from,
    request_id: JSON.stringify(['waha', event.session, p.from, p.id]),
    session_id: 'waha_' + p.from.replace(/[^a-zA-Z0-9_-]/g, '_'),
  }, pairedItem: {item: index}});
}
return output;
