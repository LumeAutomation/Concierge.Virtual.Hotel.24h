"""FNRH authorization through the same WSGI routes as the local server."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import auth


class FnrhHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = app.DB
        app.DB = Path(self.tmp.name) / 'isolated.sqlite3'
        app.init_db()

    def tearDown(self):
        app.DB = self.old
        self.tmp.cleanup()

    def token(self, role):
        auth.create_user(app.connection, dict(username='tester', name='Test Staff',
                         role=role, password='Isolated-Test-Password-123'))
        with app.connection() as db:
            db.execute('UPDATE staff_users SET must_change=0')
        return auth.login(app.connection, 'tester', 'Isolated-Test-Password-123')

    def request(self, path='/api/fnrh', body=None, token=None, origin=None):
        data = json.dumps(body).encode() if body is not None else b''
        environ = {'REQUEST_METHOD': 'POST' if body is not None else 'GET',
                   'PATH_INFO': path, 'SERVER_PORT': '8787',
                   'HTTP_HOST': '127.0.0.1:8787', 'CONTENT_TYPE': 'application/json',
                   'CONTENT_LENGTH': str(len(data)), 'wsgi.input': io.BytesIO(data)}
        if token:
            environ['HTTP_COOKIE'] = auth.COOKIE + '=' + token
        if origin:
            environ['HTTP_ORIGIN'] = origin
        response = {}
        def start(status, headers):
            response.update(status=int(status.split()[0]), headers=dict(headers))
        raw = b''.join(app.application(environ, start))
        return response['status'], raw, response['headers']

    def test_anonymous_and_editor_cannot_read_or_mutate(self):
        for token in (None, self.token('editor')):
            expected = 401 if token is None else 403
            with patch.object(app.fnrh_service, 'change') as change:
                self.assertEqual(self.request(token=token)[0], expected)
                self.assertEqual(self.request(body={'action':'simulate'}, token=token)[0], expected)
                change.assert_not_called()
        status, _, headers = self.request('/fnrh')
        self.assertEqual(status, 303)
        self.assertEqual(headers['Location'], '/login')

    def test_reception_page_overview_and_session_actor(self):
        token = self.token('recepcao')
        self.assertEqual(self.request('/fnrh', token=token)[0], 200)
        status, raw, _ = self.request(token=token)
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)['official_enabled'])
        with patch.object(app.fnrh_service, 'change', return_value={'updated':True}) as change:
            self.assertEqual(self.request(body={'actor':'forged','action':'simulate'}, token=token)[0], 200)
            self.assertEqual(change.call_args.args[2], 'tester')
            self.assertEqual(change.call_args.args[1]['actor'], 'tester')

    def test_origin_rejection_and_invalid_action(self):
        token = self.token('recepcao')
        with patch.object(app.fnrh_service, 'change') as change:
            self.assertEqual(self.request(body={}, token=token, origin='https://external.example')[0], 403)
            change.assert_not_called()
        self.assertEqual(self.request(body={'action':'send_official'}, token=token)[0], 400)


if __name__ == '__main__':
    unittest.main()
