"""Local manual-update service and OAuth callback host. No slicer control.

Run: python -m companion.server
SPDX-License-Identifier: AGPL-3.0-only
"""
import hashlib
import json
from pathlib import Path
import secrets
import socket
import threading
import time
from http.server import ThreadingHTTPServer

from .auth_probe import ROOT, Probe, ProbeError, handler_for, protect, read_config
from .export_part import Client, MAX_SNAPSHOT, decode_source, publish

MAX_REQUEST = 128 * 1024
MAX_RESPONSE = 32 * 1024 * 1024
MAX_SOURCES = 16


class Busy(ProbeError):
    pass


class CompanionServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR permits two listeners on one endpoint. Never share it.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Updates:
    def __init__(self, probe, cache, client_factory=Client):
        self.probe = probe
        self.cache = Path(cache)
        self.client_factory = client_factory
        self.lock = threading.Lock()

    def update(self, request):
        if not isinstance(request, dict) or set(request) != {'schema', 'sources'} or request['schema'] != 1:
            raise ProbeError('Unsupported companion request.')
        sources = request['sources']
        if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
            raise ProbeError('Update between 1 and 16 distinct sources at a time.')
        if any(not isinstance(s, str) or len(s) > 4096 for s in sources) or len(set(sources)) != len(sources):
            raise ProbeError('Invalid or duplicated source identity.')
        for source in sources:
            decode_source({'source_id': source})
        if not self.lock.acquire(blocking=False):
            raise Busy('The companion is updating another project. Retry when it finishes.')
        try:
            with self.probe.lock:
                stored = json.loads(protect(self.probe.token_file.read_bytes(), decrypt=True))
                if stored.get('client_id') != self.probe.client_id or stored.get('base_url') != self.probe.base:
                    raise ProbeError('Reconnect the configured test application on http://localhost:8766.')
                if stored.get('expires_at', 0) <= time.time() + 120:
                    self.probe.refresh()
                    stored = json.loads(protect(self.probe.token_file.read_bytes(), decrypt=True))
                client = self.client_factory(self.probe.base, stored['access_token'])
            # Do not return a partial batch or fall back to cached geometry.
            results = [client.update({'source_id': source}) for source in sources]
            for source, (snapshot, _, _) in zip(sources, results):
                if snapshot['source_id'] != source:
                    raise ProbeError('Export returned a different source identity.')
                if len(json.dumps(snapshot).encode()) > MAX_SNAPSHOT:
                    raise ProbeError('Export exceeds the slicer snapshot limit.')
            payload = json.dumps({'schema': 1, 'snapshots': [result[0] for result in results]},
                                 separators=(',', ':'), allow_nan=False).encode()
            if len(payload) > MAX_RESPONSE:
                raise ProbeError('Combined exports exceed the companion response limit.')
            for source, result in zip(sources, results):
                publish(self.cache / hashlib.sha256(source.encode()).hexdigest(), *result)
            return payload
        finally:
            self.lock.release()


def bridge_handler(probe, updates, key):
    class Handler(handler_for(probe)):
        def do_GET(self):
            if self.path == '/' and self.valid_host():
                self.send(200, '<!doctype html><title>Onshape Slicer Link</title><h1>Onshape Slicer Link</h1>'
                          '<p>Companion running. Choose Update linked parts inside your linked slicer to refresh geometry.</p>'
                          '<p>Slicing and printing remain manual.</p>'
                          '<form method="post" action="/connect"><button>Connect to Onshape</button></form>'
                          '<form method="post" action="/refresh"><button>Verify token refresh</button></form>')
            elif self.path == '/v1/status' and self.valid_host():
                self.send_json(200, json.dumps({'schema': 1, 'application': 'Onshape Slicer Link',
                                              'instance': hashlib.sha256(key.encode()).hexdigest()}).encode())
            else:
                super().do_GET()

        def send_json(self, status, body):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # A cancelled slicer request must not change any slicer state.

        def do_POST(self):
            if self.path != '/v1/update':
                return super().do_POST()
            authorization = self.headers.get_all('Authorization', [])
            if (not self.valid_host() or self.headers.get_all('Origin') is not None
                    or len(authorization) != 1
                    or not secrets.compare_digest(authorization[0], 'Bearer ' + key)):
                self.send_json(403, b'{"error":"Companion authorization failed. Restart the companion and slicer."}')
                return
            try:
                if self.headers.get_all('Content-Type') != ['application/json'] or self.headers.get_all('Transfer-Encoding'):
                    raise ProbeError('Expected a bounded JSON request.')
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_REQUEST:
                    raise ProbeError('Invalid companion request length.')
                self.connection.settimeout(10)
                body = self.rfile.read(int(lengths[0]))
                if len(body) != int(lengths[0]):
                    raise ProbeError('Incomplete companion request.')
                self.send_json(200, updates.update(json.loads(body)))
            except (ProbeError, OSError, ValueError, KeyError, TypeError) as error:
                message = str(error) if isinstance(error, ProbeError) else 'Update failed. Existing slicer geometry retained.'
                self.send_json(409 if isinstance(error, Busy) else 400, json.dumps({'error': message}).encode())
    return Handler


def main():
    config = ROOT / 'artifacts/onshape/bridge.json'
    server = None
    key = secrets.token_hex(32)
    try:
        client_id, client_secret, base = read_config(ROOT / '.env')
        probe = Probe(client_id, client_secret, base, ROOT / 'artifacts/onshape/tokens.dpapi')
        updates = Updates(probe, ROOT / 'artifacts/onshape/cache')
        # Bind first; an already running companion must keep its discovery key.
        server = CompanionServer(('127.0.0.1', 8766), bridge_handler(probe, updates, key))
        config.parent.mkdir(parents=True, exist_ok=True)
        temporary = config.with_suffix('.tmp')
        temporary.write_text(json.dumps({'schema': 1, 'key': key}))
        temporary.replace(config)
        print('Onshape Slicer Link companion ready on localhost:8766.', flush=True)
        print('Manual geometry requests enabled. Slicing and printing remain manual.', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (ProbeError, OSError):
        print('Cannot start companion. Check credentials and whether port 8766 is already in use.', flush=True)
        raise SystemExit(1)
    finally:
        if server:
            server.server_close()
            if config.exists() and json.loads(config.read_text()).get('key') == key:
                config.unlink()


if __name__ == '__main__':
    main()
