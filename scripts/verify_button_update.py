# SPDX-License-Identifier: AGPL-3.0-only
"""Verify the saved two-plate results of clicking the native Update button."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from verify_cad_update import CORE, geometry, world


def read_objects(path):
    with zipfile.ZipFile(path) as z:
        assert not any(n.endswith(('.gcode', '.bgcode')) for n in z.namelist())
        root = ET.fromstring(z.read('3D/3dmodel.model'))
        config = ET.fromstring(z.read('Metadata/model_settings.config'))
        result = {}
        for item in root.findall(f'{CORE}build/{CORE}item'):
            oid = item.get('objectid')
            obj = config.find(f"object[@id='{oid}']")
            metadata = {n.get('key'): n.get('value') for n in obj.findall('metadata') if n.get('key')}
            link = json.loads(bytes.fromhex(metadata.pop('onshape_slicer_link')))
            component = root.find(f"{CORE}resources/{CORE}object[@id='{oid}']/{CORE}components/{CORE}component")
            model_path = component.get('{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path')
            mesh_root = ET.fromstring(z.read(model_path.lstrip('/'))) if model_path else root
            mesh = mesh_root.find(f"{CORE}resources/{CORE}object[@id='{component.get('objectid')}']/{CORE}mesh")
            vertices = [tuple(float(n.get(a)) for a in 'xyz') for n in mesh.findall(f'{CORE}vertices/{CORE}vertex')]
            triangles = [tuple(int(n.get(a)) for a in ('v1', 'v2', 'v3')) for n in mesh.findall(f'{CORE}triangles/{CORE}triangle')]
            plates = [p.find("metadata[@key='plater_id']").get('value') for p in config.findall('plate')
                      if p.find(f"model_instance/metadata[@key='object_id'][@value='{oid}']") is not None]
            result[metadata['name']] = dict(settings=metadata, link=link, plates=plates,
                transforms=[[float(v) for v in n.get('transform').split()] for n in (item, component)],
                vertices=vertices, triangles=triangles)
        return result


def verify(target):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'artifacts' / target / 'results'
    before = read_objects(directory / 'button-before.3mf')
    after = read_objects(directory / 'button-update.3mf')
    snapshot = json.loads((root / 'artifacts/onshape/export-test/button-live-snapshot.json').read_text())
    assert before.keys() == after.keys() and len(before) == 2
    assert sorted(p['plates'] for p in before.values()) == [['1'], ['2']]
    assert {p['settings']['wall_loops'] for p in before.values()} == {'4', '6'}
    reports = []
    for name, old in before.items():
        new = after[name]
        expected = dict(vertices=[tuple(p[i] - old['link']['frame'][i] for i in range(3)) for p in snapshot['vertices']], triangles=snapshot['triangles'])
        assert geometry(new) == geometry(expected) != geometry(old), name
        assert geometry(new['link']['previous']) == geometry(old)
        assert new['link']['revision'] == snapshot['revision'] != old['link']['revision']
        assert new['link']['source_id'] == old['link']['source_id'] == snapshot['source_id']
        for key in ('settings', 'plates', 'transforms'):
            assert new[key] == old[key], (name, key)
        common = set(old['vertices']) & set(new['vertices'])
        assert common
        drift = max(max(abs(a-b) for a,b in zip(world(p, old['transforms']), world(p, new['transforms']))) for p in common)
        assert drift < 1e-5
        reports.append(dict(name=name, plates=new['plates'], settings=new['settings'], max_reference_drift_mm=drift))
    dll = root / 'artifacts' / target / 'portable' / ('OrcaSlicer.dll' if target == 'orca' else 'BambuStudio.dll')
    report = dict(status='PASS', slicer=target, objects=reports, geometry_matches_live_export=True,
        from_revision=next(iter(before.values()))['link']['revision'], to_revision=snapshot['revision'],
        previous_geometry_retained=True, toolpaths_in_saved_project=False,
        dll_sha256=hashlib.sha256(dll.read_bytes()).hexdigest(),
        scope='Saved native GUI result after one physical click on Update linked parts. Two seeded objects share a source across two plates; normal user plate dragging was not repeated.')
    (root / 'experiments/results' / target / 'update-button.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=['orca', 'bambu'])
    verify(parser.parse_args().target)
