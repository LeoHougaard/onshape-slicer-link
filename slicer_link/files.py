"""Crash-recoverable updates of managed files. Never reads or writes a slicer project."""

import json
import math
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .model import LinkError, canonical, digest, require, validate_stl

MANIFEST = "slicer-link.json"


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".osl-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def folder_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    require(not (root / ".slicer-link.lock").is_symlink(), "Invalid project lock file.")
    with (root / ".slicer-link.lock").open("a+b") as lock:
        lock.seek(0)
        if os.name == "nt":
            import msvcrt

            if not lock.read(1):
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise LinkError(
                    "Another transfer is using this folder. Try again when it finishes."
                ) from None
        else:
            import fcntl

            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise LinkError(
                    "Another transfer is using this folder. Try again when it finishes."
                ) from None
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


class Library:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.cache = self.root / ".slicer-link" / "meshes"
        self.journal = self.root / ".slicer-link" / "pending.json"

    def _check_control_paths(self):
        for path in (self.root / ".slicer-link", self.cache, self.journal, self.root / MANIFEST):
            require(
                not path.is_symlink() and path.resolve().is_relative_to(self.root),
                "A managed folder or metadata file points outside the project folder.",
            )

    def path(self, filename):
        require(
            isinstance(filename, str) and re.fullmatch(r"[A-Za-z0-9_-]+-[a-f0-9]{32}\.stl", filename),
            "The transfer contains an invalid filename.",
        )
        path = self.root / filename
        require(
            not path.is_symlink() and path.resolve().parent == self.root,
            "A managed source file points outside the project folder.",
        )
        return path

    def mesh_path(self, sha):
        require(isinstance(sha, str) and re.fullmatch(r"[a-f0-9]{64}", sha), "Invalid model checksum.")
        path = self.cache / (sha + ".stl")
        require(not path.is_symlink() and path.resolve().is_relative_to(self.root), "Invalid cache folder.")
        return path

    def manifest(self):
        path = self.root / MANIFEST
        if not path.exists():
            return {"schema": 1, "links": {}, "completed_jobs": []}
        require(not path.is_symlink() and path.stat().st_size <= 4 * 1024 * 1024, "Invalid link manifest.")
        result = json.loads(path.read_text("utf-8"))
        require(
            result.get("schema") == 1 and isinstance(result.get("links"), dict),
            "Unsupported link manifest. Keep this folder and update the helper.",
        )
        return result

    def _recover(self):
        self._check_control_paths()
        if not self.journal.exists():
            return
        pending = json.loads(self.journal.read_text("utf-8"))
        # Detect edits made after the crash before rolling back any file.
        for filename, sha in pending["before"].items():
            path = self.path(filename)
            if path.exists() and filename in pending.get("after", {}):
                require(
                    digest(path.read_bytes()) in {sha, pending["after"][filename]},
                    "A source file changed after an interrupted transfer. Keep this folder for repair.",
                )
        for filename, sha in pending["before"].items():
            path = self.path(filename)
            if sha is None:
                path.unlink(missing_ok=True)
            else:
                data = self.mesh_path(sha).read_bytes()
                require(digest(data) == sha, "Recovery file is damaged. Keep this folder for repair.")
                atomic_write(path, data)
        atomic_write(self.root / MANIFEST, canonical(pending["manifest"]).encode())
        self.journal.unlink()

    def apply(self, job_id, links, fetch, *, account=None, created=None, expected=None):
        """Stage every file before committing. Recover an interrupted commit on next use.

        Atomicity covers helper operations and crash recovery; a user must wait
        for 'Ready to reload' before asking a stock slicer to read these files.
        """
        require(
            isinstance(job_id, str) and re.fullmatch(r"[a-f0-9]{32}", job_id), "Invalid transfer identifier."
        )
        require(isinstance(links, list) and 0 < len(links) <= 100, "Transfer must contain 1 to 100 links.")
        with folder_lock(self.root):
            self._recover()
            old = self.manifest()
            if account:
                require(
                    not old.get("account") or old["account"] == account,
                    "This folder belongs to another account. Choose a separate project folder.",
                )
            if job_id in old.get("completed_jobs", []):
                return {"changed": old.get("job_changes", {}).get(job_id, 0), "replayed": True}
            if created is not None:
                require(
                    isinstance(created, (int, float))
                    and math.isfinite(created)
                    and created >= old.get("last_transfer", 0),
                    "This transfer is older than files already saved here. Refresh again from Onshape.",
                )
            if expected:
                require(
                    all(
                        old["links"].get(identity, {}).get("sha256") == sha
                        for identity, sha in expected.items()
                    ),
                    "The files changed while restore was opening. Open restore again.",
                )
            new = json.loads(canonical(old))
            if created is not None:
                new["last_transfer"] = created
            if account:
                new["account"] = account
            before, staged = {}, {}
            seen = set()
            for link in links:
                link_id = link["id"]
                require(
                    isinstance(link_id, str)
                    and re.fullmatch(r"[a-f0-9]{32}", link_id)
                    and link_id not in seen,
                    "Invalid or duplicated link.",
                )
                seen.add(link_id)
                path, sha = self.path(link["filename"]), link["sha256"]
                require(link["filename"].endswith(f"-{link_id}.stl"), "Filename does not match its link.")
                prior = old["links"].get(link_id)
                if prior:
                    require(
                        prior["filename"] == link["filename"] and prior["source"] == link["source"],
                        "The transfer would change an existing link's source.",
                    )
                elif path.exists():
                    raise LinkError("A source filename is already in use. Existing files were retained.")
                if prior and path.exists():
                    require(
                        digest(path.read_bytes()) == prior["sha256"],
                        "A linked STL was edited outside this app. Existing files were retained.",
                    )
                cache = self.mesh_path(sha)
                data = cache.read_bytes() if cache.exists() else fetch(sha)
                require(digest(data) == sha, "Downloaded model checksum does not match.")
                validate_stl(data)
                if not cache.exists():
                    atomic_write(cache, data)
                if not prior or prior["sha256"] != sha or not path.exists():
                    previous_sha = None
                    if path.exists():
                        previous_data = path.read_bytes()
                        previous_sha = digest(previous_data)
                        atomic_write(self.mesh_path(previous_sha), previous_data)
                    before[link["filename"]] = previous_sha
                    staged[link["filename"]] = data
                record = dict(link)
                record["previous"] = (
                    prior if prior and prior["sha256"] != sha else (prior or {}).get("previous")
                )
                if record["previous"]:
                    record["previous"] = {k: v for k, v in record["previous"].items() if k != "previous"}
                new["links"][link_id] = record
            new["completed_jobs"] = (old.get("completed_jobs", []) + [job_id])[-1000:]
            new["job_changes"] = {
                key: value
                for key, value in old.get("job_changes", {}).items()
                if key in new["completed_jobs"]
            }
            new["job_changes"][job_id] = len(staged)
            atomic_write(
                self.journal,
                canonical(
                    {
                        "before": before,
                        "after": {name: digest(data) for name, data in staged.items()},
                        "manifest": old,
                    }
                ).encode(),
            )
            try:
                for filename, data in staged.items():
                    atomic_write(self.path(filename), data)
                atomic_write(self.root / MANIFEST, canonical(new).encode())
                self.journal.unlink()
            except Exception:
                self._recover()
                raise
            return {"changed": len(staged), "replayed": False}

    def restore(self, link_id):
        import uuid

        with folder_lock(self.root):
            self._recover()
            link = self.manifest()["links"].get(link_id)
            require(link and link.get("previous"), "No previous downloaded geometry for this part.")
            previous = link["previous"]
        # apply acquires the lock and revalidates current files before writing.
        return self.apply(
            uuid.uuid4().hex,
            [previous],
            lambda sha: self.mesh_path(sha).read_bytes(),
            expected={link_id: link["sha256"]},
        )
