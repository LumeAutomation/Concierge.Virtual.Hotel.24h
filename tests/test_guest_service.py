import concurrent.futures
import json
import unittest
from unittest.mock import Mock
from datetime import timedelta
import test_app
import app,guest_service as svc,reception,conversation_state as state,reservations

class GuestServiceTests(unittest.TestCase):
    setUp=test_app.ConciergeTests.setUp
    tearDown=test_app.ConciergeTests.tearDown
    def ask(self,text,rid='service-test-0001',session='waha_5500000000000_c_us'):
        return app.handle_message(dict(message=text,request_id=rid,session_id=session))
    def claim(self):
        self.ask('Preciso de duas toalhas')
        reception.update(app.connection,dict(id='service-test-0001',status='in_progress',operator='Teste'))
    def action(self,action,**extra):
        return svc.staff_action(app.connection,dict(id='service-test-0001',action=action,**extra),'Teste',transport=extra.pop('transport',None),allow_notification=lambda _:True)
    def test_quantity_and_unverified_room(self):
        reply=self.ask('Preciso de duas toalhas no quarto 999')
        row=app.list_handoffs()[0]
        self.assertEqual(row['service']['quantity'],2);self.assertIsNone(row['service']['room'])
        self.assertIn('conferir sua hospedagem',reply['reply'])
    def test_room_from_checked_in_reservation_only(self):
        result=reservations.change(app.connection,dict(external_id='SERVICE-TEST',guest_name='Teste Ficticio',phone='5500000000000',cpf='52998224725',room='101',arrival='2026-10-01',departure='2026-10-03'),'Teste')
        rid=result['reservation']['id']
        with app.connection() as db:
            db.execute("UPDATE reservations SET status='CHECK_IN_REALIZADO',checkin_status='CHECK_IN_REALIZADO' WHERE id=?",(rid,))
            db.execute('INSERT INTO reservation_conversations VALUES (?,?)',('waha_5500000000000_c_us',rid))
        self.ask('Quero 2 toalhas no quarto 999')
        service=app.list_handoffs()[0]['service']
        self.assertEqual(service['room'],'101');self.assertEqual(service['reservation_id'],rid)
    def test_status_scoped_and_no_new_ticket(self):
        self.claim()
        reply=self.ask('como está meu pedido?','service-status-001')
        self.assertIn('em atendimento',reply['reply']);self.assertEqual(len(app.list_handoffs()),1)
        self.assertIn('Não encontrei',self.ask('como está meu pedido?','service-status-002','other')['reply'])
    def test_takeover_suppresses_delivery_and_release_restores(self):
        self.claim();self.action('takeover')
        reply=self.ask('Qual horario da piscina?','service-paused-001')
        self.assertTrue(reply['suppress_response']);transport=Mock()
        self.assertEqual(state.deliver(app.connection,reply['request_id'],'waha_5500000000000_c_us',transport)['delivery_status'],'suppressed')
        transport.assert_not_called()
        self.action('release')
        self.assertEqual(self.ask('Qual horario da piscina?','service-paused-002')['policy_ids'],['POL-12'])
        self.assertEqual(state.deliver(app.connection,reply['request_id'],'waha_5500000000000_c_us',transport)['delivery_status'],'suppressed')
    def test_emergency_and_sensitive_override_pause(self):
        self.claim();self.action('takeover')
        self.assertEqual(self.ask('socorro tem fogo','service-urgent-01')['priority'],'urgent')
        self.assertEqual(self.ask('minha senha','service-secret-01')['route'],'SAFE_REPLY')
    def test_manual_message_retries_send_once(self):
        self.claim();self.action('takeover');transport=Mock(return_value='fake-id')
        body=dict(id='service-test-0001',action='message',request_id='staff-message-0001',text='Estamos conferindo seu pedido.')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:svc.staff_action(app.connection,body,'Teste',transport,lambda _:True),range(4)))
        self.assertEqual(transport.call_count,1)
        self.assertEqual(svc.thread(app.connection,'service-test-0001')[-1]['role'],'staff')
        with self.assertRaises(ValueError):svc.staff_action(app.connection,{**body,'text':'Outra resposta'},'Teste',transport,lambda _:True)
    def test_unknown_send_no_retry(self):
        self.claim();transport=Mock(side_effect=TimeoutError())
        body=dict(id='service-test-0001',action='notify_start')
        for _ in range(2):self.assertEqual(svc.staff_action(app.connection,body,'Teste',transport,lambda _:True)['delivery_status'],'unknown')
        self.assertEqual(transport.call_count,1)
    def test_owner_and_contact_gate(self):
        self.claim()
        with self.assertRaises(ValueError):svc.staff_action(app.connection,dict(id='service-test-0001',action='takeover'),'Other')
        with self.assertRaises(ValueError):svc.staff_action(app.connection,dict(id='service-test-0001',action='notify_start'),'Teste',Mock(),lambda _:False)
    def test_completed_releases_and_feedback_reopens(self):
        self.claim();self.action('takeover');transport=Mock(return_value='fake-id')
        reception.update(app.connection,dict(id='service-test-0001',status='resolved',operator='Teste'),transport)
        self.assertIn('RECEBI AS TOALHAS',transport.call_args.args[0]['text'])
        self.assertIsNone(app.list_handoffs()[0]['human_operator'])
        self.ask('não recebi as toalhas','service-feedback-01')
        self.assertEqual(app.list_handoffs()[0]['status'],'open')
        self.assertEqual(app.list_handoffs()[0]['service']['guest_feedback'],'not_received')
    def test_received_feedback_and_courtesy(self):
        self.claim();self.ask('recebi as toalhas','service-feedback-01')
        self.assertEqual(svc.metrics(app.connection)['feedback']['received'],1)
        self.assertEqual(self.ask('obrigado','service-thanks-01')['answer_mode'],'courtesy')
        self.assertEqual(len(app.list_handoffs()),1)
    def test_cancel_only_unclaimed_towels(self):
        self.ask('Quero toalhas')
        self.assertEqual(self.ask('cancelar meu pedido','service-cancel-01')['answer_mode'],'service_cancelled')
        self.assertEqual(app.list_handoffs()[0]['status'],'resolved')
    def test_cannot_cancel_in_progress(self):
        self.claim();self.ask('cancelar meu pedido','service-cancel-01')
        self.assertEqual(app.list_handoffs()[0]['status'],'in_progress')
    def test_metrics_waiting_and_unknown_questions(self):
        self.ask('Quero toalhas')
        with app.connection() as db:db.execute('UPDATE interactions SET created_at=?',((state.utcnow()-timedelta(minutes=20)).isoformat(),))
        self.ask('Qual a profundidade da piscina?','service-gap-0001')
        metrics=svc.metrics(app.connection)
        self.assertEqual(metrics['waiting_over_15_minutes'],1);self.assertEqual(metrics['knowledge_gaps_sample'],1)
    def test_typo_service_query(self):
        self.assertEqual(self.ask('qual horario da piscna?')['policy_ids'],['POL-12'])

if __name__=='__main__':unittest.main()
