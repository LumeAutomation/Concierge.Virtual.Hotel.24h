"""Check demo catalog structure and representative conversations in an isolated DB."""
import csv,json,re,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,knowledge_engine as kb,operating_mode

CASES=[
 ('entrada','quando posso entrar?','AUTO_REPLY','POL-04','15h'),
 ('cafe','Qual horario do cafe da manha?','AUTO_REPLY','POL-08','06h30'),
 ('piscina','Qual horario da piscina?','AUTO_REPLY','POL-12','20h'),
 ('academia','que horas abre a academia?','AUTO_REPLY','POL-15','05h'),
 ('spa','Qual o horario do spa?','AUTO_REPLY','POL-14','09:00'),
 ('pets','Posso levar meu cachorro?','AUTO_REPLY','POL-18','15 kg'),
 ('medida_ausente','Qual a profundidade da piscina?','HUMAN_HANDOFF',None,None),
 ('pedido','Quero duas toalhas','HUMAN_HANDOFF',None,'Registrei'),
 ('reserva_spa','Quero reservar o spa','HUMAN_HANDOFF',None,None),
 ('privacidade','Qual o quarto de outro hospede?','SAFE_REPLY',None,None),
 ('emergencia','Socorro tem fogo','HUMAN_HANDOFF',None,None),
]

def main():
    original=app.DB
    with tempfile.TemporaryDirectory() as tmp:
        app.DB=Path(tmp)/'catalog.sqlite3';app.init_db()
        policies,version=kb.load_base()
        missing=[{'id':pid,'reference':ref} for pid,p in policies.items() for ref in set(re.findall(r'POL-\d+',p['content'])) if ref not in policies]
        assert not missing,missing
        assert len(policies)==101
        assert all(p.get('title') and p.get('content') and p.get('department') and p.get('example_question') for p in policies.values())
        assert '{{' not in json.dumps(policies)
        rows=[]
        try:
            for tag,message,route,pid,text in CASES:
                result=app.handle_message(dict(message=message,request_id='demo-review-'+tag,session_id='demo-review-'+tag))
                assert result['route']==route,(tag,result['route'])
                if pid:assert result['policy_ids']==[pid],(tag,result['policy_ids'])
                if text:assert text in result['reply'],tag
                if tag=='emergencia':assert result['priority']=='urgent'
                rows.append(dict(case=tag,route=route,policy_ids=result['policy_ids'],passed=True))
            operating_mode.save(app.connection,dict(mode='production',revision=0),'teste-isolado')
            assert kb.load_base()[0]=={}
            for tag,message,route,pid,text in CASES:
                if not pid:continue
                result=app.handle_message(dict(message=message,request_id='prod-review-'+tag,session_id='prod-review-'+tag))
                assert result['route']=='HUMAN_HANDOFF' and result['sources']==[],tag
        finally:app.DB=original
    matrix=app.ROOT/'docs/homologacao-modelo-aura.csv'
    if not matrix.exists():
        fields=['codigo','assunto','departamento','visibilidade','pergunta_referencia','status_modelo','dados_reais_confirmados','fonte_do_hotel','responsavel_do_hotel','data_conferencia','revisao_publicada','resultado_teste_real','observacoes']
        with matrix.open('w',encoding='utf-8-sig',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=fields,delimiter=';');writer.writeheader()
            for pid,p in policies.items():writer.writerow(dict(codigo=pid,assunto=p['title'],departamento=p['department'],visibilidade=p['audience'],pergunta_referencia=p['example_question'],status_modelo='Catalogado; estrutura conferida; dados ficticios',dados_reais_confirmados='NAO',observacoes='Revisao e aceite do hotel real pendentes.'))
    report=dict(passed=True,scope='catalogo demonstrativo base; nao homologa dados reais',isolated_database=True,policy_count=len(policies),knowledge_version=version,missing_references=missing,unresolved_placeholders=False,cases=rows,production_blocks_unapproved_catalog=True,whatsapp_sent=False,real_hotel_approved=False)
    (app.ROOT/'runtime/demo-catalog-review-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
