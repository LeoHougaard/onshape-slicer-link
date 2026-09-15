"""Compare actual stock-slicer saves from the isolated desktop experiments."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from scripts.make_fixtures import mesh
from slicer_link.model import require

ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "embedded"
C = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
P = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}"


def metadata(node):
    return {m.get("key"): m.get("value") for m in node.findall("metadata") if m.get("key")}


def load(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
        settings = ET.fromstring(archive.read("Metadata/model_settings.config"))
        objects = {}
        for item in root.find(C + "build"):
            identity = item.get("objectid")
            obj = root.find(f"{C}resources/{C}object[@id='{identity}']")
            component = obj.find(C + "components/" + C + "component")
            require(component is not None, "Expected a stock component mesh.")
            transform = component.get("transform", "1 0 0 0 1 0 0 0 1 0 0 0")
            require(
                [float(v) for v in transform.split()] == [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
                "The fixture component transform changed.",
            )
            model = ET.fromstring(archive.read(component.get(P + "path").lstrip("/")))
            mesh_node = model.find(f"{C}resources/{C}object[@id='{component.get('objectid')}']/{C}mesh")
            vertices = [tuple(float(v.get(axis)) for axis in "xyz") for v in mesh_node.find(C + "vertices")]
            faces = [
                tuple(vertices[int(t.get(axis))] for axis in ("v1", "v2", "v3"))
                for t in mesh_node.find(C + "triangles")
            ]
            config = settings.find(f"object[@id='{identity}']")
            objects[identity] = {
                "transform": [float(v) for v in item.get("transform").split()],
                "attributes": {k: v for k, v in item.attrib.items() if k != "transform"},
                "settings": metadata(config),
                "part": metadata(config.find("part")),
                "vertices": vertices,
                "faces": faces,
            }
        plates = []
        for plate in settings.findall("plate"):
            plates.append(
                {
                    "settings": metadata(plate),
                    "instances": sorted(
                        (metadata(instance)["object_id"], metadata(instance)["instance_id"])
                        for instance in plate.findall("model_instance")
                    ),
                }
            )
        return {
            "objects": objects,
            "plates": plates,
            "project_settings": json.loads(archive.read("Metadata/project_settings.config")),
        }


def world(vertex, transform):
    return tuple(sum(vertex[j] * transform[3 * j + i] for j in range(3)) + transform[9 + i] for i in range(3))


def verify(kind, mode):
    baseline = load(ROOT / f"{kind}-baseline.3mf")
    result = load(ROOT / f"{kind}-{mode}.3mf")
    require(baseline["project_settings"] == result["project_settings"], "Project settings changed.")
    require(baseline["plates"] == result["plates"], "Plate settings or assignment changed.")
    require(baseline["objects"].keys() == result["objects"].keys(), "Objects were lost or added.")
    origin_preserved = mode == "transaction-verified"
    expected_name = "osl-fixture-link-r2.stl" if origin_preserved else "linked-part.stl"
    fixture_vertices, fixture_faces = mesh(46)
    maximum_error = 0.0
    for identity, before in baseline["objects"].items():
        after = result["objects"][identity]
        require(before["attributes"] == after["attributes"], "Build properties changed.")
        require(before["settings"] == after["settings"], "Object settings or names changed.")
        require({**before["part"], "source_file": expected_name} == after["part"], "Part settings changed.")
        require(len(before["faces"]) == len(after["faces"]) == len(fixture_faces), "Wrong triangle count.")
        require(
            len(before["vertices"]) == len(after["vertices"]) == len(fixture_vertices), "Wrong vertex count."
        )
        require(
            max(abs(a - b) for a, b in zip(before["transform"][:9], after["transform"][:9])) < 1e-7,
            "Orientation or scale changed.",
        )
        old_center = (16 if origin_preserved else 23, 12, 3)
        expected = [
            world(tuple(v[i] - old_center[i] for i in range(3)), before["transform"])
            for v in fixture_vertices
        ]
        actual = [world(v, after["transform"]) for v in after["vertices"]]
        # Vertex order is not stable across a native save. Require a one-to-one match.
        remaining = actual[:]
        for point in expected:
            distances = [max(abs(a - b) for a, b in zip(point, other)) for other in remaining]
            error = min(distances)
            require(error < 1e-5, "Geometry moved or does not match the expected CAD revision.")
            maximum_error = max(maximum_error, error)
            remaining.pop(distances.index(error))
        require(not remaining, "Unexpected geometry remains.")
    return {
        "slicer": kind,
        "mode": mode,
        "objects": 3,
        "plates": 2,
        "settings_preserved": True,
        "source_filenames_retained": True,
        "cad_origin_preserved": origin_preserved,
        "maximum_vertex_error_mm": maximum_error,
        "limits": "Known simple fixture only; not live CAD, paint, plate moves or failure recovery.",
    }


def main():
    results = [
        verify(kind, mode) for kind in ("orca", "bambu") for mode in ("reloaded", "transaction-verified")
    ]
    content = json.dumps(results, indent=2) + "\n"
    (ROOT / "project-comparison.json").write_text(content)
    print(content)


if __name__ == "__main__":
    main()
