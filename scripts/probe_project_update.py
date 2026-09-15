"""Bounded 3MF round-trip experiment on the disposable two-plate fixture.

This is deliberately not a general project writer. It requires the known
fixture, a single shared mesh and no sliced data or painted triangle attributes.
The native application's subsequent save is the verification boundary.
"""

import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from slicer_link.model import require, validate_stl

ROOT = Path(__file__).resolve().parents[1]
C = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
P = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
ET.register_namespace("", C)
ET.register_namespace("p", P)


def prepare(kind):
    folder = ROOT / "artifacts" / "embedded"
    with ZipFile(folder / f"{kind}-baseline.3mf") as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    require(not any("gcode" in name.lower() for name in files), "Fixture must be unsliced.")
    model = ET.fromstring(files["3D/3dmodel.model"])
    objects = model.findall(f"{{{C}}}resources/{{{C}}}object")
    require(len(objects) == 3, "Expected the original, its clone and a second-plate object.")
    components = [obj.findall(f"{{{C}}}components/{{{C}}}component") for obj in objects]
    require(all(len(items) == 1 for items in components), "Fixture must contain simple parts.")
    targets = {(items[0].get(f"{{{P}}}path"), items[0].get("objectid")) for items in components}
    require(len(targets) == 1, "Expected the known deduplicated mesh.")
    mesh_path, mesh_id = targets.pop()
    mesh_path = mesh_path.lstrip("/")
    mesh_model = ET.fromstring(files[mesh_path])
    mesh_object = mesh_model.find(f"{{{C}}}resources/{{{C}}}object[@id='{mesh_id}']")
    old_mesh = mesh_object.find(f"{{{C}}}mesh")
    require(old_mesh is not None, "Missing mesh.")
    triangles = old_mesh.findall(f"{{{C}}}triangles/{{{C}}}triangle")
    require(all(set(t.attrib) == {"v1", "v2", "v3"} for t in triangles), "Painted fixture unsupported.")
    settings = ET.fromstring(files["Metadata/model_settings.config"])
    parts = settings.findall("object/part")
    require(len(parts) == 3, "Expected three fixture parts.")
    for part in parts:
        for axis, value in zip("xyz", (16, 12, 3)):
            require(
                float(part.find(f"metadata[@key='source_offset_{axis}']").get("value")) == value,
                "Fixture origin changed.",
            )
        source = part.find("metadata[@key='source_file']")
        require(source.get("value") == "linked-part.stl", "Unexpected fixture source.")
        source.set("value", "osl-fixture-link-r2.stl")
    data = (ROOT / "experiments" / "fixtures" / "r2.stl").read_bytes()
    validate_stl(data)
    vertices, faces, index = [], [], {}
    for values in struct.iter_unpack("<12fH", data[84:]):
        face = []
        for start in (3, 6, 9):
            vertex = tuple(values[start + axis] - offset for axis, offset in enumerate((16, 12, 3)))
            if vertex not in index:
                index[vertex] = len(vertices)
                vertices.append(vertex)
            face.append(index[vertex])
        faces.append(face)
    mesh = ET.Element(f"{{{C}}}mesh")
    v = ET.SubElement(mesh, f"{{{C}}}vertices")
    for vertex in vertices:
        ET.SubElement(v, f"{{{C}}}vertex", {axis: str(value) for axis, value in zip("xyz", vertex)})
    t = ET.SubElement(mesh, f"{{{C}}}triangles")
    for face in faces:
        ET.SubElement(
            t, f"{{{C}}}triangle", {axis: str(value) for axis, value in zip(("v1", "v2", "v3"), face)}
        )
    mesh_object.remove(old_mesh)
    mesh_object.append(mesh)
    files[mesh_path] = ET.tostring(mesh_model, encoding="utf-8", xml_declaration=True)
    files["Metadata/model_settings.config"] = ET.tostring(settings, encoding="utf-8", xml_declaration=True)
    target = folder / f"{kind}-transaction.3mf"
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    print(target)


if __name__ == "__main__":
    for kind in ("orca", "bambu"):
        prepare(kind)
