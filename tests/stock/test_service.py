import uuid
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from slicer_link.helper import handoff_id, transfer
from slicer_link.model import LinkError, digest, validate_stl
from slicer_link.service import Settings, create_app
from slicer_link.store import Store

DATA = (Path(__file__).resolve().parents[2] / "experiments/fixtures/r1.stl").read_bytes()
ALICE, BOB = "a" * 24, "b" * 24


class FakeCAD:
    def __init__(self):
        self.calls = []
        self.failure = None

    def microversion(self, *args):
        self.calls.append("revision")
        if self.failure:
            raise LinkError(self.failure)
        return "d" * 24

    def parts(self, source):
        self.calls.append("parts")
        return [
            {"partId": "P1", "name": "Bracket", "bodyType": "solid"},
            {"partId": "SHEET", "name": "Sheet", "bodyType": "sheet"},
        ]

    def export(self, source):
        self.calls.append("export")
        return DATA, validate_stl(DATA)


class FakeAuth:
    def __init__(self):
        self.cad = FakeCAD()

    def owner(self, token):
        if token == "a" * 40:
            return ALICE
        if token == "b" * 40:
            return BOB
        raise LinkError("Invalid session")

    def client(self, owner):
        return self.cad


@pytest.fixture
def system(tmp_path):
    key = Fernet.generate_key()
    store = Store(tmp_path / "server", key)
    auth = FakeAuth()
    app = create_app(Settings("https://link.example", str(tmp_path / "server"), key), store=store, auth=auth)
    with TestClient(app, base_url="https://link.example") as client:
        yield client, store, auth
    store.close()


def headers(who="a"):
    return {"Authorization": "Bearer " + who * 40}


def paired(client, name="Laptop", who="a"):
    pair = client.post("/api/devices", json={"name": name}).json()
    response = client.post(
        "/api/devices/claim", headers=headers(who), json={"code": pair["url"].split("#")[1]}
    )
    assert response.status_code == 200, response.text
    return pair


def linked(client):
    selection = client.post(
        "/api/selection",
        headers=headers(),
        json={
            "document_id": "1" * 24,
            "workspace_id": "2" * 24,
            "element_id": "3" * 24,
            "configuration": "size=Large",
        },
    ).json()
    assert [part["id"] for part in selection["parts"]] == ["P1"]
    response = client.post(
        "/api/links", headers=headers(), json={"selection": selection["id"], "part_id": "P1"}
    )
    assert response.status_code == 200, response.text
    return response.json(), selection


def refresh(client, pair, link):
    body = {"device": pair["id"], "links": [link["id"]], "request_id": uuid.uuid4().hex}
    response = client.post("/api/jobs", headers=headers(), json=body)
    assert response.status_code == 200, response.text
    return body


class LocalRemote:
    origin = "https://link.example"

    def __init__(self, client, token):
        self.client, self.token = client, token
        self.downloads = 0
        self.fail_receipt = False

    def request(self, path, body=None, *, binary=False):
        if path.endswith("/receipt") and self.fail_receipt:
            raise LinkError("Network lost")
        response = self.client.request(
            "GET" if body is None else "POST",
            path,
            json=body,
            headers={"Authorization": "Bearer " + self.token},
        )
        if response.status_code != 200:
            raise LinkError(response.text)
        if binary:
            self.downloads += 1
            return response.content
        return response.json()


def test_onshape_to_files_retry_and_cached_refresh(system, tmp_path):
    client, _store, auth = system
    pair = paired(client)
    link, _ = linked(client)
    body = refresh(client, pair, link)
    assert auth.cad.calls == ["revision", "parts", "revision", "export"]
    identity = body["request_id"]
    remote = LocalRemote(client, pair["token"])
    folder = tmp_path / "project"
    remote.fail_receipt = True
    result = transfer(remote, identity, folder)
    assert result == {"changed": 1, "replayed": False, "acknowledged": False}
    assert client.get(f"/api/jobs/{identity}", headers=headers()).json()["status"] == "prepared"
    remote.fail_receipt = False
    result = transfer(remote, identity, folder)
    assert result == {"changed": 1, "replayed": True, "acknowledged": True}
    assert remote.downloads == 1
    assert (folder / link["filename"]).read_bytes() == DATA
    status = client.get(f"/api/jobs/{identity}", headers=headers()).json()
    assert status["status"] == "delivered" and status["changed"] == 1
    # Duplicate browser submission cannot spend more Onshape requests.
    auth.cad.calls.clear()
    assert client.post("/api/jobs", headers=headers(), json=body).status_code == 200
    assert auth.cad.calls == []
    new = refresh(client, pair, link)
    assert auth.cad.calls == ["revision"]
    assert transfer(remote, new["request_id"], folder)["changed"] == 0
    assert remote.downloads == 1


