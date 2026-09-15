"""The local desktop proxy must not expose the private automation API."""

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from scripts import embedded_probe as probe


@pytest.fixture
def client(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text="stock desktop", headers={"Content-Type": "text/html"})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(probe, "authorization", lambda: "Basic isolated-test-only")
    monkeypatch.setattr(
        probe.httpx,
        "AsyncClient",
        lambda **kwargs: async_client(**kwargs, transport=httpx.MockTransport(respond)),
    )
    with TestClient(probe.create_app(), base_url="http://localhost:8768") as client:
        yield client, requests


def test_proxy_keeps_runtime_auth_on_backend(client):
    browser, requests = client
    response = browser.get("/desktop/orca/")
    assert response.status_code == 200
    assert response.text == "stock desktop"
    assert "isolated-test-only" not in response.text
    assert requests[0].headers["authorization"] == "Basic isolated-test-only"
    assert str(requests[0].url) == "http://127.0.0.1:18871/desktop/orca/"
    assert "https://cad.onshape.com" in response.headers["content-security-policy"]
    assert "authorization" not in response.headers


@pytest.mark.parametrize(
    "path",
    [
        "/desktop/other/",
        "/desktop/orca/pelorus/api/state",
        "/desktop/orca//pelorus/api/state",
        "/desktop/orca/%2Fpelorus/api/state",
        "/desktop/orca/%252Fpelorus/api/state",
        "/desktop/orca/%5Cpelorus/api/state",
        "/desktop/orca/a/%2E%2E/pelorus/api/state",
    ],
)
def test_private_paths_never_reach_runtime(client, path):
    browser, requests = client
    assert browser.get(path).status_code == 404
    assert requests == []


def test_rebinding_and_writes_rejected(client):
    browser, requests = client
    assert browser.get("/", headers={"Host": "attacker.example:8768"}).status_code == 403
    assert browser.post("/desktop/orca/pelorus/api/desktop/control", json={}).status_code == 405
    assert requests == []


def test_import_requires_same_origin_session_and_excludes_concurrent_work(client):
    browser, _ = client
    body = {"selections": [{"name": "Test"}], "request_id": "a" * 32}
    assert browser.post("/api/orca/add", json=body).status_code == 403
    token = browser.get("/api/session").json()["session"]
    headers = {"Origin": "https://attacker.example", "X-OSL-Session": token}
    assert browser.post("/api/orca/add", json=body, headers=headers).status_code == 403
    headers["Origin"] = "http://localhost:8768"
    browser.app.state.busy = True
    assert browser.post("/api/orca/add", json=body, headers=headers).status_code == 409
    browser.app.state.busy = False

    class Cad:
        def add(self, kind, selections, request_id):
            assert (kind, selections, request_id) == ("orca", body["selections"], body["request_id"])
            return {"status": "verified"}

        def close(self):
            pass

    browser.app.state.cad = Cad()
    assert browser.post("/api/orca/add", json=body, headers=headers).json() == {"status": "verified"}
    assert browser.app.state.busy is False


@pytest.mark.parametrize(
    "origin,path",
    [
        ("https://attacker.example", "/desktop/orca/websockets"),
        ("https://cad.onshape.com", "/desktop/orca/websockets"),
        ("http://localhost:8768", "/desktop/orca//pelorus/api/state"),
    ],
)
def test_cross_origin_or_private_websockets_rejected(client, origin, path):
    browser, _ = client
    with (
        pytest.raises(WebSocketDisconnect) as error,
        browser.websocket_connect(path, headers={"Origin": origin}),
    ):
        pass
    assert error.value.code == 1008
