"""Export an unconfigured Onshape solid from an immutable microversion.

This experiment writes a validated local snapshot. It never modifies CAD,
contacts a slicer, slices, or prints.
SPDX-License-Identifier: AGPL-3.0-only
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener

from companion.auth_probe import ROOT, NoRedirect, ProbeError, protect, read_config

MAX_DOWNLOAD = 32 * 1024 * 1024
MAX_SNAPSHOT = 8 * 1024 * 1024
SOURCE_PREFIX = 'onshape-v1:'


def require(condition, message):
    if not condition:
        raise ProbeError(message)


def parse_studio_url(url):
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.netloc == 'cad.onshape.com',
            'This export experiment accepts cad.onshape.com URLs only.')
    match = re.fullmatch(r'/documents/([a-f0-9]{24})/w/([a-f0-9]{24})/e/([a-f0-9]{24})/?', parsed.path)
    require(match is not None, 'Paste a workspace Part Studio URL.')
    require(not parse_qs(parsed.query).get('configuration'),
            'Configured parts are not supported by this first export experiment.')
    return dict(zip(('document_id', 'workspace_id', 'element_id'), match.groups()))


def source_identity(source):
    # The existing native builds persist this string in each object's 3MF metadata.
    # Embed the immutable selection anchor so identity survives loss of the cache.
    return SOURCE_PREFIX + json.dumps(source, sort_keys=True, separators=(',', ':'))


def decode_source(snapshot):
    identity = snapshot.get('source_id', '')
    require(isinstance(identity, str) and identity.startswith(SOURCE_PREFIX), 'Not an Onshape-linked snapshot.')
    source = json.loads(identity[len(SOURCE_PREFIX):])
    require(set(source) == {'base_url', 'document_id', 'workspace_id', 'element_id',
                            'configuration', 'initial_microversion', 'initial_part_id'}, 'Invalid source identity.')
    require(source['base_url'] == 'https://cad.onshape.com' and source['configuration'] == '',
            'Unsupported source host or configuration.')
    for key in ('document_id', 'workspace_id', 'element_id', 'initial_microversion'):
        require(isinstance(source[key], str) and re.fullmatch('[a-f0-9]{24}', source[key]), 'Invalid source identifier.')
    require(isinstance(source['initial_part_id'], str) and 0 < len(source['initial_part_id']) <= 4096,
            'Invalid source part identifier.')
    return source


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def parse_binary_stl(data):
    require(84 <= len(data) <= MAX_DOWNLOAD, 'Invalid STL size.')
    count = struct.unpack_from('<I', data, 80)[0]
    require(4 <= count <= 200000 and len(data) == 84 + count * 50, 'Truncated, oversized, or non-binary STL.')
    vertices, triangles, lookup, edges = [], [], {}, Counter()
    volume6 = 0.0
    for normal_x, normal_y, normal_z, ax, ay, az, bx, by, bz, cx, cy, cz, attribute in struct.iter_unpack('<12fH', data[84:]):
        face = []
        for vertex in ((ax, ay, az), (bx, by, bz), (cx, cy, cz)):
            require(all(math.isfinite(x) and abs(x) <= 10000 for x in vertex), 'Invalid vertex coordinate.')
            if vertex not in lookup:
                lookup[vertex] = len(vertices)
                vertices.append(vertex)
                require(len(vertices) <= 100000, 'Mesh exceeds the native vertex limit.')
            face.append(lookup[vertex])
        a, b, c = (vertices[i] for i in face)
        area = cross(tuple(b[i]-a[i] for i in range(3)), tuple(c[i]-a[i] for i in range(3)))
        require(sum(x*x for x in area) > 1e-12, 'Degenerate triangle.')
        volume6 += sum(x*y for x, y in zip(a, cross(b, c)))
        for i in range(3):
            edges[face[i], face[(i+1) % 3]] += 1
        triangles.append(face)
    require(all(n == 1 and edges[b, a] == 1 for (a, b), n in edges.items()),
            'Mesh is not closed and consistently oriented.')
    require(math.isfinite(volume6) and volume6 > 1e-6, 'Mesh has no positive volume.')
    bounds = [[min(v[i] for v in vertices) for i in range(3)],
              [max(v[i] for v in vertices) for i in range(3)]]
    return {'vertices': vertices, 'triangles': triangles}, {'bounds_mm': bounds, 'volume_mm3': volume6 / 6}


def resolve_translation(result, source, target):
    require(result.get('documentId') == source['document_id'] and
            result.get('elementId') == source['element_id'] and
            result.get('sourceDocumentMicroversion') == source['initial_microversion'] and
            result.get('targetDocumentMicroversion') == target, 'ID translation returned a different source snapshot.')
    ids = result.get('ids')
    require(isinstance(ids, list) and len(ids) == 1, 'Ambiguous ID translation response.')
    item = ids[0]
    require(item.get('source') == source['initial_part_id'] and item.get('status') == 'OK' and
            isinstance(item.get('target'), list) and len(item['target']) == 1 and
            isinstance(item['target'][0], str) and bool(item['target'][0]),
            'Broken link: source part is missing, split, or ambiguous. Existing snapshot retained.')
    return item['target'][0]


class Client:
    def __init__(self, base, token, opener=None):
        require(base == 'https://cad.onshape.com', 'Only the configured cad.onshape.com test account is supported.')
        self.base, self.token = base, token
        self.opener = opener or build_opener(NoRedirect)

    def request(self, path, body=None, binary=False, source=None, microversion=None, part_id=None):
        require(path.startswith('/api/v16/'), 'Invalid API path.')
        url = self.base + path
        payload = None if body is None else json.dumps(body).encode()
        headers = {'Authorization': 'Bearer ' + self.token,
                   'Accept': 'application/octet-stream' if binary else 'application/json'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        for attempt in range(3):
            try:
                with self.opener.open(Request(url, data=payload, headers=headers), timeout=45) as response:
                    require(response.status == 200, 'Unexpected Onshape response status.')
                    limit = MAX_DOWNLOAD if binary else 2 * 1024 * 1024
                    data = response.read(limit + 1)
                    require(len(data) <= limit, 'Onshape response exceeded the experiment limit.')
                    return data if binary else json.loads(data)
            except HTTPError as error:
                error.close()
                if not binary or error.code != 307:
                    raise ProbeError(f'Onshape returned HTTP {error.code}. Existing snapshot retained.') from None
                target = urljoin(url, error.headers.get('Location', ''))
                parsed = urlsplit(target)
                require(parsed.scheme == 'https' and parsed.username is None and parsed.password is None and
                        parsed.port in (None, 443) and parsed.hostname is not None and
                        re.fullmatch(r'cad(?:-[a-z0-9]+)?\.onshape\.com', parsed.hostname) and
                        parsed.path == '/modelexport' and not parsed.fragment,
                        'Rejected an unexpected export redirect.')
                query = parse_qs(parsed.query, keep_blank_values=True)
                for key, expected in {'documentId': source['document_id'], 'elementId': source['element_id'],
                                      'microversion': microversion, 'partIds': part_id,
                                      'units': 'millimeter', 'mode': 'binary'}.items():
                    require(query.get(key) == [expected], 'Export redirect changed the requested source or units.')
                require(len(query.get('scale', [])) == 1 and float(query['scale'][0]) == 1.0,
                        'Export redirect changed the requested scale.')
                url = target
            except (URLError, TimeoutError, OSError):
                raise ProbeError('Onshape request failed. Existing snapshot retained.') from None
        raise ProbeError('Too many export redirects. Existing snapshot retained.')

    def microversion(self, source):
        result = self.request(f"/api/v16/documents/d/{source['document_id']}/w/{source['workspace_id']}/currentmicroversion")
        value = result.get('microversion')
        require(isinstance(value, str) and re.fullmatch('[a-f0-9]{24}', value), 'Invalid microversion response.')
        return value

    def studio_parts(self, source, microversion):
        did, eid = source['document_id'], source['element_id']
        tabs = self.request(f'/api/v16/documents/d/{did}/m/{microversion}/elements?elementId={eid}')
        matches = [t for t in tabs if t.get('id') == eid]
        require(len(matches) == 1 and matches[0].get('elementType') == 'PARTSTUDIO', 'Source is not a Part Studio.')
        config = self.request(f'/api/v16/partstudios/d/{did}/m/{microversion}/e/{eid}/configuration')
        require(config.get('sourceMicroversion') == microversion and not config.get('microversionSkew'),
                'Configuration response does not match the snapshot.')
        require(config.get('configurationParameters') == [] and config.get('currentConfiguration') == [],
                'Configured parts are not supported by this first export experiment.')
        parts = self.request(f'/api/v16/parts/d/{did}/m/{microversion}/e/{eid}')
        require(isinstance(parts, list), 'Invalid part-list response.')
        return parts

    def capture(self, studio_url, part_id=None):
        source = parse_studio_url(studio_url)
        microversion = self.microversion(source)
        parts = self.studio_parts(source, microversion)
        candidates = parts if part_id is None else [p for p in parts if p.get('partId') == part_id]
        require(len(candidates) == 1, 'Select exactly one part by ID; this Part Studio does not have a unique selection.')
        part = candidates[0]
        source.update(base_url=self.base, configuration='', initial_microversion=microversion, initial_part_id=part['partId'])
        return self.export(source, microversion, part)

    def update(self, previous):
        source = decode_source(previous)
        microversion = self.microversion(source)
        parts = self.studio_parts(source, microversion)
        path = f"/api/v16/partstudios/d/{source['document_id']}/m/{microversion}/e/{source['element_id']}/idtranslations"
        translated = self.request(path, {'sourceDocumentMicroversion': source['initial_microversion'],
                                         'sourceConfiguration': '', 'targetConfiguration': '',
                                         'ids': [source['initial_part_id']]})
        part_id = resolve_translation(translated, source, microversion)
        matches = [part for part in parts if part.get('partId') == part_id]
        require(len(matches) == 1, 'Broken link: translated part is missing or ambiguous.')
        return self.export(source, microversion, matches[0])

    def export(self, source, microversion, part):
        require(part.get('bodyType') == 'solid' and not part.get('isMesh') and not part.get('isComposite'),
                'This experiment exports a single native solid part only.')
        pid = quote(part['partId'], safe='')
        path = f"/api/v16/parts/d/{source['document_id']}/m/{microversion}/e/{source['element_id']}/partid/{pid}"
        bounds = self.request(path + '/boundingboxes')
        data = self.request(path + '/stl?' + urlencode({'mode': 'binary', 'grouping': 'false', 'scale': 1, 'units': 'millimeter'}),
                            binary=True, source=source, microversion=microversion, part_id=part['partId'])
        mesh, metrics = parse_binary_stl(data)
        expected = [[bounds[end + axis] * 1000 for axis in 'XYZ'] for end in ('low', 'high')]
        error = max(abs(expected[j][i] - metrics['bounds_mm'][j][i]) for i in range(3) for j in range(2))
        require(math.isfinite(error) and error <= 0.1, 'STL bounds differ from Onshape by more than 0.1 mm. Snapshot retained.')
        snapshot = {'schema': 1, 'source_id': source_identity(source), 'revision': microversion,
                    'source_part_id': part['partId'], 'display_name': part.get('name', ''),
                    'units': 'millimeter', 'stl_sha256': hashlib.sha256(data).hexdigest(), **mesh}
        report = {'status': 'passed', 'microversion': microversion, 'part_id': part['partId'],
                  'display_name': part.get('name', ''), 'vertices': len(mesh['vertices']),
                  'triangles': len(mesh['triangles']), 'bounds_error_mm': error, **metrics,
                  'checks': ['pinned microversion', 'single solid', 'unconfigured source',
                             'closed oriented mesh', 'positive volume', 'millimeter bounds', 'fixed CAD origin'],
                  'scope': 'export only; no slicer update or CAD modification'}
        return snapshot, data, report


def publish(output, snapshot, stl, report):
    payload = json.dumps(snapshot, separators=(',', ':'), allow_nan=False).encode()
    require(len(payload) <= MAX_SNAPSHOT, 'Snapshot exceeds the native integration limit.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Immutable files are written before the one active pointer. A failed request
    # never calls this function; a failed staging write leaves current.json intact.
    digest = hashlib.sha256(payload).hexdigest()
    (output / (digest + '.stl')).write_bytes(stl)
    (output / (digest + '.json')).write_bytes(payload)
    (output / (digest + '.report.json')).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output, prefix='.snapshot-', delete=False) as file:
            temporary = Path(file.name)
            file.write(payload)
        temporary.replace(output / 'current.json')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output / 'current.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--url', help='Workspace Part Studio URL; automatically selects only if there is one part.')
    selection.add_argument('--update', type=Path, help='Previous snapshot; translate its initial part ID to the current microversion.')
    parser.add_argument('--part-id', help='Explicit part ID from the selected snapshot, never a display name.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        client_id, _, base = read_config(ROOT / '.env')
        token = json.loads(protect((ROOT / 'artifacts/onshape/tokens.dpapi').read_bytes(), decrypt=True))
        require(token.get('client_id') == client_id and token.get('base_url') == base, 'Authenticate the configured test application first.')
        require(token.get('expires_at', 0) > time.time() + 60, 'Refresh the token on http://localhost:8766 before exporting.')
        client = Client(base, token['access_token'])
        if args.update:
            require(args.update.stat().st_size <= MAX_SNAPSHOT, 'Previous snapshot exceeds the size limit.')
            result = client.update(json.loads(args.update.read_text(encoding='utf-8')))
        else:
            result = client.capture(args.url, args.part_id)
        path = publish(args.output, *result)
        print(json.dumps(result[2], indent=2))
        print('Validated snapshot: ' + str(path.resolve()))
    except (ProbeError, OSError, ValueError, KeyError, TypeError) as error:
        print(str(error) if isinstance(error, ProbeError) else 'Export failed. Existing snapshot retained.')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
