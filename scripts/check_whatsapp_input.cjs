const assert = require('node:assert/strict');
const fs = require('node:fs');
const wf = JSON.parse(fs.readFileSync('workflows/WF-02-whatsapp-entrada.json','utf8').replace(/^\uFEFF/,''));
const code = wf.nodes.find(n=>n.type==='n8n-nodes-base.code').parameters.jsCode;
const run = data => new Function('$input',code)({all:()=>data.map(json=>({json}))});
const message = {id:'wamid.TEST123+/==',from:'5500000000000',type:'text',text:{body:'Quero toalhas'}};
const value = {metadata:{phone_number_id:'1280781558460646'},messages:[message]};
assert.equal(run([value])[0].json.request_id,message.id);
assert.equal(run([{entry:[{changes:[{value}]}]}])[0].json.message,'Quero toalhas');
assert.equal(run([{body:{entry:[{changes:[{value}]}]}}]).length,1);
assert.equal(run([{metadata:value.metadata,statuses:[{status:'failed'}]}]).length,0);
assert.equal(run([{...value,metadata:{phone_number_id:'other'}}]).length,0);
assert.match(run([{...value,messages:[{...message,type:'audio'}]}])[0].json.message,/humano/);
assert.throws(()=>run([{...value,messages:[{...message,id:'bad'}]}]));
assert.throws(()=>run([{...value,messages:[{...message,text:{body:'x'.repeat(2001)}}]}]));
assert.equal(wf.active,false);
assert(!wf.nodes.some(n=>n.type==='n8n-nodes-base.whatsApp'));
console.log('10 verificacoes passaram: envelopes, entrada, status, numero, midia, validacao e ausencia de envio.');

