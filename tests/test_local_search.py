import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import app,knowledge_engine as kb,policy_review

class LocalSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DB
        app.DB=Path(self.tmp.name)/'test.sqlite3';app.init_db();self.i=0
    def tearDown(self):
        app.DB=self.old;self.tmp.cleanup()
    def ask(self,q,session='search-test'):
        self.i+=1
        return app.handle_message(dict(message=q,request_id=f'search-test-{self.i:04}',session_id=session))
    def test_equivalent_questions(self):
        for q,pid in [('quando posso entrar?','POL-04'),('horario de entrada','POL-04'),('que horas é o check-in?','POL-04'),('que horas abre a musculação?','POL-15'),('que horas é o desjejum?','POL-08')]:
            with self.subTest(q=q):self.assertEqual(self.ask(q)['policy_ids'],[pid])
    def test_followup_and_change_topic(self):
        self.ask('Qual horario da piscina?')
        self.assertEqual(self.ask('e fecha que horas?')['policy_ids'],['POL-12'])
        self.assertEqual(self.ask('e o café da manhã?')['policy_ids'],['POL-08'])
        self.assertEqual(self.ask('e aos domingos?')['policy_ids'],['POL-08'])
        self.assertEqual(self.ask('e qual a profundidade?')['route'],'HUMAN_HANDOFF')
    def test_no_context_leak_or_expired_context(self):
        self.ask('Qual horario da piscina?')
        self.assertEqual(self.ask('e fecha que horas?','other')['answer_mode'],'clarification')
        with app.connection() as db:
            db.execute('UPDATE interactions SET created_at=?',((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),))
        self.assertEqual(self.ask('e fecha que horas?')['answer_mode'],'clarification')
    def test_safety_and_actions_precede_followup(self):
        self.ask('Qual horario da piscina?')
        self.assertEqual(self.ask('e tem fogo na piscina')['priority'],'urgent')
        self.assertEqual(self.ask('e minha senha?')['route'],'SAFE_REPLY')
        self.assertEqual(self.ask('e quero reservar a piscina')['route'],'HUMAN_HANDOFF')
    def test_unknown_facts_never_topic_only(self):
        for q in ['Qual a profundidade da piscina?','Qual horario e temperatura da piscina?','A piscina tem tubarões?','Qual o preço da academia?']:
            with self.subTest(q=q):self.assertEqual(self.ask(q)['route'],'HUMAN_HANDOFF')
    def test_published_policy_variants_and_draft_isolation(self):
        fields=dict(title='Biblioteca',content='A biblioteca abre das 09h às 17h.',department='recepcao',example_question='Qual o horário da biblioteca?')
        r=policy_review.change(app.connection,app.POLICIES,dict(action='create',actor='Teste',audience='guest',draft=fields,publish=True))
        self.assertEqual(self.ask('que horas abre a biblioteca?')['policy_ids'],[r['id']])
        row=next(p for p in policy_review.catalog(app.connection,app.POLICIES) if p['id']==r['id'])
        policy_review.change(app.connection,app.POLICIES,dict(action='save',id=r['id'],actor='Teste',revision=row['revision'],draft={**fields,'content':'A biblioteca abre das 10h às 18h.'}))
        self.assertIn('09h',self.ask('que horas abre a biblioteca?')['reply'])
        policy_review.change(app.connection,app.POLICIES,dict(action='approve',id=r['id'],actor='Teste',revision=row['revision']+1))
        self.assertIn('10h',self.ask('que horas abre a biblioteca?')['reply'])
    def test_ambiguous_topics_clarify(self):
        for title in ['Jardim norte','Jardim sul']:
            policy_review.change(app.connection,app.POLICIES,dict(action='create',actor='Teste',audience='guest',draft=dict(title=title,content=title+' abre das 08h às 18h.',department='recepcao',example_question='Qual o horário do '+title+'?'),publish=True))
        self.assertEqual(self.ask('que horas abre o jardim?')['answer_mode'],'clarification')
        self.assertEqual(self.ask('e o jardim norte?')['answer_mode'],'local_knowledge')
    def test_no_external_calls_and_retry_stable(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('external call')):
            body=dict(message='quando posso entrar?',request_id='search-repeat-0001',session_id='search-test')
            first=app.handle_message(body)
            self.assertFalse(first['ai_used']);self.assertEqual(first,app.handle_message(body))

if __name__=='__main__':unittest.main()
