import unittest
import json
import concurrent.futures
import test_app
import app
import knowledge_engine as kb
import policy_review as review

class PolicyReviewTests(unittest.TestCase):
    setUp=test_app.ConciergeTests.setUp
    tearDown=test_app.ConciergeTests.tearDown

    def body(self):
        return dict(id='POL-08',action='save',actor='Hotel QA',revision=0,
                    draft={**{k:app.POLICIES['POL-08'][k] for k in review.FIELDS},'title':'Cafe revisado','content':'Cafe da manha: domingos das 07h as 12h. Inclusao depende da tarifa.'})

    def test_draft_is_not_live_and_approval_updates_both_paths(self):
        before,version=kb.load_base();body=self.body()
        review.change(app.connection,app.POLICIES,body)
        self.assertEqual(kb.load_base()[1],version)
        review.change(app.connection,app.POLICIES,{**body,'action':'approve','revision':1})
        current,new_version=kb.load_base()
        self.assertNotEqual(new_version,version)
        self.assertEqual(current['POL-08']['content'],body['draft']['content'])
        result=app.classify('Qual horario do cafe da manha?')
        self.assertEqual(result['reply'],body['draft']['content'])
        self.assertIn(body['draft']['content'],kb.build_context('e aos domingos?','test-0001','local',True)['model_request']['messages'][0]['content'])
        self.assertIsNone(kb.validated_answer({},version))
        app.init_db();self.assertEqual(kb.load_base()[1],new_version)

    def test_new_draft_keeps_previous_approval_and_history(self):
        body=self.body();review.change(app.connection,app.POLICIES,body)
        review.change(app.connection,app.POLICIES,{**body,'action':'approve','revision':1})
        review.change(app.connection,app.POLICIES,{**body,'action':'approve','revision':1})
        review.change(app.connection,app.POLICIES,{**body,'revision':1,'draft':{**body['draft'],'content':'Novo texto ainda em revisao.'}})
        self.assertEqual(kb.load_base()[0]['POL-08']['content'],body['draft']['content'])
        row=next(r for r in review.catalog(app.connection,app.POLICIES) if r['id']=='POL-08')
        self.assertEqual(row['state'],'draft');self.assertEqual(row['published_revision'],1)
        with app.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM policy_review_history').fetchone()[0],3)

    def test_conflicting_edits_and_unsaved_approval_rejected(self):
        body=self.body()
        with self.assertRaises(ValueError):review.change(app.connection,app.POLICIES,{**body,'action':'approve'})
        def save(_):
            try:review.change(app.connection,app.POLICIES,body);return True
            except review.Conflict:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(sum(pool.map(save,range(4))),1)
        with self.assertRaises(review.Conflict):review.change(app.connection,app.POLICIES,{**body,'action':'approve'})

    def test_validation_and_internal_visibility(self):
        body=self.body()
        for override in [{'actor':''},{'revision':True},{'draft':{**body['draft'],'content':''}},{'draft':{**body['draft'],'audience':'guest'}}]:
            with self.assertRaises(ValueError):review.change(app.connection,app.POLICIES,{**body,**override})
        body.update(id='POL-02');review.change(app.connection,app.POLICIES,body)
        review.change(app.connection,app.POLICIES,{**body,'action':'approve','revision':1})
        self.assertNotIn('POL-02',kb.guest_ids(kb.load_base()[0]))
        self.assertEqual(len(review.catalog(app.connection,app.POLICIES)),101)
