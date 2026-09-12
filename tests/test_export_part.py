# SPDX-License-Identifier: AGPL-3.0-only
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode

from companion.auth_probe import ProbeError
from companion.export_part import (Client, decode_source, parse_binary_stl, parse_studio_url,
                                   publish, resolve_translation, source_identity)
from scripts.make_fixtures import mesh, stl


SOURCE = {'base_url': 'https://cad.onshape.com', 'document_id': 'a'*24,
          'workspace_id': 'b'*24, 'element_id': 'c'*24, 'configuration': '',
          'initial_microversion': 'd'*24, 'initial_part_id': 'JHD'}
URL = f"https://cad.onshape.com/documents/{'a'*24}/w/{'b'*24}/e/{'c'*24}"


class ExportPartTests(unittest.TestCase):
    def test_binary_mesh_keeps_source_coordinates_and_millimeters(self):
        vertices, faces = mesh(32)
        shifted = [(x-25, y-12.5, z-7.5) for x, y, z in vertices]
        parsed, metrics = parse_binary_stl(stl(shifted, faces))
        self.assertEqual(metrics['bounds_mm'], [[-25, -12.5, -7.5], [7, 11.5, -1.5]])
        self.assertAlmostEqual(metrics['volume_mm3'], 2688)
        self.assertEqual(set(map(tuple, parsed['vertices'])), set(shifted))

    def test_rejects_truncated_open_nonfinite_and_reversed_meshes(self):
        vertices, faces = mesh(32)
        good = stl(vertices, faces)
        nonfinite = bytearray(good)
        struct.pack_into('<f', nonfinite, 96, float('nan'))
        for data in (good[:-1], stl(vertices, faces[:-1]), bytes(nonfinite),
                     stl(vertices, [(a, c, b) for a, b, c in faces])):
            with self.assertRaises(ProbeError):
                parse_binary_stl(data)

    def test_source_identity_survives_name_changes_and_requires_workspace(self):
        identity = source_identity(SOURCE)
        self.assertEqual(decode_source({'source_id': identity, 'display_name': 'renamed'}), SOURCE)
        self.assertEqual(parse_studio_url(URL)['element_id'], 'c'*24)
        for url in [URL.replace('/w/', '/v/'), URL.replace('cad.onshape.com', 'attacker.example'),
                    URL + '?configuration=size%3D5']:
            with self.assertRaises(ProbeError):
                parse_studio_url(url)

    def test_translation_requires_one_resolved_part_at_exact_snapshot(self):
        response = {'documentId': 'a'*24, 'elementId': 'c'*24,
                    'sourceDocumentMicroversion': 'd'*24, 'targetDocumentMicroversion': 'e'*24,
                    'ids': [{'source': 'JHD', 'status': 'OK', 'target': ['NEW_ID']}]}
        self.assertEqual(resolve_translation(response, SOURCE, 'e'*24), 'NEW_ID')
        for status, targets in [('SPLIT', ['A', 'B']), ('TRANSLATION_ERROR', []), ('OK', ['A', 'B'])]:
            bad = {**response, 'ids': [{'source': 'JHD', 'status': status, 'target': targets}]}
            with self.assertRaises(ProbeError):
                resolve_translation(bad, SOURCE, 'e'*24)
        with self.assertRaises(ProbeError):
            resolve_translation(response, SOURCE, 'f'*24)

    def test_export_redirect_is_checked_before_forwarding_credentials(self):
        query = {'documentId': 'a'*24, 'elementId': 'c'*24, 'microversion': 'd'*24,
                 'partIds': 'JHD', 'units': 'millimeter', 'scale': '1.0', 'mode': 'binary'}
        valid = 'https://cad-usw2.onshape.com/modelexport?' + urlencode(query)

        class Response(io.BytesIO):
            status = 200

        class Opener:
            def __init__(self, location):
                self.location, self.requests = location, []

            def open(self, request, timeout):
                self.requests.append(request)
                if len(self.requests) == 1:
                    raise HTTPError(request.full_url, 307, 'Redirect', {'Location': self.location}, io.BytesIO())
                return Response(b'test-export')

        for location in [valid.replace('cad-usw2.onshape.com', 'attacker.example'),
                         valid.replace('https:', 'http:'), valid.replace('microversion='+'d'*24, 'microversion='+'e'*24),
                         valid.replace('scale=1.0', 'scale=2')]:
            opener = Opener(location)
            with self.assertRaises(ProbeError):
                Client(SOURCE['base_url'], 'test-token', opener).request('/api/v16/test', binary=True,
                    source=SOURCE, microversion='d'*24, part_id='JHD')
            self.assertEqual(len(opener.requests), 1)
        opener = Opener(valid)
        result = Client(SOURCE['base_url'], 'test-token', opener).request('/api/v16/test', binary=True,
            source=SOURCE, microversion='d'*24, part_id='JHD')
        self.assertEqual(result, b'test-export')
        self.assertEqual(opener.requests[1].get_header('Authorization'), 'Bearer test-token')

    def test_capture_pins_every_geometry_request_before_workspace_can_change(self):
        calls = []
        class FakeClient(Client):
            def request(self, path, body=None, **kwargs):
                calls.append(path)
                if path.endswith('/currentmicroversion'):
                    return {'microversion': 'd'*24}
                self_test.assertIn('/m/'+'d'*24, path)
                if '/elements?' in path:
                    return [{'id': 'c'*24, 'elementType': 'PARTSTUDIO'}]
                if path.endswith('/configuration'):
                    return {'sourceMicroversion': 'd'*24, 'configurationParameters': [], 'currentConfiguration': []}
                if path.endswith('/boundingboxes'):
                    return dict(lowX=0, lowY=0, lowZ=0, highX=.032, highY=.024, highZ=.006)
                if '/stl?' in path:
                    return stl(*mesh(32))
                return [{'partId': 'JHD', 'name': 'Same name', 'bodyType': 'solid'}]
        self_test = self
        snapshot, data, report = FakeClient(SOURCE['base_url'], 'unused').capture(URL)
        self.assertEqual(snapshot['revision'], 'd'*24)
        self.assertEqual(decode_source(snapshot), SOURCE)
        self.assertEqual(report['bounds_error_mm'], 0)
        self.assertEqual(sum('/w/' in path for path in calls), 1)

    def test_failed_publish_retains_active_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            active = Path(directory) / 'current.json'
            active.write_bytes(b'previous snapshot')
            with patch.object(Path, 'write_bytes', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    publish(directory, {'schema': 1}, b'stl', {'status': 'passed'})
            self.assertEqual(active.read_bytes(), b'previous snapshot')


if __name__ == '__main__':
    unittest.main()
