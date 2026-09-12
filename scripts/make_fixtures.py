"""Generate two closed asymmetric prisms in one unchanged source frame.

SPDX-License-Identifier: AGPL-3.0-only
"""
import hashlib
import json
import math
from pathlib import Path
import struct


def mesh(length):
    # Counterclockwise L outline. Only the end of its lower arm grows.
    outline = [(0, 0), (length, 0), (length, 8), (12, 8), (12, 24), (0, 24)]
    vertices = [(x, y, z) for z in (0, 6) for x, y in outline]
    top = [(0, 1, 3), (1, 2, 3), (0, 3, 5), (3, 4, 5)]
    faces = [(c, b, a) for a, b, c in top]
    faces += [(a + 6, b + 6, c + 6) for a, b, c in top]
    for a in range(6):
        b = (a + 1) % 6
        faces.extend([(a, b, b + 6), (a, b + 6, a + 6)])
    return vertices, faces


def stl(vertices, faces):
    data = bytearray(b'Onshape Slicer Link local experiment'.ljust(80, b'\0'))
    data += struct.pack('<I', len(faces))
    for face in faces:
        a, b, c = [vertices[i] for i in face]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        norm = math.sqrt(sum(x*x for x in normal))
        data += struct.pack('<12fH', *(x/norm for x in normal), *a, *b, *c, 0)
    return bytes(data)


def main():
    root = Path(__file__).resolve().parents[1] / 'experiments' / 'fixtures'
    root.mkdir(parents=True, exist_ok=True)
    for revision, length in [('r1', 32), ('r2', 46)]:
        vertices, faces = mesh(length)
        content = stl(vertices, faces)
        (root / f'{revision}.stl').write_bytes(content)
        (root / f'{revision}.json').write_text(json.dumps({
            'schema': 1, 'source_id': 'local:asymmetric-part:configuration-default',
            'revision': revision, 'vertices': vertices, 'triangles': faces,
            'stl_sha256': hashlib.sha256(content).hexdigest(),
        }, indent=2) + '\n')
    (root / 'current.json').write_bytes((root / 'r1.json').read_bytes())
    (root / 'invalid.json').write_text('{"schema":1,"source_id":"wrong-source"}\n')


if __name__ == '__main__':
    main()
