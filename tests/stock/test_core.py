import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from slicer_link import files
from slicer_link.files import Library
from slicer_link.model import LinkError, Source, digest, link_filename
from slicer_link.onshape import Exporter
from slicer_link.store import Store

FIXTURES = Path(__file__).resolve().parents[2] / "experiments/fixtures"


def source(**changes):
    return Source(
        **{
            "document_id": "a" * 24,
            "workspace_id": "b" * 24,
            "element_id": "c" * 24,
            "microversion": "d" * 24,
            "part_id": "PART",
            **changes,
        }
    )


def link(data, *, identity=None, **changes):
    identity = identity or uuid.uuid4().hex
    return {
        "id": identity,
        "filename": link_filename("Bracket", identity),
        "name": "Bracket",
        "source": source().to_dict(),
        "sha256": digest(data),
        "revision": "d" * 24,
        **changes,
    }


def test_files_survive_partial_commit_and_can_restore_after_reopen(tmp_path, monkeypatch):
    first, second = ((FIXTURES / name).read_bytes() for name in ("r1.stl", "r2.stl"))
    library = Library(tmp_path)
    a, b = link(first), link(first)
    library.apply(uuid.uuid4().hex, [a, b], lambda sha: first)
    project = tmp_path / "my-project.3mf"
    project.write_bytes(b"opaque-user-project")
    original = files.atomic_write
    failed = False

    def fail_second(path, data):
        nonlocal failed
        if path.name == b["filename"] and data == second and not failed:
            failed = True
            raise OSError("simulated disk failure")
        original(path, data)

    monkeypatch.setattr(files, "atomic_write", fail_second)
    replacements = [{**item, "sha256": digest(second), "revision": "e" * 24} for item in (a, b)]
    with pytest.raises(OSError):
        library.apply(uuid.uuid4().hex, replacements, lambda sha: second)
    assert all((tmp_path / item["filename"]).read_bytes() == first for item in (a, b))
    assert library.manifest()["links"][a["id"]]["sha256"] == digest(first)
    job = uuid.uuid4().hex
    library.apply(job, replacements, lambda sha: second)
    assert Library(tmp_path).apply(job, replacements, lambda sha: pytest.fail("repeat download"))["replayed"]
    Library(tmp_path).restore(a["id"])
    assert (tmp_path / a["filename"]).read_bytes() == first
    assert (tmp_path / b["filename"]).read_bytes() == second
    assert project.read_bytes() == b"opaque-user-project"


def test_invalid_download_and_external_edits_preserve_files(tmp_path):
    data = (FIXTURES / "r1.stl").read_bytes()
    library = Library(tmp_path)
    item = link(data)
    with pytest.raises(LinkError, match="checksum"):
        library.apply(uuid.uuid4().hex, [item], lambda sha: b"truncated")
    assert not (tmp_path / item["filename"]).exists()
    library.apply(uuid.uuid4().hex, [item], lambda sha: data)
    (tmp_path / item["filename"]).write_bytes(b"user-edit")
    with pytest.raises(LinkError, match="edited outside"):
        library.apply(uuid.uuid4().hex, [item], lambda sha: data)
    assert (tmp_path / item["filename"]).read_bytes() == b"user-edit"


def test_crash_journal_is_recovered_before_next_transfer(tmp_path):
    first, second = ((FIXTURES / name).read_bytes() for name in ("r1.stl", "r2.stl"))
    library = Library(tmp_path)
    a = link(first)
    library.apply(uuid.uuid4().hex, [a], lambda sha: first)
    old = library.manifest()
    library.journal.write_text(json.dumps({"before": {a["filename"]: digest(first)}, "manifest": old}))
    (tmp_path / a["filename"]).write_bytes(second)
    library.apply(uuid.uuid4().hex, [a], lambda sha: pytest.fail("cached file downloaded"))
    assert (tmp_path / a["filename"]).read_bytes() == first
    assert not library.journal.exists()


def test_account_and_path_boundaries(tmp_path):
    data = (FIXTURES / "r1.stl").read_bytes()
    library = Library(tmp_path)
    item = link(data)
    library.apply(uuid.uuid4().hex, [item], lambda sha: data, account="first")
    with pytest.raises(LinkError, match="another account"):
        library.apply(uuid.uuid4().hex, [item], lambda sha: data, account="second")
    for filename in ("../part.stl", "C:\\other.stl", "my-project.3mf", "CON.stl"):
        with pytest.raises(LinkError):
            library.apply(uuid.uuid4().hex, [{**item, "filename": filename}], lambda sha: data)


def test_cache_shares_revision_checks_and_exports_across_slicers(tmp_path):
    store = Store(tmp_path, Fernet.generate_key())
    exporter = Exporter(store)
    data = (FIXTURES / "r1.stl").read_bytes()

    class FakeClient:
        def __init__(self):
            self.calls = []
            self.revision = "e" * 24

        def microversion(self, *args):
            self.calls.append("revision")
            return self.revision

        def translate(self, sources, target):
            self.calls.append("translate")
            return {item.part_id: item.part_id + "NEW" for item in sources}

        def export(self, selected):
            self.calls.append("export")
            return data, {"sha256": digest(data), "bounds_mm": [[0, 0, 0], [32, 24, 6]]}

    client = FakeClient()
    links = [link(data), link(data)]
    result = exporter.refresh("owner", client, links)
    assert client.calls == ["revision", "translate", "export"]
    assert result[0]["sha256"] == result[1]["sha256"]
    client.calls.clear()
    assert exporter.refresh("owner", client, links) == result
    assert client.calls == ["revision"]
    client.calls.clear()
    Exporter(store).refresh("owner", client, links)
    assert client.calls == ["revision"]  # Survives restarting the service.
    store.close()


def test_source_configuration_and_identity_are_not_names():
    original = source(configuration="size=Large")
    assert original.key != replace(original, configuration="size=Small").key
    assert original.key != replace(original, element_id="f" * 24).key
    for name in ("same name", "CON", "a/b", "日本語", "a.b"):
        assert link_filename(name, "a" * 32).endswith("-" + "a" * 32 + ".stl")
