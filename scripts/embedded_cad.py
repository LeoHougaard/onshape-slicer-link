"""Development CAD import using the existing authorized local account and exporter."""

import io
import json
import re
import struct
import threading
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from zipfile import ZipFile

from scripts.embedded_adapter import Desktop, inventory
from scripts.embedded_runtime import ROOT
from slicer_link import platforms
from slicer_link.auth import Auth
from slicer_link.files import atomic_write, folder_lock
from slicer_link.local import ORIGIN, configuration
from slicer_link.model import Source, require
from slicer_link.onshape import Exporter
from slicer_link.store import Store

C = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
P = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}"


def signature(faces):
    low = [min(p[i] for face in faces for p in face) for i in range(3)]
    high = [max(p[i] for face in faces for p in face) for i in range(3)]
    center = [(a + b) / 2 for a, b in zip(low, high)]
    normalized = [tuple(tuple(round(p[i] - center[i], 5) for i in range(3)) for p in face) for face in faces]
    return Counter(min(face, face[1:] + face[:1], face[2:] + face[:2]) for face in normalized)


def verify_mesh(project, record, stl):
    expected = [
        tuple(tuple(values[i : i + 3]) for i in (3, 6, 9)) for values in struct.iter_unpack("<12fH", stl[84:])
    ]
    with ZipFile(io.BytesIO(project)) as archive:
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
        obj = root.find(f"{C}resources/{C}object[@id='{record['object_id']}']")
        components = obj.findall(f"{C}components/{C}component")
        require(len(components) == 1, "The new linked part is not a simple solid object.")
        component = components[0]
        model = ET.fromstring(archive.read(component.get(P + "path").lstrip("/")))
        mesh = model.find(f"{C}resources/{C}object[@id='{component.get('objectid')}']/{C}mesh")
        vertices = [tuple(float(v.get(axis)) for axis in "xyz") for v in mesh.find(C + "vertices")]
        actual = [
            tuple(vertices[int(t.get(axis))] for axis in ("v1", "v2", "v3"))
            for t in mesh.find(C + "triangles")
        ]
    require(signature(expected) == signature(actual), "The slicer did not save the expected CAD geometry.")


class Cad:
    def __init__(self):
        config = configuration()
        require(
            config and config.get("owner"), "Connect the existing local Slicer Link app to Onshape first."
        )
        self.owner = config["owner"]
        self.auth_store = Store(platforms.config_dir() / "local" / "service", config["key"])
        self.auth = Auth(self.auth_store, config["client_id"], config["client_secret"], ORIGIN)
        self.store = Store(platforms.config_dir() / "embedded-development" / "service", config["key"])
        self.exporter = Exporter(self.store)
        self.lock = threading.Lock()

    def close(self):
        self.store.close()
        self.auth_store.close()

    def add(self, kind, selections, request_id):
        require(re.fullmatch(r"[a-f0-9]{32}", request_id), "Invalid import request.")
        require(1 <= len(selections) <= 20, "Choose between one and twenty solid parts.")
        with self.lock, folder_lock(platforms.config_dir() / "embedded-development" / kind):
            previous = self.store.get("embedded-job", request_id)
            if previous:
                require(previous["kind"] == kind, "This import belongs to a different slicer.")
                require(
                    previous.get("result"),
                    "This import was interrupted. Inspect the slicer before adding again.",
                )
                return previous["result"]
            desktop = Desktop(kind)
            links = []
            for item in selections:
                source = Source(
                    item["documentId"],
                    item["workspaceId"],
                    item["elementId"],
                    item["microversionId"],
                    item["partId"],
                    item.get("configuration", ""),
                )
                identity = uuid.uuid4().hex
                links.append({"id": identity, "source": source.to_dict(), "name": item["name"][:100]})
            prepared = self.exporter.refresh(self.owner, self.auth.client(self.owner), links)
            self.store.put("embedded-job", request_id, self.owner, {"kind": kind, "status": "preparing"})
            folder = ROOT / "artifacts" / "embedded" / "jobs" / request_id
            folder.mkdir(parents=True)
            before = desktop.save_copy(f"/config/osl/jobs/{request_id}/before.3mf")
            atomic_write(folder / "before.3mf", before)
            for link in prepared:
                label = re.sub(r"[^A-Za-z0-9_-]+", "-", link["name"]).strip("-")[:32] or "Part"
                filename = f"{label}--osl--{link['id']}--{link['revision']}.stl"
                link["filename"] = filename
                self.store.put("embedded-link", link["id"], self.owner, link)
                self.store.put("embedded-revision", filename, self.owner, link)
                stl = (self.exporter.meshes / (link["sha256"] + ".stl")).read_bytes()
                path = "/config/osl/sources/" + filename
                desktop.put(path, stl)
                desktop.import_model(path)
            after = desktop.save_copy(f"/config/osl/jobs/{request_id}/after.3mf")
            atomic_write(folder / "after.3mf", after)
            objects = inventory(after)
            received = []
            for link in prepared:
                matches = [obj for obj in objects if obj["source_file"] == link["filename"]]
                require(len(matches) == 1, "The slicer did not acknowledge exactly one imported part.")
                verify_mesh(
                    after, matches[0], (self.exporter.meshes / (link["sha256"] + ".stl")).read_bytes()
                )
                received.append(
                    {
                        **matches[0],
                        "name": link["name"],
                        "revision": link["revision"],
                        "configuration": link["source"]["configuration"],
                        "link_id": link["id"],
                    }
                )
            result = {
                "objects": received,
                "status": "verified",
                "slicer": kind,
                "recovery": str(folder / "before.3mf"),
            }
            self.store.put("embedded-job", request_id, self.owner, {"kind": kind, "result": result})
            atomic_write(folder / "receipt.json", json.dumps(result, indent=2).encode())
            return result
