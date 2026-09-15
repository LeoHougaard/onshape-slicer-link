"""Development adapter for the dedicated, version-pinned stock desktop.

All input targets the container desktop. Native saves provide the receipt;
an input acknowledgement alone never counts as a successful import.
"""

import io
import re
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from scripts.embedded_runtime import ROOT, docker, request
from slicer_link.model import LinkError, require


class Desktop:
    def __init__(self, kind):
        require(kind in {"orca", "bambu"}, "Choose OrcaSlicer or Bambu Studio.")
        self.kind = kind
        self.container = f"osl-{kind}-development"
        self.app_id = "orca-slicer" if kind == "orca" else "bambu-studio"
        self.main = self.ready()

    def windows(self):
        return [
            window
            for window in request(self.kind, "/api/windows")["windows"]
            if window.get("width", 0) > 0 and window.get("height", 0) > 0
        ]

    def ready(self):
        windows = self.windows()
        require(
            len(windows) == 1 and windows[0].get("app_id") == self.app_id,
            "Close the slicer's dialog or extra window, then try again.",
        )
        require(
            windows[0]["width"] >= 1000 and windows[0]["height"] >= 600,
            "Maximize the dedicated slicer before continuing.",
        )
        return windows[0]

    def input(self, action, **values):
        result = request(self.kind, "/api/desktop/control", {"action": action, **values})
        require(not result.get("error"), "The dedicated desktop could not accept input.")

    def key(self, *keys):
        docker(
            "exec",
            "--user",
            "abc",
            "--env",
            "WAYLAND_DISPLAY=wayland-0",
            "--env",
            "XDG_RUNTIME_DIR=/config/.XDG",
            self.container,
            "wtype",
            *keys,
        )

    def tree(self):
        return request(self.kind, f"/api/desktop/explore/{self.main['pid']}")["tree"]

    def menu(self, prefix):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            entries = []
            for line in self.tree().splitlines():
                match = re.search(r'\[menu(?: item)?\] "([^"]+)".*?screen \((\d+),(\d+)\) (\d+)x(\d+)', line)
                if match and match[1].startswith(prefix):
                    entries.append(match)
            if len(entries) == 1:
                match = entries[0]
                coordinate = [int(match[2]) + int(match[4]) // 2, int(match[3]) + int(match[5]) // 2]
                # A click can close a submenu that GTK opened on pointer entry.
                self.input("mouse_move" if prefix == "Import" else "left_click", coordinate=coordinate)
                return
            time.sleep(0.15)
        raise LinkError(f"The stock slicer did not expose its {prefix} command. No further input was sent.")

    def file_menu(self):
        main = self.ready()
        self.input("left_click", coordinate=[main["x"] + 40, main["y"] + 15])

    def wait_dialog(self, prefix):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if any(window["title"].startswith(prefix) for window in self.windows()):
                return
            time.sleep(0.15)
        raise LinkError("The expected slicer file dialog did not open. No file was selected.")

    def put(self, path, content):
        require(path.startswith("/config/osl/") and ".." not in path, "Invalid managed file path.")
        folder = str(Path(path).parent).replace("\\", "/")
        docker("exec", self.container, "mkdir", "-p", folder)
        docker("exec", self.container, "chown", "1000:1000", folder)
        # Write bytes over stdin; neither geometry nor paths become shell code.
        docker("exec", "-i", self.container, "tee", path, data=content)
        docker("exec", self.container, "chown", "1000:1000", path)

    def save_copy(self, path):
        require(path.startswith("/config/osl/") and ".." not in path, "Invalid recovery path.")
        folder = str(Path(path).parent).replace("\\", "/")
        docker("exec", self.container, "mkdir", "-p", folder)
        docker("exec", self.container, "chown", "1000:1000", folder)
        self.file_menu()
        self.menu("Save Project as")
        self.wait_dialog("Save file as")
        self.key("-M", "ctrl", "-k", "a", "-m", "ctrl", path)
        self.input("key", text="Return")
        submitted = time.monotonic()
        retried = False
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                data = docker("exec", self.container, "cat", path)
                with ZipFile(io.BytesIO(data)) as archive:
                    require(archive.testzip() is None, "The slicer save is incomplete.")
                    archive.read("Metadata/model_settings.config")
                self.ready()
                return data
            except (RuntimeError, OSError, ValueError, LinkError, BadZipFile):
                # GTK's filename completion can consume the first Return.
                # Retry only while the same known save dialog is still open.
                if not retried and time.monotonic() - submitted > 1:
                    if any(w["title"].startswith("Save file as") for w in self.windows()):
                        self.input("key", text="Return")
                    retried = True
                time.sleep(0.2)
        raise LinkError("The slicer did not finish saving its recovery copy. The operation stopped.")

    def import_model(self, path):
        require(path.startswith("/config/osl/sources/") and ".." not in path, "Invalid source path.")
        self.file_menu()
        self.menu("Import")
        self.menu("Import 3MF")
        self.wait_dialog("Choose")
        self.key("-M", "ctrl", "-k", "l", "-m", "ctrl", path)
        self.input("key", text="Return")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                self.ready()
                return
            except LinkError:
                time.sleep(0.2)
        raise LinkError("The slicer is waiting for input. Resolve its dialog before trying again.")


def inventory(data):
    """Read the native saved source names and plate membership, never GUI guesses."""
    with ZipFile(io.BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("Metadata/model_settings.config"))
    meta = lambda node: {m.get("key"): m.get("value") for m in node.findall("metadata")}
    membership = {}
    for plate in root.findall("plate"):
        for instance in plate.findall("model_instance"):
            membership.setdefault(meta(instance)["object_id"], []).append(meta(plate)["plater_id"])
    result = []
    for obj in root.findall("object"):
        for part in obj.findall("part"):
            values = meta(part)
            filename = values.get("source_file", "").replace("\\", "/").rsplit("/", 1)[-1]
            result.append(
                {
                    "object_id": obj.get("id"),
                    "name": meta(obj).get("name", "Part"),
                    "part_id": part.get("id"),
                    "source_file": filename,
                    "plates": membership.get(obj.get("id"), []),
                }
            )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("orca", "bambu"))
    options = parser.parse_args()
    desk = Desktop(options.kind)
    job = uuid.uuid4().hex
    data = desk.save_copy(f"/config/osl/jobs/{job}/before.3mf")
    (ROOT / "artifacts" / "embedded" / f"{options.kind}-adapter-save.3mf").write_bytes(data)
    print(inventory(data))
