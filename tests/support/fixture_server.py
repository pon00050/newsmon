"""Loopback fixture HTTP server with scripted responses and a request log (T-04).

Routes are keyed by path (including the query string). A route holds one response or a list of responses served in
order (the last one repeats). Responses can set status, body, headers, a delay, a redirect, or ask to be dropped.
Every request is logged with path, headers, start/end timestamps and client address, so tests can prove what was (and
was not) requested: robots refusals, conditional GET headers, the User-Agent, per-host concurrency.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


@dataclass
class Resp:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0  # seconds before the body is sent
    content_type: str = "application/rss+xml; charset=utf-8"

    @classmethod
    def file(cls, path: Path, **kw) -> "Resp":
        return cls(body=Path(path).read_bytes(), **kw)

    @classmethod
    def redirect(cls, location: str, status: int = 302) -> "Resp":
        return cls(status=status, headers={"Location": location}, content_type="text/plain")


@dataclass
class LoggedRequest:
    path: str
    headers: dict[str, str]
    start: float
    end: float
    client: str


class FixtureServer:
    def __init__(self) -> None:
        self.routes: dict[str, list[Resp]] = {}
        self._served: dict[str, int] = {}
        self.log: list[LoggedRequest] = []
        self._lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # silence stderr
                pass

            def do_GET(self):
                start = time.monotonic()
                entry = LoggedRequest(self.path, {k.lower(): v for k, v in self.headers.items()}, start, start,
                                      self.client_address[0])
                with server._lock:
                    server.log.append(entry)  # logged before responding, so a client never sees an unlogged reply
                resp = server._next(self.path)
                if resp.delay:
                    time.sleep(resp.delay)
                entry.end = time.monotonic()  # set before replying: the client cannot act on the reply earlier
                try:
                    self.send_response(resp.status)
                    headers = {"Content-Type": resp.content_type, "Content-Length": str(len(resp.body)), **resp.headers}
                    for k, v in headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    if resp.body and resp.status != 304:
                        self.wfile.write(resp.body)
                except (ConnectionError, OSError):
                    pass
                finally:
                    pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    # --- control ----------------------------------------------------------------------------------------------------
    def start(self) -> "FixtureServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path if path.startswith('/') else '/' + path}"

    def route(self, path: str, *responses: Resp) -> str:
        with self._lock:
            self.routes[path] = list(responses) or [Resp(status=200)]
            self._served[path] = 0
        return self.url(path)

    def requests_for(self, path: str) -> list[LoggedRequest]:
        with self._lock:
            return [r for r in self.log if r.path == path]

    def _next(self, path: str) -> Resp:
        with self._lock:
            seq = self.routes.get(path)
            if seq is None:
                return Resp(status=404, body=b"not found", content_type="text/plain")
            i = self._served[path]
            self._served[path] = i + 1
            return seq[min(i, len(seq) - 1)]
