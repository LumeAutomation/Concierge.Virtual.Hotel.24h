import concurrent.futures
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import test_app
import app
import knowledge_engine as kb
import policy_review as review

class NewPolicyTests(unittest.TestCase):
    setUp=test_app.ConciergeTests.setUp
    tearDown=test_app.ConciergeTests.tearDown

    def create(self,publish=True,audience='guest',suffix=''):
        return review.change(app.connection,app.POLICIES,dict(action='create',actor='uiliam',publish=publish,audience=audience,
          draft=dict(title='Sala de leitura'+suffix,content='A sala de leitura funciona das 09h as 17h.'+suffix,department='recepcao',example_question='Qual o horario da sala de leitura?'+suffix)))

    def test_create_publish_updates_base_and_reply_without_restart(self):
        _,old=kb.load_base();result=self.create();self.assertEqual(result['id'],'POL-101')
        policies,version=kb.load_base();self.assertNotEqual(version,old)
        answer=app.handle_message(dict(message='Qual o horario da sala de leitura?',request_id='new-policy-0001'))
        self.assertEqual(answer['policy_ids'],['POL-101']);self.assertIn(policies['POL-101']['content'],answer['reply'])
        app.init_db();self.assertIn('POL-101',kb.load_base()[0])

    def test_concurrent_creation_uses_unique_ordered_ids(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(lambda i:self.create(suffix=str(i)),range(4)))
        self.assertEqual({r['id'] for r in rows},{'POL-101','POL-102','POL-103','POL-104'})
        ids=[r['id'] for r in review.catalog(app.connection,app.POLICIES)]
        self.assertEqual(ids[0],'POL-00');self.assertLess(ids.index('POL-99'),ids.index('POL-100'))
        self.assertEqual(ids[-1],'POL-104')

    def test_draft_and_internal_policy_not_answered(self):
        draft=self.create(False);self.assertNotIn(draft['id'],kb.load_base()[0])
        self.assertIsNone(kb.local_answer('Qual o horario da sala de leitura?'))
        internal=self.create(True,'internal',' interno')
        self.assertNotIn(internal['id'],kb.guest_ids(kb.load_base()[0]))
        self.assertIsNone(kb.local_answer('Qual o horario da sala de leitura? interno'))

    def test_ambiguous_questions_do_not_pick_a_policy(self):
        self.create();self.create();self.assertIsNone(kb.local_answer('Qual o horario da sala de leitura?'))

    def test_welcome_once_even_with_concurrent_messages_and_retries(self):
        def send(i):return app.handle_message(dict(message='Qual horario do cafe da manha?',request_id='welcome-00'+str(i),session_id='new-visitor'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(send,range(4)))
        self.assertEqual(sum(bool(r.get('welcome_included')) for r in results),1)
        self.assertEqual(send(0),results[0])
        for row in results:self.assertIn(kb.load_base()[0]['POL-08']['content'],row['reply'])

    def test_model_output_is_ignored_and_workflow_has_no_external_model(self):
        body=dict(message='Qual a profundidade da piscina?',request_id='forged-model-123',model_output={'reply':'Inventado: 10 metros'})
        with patch('knowledge_engine.validated_answer',side_effect=AssertionError('Must not call model')):
            reply=app.handle_knowledge_message(body)
        self.assertFalse(reply['ai_used']);self.assertNotIn('10 metros',reply['reply'])
        self.assertEqual(reply['route'],'HUMAN_HANDOFF')
        workflow=json.loads((Path(app.ROOT)/'workflows/WF-03-waha-entrada.json').read_text(encoding='utf-8'))
        self.assertTrue(all(not n.get('parameters',{}).get('url','').startswith('https://') for n in workflow['nodes']))
        self.assertFalse(any('openAiApi' in n.get('credentials',{}) for n in workflow['nodes']))

if __name__=='__main__':unittest.main()
