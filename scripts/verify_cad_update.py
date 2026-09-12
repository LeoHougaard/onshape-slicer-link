# SPDX-License-Identifier: AGPL-3.0-only
"""Compare projects saved by the native GUI during the real-CAD experiment."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'


def read_project(path):
    with zipfile.ZipFile(path) as archive:
        assert not any(n.endswith(('.gcode', '.bgcode')) for n in archive.namelist()), 'Unexpected toolpaths'
        root = ET.fromstring(archive.read('3D/3dmodel.model'))
        items = root.findall(f'{CORE}build/{CORE}item')
        components = root.findall(f'.//{CORE}component')
        assert len(items) == len(components) == 1
        transforms = [[float(v) for v in node.attrib['transform'].split()] for node in (items[0], components[0])]
        config = ET.fromstring(archive.read('Metadata/model_settings.config'))
        objects = config.findall('object')
        assert len(objects) == 1
        metadata = {n.attrib['key']: n.attrib['value'] for n in objects[0].findall('metadata') if 'key' in n.attrib}
        link = json.loads(bytes.fromhex(metadata.pop('onshape_slicer_link')))
        plates = []
        for plate in config.findall('plate'):
            plate_id = plate.find("metadata[@key='plater_id']").attrib['value']
            for instance in plate.findall('model_instance'):
                plates.append((plate_id, instance.find("metadata[@key='object_id']").attrib['value'],
                               instance.find("metadata[@key='instance_id']").attrib['value']))
        meshes = []
        for name in archive.namelist():
            if name.endswith('.model'):
                meshes.extend(ET.fromstring(archive.read(name)).findall(f'.//{CORE}mesh'))
        assert len(meshes) == 1
        vertices = [tuple(float(n.attrib[a]) for a in 'xyz') for n in meshes[0].findall(f'{CORE}vertices/{CORE}vertex')]
        triangles = [tuple(int(n.attrib[a]) for a in ('v1', 'v2', 'v3')) for n in meshes[0].findall(f'{CORE}triangles/{CORE}triangle')]
        process = json.loads(archive.read('Metadata/project_settings.config'))
    assert all(math.isfinite(v) for row in transforms + vertices for v in row)
    return dict(link=link, settings=metadata, plates=plates, transforms=transforms,
                vertices=vertices, triangles=triangles, process=process)


def geometry(project):
    # Compare triangle coordinates, independent of vertex numbering and face order.
    vertices = [tuple(round(x, 5) for x in p) for p in project['vertices']]
    return sorted(tuple(sorted(vertices[i] for i in face)) for face in project['triangles'])


def world(point, transforms):
    for t in reversed(transforms):
        point = tuple(sum(t[3 * j + i] * point[j] for j in range(3)) + t[9 + i] for i in range(3))
    return point


def verify(target, include_revert, bridge=False):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'artifacts' / target / 'results'
    prefix = 'bridge' if bridge else 'onshape'
    before = read_project(directory / ('bridge-before.3mf' if bridge else 'onshape-before-update.3mf'))
    updated = read_project(directory / (prefix + '-updated.3mf'))
    snapshot_file = 'artifacts/onshape/export-test/bridge-live-snapshot.json' if bridge else 'artifacts/onshape/linked-part/current.json'
    snapshot = json.loads((root / snapshot_file).read_text())
    if bridge:
        assert not Path(before['link']['path']).exists(), 'This bridge test requires an absent legacy snapshot'
    expected = dict(vertices=[tuple(p[i] - before['link']['frame'][i] for i in range(3)) for p in snapshot['vertices']],
                    triangles=snapshot['triangles'])
    assert geometry(updated) == geometry(expected), 'Updated mesh differs from validated CAD snapshot'
    assert geometry(before) != geometry(updated), 'Geometry did not change'
    assert updated['link']['revision'] == snapshot['revision'] != before['link']['revision']
    assert updated['link']['previous']['revision'] == before['link']['revision']
    previous = updated['link']['previous']
    assert geometry(previous) == geometry(before), 'Previous geometry was not retained'
    stages = [updated]
    if include_revert:
        reverted = read_project(directory / (prefix + '-reverted.3mf'))
        assert geometry(reverted) == geometry(before), 'Revert did not restore the initial mesh'
        assert reverted['link']['revision'] == before['link']['revision']
        assert reverted['link']['previous'] is None
        assert reverted['link']['automatic_updates_paused'] is True
        stages.append(reverted)
    for project in stages:
        assert project['link']['source_id'] == before['link']['source_id'] == snapshot['source_id']
        assert project['link']['frame'] == before['link']['frame']
        assert project['plates'] == before['plates'], 'Plate membership changed'
        assert project['settings'] == before['settings'], 'Object settings changed'
        for old, new in zip(before['transforms'], project['transforms']):
            assert max(abs(a - b) for a, b in zip(old, new)) < 1e-8, 'Transform changed'
        for key in ('filament_type', 'filament_settings_id', 'filament_colour'):
            assert project['process'].get(key) == before['process'].get(key), key
    common = set(before['vertices']) & set(updated['vertices'])
    assert common, 'No unchanged reference vertices'
    drift = max(math.dist(world(p, before['transforms']), world(p, updated['transforms'])) for p in common)
    assert drift < 1e-5, 'Unchanged geometry shifted in world coordinates'
    report = dict(status='PASS', slicer=target, source_id=snapshot['source_id'],
                  from_revision=before['link']['revision'], to_revision=updated['link']['revision'],
                  settings=before['settings'], plate_membership=before['plates'],
                  instance_transform=before['transforms'][0], unchanged_reference_vertices=len(common),
                  max_reference_drift_mm=drift, geometry_matches_export=True,
                  previous_geometry_retained=True, revert_verified=include_revert,
                  legacy_snapshot_missing=bridge,
                  toolpaths_in_saved_projects=False,
                  scope='Saved native GUI results. Test placement/settings were seeded in an isolated 3MF; plate moves were not repeated here.')
    output = root / 'artifacts/onshape/export-test' / (target + ('-bridge-results.json' if bridge else '-cad-update-results.json'))
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=['orca', 'bambu'])
    parser.add_argument('--include-revert', action='store_true')
    parser.add_argument('--bridge', action='store_true', help='Check native companion requests with a missing legacy snapshot.')
    args = parser.parse_args()
    verify(args.target, args.include_revert, args.bridge)
