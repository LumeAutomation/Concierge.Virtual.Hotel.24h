import concurrent.futures
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock
import app
import conversation_state as state

class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=app.DB
        app.DB=Path(self.tmp.name)/'state.sqlite3'
        app.init_db()
        self.session='waha_5500000000000_c_us'

    def tearDown(self):
        app.DB=self.old
        self.tmp.cleanup()

    def body(self, message='Qual horario do cafe da manha?', rid='context-0001', session=None):
        return dict(message=message,request_id=rid,session_id=session or self.session)

    def test_concurrent_delivery_is_once_and_survives_restart(self):
        body=self.body()
        reply=app.handle_message(body)
        transport=Mock(return_value='provider-1')
        def send(_): return state.deliver(app.connection,body['request_id'],self.session,transport)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(send,range(8)))
        self.assertEqual(transport.call_count,1)
        self.assertEqual(sum(not r['duplicate'] for r in results),1)
        payload=transport.call_args.args[0]
        self.assertEqual(payload['chatId'],'5500000000000@c.us')
        self.assertTrue(payload['text'].endswith(reply['reply']))
        app.init_db()
        self.assertEqual(send(None)['delivery_status'],'sent')
        self.assertEqual(transport.call_count,1)

    def test_timeout_is_never_automatically_retried(self):
        app.handle_message(self.body())
        transport=Mock(side_effect=TimeoutError())
        for _ in range(2):
            result=state.deliver(app.connection,'context-0001',self.session,transport)
            self.assertEqual(result['delivery_status'],'unknown')
            self.assertTrue(result['needs_review'])
        self.assertEqual(transport.call_count,1)

    def test_wrong_session_and_unpersisted_are_rejected(self):
        app.handle_message(self.body())
        transport=Mock()
        for rid,session in [('context-0001','waha_5500000000001_c_us'),('missing-0001',self.session)]:
            with self.assertRaises(ValueError): state.deliver(app.connection,rid,session,transport)
        transport.assert_not_called()

    def test_legacy_migration_blocks_resend_and_stale_attempt_needs_review(self):
        app.handle_message(self.body())
        with app.connection() as db:
            db.execute('DELETE FROM schema_migrations')
        app.init_db()
        transport=Mock()
        result=state.deliver(app.connection,'context-0001',self.session,transport)
        self.assertEqual(result['delivery_status'],'legacy_unverified')
        with app.connection() as db:
            db.execute("UPDATE whatsapp_deliveries SET status='sending',updated_at=?",((state.utcnow()-timedelta(minutes=3)).isoformat(),))
        self.assertTrue(state.deliver(app.connection,'context-0001',self.session,transport)['needs_review'])
        transport.assert_not_called()

    def test_history_is_not_forwarded_in_local_only_mode(self):
        for i in range(5):app.handle_message(self.body(rid=f'context-00{i+1:02}'))
        for sid in [self.session,'other-chat']:
            context=app.knowledge_context(self.body('e aos domingos?','followup-0001',sid))
            self.assertFalse(context['use_ai'])
            self.assertNotIn('model_request',context)
            self.assertEqual(context['context_turns'],0)

    def test_expired_and_sensitive_history_not_forwarded(self):
        app.handle_message(self.body())
        with app.connection() as db:
            db.execute('UPDATE interactions SET created_at=?',((state.utcnow()-timedelta(minutes=31)).isoformat(),))
        self.assertEqual(app.knowledge_context(self.body('e aos domingos?','followup-0001'))['context_turns'],0)
        sensitive=self.body('minha senha secreta','sensitive-0001')
        app.handle_message(sensitive)
        self.assertTrue(app.knowledge_context(sensitive)['cached_response'])
        self.assertEqual(app.knowledge_context(self.body('Qual horario da piscina?','followup-0002'))['context_turns'],0)

    def test_duplicate_skips_model_and_orphan_followup_clarifies(self):
        body=self.body()
        app.handle_message(body)
        result=app.knowledge_context(body)
        self.assertTrue(result['cached_response'])
        self.assertFalse(result['use_ai'])
        self.assertNotIn('model_request',result)
        follow=self.body('e aos domingos?','followup-0001','empty-chat')
        self.assertFalse(app.knowledge_context(follow)['use_ai'])
        self.assertEqual(app.handle_message(follow)['answer_mode'],'clarification')

if __name__=='__main__': unittest.main()
