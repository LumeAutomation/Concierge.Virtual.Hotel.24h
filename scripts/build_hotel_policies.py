"""Gera os artefatos da base de 100 politicas a partir do texto editorial."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INTERNAL={2,3,5,23,24,26,27,36,37,38,39,100}
SOURCES=[
 {'id':'REF-01','title':'Hilton - Hotel policies','url':'https://www.hilton.com/en/help-center/hotel-information/hilton-hotel-policies/','checked_on':'2026-09-15','summary':'Exemplos reais de temas: achados e perdidos, recebimento de encomendas, fumo, idade de cadastro e taxas que variam por unidade. Nao adotamos valores ou condicoes de uma unidade como regra universal.'},
 {'id':'REF-02','title':'7Pines Resort Ibiza / Hyatt - Hotel policies','url':'https://www.hyatt.com/destination-by-hyatt/en-US/ibzdh-7-pines-resort-ibiza/policies','checked_on':'2026-09-15','summary':'Exemplos reais de regras especificas para pets e piscinas por faixa etaria. Idades, pesos, taxas e condicoes do Aurora sao propostas proprias; nao correspondem aos parametros deste resort.'},
 {'id':'REF-03','title':'Hana-Maui Resort / Hyatt - FAQs','url':'https://www.hyatt.com/destination-by-hyatt/en-US/oggal-hana-maui-resort/faqs','checked_on':'2026-09-15','summary':'A FAQ trata de horarios de entrada e saida, disponibilidade para antecipacao ou extensao e condicoes de estadia. Os horarios do Aurora permanecem parametros ficticios do piloto.'},
 {'id':'REF-04','title':'Iberostar - Perguntas frequentes','url':'https://www.iberostar.com/pt/faq/','checked_on':'2026-09-15','summary':'Exemplos de assuntos operacionais: ocupacao maxima, pre-check-in, preferencias de quarto, recreacao infantil, beneficios e sustentabilidade. Nao copiamos marcas de programas nem prometemos beneficios dessas redes.'},
 {'id':'REF-05','title':'Ministerio do Turismo - Portaria MTur 41/2025','url':'https://www.gov.br/turismo/pt-br/publicacoes/atos-normativos-2/2025/portaria-mtur-no-41-de-14-de-novembro-de-2025','checked_on':'2026-09-15','summary':'Referencia brasileira para registro de hospedes e FNRH Digital. A recepcao real deve validar documentos, autorizacoes e exigencias vigentes; o piloto nao transmite cadastro a plataforma oficial.'},
 {'id':'REF-06','title':'Hilton - Payment for reservations','url':'https://www.hilton.com/en/help-center/reservations/payment-for-hilton-reservations/','checked_on':'2026-09-15','summary':'Referencia de temas ligados a pagamento e reservas com deposito. Metodos, valores de garantia e prazos do Aurora dependem de definicao propria; nenhum prazo bancario e adotado dessa pagina.'},
]
REFS={25:['REF-01'],57:['REF-01'],82:['REF-01'],90:['REF-01'],18:['REF-02'],61:['REF-02'],4:['REF-03'],40:['REF-03'],41:['REF-03'],6:['REF-04'],16:['REF-04'],17:['REF-04'],35:['REF-04'],44:['REF-04'],45:['REF-04'],48:['REF-04','REF-05'],98:['REF-04'],47:['REF-05'],84:['REF-06']}
rows=[]
for line in (ROOT/'knowledge/policies-authoring.txt').read_text(encoding='utf-8-sig').splitlines():
 if not line.strip(): continue
 fields=line.split('|')
 if len(fields)!=6: raise ValueError('Linha editorial invalida: '+fields[0])
 number,title,team,rule,exceptions,example=fields
 n=int(number)
 rows.append({'id':f'POL-{n:02}','hotel_id':'aurora_grand_resort','title':title,'content':rule+'\n\nCondicoes e excecoes: '+exceptions,'language':'pt-BR','status':'active','version':2,'audience':'internal' if n in INTERNAL else 'guest','department':team,'example_question':example,'escalate_when':exceptions,'source_refs':REFS.get(n,[]),'origin':'proposta_autoral_para_piloto','deployment_scope':'hotel_ficticio','real_hotel_approval':'pendente','reviewed_on':'2026-09-15'})
assert [r['id'] for r in rows]==[f'POL-{i:02}' for i in range(1,101)]
assert len({r['title'] for r in rows})==100
(ROOT/'knowledge/policies.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'knowledge/references.json').write_text(json.dumps(SOURCES,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
intro='''# Aurora Grand Resort & Spa - Manual de 100 politicas

**Edicao 2 | 15/09/2026 | Hotel ficticio de demonstracao**

Esta base cobre 100 situacoes da operacao de resorts e grandes hoteis. As regras sao propostas autorais para o Aurora, inspiradas em temas publicados por redes reais. Nao sao 100 normas universais nem politicas aprovadas de um hotel real. Parametros preservados do piloto (horarios, capacidade e limites) continuam ficticios. O uso em empreendimento real exige homologacao operacional e revisao das condicoes contratuais e legais aplicaveis.

Cada politica identifica regra, condicoes, setor responsavel, exemplo de pergunta e visibilidade. As referencias externas comprovam a existencia do tema indicado, nao todos os detalhes da regra proposta. Politicas sem referencia especifica sao identificadas como propostas operacionais; nao atribui-las a uma rede.

## Como manter

Edite `knowledge/policies-authoring.txt` (numero, titulo, setor, regra, excecoes e pergunta, separados por barra vertical) e execute `python scripts/build_hotel_policies.py`. Isso gera este manual, `policies.json`, `references.json` e a carga SQL. A API relê o JSON em cada consulta da base. Referencias e mapeamentos ficam no gerador. Nao alterar um horario sem revisar as respostas locais de contingencia em `app.py`.

**Fluxo de atendimento:** identificar a pergunta; consultar a regra aplicavel; conferir condicoes e excecoes; registrar pedidos de acao no setor; confirmar somente o que tiver retorno operacional. Um protocolo local nao significa que um servico real foi executado.

## Indice

'''
sections=[intro]+[f"- {r['id']} - {r['title']} ({r['department']})\n" for r in rows]
for r in rows:
 refs=', '.join(r['source_refs']) or 'Proposta operacional autoral, sem referencia externa especifica.'
 sections.append(f"\n## {r['id']} - {r['title']}\n\n**Responsavel:** {r['department']} | **Visibilidade:** {r['audience']} | **Versao:** 2\n\n{r['content']}\n\n**Exemplo de atendimento:** {r['example_question']}\n\n**Quando encaminhar:** {r['escalate_when']}\n\n**Referencias do tema:** {refs}\n")
sections.append('\n## Referencias verificadas\n\n')
for ref in SOURCES: sections.append(f"- **{ref['id']}** [{ref['title']}]({ref['url']}) - {ref['summary']} Consulta: {ref['checked_on']}.\n")
(ROOT/'knowledge/aurora-source.md').write_text(''.join(sections),encoding='utf-8')
def sql(s): return "'"+str(s).replace("'","''")+"'"
statements=['-- Carga proposta do piloto; gerada de policies-authoring.txt. Nao executada automaticamente.','BEGIN;',"INSERT INTO hotels(id,name,timezone) VALUES ('aurora_grand_resort','Aurora Grand Resort & Spa','America/Bahia') ON CONFLICT (id) DO NOTHING;","UPDATE hotel_policies SET status='inactive' WHERE hotel_id='aurora_grand_resort' AND version < 2;"]
for r in rows:
 values=','.join(sql(r[k]) for k in ['hotel_id','id','title','content','language','version','status'])
 statements.append('INSERT INTO hotel_policies(hotel_id,id,title,content,language,version,status) VALUES ('+values+') ON CONFLICT (hotel_id,id,version) DO UPDATE SET title=EXCLUDED.title,content=EXCLUDED.content,language=EXCLUDED.language,status=EXCLUDED.status;')
statements.append('COMMIT;')
(ROOT/'database/002_seed.sql').write_text('\n'.join(statements)+'\n',encoding='utf-8')
print('Base gerada:',len(rows),'politicas;',sum(r['audience']=='guest' for r in rows),'publicas;',sum(r['audience']=='internal' for r in rows),'internas.')
