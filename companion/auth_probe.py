"""Private-app OAuth probe. No geometry, slicing, or printing operations.

Run: python -m companion.auth_probe
SPDX-License-Identifier: AGPL-3.0-only
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://localhost:8766'
CALLBACK = ORIGIN + '/oauth/callback'
TOKEN_URL = 'https://oauth.onshape.com/oauth/token'
AUTHORIZE_URL = 'https://oauth.onshape.com/oauth/authorize'


class ProbeError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    # Never forward credentials or bearer tokens to a redirected host.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, fields=None, token=None):
    headers = {'Accept': 'application/json'}
    data = None
    if fields is not None:
        data = urlencode(fields).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with build_opener(NoRedirect).open(Request(url, data=data, headers=headers), timeout=30) as response:
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise ProbeError('Onshape response exceeded the probe limit.')
            return json.loads(body)
    except HTTPError as error:
        # Response bodies and request URLs can contain credentials or private data.
        raise ProbeError(f'Onshape returned HTTP {error.code}. Existing credentials retained.') from None
    except (URLError, TimeoutError, ValueError):
        raise ProbeError('Onshape request failed. Existing credentials retained.') from None


def read_config(path):
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or key in values:
            raise ProbeError('Invalid or duplicated entry in .env.')
        values[key.strip()] = value.strip()
    for key in ('ONSHAPE_CLIENT_ID', 'ONSHAPE_CLIENT_SECRET'):
        if not values.get(key):
            raise ProbeError(f'Missing {key}. Run the private-app setup wizard.')
    base = values.get('ONSHAPE_BASE_URL', 'https://cad.onshape.com')
    if not re.fullmatch(r'https://[a-z0-9-]+\.onshape\.com', base):
        raise ProbeError('Expected an HTTPS Onshape base URL without a path.')
    return values['ONSHAPE_CLIENT_ID'], values['ONSHAPE_CLIENT_SECRET'], base


def protect(data, decrypt=False):
    """Windows user-bound DPAPI; never fall back to plaintext token storage."""
    if os.name != 'nt':
        raise ProbeError('This authentication probe requires Windows DPAPI.')

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    incoming = Blob(len(data), buffer)
    outgoing = Blob()
    library = ctypes.WinDLL('crypt32', use_last_error=True)
    function = library.CryptUnprotectData if decrypt else library.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ProbeError('Windows could not protect or read the stored credentials.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel.LocalFree(outgoing.data)


class Probe:
    def __init__(self, client_id, client_secret, base, token_file, transport=request_json):
        self.client_id, self.client_secret, self.base = client_id, client_secret, base
        self.token_file = Path(token_file)
        self.transport = transport
        self.pending = {}
        self.lock = threading.RLock()

    def authorize(self):
        with self.lock:
            now = time.monotonic()
            self.pending = {key: expiry for key, expiry in self.pending.items() if expiry > now}
            if len(self.pending) >= 8:
                raise ProbeError('Too many pending sign-ins. Wait five minutes and retry.')
            state = secrets.token_urlsafe(32)
            self.pending[state] = now + 300
        return AUTHORIZE_URL + '?' + urlencode({
            'response_type': 'code', 'client_id': self.client_id,
            'redirect_uri': CALLBACK, 'scope': 'OAuth2Read', 'state': state})

    def complete(self, query):
        state = query.get('state', [])
        if len(state) != 1:
            raise ProbeError('Missing or duplicated OAuth state.')
        with self.lock:
            expiry = self.pending.pop(state[0], 0)
        if expiry <= time.monotonic():
            raise ProbeError('Invalid, expired, or already used OAuth state. Start sign-in again.')
        if 'error' in query:
            raise ProbeError('Onshape authorization was declined. Existing credentials retained.')
        code = query.get('code', [])
        if len(code) != 1 or not code[0] or len(code[0]) > 16384:
            raise ProbeError('Missing or invalid authorization code.')
        with self.lock:
            tokens = self.transport(TOKEN_URL, fields={
                'grant_type': 'authorization_code', 'code': code[0],
                'client_id': self.client_id, 'client_secret': self.client_secret, 'redirect_uri': CALLBACK})
            self.verify_and_save(tokens)

    def verify_and_save(self, tokens):
        if not isinstance(tokens, dict) or any(not isinstance(tokens.get(k), str) or not tokens[k]
                                              for k in ('access_token', 'refresh_token')):
            raise ProbeError('Onshape returned an incomplete token response.')
        if not isinstance(tokens.get('expires_in'), (int, float)) or not 0 < tokens['expires_in'] <= 86400:
            raise ProbeError('Onshape returned an invalid token lifetime.')
        # A real read verifies the grant. Do not print document names or response data.
        result = self.transport(self.base + '/api/v16/documents?limit=1', token=tokens['access_token'])
        if not isinstance(result, dict) or not isinstance(result.get('items'), list):
            raise ProbeError('Unexpected document-list response. Credentials were not saved.')
        envelope = {'client_id': self.client_id, 'base_url': self.base,
                    'access_token': tokens['access_token'], 'refresh_token': tokens['refresh_token'],
                    'expires_at': time.time() + tokens['expires_in']}
        encrypted = protect(json.dumps(envelope).encode())
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.token_file.with_suffix('.tmp')
        try:
            temporary.write_bytes(encrypted)
            temporary.replace(self.token_file)
        finally:
            temporary.unlink(missing_ok=True)

    def refresh(self):
        with self.lock:
            if not self.token_file.exists():
                raise ProbeError('Connect to Onshape first.')
            stored = json.loads(protect(self.token_file.read_bytes(), decrypt=True))
            if stored.get('client_id') != self.client_id or stored.get('base_url') != self.base:
                raise ProbeError('Stored credentials belong to a different application or Onshape host.')
            tokens = self.transport(TOKEN_URL, fields={
                'grant_type': 'refresh_token', 'refresh_token': stored['refresh_token'],
                'client_id': self.client_id, 'client_secret': self.client_secret})
            self.verify_and_save(tokens)


def handler_for(probe):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # OAuth callback URLs contain a one-time code.

        def send(self, status, text, location=None):
            body = text.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            # Same-origin form POSTs need their Origin header for the CSRF check.
            # Never send callback paths or codes to an external site as a referrer.
            self.send_header('Referrer-Policy', 'same-origin')
            # Chromium also checks form-action on the OAuth redirect chain.
            self.send_header('Content-Security-Policy', "default-src 'none'; form-action 'self' https://*.onshape.com; frame-ancestors 'none'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            if location:
                self.send_header('Location', location)
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get_all('Host') == ['localhost:8766']

        def do_GET(self):
            if not self.valid_host():
                self.send(403, 'Invalid host.')
                return
            url = urlsplit(self.path)
            if url.path == '/':
                self.send(200, '<!doctype html><title>Onshape Slicer Link authentication</title>'
                          '<h1>Onshape Slicer Link</h1><p>Private-app authentication probe.</p>'
                          '<form method="post" action="/connect"><button>Connect to Onshape</button></form>'
                          '<form method="post" action="/refresh"><button>Verify token refresh</button></form>'
                          '<p>This probe does not change geometry, slice, or print.</p>')
            elif url.path == '/oauth/callback':
                try:
                    probe.complete(parse_qs(url.query, keep_blank_values=True, max_num_fields=10))
                    self.send(200, 'Connected. Document read succeeded; tokens stored with Windows encryption. '
                              '<a href="/">Return to verify refresh</a>')
                except (ProbeError, ValueError) as error:
                    # Only controlled messages go to the browser, never provider response bodies.
                    import html
                    message = str(error) if isinstance(error, ProbeError) else 'Invalid callback.'
                    self.send(400, html.escape(message))
            else:
                self.send(404, 'Not found.')

        def do_POST(self):
            if not self.valid_host() or self.headers.get_all('Origin') != [ORIGIN]:
                self.send(403, 'Use the form on the local authentication page.')
                return
            try:
                if self.path == '/connect':
                    self.send(303, '', location=probe.authorize())
                elif self.path == '/refresh':
                    probe.refresh()
                    self.send(200, 'Token refresh and document read succeeded. <a href="/">Return</a>')
                else:
                    self.send(404, 'Not found.')
            except ProbeError as error:
                import html
                self.send(400, html.escape(str(error)))
    return Handler


def main():
    try:
        client_id, client_secret, base = read_config(ROOT / '.env')
        probe = Probe(client_id, client_secret, base, ROOT / 'artifacts/onshape/tokens.dpapi')
        server = ThreadingHTTPServer(('127.0.0.1', 8766), handler_for(probe))
        print(f'Authentication probe ready: {ORIGIN}', flush=True)
        print('Open that address and choose Connect to Onshape. Ctrl+C stops the probe.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    except (ProbeError, OSError) as error:
        print(f'Cannot start authentication probe: {error}')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
