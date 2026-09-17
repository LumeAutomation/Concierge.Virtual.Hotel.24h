import concurrent.futures
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import app
import auth
import reservations as r
import conversation_state

class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=app.DB
        app.DB=Path(self.tmp.name)/'test.sqlite3'
        app.init_db()
        self.number='5511000000000'
        self.session='waha_'+self.number+'_c_us'
        self.count=0
        self.bot=patch.object(r,'bot_phone',return_value='5524999999999');self.bot.start()
        self.sender=patch.object(conversation_state,'send_waha',return_value='fake-welcome-id');self.sender.start()
        self.record=self.create()
        self.action("welcome")

    def tearDown(self):
        self.sender.stop();self.bot.stop();app.DB=self.old;self.tmp.cleanup()

    def create(self,external='TEST-001',phone=None):
        return r.change(app.connection,dict(external_id=external,guest_name='Hospede Ficticio',phone=phone or self.number,cpf='52998224725',arrival='2026-10-01',departure='2026-10-03',room='101'),'recepcao')['reservation']

    def current(self):
        return r.detail(app.connection,self.record['id'])

    def action(self,action,**kw):
        value=self.current()
        return r.change(app.connection,dict(id=value['id'],version=value['version'],action=action,**kw),'recepcao')

    def link(self):
        result=self.action('link')
        message=parse_qs(urlparse(result['url']).query)['text'][0]
        self.assertNotIn('52998224725',result['url'])
        self.assertNotIn('Hospede',result['url'])
        self.assertNotIn('TEST-001',result['url'])
        return message

    def say(self,text,session=None,rid=None):
        self.count+=1
        return app.handle_message(dict(message=text,session_id=session or self.session,request_id=rid or f'reservation-message-{self.count:04}'))

    def precheck(self):
        self.say(self.link())
        self.say('CONFIRMAR NOME')
        self.say('CONFIRMAR DADOS')
        self.say('CONCLUIR')
        self.assertEqual(self.current()['pre_status'],'PRE_CHECKIN_CONCLUIDO')

    def test_complete_journey_and_existing_knowledge(self):
        message=self.link()
        self.assertTrue(r.access(app.connection,dict(message=message,session_id=self.session)))
        self.assertEqual(self.say(message)['answer_mode'],'reservation')
        self.assertEqual(self.current()['stage'],'NAME')
        faq=self.say('Qual o horario do cafe da manha?')
        self.assertIn('POL-08',faq['policy_ids'])
        self.assertEqual(self.current()['stage'],'NAME')
        self.say('CONFIRMAR NOME');self.say('CONFIRMAR DADOS');self.say('CONCLUIR')
        self.assertEqual(self.current()['checkin_status'],'PENDENTE')
        with self.assertRaises(ValueError):self.action('checkin')
        self.action('checkin',document_checked=True)
        self.assertIn('101',self.say('Quero fazer check-in')['reply'])
        blocked=self.say('Quero fazer checkout')
        self.assertEqual(blocked['route'],'HUMAN_HANDOFF')
        self.assertEqual(self.current()['checkout_status'],'PENDENTE_RECEPCAO')
        with self.assertRaises(ValueError):self.action('checkout')
        with self.assertRaises(ValueError):self.action('clear_checkout',pending_reviewed=True)
        self.action('clear_checkout',pending_reviewed=True,payments_reviewed=True)
        done=self.say('Quero fazer checkout')
        self.assertEqual(self.current()['status'],'CHECK_OUT_REALIZADO')
        self.assertTrue(r.access(app.connection,dict(session_id=self.session,request_id=done['request_id'])))
        self.assertFalse(r.access(app.connection,dict(session_id=self.session,message='oi',request_id='unknown-123')))
        transport=Mock(return_value='fake-provider-id')
        self.assertEqual(conversation_state.deliver(app.connection,done['request_id'],self.session,transport)['delivery_status'],'sent')
        with self.assertRaises(ValueError):self.action('link')

    def test_token_bound_to_phone_expiry_rotation_and_redaction(self):
        message=self.link()
        other='waha_5522000000000_c_us'
        self.assertFalse(r.access(app.connection,dict(message=message,session_id=other)))
        self.say(message,session=other)
        self.assertEqual(self.current()['pre_status'],'PRE_CHECKIN_PENDENTE')
        with app.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reservation_conversations').fetchone()[0],0)
            data=' '.join(str(x) for x in db.execute('SELECT message,response FROM interactions').fetchall())
            self.assertNotIn(r.TOKEN_RE.search(message)[1],data)
        replacement=self.link()
        self.assertFalse(r.access(app.connection,dict(message=message,session_id=self.session)))
        self.assertTrue(r.access(app.connection,dict(message=replacement,session_id=self.session)))
        with app.connection() as db:db.execute('UPDATE reservation_links SET expires=?',(time.time()-1,))
        self.assertFalse(r.access(app.connection,dict(message=replacement,session_id=self.session)))
        self.say(replacement)
        self.assertEqual(self.current()['pre_status'],'PRE_CHECKIN_PENDENTE')

    def test_lid_requires_verified_phone_and_supports_named_session(self):
        message=self.link();sid='waha_1234567890_lid'
        with patch.object(r,'waha_get',return_value={'lid':'1234567890@lid','pn':self.number+'@c.us'}):
            self.assertTrue(r.access(app.connection,dict(message=message,session_id=sid)))
            self.say(message,session=sid)
        self.assertEqual(self.current()['stage'],'NAME')
        with patch.object(r,'waha_get',return_value={'lid':'1234567890@lid','pn':'5522000000000@c.us'}):
            self.assertFalse(r.access(app.connection,dict(session_id=sid)))
        with patch.object(r,'waha_get',side_effect=TimeoutError):
            self.assertFalse(r.access(app.connection,dict(session_id=sid)))

    def test_duplicate_and_concurrent_message_do_not_advance_twice(self):
        message=self.link()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            result=list(pool.map(lambda _:self.say(message,rid='duplicate-reservation-1'),range(4)))
        self.assertTrue(all(x==result[0] for x in result))
        first=self.say('sim',rid='duplicate-confirm-01')
        self.assertEqual(first,self.say('sim',rid='duplicate-confirm-01'))
        self.assertEqual(self.current()['stage'],'DOCUMENT')
        with app.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM reservation_events WHERE action='PRE_CHECKIN_INICIADO'").fetchone()[0],1)

    def test_no_ambiguous_switch_correction_and_edit_invalidate(self):
        self.say(self.link())
        second=self.create('TEST-002')
        result=r.change(app.connection,dict(id=second['id'],version=second['version'],action='link'),'recepcao')
        message=parse_qs(urlparse(result['url']).query)['text'][0]
        self.assertEqual(self.say(message)['route'],'HUMAN_HANDOFF')
        self.assertEqual(self.current()['stage'],'NAME')
        self.say('CORRIGIR')
        self.assertEqual(self.current()['stage'],'REVIEW')
        self.assertEqual(self.say('PRE-CHECK-IN')['route'],'HUMAN_HANDOFF')
        updated=self.current()
        r.change(app.connection,dict(updated,action='save',guest_name='Novo Nome'),'recepcao')
        self.assertFalse(r.access(app.connection,dict(session_id=self.session)))
        self.assertEqual(self.current()['pre_status'],'PRE_CHECKIN_PENDENTE')

    def test_state_guards_version_and_cpf(self):
        with self.assertRaises(ValueError):self.action('checkin',document_checked=True)
        with self.assertRaises(ValueError):self.action('checkout')
        with self.assertRaises(ValueError):r.cpf_number('11111111111')
        with self.assertRaises(ValueError):r.cpf_number('52998224724')
        self.assertEqual(r.phone_number('(24) 98829-6985'),'5524988296985')
        old=self.current();self.link()
        with self.assertRaises(r.Conflict):r.change(app.connection,dict(old,action='save'),'recepcao')
        self.precheck();self.action('checkin',document_checked=True)
        with self.assertRaises(ValueError):r.change(app.connection,dict(self.current(),action='save'),'recepcao')

    def test_urgent_and_hours_are_not_captured_by_reservation_flow(self):
        self.say(self.link())
        self.assertEqual(self.say('Socorro, quero fazer checkout')['priority'],'urgent')
        self.assertEqual(self.current()['stage'],'NAME')
        result=self.say('Qual o horario do check-in?')
        self.assertIn('POL-04',result['policy_ids'])
        with app.connection() as db:
            logs=' '.join(str(x) for x in db.execute('SELECT message FROM interactions').fetchall())
        self.assertNotIn('AURA-RESERVA',logs)

    def test_api_auth_roles_and_checkout_delivery_gate(self):
        auth.create_user(app.connection,dict(username='front',name='Recepcao',role='recepcao',password='Reservation-test-123'))
        auth.create_user(app.connection,dict(username='editor',name='Editor',role='editor',password='Reservation-test-123'))
        with app.connection() as db:db.execute('UPDATE staff_users SET must_change=0')
        front=auth.login(app.connection,'front','Reservation-test-123')
        editor=auth.login(app.connection,'editor','Reservation-test-123')
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,body=None,token=None,service=False):
            headers={'Content-Type':'application/json'}
            if token:headers['Cookie']=auth.COOKIE+'='+token
            req=Request('http://127.0.0.1:'+str(server.server_port)+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            try:
                with urlopen(req,timeout=15) as response:return response.status,json.load(response)
            except HTTPError as error:return error.code,json.load(error)
        try:
            self.assertEqual(request('/api/reservations')[0],401)
            self.assertEqual(request('/api/reservations',token=editor)[0],403)
            self.assertEqual(request('/api/reservations',token=front)[0],200)
            self.assertEqual(request('/api/reservations/'+self.record['id'],token=editor)[0],403)
            self.assertEqual(request('/api/reservations',dict(action='link',id=self.record['id'],version=1))[0],401)
            self.assertEqual(request('/api/chat',dict(message=self.link(),session_id=self.session,request_id='spoofed-message-1'))[0],401)
            self.assertEqual(request('/api/reservations',dict(action='checkin',id=self.record['id'],version=self.current()['version'],document_checked=True),front)[0],400)
            with patch.object(app.Handler,'service',return_value=True),patch.object(conversation_state,'send_waha',return_value='test-provider') as transport:
                link=self.link()
                for i,text in enumerate([link,'CONFIRMAR NOME','CONFIRMAR DADOS','CONCLUIR']):
                    body=dict(message=text,session_id=self.session,request_id='http-reservation-'+str(i))
                    status,gate=request('/api/pilot/check',body)
                    self.assertEqual(status,200);self.assertTrue(gate['allowed'])
                    status,result=request('/api/chat',body)
                    self.assertEqual(status,200)
                    self.assertEqual(result['answer_mode'],'reservation')
                self.action('checkin',document_checked=True)
                self.action('clear_checkout',pending_reviewed=True,payments_reviewed=True)
                body=dict(message='Quero fazer checkout',session_id=self.session,request_id='http-checkout-final')
                self.assertEqual(request('/api/chat',body)[0],200)
                outbound=dict(session_id=self.session,request_id='http-checkout-final')
                status,result=request('/api/whatsapp/reply',outbound)
                self.assertEqual(status,200);self.assertEqual(result['delivery_status'],'sent')
                self.assertEqual(request('/api/whatsapp/reply',outbound)[0],200)
                self.assertEqual(transport.call_count,1)
        finally:server.shutdown();server.server_close();thread.join()

    def test_welcome_button_short_protocol_and_no_duplicate(self):
        self.assertEqual(self.current()['welcome_status'],'sent')
        self.assertRegex(self.current()['public_protocol'],r'^HA-\d{8}$')
        transport=conversation_state.send_waha
        self.assertEqual(transport.call_count,1)
        payload=transport.call_args.args[0]
        self.assertEqual(payload['chatId'],self.number+'@c.us')
        self.assertIn('Hostess do Hotel Aura',payload['text'])
        self.assertIn('INICIAR',payload['text'])
        self.assertNotIn('52998224725',payload['text'])
        self.assertNotIn('AURA-RESERVA',payload['text'])
        self.assertNotIn(self.record['id'],payload['text'])
        rid='reservation-welcome-'+self.record['id']+'-1'
        conversation_state.deliver(app.connection,rid,self.session)
        self.assertEqual(transport.call_count,1)
        with self.assertRaises(ValueError):self.create()
        self.assertEqual(transport.call_count,1)

    def test_iniciar_verifies_phone_and_offers_precheckin(self):
        self.assertTrue(r.access(app.connection,dict(message='INICIAR',session_id=self.session)))
        self.assertFalse(r.access(app.connection,dict(message='INICIAR',session_id='waha_5522000000000_c_us')))
        response=self.say('INICIAR',rid='start-unique-001')
        self.assertIn('Gostaria de realizar seu pré-check-in agora?',response['reply'])
        self.assertEqual(self.current()['stage'],'OFFER')
        self.assertEqual(self.say('INICIAR',rid='start-unique-001'),response)
        self.say('DEPOIS');self.assertEqual(self.current()['pre_status'],'PRE_CHECKIN_PENDENTE')
        self.say('SIM');self.assertEqual(self.current()['stage'],'NAME')
        self.say('CONFIRMAR NOME')
        dates=self.say('CONFIRMAR DADOS')['reply']
        self.assertIn('01/10/2026',dates);self.assertNotIn('2026-10-01',dates)
        self.say('CONCLUIR');self.assertEqual(self.current()['pre_status'],'PRE_CHECKIN_CONCLUIDO')

    def test_iniciar_lid_and_multiple_reservations_do_not_guess(self):
        sid='waha_1234567890_lid'
        with patch.object(r,'waha_get',return_value={'lid':'1234567890@lid','pn':self.number+'@c.us'}):
            self.assertTrue(r.access(app.connection,dict(message='INICIAR',session_id=sid)))
            self.say('INICIAR',session=sid)
        self.assertEqual(self.current()['stage'],'OFFER')
        second=self.create('SECOND-RESERVATION')
        r.change(app.connection,dict(action='welcome',id=second['id'],version=second['version']),'recepcao')
        result=self.say('INICIAR')
        self.assertEqual(result['route'],'HUMAN_HANDOFF')
        self.assertNotIn('Hospede Ficticio',result['reply'])
        self.assertRegex(result['reply'],r'HA-\d{8}')
        self.assertNotIn(result['request_id'],result['reply'])
        with app.connection() as db:db.execute('UPDATE reservation_links SET expires=?',(time.time()-1,))
        self.assertFalse(r.access(app.connection,dict(message='INICIAR',session_id=self.session)))

    def test_welcome_timeout_is_visible_and_never_retried(self):
        transport=Mock(side_effect=TimeoutError)
        result=r.change(app.connection,dict(external_id='FAIL-WELCOME',guest_name='Pessoa Teste',phone='5522000000000',cpf='52998224725'),'recepcao',transport=transport)
        result=r.change(app.connection,dict(action='welcome',id=result['reservation']['id'],version=result['reservation']['version']),'recepcao',transport=transport)
        self.assertEqual(result['welcome_status'],'unknown')
        self.assertEqual(result['reservation']['welcome_status'],'unknown')
        rid='reservation-welcome-'+result['reservation']['id']+'-1'
        conversation_state.deliver(app.connection,rid,'waha_5522000000000_c_us',transport)
        self.assertEqual(transport.call_count,1)

    def test_migration_does_not_send_historical_reservations(self):
        before=conversation_state.send_waha.call_count
        with app.connection() as db:
            db.execute("INSERT INTO reservations(id,external_id,guest_name,phone,cpf,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",('legacy-row','LEGACY','Antigo Hospede',self.number,'52998224725',r.now(),r.now()))
        app.init_db()
        self.assertEqual(conversation_state.send_waha.call_count,before)
        self.assertEqual(r.detail(app.connection,'legacy-row')['welcome_status'],'not_sent')

    def test_save_never_sends_and_concurrent_clicks_send_once(self):
        transport=conversation_state.send_waha
        transport.reset_mock()
        record=self.create('CLICK-ONLY')
        self.assertEqual(r.detail(app.connection,record['id'])['welcome_status'],'not_sent')
        transport.assert_not_called()
        body=dict(action='welcome',id=record['id'],version=record['version'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:r.change(app.connection,body,'recepcao'),range(4)))
        self.assertEqual(transport.call_count,1)
        self.assertTrue(all(x['welcome_status'] in ('sending','sent') for x in results))
        self.assertEqual(r.detail(app.connection,record['id'])['welcome_status'],'sent')
        self.assertTrue(r.access(app.connection,dict(message='INICIAR',session_id=self.session)))

    def test_edit_refreshes_recipient_for_new_explicit_welcome(self):
        current=self.current()
        changed=r.change(app.connection,dict(current,action='save',phone='5522000000000'),'recepcao')['reservation']
        self.assertEqual(changed['welcome_status'],'not_sent')
        conversation_state.send_waha.reset_mock()
        r.change(app.connection,dict(action='welcome',id=changed['id'],version=changed['version']),'recepcao')
        self.assertEqual(conversation_state.send_waha.call_args.args[0]['chatId'],'5522000000000@c.us')

if __name__=='__main__':unittest.main()
