# SPDX-License-Identifier: AGPL-3.0-only
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit
from http.server import ThreadingHTTPServer

from companion.auth_probe import Probe, ProbeError, protect, handler_for, CALLBACK


class AuthProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.token_file = Path(self.directory.name) / 'tokens.dpapi'
        self.calls = []
        self.fail = False
        self.serial = 0

        def transport(url, fields=None, token=None):
            self.calls.append((url, fields, token))
            if self.fail:
                raise ProbeError('Simulated network failure.')
            if fields is None:
                return {'items': []}
            self.serial += 1
            return {'access_token': f'test-access-{self.serial}',
                    'refresh_token': f'test-refresh-{self.serial}', 'expires_in': 3600}

        self.probe = Probe('test-client', 'test-secret', 'https://cad.onshape.com', self.token_file, transport)

    def sign_in(self):
        query = parse_qs(urlsplit(self.probe.authorize()).query)
        self.assertEqual(query['redirect_uri'], [CALLBACK])
        self.probe.complete({'state': query['state'], 'code': ['test-code']})
        return query['state']

    def test_exchange_refresh_and_windows_encryption(self):
        self.sign_in()
        encrypted = self.token_file.read_bytes()
        self.assertNotIn(b'test-access', encrypted)
        stored = json.loads(protect(encrypted, decrypt=True))
        self.assertEqual(stored['refresh_token'], 'test-refresh-1')
        self.probe.refresh()
        self.assertEqual(self.calls[2][1]['refresh_token'], 'test-refresh-1')
        self.assertEqual(json.loads(protect(self.token_file.read_bytes(), decrypt=True))['refresh_token'], 'test-refresh-2')

    def test_replayed_and_unknown_state_never_exchange_tokens(self):
        state = self.sign_in()
        count = len(self.calls)
        for candidate in (state, ['unknown'], []):
            with self.assertRaises(ProbeError):
                self.probe.complete({'state': candidate, 'code': ['test-code']})
        self.assertEqual(len(self.calls), count)

    def test_failed_refresh_preserves_existing_credentials(self):
        self.sign_in()
        before = self.token_file.read_bytes()
        self.fail = True
        with self.assertRaises(ProbeError):
            self.probe.refresh()
        self.assertEqual(self.token_file.read_bytes(), before)

    def test_local_http_rejects_foreign_host_and_cross_site_posts(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.probe))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for host, origin in [('attacker.example', 'http://localhost:8766'),
                                 ('localhost:8766', 'https://attacker.example')]:
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
                connection.request('POST', '/connect', body='', headers={'Host': host, 'Origin': origin})
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.close()
            self.assertFalse(self.probe.pending)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_local_form_can_start_official_oauth_redirect(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.probe))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            connection.request('GET', '/', headers={'Host': 'localhost:8766'})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Referrer-Policy'), 'same-origin')
            self.assertIn('https://*.onshape.com', response.getheader('Content-Security-Policy'))
            response.read()
            connection.close()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            connection.request('POST', '/connect', body='', headers={
                'Host': 'localhost:8766', 'Origin': 'http://localhost:8766'})
            response = connection.getresponse()
            self.assertEqual(response.status, 303)
            target = urlsplit(response.getheader('Location'))
            self.assertEqual((target.scheme, target.netloc, target.path),
                             ('https', 'oauth.onshape.com', '/oauth/authorize'))
            self.assertEqual(parse_qs(target.query)['redirect_uri'], [CALLBACK])
            response.read()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