def test_other_accounts_and_devices_cannot_access_links_or_transfers(system):
    client, _store, _auth = system
    pair, other = paired(client), paired(client, "Other", "b")
    second = paired(client, "Second Alice computer")
    link, selection = linked(client)
    assert (
        client.post(
            "/api/links", headers=headers("b"), json={"selection": selection["id"], "part_id": "P1"}
        ).status_code
        == 404
    )
    identity = refresh(client, pair, link)["request_id"]
    for token in (other["token"], second["token"]):
        device_headers = {"Authorization": "Bearer " + token}
        assert client.get(f"/api/transfers/{identity}", headers=device_headers).status_code == 404
        assert (
            client.get(f"/api/transfers/{identity}/meshes/{digest(DATA)}", headers=device_headers).status_code
            == 404
        )
    assert client.get(f"/api/jobs/{identity}", headers=headers("b")).status_code == 404
    assert client.delete(f"/api/links/{link['id']}", headers=headers("b")).status_code == 404
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers=headers("b")).json()["links"] == []
    assert client.delete(f"/api/devices/{pair['id']}", headers=headers()).status_code == 200
    assert (
        client.get(
            f"/api/transfers/{identity}", headers={"Authorization": "Bearer " + pair["token"]}
        ).status_code
        == 401
    )


def test_pairing_expiry_replay_and_request_boundaries(system):
    client, _store, auth = system
    pair = paired(client)
    assert (
        client.post(
            "/api/devices/claim", headers=headers(), json={"code": pair["url"].split("#")[1]}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/devices", headers={"Origin": "https://evil.example"}, json={"name": "Bad"}
        ).status_code
        == 403
    )
    assert client.post("/api/devices", content=b"x" * (128 * 1024 + 1)).status_code == 413
    assert client.post("/api/devices", json={"name": "ok", "owner": ALICE}).status_code == 422
    response = client.get("/")
    assert response.status_code == 200
    assert "frame-ancestors https://cad.onshape.com" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert auth.cad.calls == []  # Browsing, pairing, and status do not touch CAD.


def test_failed_export_never_replaces_local_files(system, tmp_path):
    client, _store, auth = system
    pair = paired(client)
    link, _ = linked(client)
    identity = refresh(client, pair, link)["request_id"]
    remote = LocalRemote(client, pair["token"])
    folder = tmp_path / "project"
    transfer(remote, identity, folder)
    auth.cad.failure = "Onshape's annual API allowance is exhausted."
    failed = refresh(client, pair, link)["request_id"]
    with pytest.raises(LinkError, match="allowance"):
        transfer(remote, failed, folder)
    assert (folder / link["filename"]).read_bytes() == DATA
    assert remote.downloads == 1


def test_old_transfer_cannot_roll_back_newer_download(system, tmp_path):
    client, _store, _auth = system
    pair = paired(client)
    link, _ = linked(client)
    old = refresh(client, pair, link)["request_id"]
    recent = refresh(client, pair, link)["request_id"]
    remote = LocalRemote(client, pair["token"])
    transfer(remote, recent, tmp_path / "project")
    with pytest.raises(LinkError, match="older"):
        transfer(remote, old, tmp_path / "project")


def test_service_restart_marks_interrupted_work_failed(system, tmp_path):
    _client, store, auth = system
    identity = uuid.uuid4().hex
    store.put("job", identity, ALICE, {"id": identity, "owner": ALICE, "status": "preparing"}, ttl=100)
    create_app(
        Settings("https://link.example", str(store.root), Fernet.generate_key()), store=store, auth=auth
    )
    assert store.get("job", identity)["status"] == "failed"


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example/job/" + "a" * 32,
        "onshape-slicer-link://job/../file",
        "onshape-slicer-link://job/" + "a" * 32 + "?url=https://evil.example",
        "onshape-slicer-link://job/" + "a" * 32 + "#x",
        "onshape-slicer-link://user@job/" + "a" * 32,
        "onshape-slicer-link://job/%2e%2e",
    ],
)
def test_handoff_contains_only_job_identity(value):
    with pytest.raises(LinkError):
        handoff_id(value)
    assert handoff_id("onshape-slicer-link://job/" + "a" * 32) == "a" * 32
