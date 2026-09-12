# SPDX-License-Identifier: AGPL-3.0-only
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from companion.auth_probe import Probe, ProbeError, protect
from companion.export_part import source_identity
from companion.server import Updates, Busy, CompanionServer, bridge_handler


def source(part='part-a'):
    return source_identity(dict(base_url='https://cad.onshape.com', document_id='a' * 24,
                                workspace_id='b' * 24, element_id='c' * 24, configuration='',
                                initial_microversion='d' * 24, initial_part_id=part))


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.refreshes = []

        def auth(url, fields=None, token=None):
            if fields is None:
                return {'items': []}
            self.refreshes.append(fields)
            return dict(access_token='fresh-test-access', refresh_token='fresh-test-refresh', expires_in=3600)

        self.probe = Probe('test-client', 'test-secret', 'https://cad.onshape.com', self.root / 'tokens.dpapi', auth)
        self.save_token()
        self.calls = []
        self.fail_source = None
        outer = self

        class Client:
            def __init__(self, base, token):
                outer.last_token = token

            def update(self, previous):
                identity = previous['source_id']
                outer.calls.append(identity)
                if identity == outer.fail_source:
                    raise ProbeError('Simulated network/export failure.')
                # Mesh validity is the tested export client's responsibility.
                snapshot = dict(schema=1, source_id=identity, revision='e' * 24, vertices=[], triangles=[])
                return snapshot, b'simulated-stl', {'status': 'passed'}

        self.service = Updates(self.probe, self.root / 'cache', Client)

    def save_token(self, expiry=None, client='test-client'):
        self.probe.token_file.write_bytes(protect(json.dumps(dict(
            client_id=client, base_url='https://cad.onshape.com', access_token='test-access',
            refresh_token='test-refresh', expires_at=expiry or time.time() + 3600)).encode()))

    def test_batch_response_and_cache_need_no_caller_paths(self):
        response = json.loads(self.service.update(dict(schema=1, sources=[source(), source('b')])))
        self.assertEqual([s['source_id'] for s in response['snapshots']], [source(), source('b')])
        self.assertEqual(len(list((self.root / 'cache').glob('*/current.json'))), 2)
        self.assertNotIn('test-access', json.dumps(response))
        self.assertFalse(self.refreshes)

    def test_failed_batch_returns_no_partial_success_or_stale_cache(self):
        self.service.update(dict(schema=1, sources=[source()]))
        before = {p: p.read_bytes() for p in (self.root / 'cache').rglob('*') if p.is_file()}
        self.fail_source = source('missing')
        with self.assertRaisesRegex(ProbeError, 'failure'):
            self.service.update(dict(schema=1, sources=[source(), self.fail_source]))
        self.assertEqual(before, {p: p.read_bytes() for p in (self.root / 'cache').rglob('*') if p.is_file()})

    def test_expiring_token_refreshes_and_wrong_account_is_rejected(self):
        self.save_token(time.time() + 10)
        self.service.update(dict(schema=1, sources=[source()]))
        self.assertEqual(len(self.refreshes), 1)
        self.assertEqual(self.last_token, 'fresh-test-access')
        self.save_token(client='different-client')
        self.calls.clear()
        with self.assertRaises(ProbeError):
            self.service.update(dict(schema=1, sources=[source()]))
        self.assertEqual(self.calls, [])

    def test_failed_refresh_preserves_tokens_and_does_not_export(self):
        self.save_token(time.time() + 10)
        before = self.probe.token_file.read_bytes()
        def fail(*args, **kwargs):
            raise ProbeError('Refresh failed.')
        self.probe.transport = fail
        with self.assertRaises(ProbeError):
            self.service.update(dict(schema=1, sources=[source()]))
        self.assertEqual(self.probe.token_file.read_bytes(), before)
        self.assertEqual(self.calls, [])

    def test_invalid_batches_and_concurrent_updates_never_export(self):
        for sources in ([], [source()] * 2, [source(str(i)) for i in range(17)], ['local:part'], [42]):
            with self.assertRaises(ProbeError):
                self.service.update(dict(schema=1, sources=sources))
        self.service.lock.acquire()
        try:
            with self.assertRaises(Busy):
                self.service.update(dict(schema=1, sources=[source()]))
        finally:
            self.service.lock.release()
        self.assertFalse(self.calls)

    def test_http_rejects_browser_foreign_host_bad_key_and_oversize(self):
        key = 'a' * 64
        server = ThreadingHTTPServer(('127.0.0.1', 0), bridge_handler(self.probe, self.service, key))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def post(extra=None, body=None):
            headers = {'Host': 'localhost:8766', 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
            headers.update(extra or {})
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            try:
                conn.request('POST', '/v1/update', body or json.dumps(dict(schema=1, sources=[source()])), headers)
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()
        for extra in ({'Origin': 'http://localhost:8766'}, {'Host': 'attacker.example'},
                      {'Authorization': 'Bearer wrong'}):
            self.assertEqual(post(extra)[0], 403)
        self.assertEqual(post({'Content-Length': str(129 * 1024)})[0], 400)
        self.assertFalse(self.calls)
        self.assertEqual(post()[0], 200)
        self.fail_source = source()
        status, body = post()
        self.assertEqual(status, 400)
        self.assertIn('failure', json.loads(body)['error'])
        self.assertNotIn(b'test-access', body)

    def test_companion_port_has_one_owner(self):
        handler = bridge_handler(self.probe, self.service, 'a' * 64)
        with CompanionServer(('127.0.0.1', 0), handler) as first:
            with self.assertRaises(OSError):
                CompanionServer(first.server_address, handler)


if __name__ == '__main__':
    unittest.main()
