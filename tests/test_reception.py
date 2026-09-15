import concurrent.futures
import unittest
from unittest.mock import Mock
import test_app
import app
import reception

class ReceptionTests(unittest.TestCase):
    setUp=test_app.ConciergeTests.setUp
    tearDown=test_app.ConciergeTests.tearDown
    def prepare(self,session='waha_5500000000000_c_us'):
        rid='reception-test-001'
        app.handle_message(dict(message='Quero toalhas',request_id=rid,session_id=session))
        reception.update(app.connection,dict(id=rid,status='in_progress',operator='Teste'))
        return dict(id=rid,status='resolved',operator='Teste')

    def test_complete_concurrent_and_restart_no_duplicate(self):
        body=self.prepare();transport=Mock(return_value='provider-test')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: reception.update(app.connection,body,transport),range(8)))
        self.assertEqual(transport.call_count,1)
        self.assertEqual(transport.call_args.args[0]['chatId'],'5500000000000@c.us')
        app.init_db();reception.update(app.connection,body,transport)
        self.assertEqual(transport.call_count,1)
        row=app.list_handoffs()[0]
        self.assertEqual(row['status'],'resolved');self.assertEqual(row['notification_status'],'sent')
        self.assertEqual(row['operator'],'Teste')

    def test_failed_notification_does_not_reopen_or_resend(self):
        body=self.prepare();transport=Mock(side_effect=TimeoutError())
        for _ in range(2): self.assertEqual(reception.update(app.connection,body,transport)['notification_status'],'unknown')
        self.assertEqual(transport.call_count,1)
        self.assertEqual(app.list_handoffs()[0]['status'],'resolved')

    def test_local_completion_never_sends(self):
        body=self.prepare('local-demo');transport=Mock()
        self.assertEqual(reception.update(app.connection,body,transport)['notification_status'],'local_only')
        transport.assert_not_called()

    def test_claim_required_and_owner_preserved(self):
        rid='reception-test-001';app.handle_message(dict(message='Quero toalhas',request_id=rid))
        body=dict(id=rid,status='resolved',operator='Teste')
        with self.assertRaises(ValueError): reception.update(app.connection,body)
        reception.update(app.connection,{**body,'status':'in_progress'})
        with self.assertRaises(ValueError): reception.update(app.connection,{**body,'operator':'Outra pessoa'})
        with self.assertRaises(ValueError): reception.update(app.connection,{**body,'status':'open'})
