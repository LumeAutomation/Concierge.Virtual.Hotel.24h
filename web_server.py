"""Bounded local Waitress transport; business routes remain in app.Routes."""
import io
import logging
from email.message import Message
from http import HTTPStatus
from types import SimpleNamespace

MAX_BODY = 16384


def make_application(routes):
    class Request(routes):
        def __init__(self, environ):
            self.path = environ.get('PATH_INFO', '/')
            self.headers = Message()
            for key, value in environ.items():
                if key.startswith('HTTP_'):
                    self.headers[key[5:].replace('_', '-')] = value
            for key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                if environ.get(key):
                    self.headers[key.replace('_', '-')] = environ[key]
            self.server = SimpleNamespace(server_port=int(environ['SERVER_PORT']))
            self.rfile = environ['wsgi.input']
            self.wfile = io.BytesIO()
            self.status = 500
            self.response_headers = []

        def send_response(self, status):
            self.status = status

        def send_header(self, name, value):
            self.response_headers.append((name, str(value)))

        def end_headers(self):
            pass

    def application(environ, start_response):
        request = Request(environ)
        method = environ.get('REQUEST_METHOD', 'GET')
        try:
            if not request.local_request():
                request.respond(403, {'error': 'Acesso somente local.'})
            elif method not in ('GET', 'HEAD', 'POST'):
                request.respond(405, {'error': 'Metodo nao permitido.'})
                request.send_header('Allow', 'GET, HEAD, POST')
            elif method == 'POST':
                request.do_POST()
            else:
                request.do_GET()
        except Exception as error:
            # Never log request bodies, cookies, credentials or exception messages.
            logging.getLogger('aura.http').error('Request failed: %s', type(error).__name__)
            request.wfile = io.BytesIO()
            request.response_headers = []
            request.respond(500, {'error': 'Falha interna. Tente novamente.'})
        start_response(f'{request.status} {HTTPStatus(request.status).phrase}', request.response_headers)
        return [b'' if method == 'HEAD' else request.wfile.getvalue()]

    return application


def create_server(application, port=8787):
    from waitress import create_server as waitress_server
    return waitress_server(
        application, host='127.0.0.1', port=port, threads=8,
        connection_limit=100, backlog=100, channel_timeout=30,
        cleanup_interval=5, max_request_body_size=MAX_BODY,
        max_request_header_size=16384, clear_untrusted_proxy_headers=True,
        expose_tracebacks=False, log_socket_errors=False,
    )
