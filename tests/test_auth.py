import json
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import app
import auth

class AccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DB
        app.DB=Path(self.tmp.name)/'aura.sqlite3';app.init_db()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.password='Original-password-123'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        app.DB=self.old;self.tmp.cleanup()

    def request(self,path,body=None,token=None,extra=None):
        headers={'Content-Type':'application/json',**getattr(self,'service_header',{})}
        if token: headers['Cookie']=auth.COOKIE+'='+token
        headers.update(extra or {})
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return r.status,json.load(r),r.headers
        except urllib.error.HTTPError as e:return e.code,json.load(e),e.headers

    def user(self,name,role,changed=True):
        auth.create_user(app.connection,dict(username=name,name=name,role=role,password=self.password))
        if changed: auth.change_password(app.connection,name,self.password,'Changed-password-456')
        return auth.login(app.connection,name,'Changed-password-456' if changed else self.password)

    def test_anonymous_protection_and_first_password_change(self):
        for path in ['/api/users','/api/handoffs','/api/policies','/api/operations','/api/whatsapp/deliveries','/api/pilot/contacts']:
            self.assertEqual(self.request(path)[0],401,path)
        token=self.user('admin','admin',False)
        self.assertEqual(self.request('/api/users',token=token)[0],401)
        self.assertTrue(self.request('/api/auth/me',token=token)[1]['must_change'])
        result=self.request('/api/auth/password',{'old_password':self.password,'password':'Changed-password-456'},token)
        self.assertEqual(result[0],200);self.assertIsNone(auth.current(app.connection,token))
        status,body,headers=self.request('/api/auth/login',{'username':'admin','password':'Changed-password-456'})
        self.assertEqual(status,200);self.assertFalse(body['must_change'])
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])

    def test_roles_and_actor_cannot_be_spoofed(self):
        receptionist=self.user('front','recepcao');editor=self.user('writer','editor');manager=self.user('manager','gestor')
        self.assertEqual(self.request('/api/policies',token=receptionist)[0],403)
        self.assertEqual(self.request('/api/handoffs',token=editor)[0],403)
        self.assertEqual(self.request('/api/users',token=manager)[0],403)
        draft={key:app.POLICIES['POL-08'][key] for key in ['title','content','department','example_question']}
        body=dict(id='POL-08',action='save',revision=0,draft=draft,actor='forged')
        self.assertEqual(self.request('/api/policies',body,editor)[0],200)
        body.update(action='approve',revision=1)
        self.assertEqual(self.request('/api/policies',body,editor)[0],403)
        self.assertEqual(self.request('/api/policies',body,manager)[0],200)
        with app.connection() as db:
            self.assertEqual(db.execute('SELECT editor,approved_by FROM policy_reviews').fetchone(),('writer','manager'))
        app.handle_message(dict(message='Quero toalhas',request_id='role-test-123'))
        self.assertEqual(self.request('/api/handoffs/status',dict(id='role-test-123',status='in_progress',operator='forged'),receptionist)[0],200)
        self.assertEqual(app.list_handoffs()[0]['operator'],'front')

    def test_revocation_expiry_password_reset_and_last_admin(self):
        admin=self.user('admin','admin');token=self.user('front','recepcao')
        auth.update_user(app.connection,dict(username='front',role='editor',active=True,password='Reset-password-123'),'admin')
        self.assertIsNone(auth.current(app.connection,token))
        reset=auth.login(app.connection,'front','Reset-password-123')
        self.assertTrue(auth.current(app.connection,reset)['must_change'])
        auth.update_user(app.connection,dict(username='front',role='editor',active=False),'admin')
        self.assertIsNone(auth.current(app.connection,reset))
        with self.assertRaises(ValueError): auth.update_user(app.connection,dict(username='admin',role='recepcao',active=True),'admin')
        with patch('auth.time.time',return_value=time.time()+auth.TTL+1):self.assertIsNone(auth.current(app.connection,admin))
        auth.logout(app.connection,admin);self.assertIsNone(auth.current(app.connection,admin))

    def test_rate_limit_survives_reinitialization(self):
        self.user('front','recepcao')
        for _ in range(5): self.assertIsNone(auth.login(app.connection,'front','wrong-password'))
        auth.init_schema(app.connection)
        self.assertIsNone(auth.login(app.connection,'front','Changed-password-456'))
        with patch('auth.time.time',return_value=time.time()+901):
            self.assertIsNotNone(auth.login(app.connection,'front','Changed-password-456'))

    def test_service_and_pilot_gate_before_persistence(self):
        body=dict(message='Quero toalhas',request_id='pilot-test-123',session_id='waha_5511000000000_c_us')
        self.assertEqual(self.request('/api/chat',body)[0],401)
        secret=Path(self.tmp.name)/'runtime/auth/service-token.txt'
        secret.parent.mkdir(parents=True);secret.write_text('isolated-test-token')
        self.service_header={'Authorization':'Bearer incorrect'}
        with patch.object(app,'ROOT',Path(self.tmp.name)):
            self.assertEqual(self.request('/api/chat',body)[0],401)
            self.service_header={'Authorization':'Bearer isolated-test-token'}
            self.assertEqual(self.request('/api/pilot/check',body)[1]['allowed'],False)
            self.assertEqual(self.request('/api/chat',body)[0],403)
            self.assertEqual(app.list_handoffs(),[])
            auth.save_contact(app.connection,dict(identifier='5511000000000',label='Ficticio'),'admin')
            self.assertEqual(self.request('/api/pilot/check',body)[1]['allowed'],True)
            self.assertEqual(self.request('/api/chat',body)[0],200)
            auth.save_contact(app.connection,dict(identifier='5511000000000',label='Ficticio',active=False),'admin')
            self.assertEqual(self.request('/api/whatsapp/reply',body)[0],403)
        token=self.user('front','recepcao')
        self.request('/api/handoffs/status',dict(id=body['request_id'],status='in_progress'),token)
        with patch('conversation_state.send_waha') as send:
            result=self.request('/api/handoffs/status',dict(id=body['request_id'],status='resolved'),token)
            self.assertEqual(result[1]['notification_status'],'blocked');send.assert_not_called()

    def test_editor_can_create_draft_but_not_publish_new_policy(self):
        token=self.user('writer','editor')
        body=dict(action='create',publish=True,audience='guest',draft=dict(title='Leitura',content='Sala aberta das 09h as 17h.',department='recepcao',example_question='Qual horario da sala de leitura?'))
        self.assertEqual(self.request('/api/policies',body,token)[0],403)
        body['publish']=False
        status,result,_=self.request('/api/policies',body,token)
        self.assertEqual(status,200);self.assertEqual(result['id'],'POL-101')
        self.assertNotIn(result['id'],app.knowledge_engine.load_base()[0])
        rows=self.request('/api/policies',token=token)[1]
        self.assertEqual(rows[-1]['editor'],'writer')

    def test_origin_and_invalid_inputs(self):
        token=self.user('admin','admin')
        self.assertEqual(self.request('/api/users',{},token,{'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request('/api/users',dict(username='new',name='New',role=[],password=self.password),token)[0],400)
        self.assertEqual(self.request('/api/knowledge/context',{})[0],401)
        with app.connection() as db:
            hashed=db.execute('SELECT password FROM staff_users').fetchone()[0]
            self.assertNotIn('Changed-password',hashed)
            stored=db.execute('SELECT token FROM staff_sessions').fetchone()[0]
            self.assertNotEqual(stored,token)

if __name__=='__main__':unittest.main()
