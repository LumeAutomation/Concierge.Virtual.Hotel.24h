"""Real Waitress socket fixture for isolated HTTP and browser checks."""
import threading
from web_server import create_server

class ServerFixture:
    def __init__(self, application):
        self.server = create_server(application, port=0)
        self.server_port = int(self.server.effective_port)
        self.stopped = threading.Event()

    def serve_forever(self):
        while not self.stopped.is_set():
            self.server.asyncore.loop(timeout=0.1, count=1, map=self.server._map)

    def shutdown(self):
        self.stopped.set()

    def server_close(self):
        self.server.task_dispatcher.shutdown()
        self.server.asyncore.close_all(map=self.server._map)
