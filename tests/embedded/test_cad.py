import threading

import pytest

from scripts import embedded_cad as cad
from slicer_link.model import LinkError


def test_mesh_receipt_detects_changed_triangles_even_with_same_vertices():
    faces = [((0, 0, 0), (2, 0, 0), (0, 1, 0)), ((2, 0, 0), (2, 1, 0), (0, 1, 0))]
    moved = [tuple(tuple(v + 10 for v in point) for point in face) for face in faces]
    assert cad.signature(faces) == cad.signature(moved)
    changed = [faces[0], (faces[1][1], faces[1][0], faces[1][2])]
    assert cad.signature(faces) != cad.signature(changed)


@pytest.mark.parametrize("completed", [False, True])
def test_retried_import_never_sends_more_desktop_input(monkeypatch, tmp_path, completed):
    receipt = {"status": "verified", "objects": [{"name": "Part"}]}

    class Store:
        def get(self, kind, identity):
            return {"kind": "orca", **({"result": receipt} if completed else {"status": "preparing"})}

    def unexpected(*args):
        pytest.fail("A retried import must not send another import to the slicer.")

    service = object.__new__(cad.Cad)
    service.lock, service.store = threading.Lock(), Store()
    monkeypatch.setattr(cad.platforms, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cad, "Desktop", unexpected)
    if completed:
        assert service.add("orca", [{"name": "Part"}], "a" * 32) == receipt
    else:
        with pytest.raises(LinkError, match="interrupted"):
            service.add("orca", [{"name": "Part"}], "a" * 32)
