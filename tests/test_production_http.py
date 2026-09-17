import concurrent.futures
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import auth
from scripts.http_fixture import ServerFixture

class ProductionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = app.DB
        app.DB = Path(self.tmp.name) / 'test.sqlite3'
        app.init_db()
        self.server = ServerFixture(app.application)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        app.DB = self.old
        self.tmp.cleanup()

    def request(self, path='/api/health', method='GET', body=None, headers=None, read_body=True):
        client = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        try:
            client.request(method, path, body=body, headers=headers or {})
            response = client.getresponse()
            return response.status, response.read() if read_body else b'', dict(response.getheaders())
        finally:
            client.close()

    def post(self, body):
        return self.request('/api/chat', 'POST', json.dumps(body), {'Content-Type':'application/json'})

    def test_transport_guards(self):
        status, body, headers = self.request()
        self.assertEqual(status, 200)
        self.assertIn('waitress', headers['Server'])
        self.assertEqual(json.loads(body)['mode'], 'local_demo')
        self.assertEqual(self.request(headers={'Host':'evil.example'})[0], 403)
        self.assertEqual(self.request(headers={'Origin':'https://evil.example'})[0], 403)
        self.assertEqual(self.request(headers={'Host':'evil.example','X-Forwarded-Host':f'localhost:{self.server.server_port}'})[0], 403)
        self.assertEqual(self.request(method='HEAD')[1], b'')
        self.assertEqual(self.request(method='DELETE')[0], 405)
        self.assertEqual(self.request('/missing')[0], 404)
        self.assertEqual(self.request('/api/users')[0], 401)
        self.assertEqual(self.request('/hotel')[0], 303)
        self.assertEqual(self.request('/api/pilot/check','POST','{}',{'Content-Type':'application/json'})[0],401)

    def test_parser_limits_and_errors(self):
        self.assertEqual(self.request('/api/chat','POST','x'*16385,{'Content-Type':'application/json'},read_body=False)[0],413)
        self.assertEqual(self.request(headers={'X-Large':'x'*17000})[0],431)
        self.assertEqual(self.request('/api/chat','POST','{',{'Content-Type':'application/json'})[0],400)
        self.assertEqual(self.request('/api/chat','POST','{}',{'Content-Type':'text/plain'})[0],415)
        with patch.object(app.operating_mode, 'production', side_effect=RuntimeError('secret-test-value')):
            with self.assertLogs('aura.http', level='ERROR') as logs:
                status,body,_=self.request()
            self.assertEqual(status,500)
            self.assertNotIn('secret-test-value',body.decode()+str(logs.output))
        self.assertEqual(self.request()[0],200)

    def test_login_cookie_and_permissions(self):
        auth.create_user(app.connection,dict(username='front',name='Test',role='recepcao',password='Initial-test-123'))
        auth.change_password(app.connection,'front','Initial-test-123','Changed-test-123')
        status,body,headers=self.request('/api/auth/login','POST',json.dumps(dict(username='front',password='Changed-test-123')),{'Content-Type':'application/json'})
        self.assertEqual(status,200)
        cookie=headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie)
        self.assertIn('SameSite=Strict',cookie)
        credentials={'Cookie':cookie.split(';')[0]}
        self.assertEqual(self.request('/recepcao',headers=credentials)[0],200)
        self.assertEqual(self.request('/api/reservations',headers=credentials)[0],200)
        self.assertEqual(self.request('/api/users',headers=credentials)[0],403)

    def test_controlled_load_and_duplicate_writes(self):
        # Local baseline acceptance: 120 requests / 12 clients, zero errors,
        # p95 < 5 seconds; duplicated request creates exactly one interaction.
        def execute(index):
            start=time.perf_counter()
            if index % 3 == 0:
                result=self.request()
            elif index % 3 == 1:
                result=self.post(dict(message='Qual o horario do cafe da manha?',request_id=f'load-faq-{index:04}'))
            else:
                result=self.post(dict(message='Quero toalhas',request_id='load-duplicate-001',session_id='load-guest'))
            return result[0], time.perf_counter()-start
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results=list(pool.map(execute,range(120)))
        latencies=sorted(item[1] for item in results)
        self.assertTrue(all(status==200 for status,_ in results),results)
        self.assertLess(latencies[113],5)
        with app.connection() as db:
            self.assertEqual(db.execute("select count(*) from interactions where id='load-duplicate-001'").fetchone()[0],1)
            self.assertEqual(db.execute("select count(*) from handoffs where id='load-duplicate-001'").fetchone()[0],1)
        report=dict(passed=True,requests=120,clients=12,errors=0,p95_ms=round(latencies[113]*1000,2),max_ms=round(max(latencies)*1000,2),p95_limit_ms=5000,duplicate_interactions=1,duplicate_handoffs=1,isolated_database=True,whatsapp_sent=False)
        (app.ROOT/'runtime/http-load-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':unittest.main()
