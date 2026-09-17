import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import knowledge_engine as kb

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=app.DB
        app.DB=Path(self.tmp.name)/'test.sqlite3'
        app.init_db()
        self.policies,self.version=kb.load_base()
    def tearDown(self):
        app.DB=self.old
        self.tmp.cleanup()
    def output(self,pid='POL-14',quote=None):
        evidence={'route':'ANSWER','evidence':[{'policy_id':pid,'quote':quote or self.policies[pid]['content']}]}
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(evidence)}}]}
    def body(self,**updates):
        value={'message':'Qual o horario do spa?','request_id':'kb-test-0001','session_id':'local-demo','knowledge_version':self.version,'model_output':self.output()}
        value.update(updates)
        return value
    def test_base_and_no_guest_identifiers_in_model(self):
        c=app.knowledge_context(self.body(session_id='private_session'))
        self.assertEqual(c['policy_count'],101)
        self.assertFalse(c['use_ai'])
        self.assertNotIn('model_request',c)
    def test_extract_persisted_and_idempotent(self):
        body=self.body(message=self.policies['POL-08']['example_question'])
        first=app.handle_knowledge_message(body)
        self.assertEqual(first['answer_mode'],'local_knowledge')
        self.assertEqual(first['policy_ids'],['POL-08'])
        self.assertFalse(first['ai_used'])
        self.assertTrue(first['persisted'])
        self.assertEqual(first,app.handle_knowledge_message(body))
        self.assertEqual(app.list_handoffs(),[])
    def test_fabricated_quote_and_invalid_sources_rejected(self):
        for out in [self.output(quote='O spa funciona 24 horas e e gratuito.'),self.output(pid='POL-02'),self.output(pid='POL-999',quote='Informacao inexistente')]:
            self.assertIsNone(kb.validated_answer(out,self.version))
    def test_measurement_requires_measurement_in_evidence(self):
        output=self.output(pid='POL-12')
        self.assertIsNone(kb.validated_answer(output,self.version,'Qual a profundidade da piscina?'))
        self.assertIsNone(kb.validated_answer(output,self.version,'Qual a largura da piscina?'))
        self.assertIsNotNone(kb.validated_answer(output,self.version,'Quais os horarios das piscinas?'))

    def test_stale_base_refused(self):
        self.assertIsNone(kb.validated_answer(self.output(),'stale'))
    def test_error_refusal_truncation_and_empty(self):
        for out in [{}, {'error':'timeout'}, {'choices':[]}, {'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}]:
            self.assertIsNone(kb.validated_answer(out,self.version))
        self.assertEqual(app.handle_knowledge_message(self.body(message='Qual a profundidade da piscina?',model_output={}))['route'],'HUMAN_HANDOFF')
    def test_actions_emergency_and_sensitive_bypass_model(self):
        for i,message in enumerate(['Quero reservar o spa','Quero toalhas','Socorro tem fogo','Minha senha e segredo']):
            body=self.body(message=message,request_id='kb-guard-'+str(i))
            context=app.knowledge_context(body)
            self.assertFalse(context['use_ai'])
            self.assertNotIn('model_request',context)
            result=app.handle_knowledge_message(body)
            self.assertFalse(result['ai_used'])
            self.assertNotEqual(result['route'],'AUTO_REPLY')
    def test_policy_change_loaded_without_restart(self):
        root=Path(self.tmp.name)
        (root/'knowledge').mkdir()
        (root/'knowledge/policies.json').write_text(json.dumps(list(self.policies.values())),encoding='utf-8')
        with patch.object(kb,'ROOT',root):
            _,before=kb.load_base()
            rows=list(self.policies.values())
            rows[0]={**rows[0],'content':'Changed'}
            (root/'knowledge/policies.json').write_text(json.dumps(rows),encoding='utf-8')
            self.assertNotEqual(before,kb.load_base()[1])

    def test_v2_catalog_and_new_guest_policy(self):
        self.assertEqual(set(self.policies),{f'POL-{i:02}' for i in range(0,101)})
        self.assertEqual(len(kb.guest_ids(self.policies)),89)
        self.assertIn('POL-57',kb.guest_ids(self.policies))
        self.assertNotIn('POL-100',kb.guest_ids(self.policies))
        result=kb.validated_answer(self.output(pid='POL-57'),self.version)
        self.assertEqual(result['policy_ids'],['POL-57'])
        self.assertIsNone(kb.validated_answer(self.output(pid='POL-100'),self.version))
        for row in self.policies.values():
            self.assertEqual(row['version'],2)
            self.assertTrue(row['department'])
            self.assertTrue(row['example_question'])
            self.assertEqual(row['deployment_scope'],'hotel_ficticio')

if __name__=='__main__': unittest.main()
