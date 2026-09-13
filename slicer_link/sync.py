"""Local delivery to stock slicers, with durable files and no duplicate reimports."""

import os
import re
import subprocess
import threading
import time
from pathlib import Path

from . import platforms
from .files import Library
from .model import LinkError, canonical, digest, require
from .onshape import Exporter


def open_models(command, paths):
    # Use the stock open-file interface and respect its existing preferences.
    # No shell, slicing flags, or project rewriting.
    require(paths, "There are no new parts to open.")
    if len(command) == 3 and command[0] == "flatpak" and command[1] == "run":
        # Give this launch read access to the managed folder. This does not
        # change Flatpak's persistent overrides or expose other project data.
        folders = sorted({str(Path(path).parent) for path in paths})
        command = [*command[:2], *("--filesystem=" + folder + ":ro" for folder in folders), command[2]]
    try:
        process = subprocess.Popen(
            [*command, *map(str, paths)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            code = process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            return
        require(code == 0, "The slicer could not open the models. Check its setup, then try again.")
    except OSError:
        raise OSError("Cannot start this slicer. Choose its installed executable and retry.") from None


class Sync:
    def __init__(self, store, auth, root, *, discover=platforms.slicers, launch=open_models):
        self.store, self.auth, self.root = store, auth, Path(root)
        self.discover, self.launch = discover, launch
        self.exporter = Exporter(store)
        self.lock = threading.RLock()
        for record in store.list("sync"):
            if record["status"] == "preparing":
                record.update(status="failed", error="The app restarted. Send again to finish the update.")
                store.put("sync", record["id"], record["owner"], record, ttl=86400)

    def targets(self, owner):
        found = self.discover()
        custom = self.store.get("slicer-path", owner)
        if custom:
            found[custom["name"]] = [custom["path"]]
        return {
            digest(name.encode())[:32]: {"id": digest(name.encode())[:32], "name": name, "command": command}
            for name, command in found.items()
        }

    def choose_path(self, owner, path, name):
        require(name in {"OrcaSlicer", "Bambu Studio"}, "Choose OrcaSlicer or Bambu Studio.")
        candidate = Path(path).expanduser()
        require(candidate.is_absolute() and candidate.is_file(), "Choose an installed slicer executable.")
        require(
            candidate.suffix.lower() == ".exe" if os.name == "nt" else os.access(candidate, os.X_OK),
            "Choose the executable or executable AppImage, not a shortcut or a folder.",
        )
        self.store.put("slicer-path", owner, owner, {"name": name, "path": str(candidate.resolve())})

    def project_key(self, owner, target_id, source):
        return digest(canonical([owner, target_id, source["document_id"], source["workspace_id"]]).encode())

    def connect_project(self, owner, target_id, source, path):
        require(target_id in self.targets(owner), "Choose a slicer first.")
        project = Path(path).expanduser().resolve()
        require(project.is_file() and project.suffix.lower() == ".3mf", "Choose your saved slicer project.")
        from zipfile import BadZipFile, ZipFile

        try:
            with ZipFile(project) as archive:
                require(
                    "Metadata/model_settings.config" in archive.namelist(),
                    "Choose a project saved by OrcaSlicer or Bambu Studio.",
                )
        except BadZipFile:
            raise LinkError("This is not a valid saved slicer project.") from None
        key = self.project_key(owner, target_id, source)
        # This stores only the location. The next explicit Send updates managed
        # sources beside it. The 3MF itself is never rewritten.
        self.store.put("slicer-project", key, owner, {"path": str(project)})
        return {"name": project.name, "path": str(project)}

    def send(self, owner, target_id, identities, request_id, *, reopen=False):
        require(re.fullmatch(r"[a-f0-9]{32}", request_id), "Invalid send identifier.")
        require(
            0 < len(identities) <= 100 and len(set(identities)) == len(identities), "Choose distinct parts."
        )
        signature = digest(canonical([target_id, sorted(identities), reopen]).encode())
        key = digest((owner + request_id).encode())
        with self.lock:
            prior = self.store.get("sync", key)
            if prior:
                require(prior["signature"] == signature, "This send identifier was already used.")
                return prior
            target = self.targets(owner).get(target_id)
            require(target, "Choose an installed slicer first.")
            links = [self.store.get("link", identity) for identity in identities]
            require(
                all(link and link.get("owner") == owner for link in links), "A selected part is unavailable."
            )
            record = {"id": key, "owner": owner, "signature": signature, "status": "preparing"}
            self.store.put("sync", key, owner, record, ttl=86400)
            try:
                prepared = self.exporter.refresh(owner, self.auth.client(owner), links)
                library = Library(self.root / owner / target_id)
                result = library.apply(
                    request_id,
                    prepared,
                    lambda sha: (self.exporter.meshes / (sha + ".stl")).read_bytes(),
                    account=owner,
                    created=time.time(),
                )
                projects = {}
                for link in prepared:
                    project_key = self.project_key(owner, target_id, link["source"])
                    project = self.store.get("slicer-project", project_key)
                    if project:
                        path = Path(project["path"])
                        require(path.is_file(), "The connected project moved. Connect its new location.")
                        projects.setdefault(path.parent, []).append(link)
                for folder, project_links in projects.items():
                    Library(folder).apply(
                        request_id,
                        project_links,
                        lambda sha: (self.exporter.meshes / (sha + ".stl")).read_bytes(),
                        account=owner,
                        created=time.time(),
                    )
                new, existing, uncertain = [], [], []
                for link in prepared:
                    delivery_key = digest((owner + target_id + link["id"]).encode())
                    delivery = self.store.get("slicer-import", delivery_key)
                    if reopen or not delivery:
                        new.append((delivery_key, link))
                    elif delivery["status"] == "launching":
                        uncertain.append(link["name"])
                    else:
                        existing.append(link["name"])
                # Record intent first. A crash around process launch must not
                # silently open the same objects again on retry.
                for delivery_key, link in new:
                    self.store.put("slicer-import", delivery_key, owner, {"status": "launching"})
                if new:
                    try:
                        self.launch(target["command"], [library.path(link["filename"]) for _, link in new])
                    except OSError:
                        for delivery_key, _ in new:
                            self.store.delete("slicer-import", delivery_key)
                        raise
                    for delivery_key, _ in new:
                        self.store.put("slicer-import", delivery_key, owner, {"status": "sent"})
                self.store.put("slicer-choice", owner, owner, {"id": target_id})
                record.update(
                    status="ready",
                    slicer=target["name"],
                    opened=len(new),
                    reload=existing,
                    uncertain=uncertain,
                    changed=result["changed"],
                )
            except (LinkError, OSError) as error:
                record.update(status="failed", error=str(error))
            self.store.put("sync", key, owner, record, ttl=86400)
            return record
