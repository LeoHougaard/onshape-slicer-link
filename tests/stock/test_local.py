import os
import socket
import threading
import uuid
from pathlib import Path

import pytest
import uvicorn
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from test_service import ALICE, DATA, FakeAuth, headers, linked

from slicer_link.documents import resolve
from slicer_link.local_service import create_local_app
from slicer_link.model import LinkError, digest, validate_stl
from slicer_link.service import Settings
from slicer_link.store import Store
from slicer_link.sync import Sync

TARGETS = {"OrcaSlicer": ["stock orca.exe"], "Bambu Studio": ["stock bambu.exe"]}
ORCA = digest(b"OrcaSlicer")[:32]
BAMBU = digest(b"Bambu Studio")[:32]


def document_response(path):
    if path.endswith("/elements"):
        return [
            {"id": "3" * 24, "name": "Main parts", "elementType": "PARTSTUDIO"},
            {"id": "4" * 24, "name": "Assembly", "elementType": "ASSEMBLY"},
        ]
    return {"name": "My printer bracket", "defaultWorkspace": {"id": "2" * 24}}


@pytest.fixture
def local(tmp_path):
    store = Store(tmp_path / "service", Fernet.generate_key())
    auth, launches = FakeAuth(), []
    auth.cad.request = document_response
    sync = Sync(
        store,
        auth,
        tmp_path / "models",
        discover=lambda: TARGETS,
        launch=lambda command, paths: launches.append((command, paths)),
    )
    app = create_local_app(
        Settings("http://127.0.0.1:8767", str(store.root), "unused", development=True),
        store,
        auth,
        tmp_path / "models",
        sync=sync,
    )
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        yield client, sync, launches
    store.close()


def body(link, slicer=ORCA, **changes):
    return {"slicer": slicer, "links": [link["id"]], "request_id": uuid.uuid4().hex, **changes}


def send(client, payload):
    result = client.post("/api/local/send", headers=headers(), json=payload)
    assert result.status_code == 200, result.text
    return result.json()


def test_send_updates_stable_file_without_duplicate_import(local):
    client, sync, launches = local
    link, _ = linked(client)
    payload = body(link)
    first = send(client, payload)
    assert first["opened"] == 1 and first["reload"] == []
    path = launches[0][1][0]
    assert path.read_bytes() == DATA
    before = list(sync.auth.cad.calls)
    assert send(client, payload) == first
    assert sync.auth.cad.calls == before and len(launches) == 1
    updated = (Path(__file__).resolve().parents[2] / "experiments/fixtures/r2.stl").read_bytes()
    sync.auth.cad.microversion = lambda *args: "e" * 24
    sync.auth.cad.translate = lambda sources, target: {source.part_id: source.part_id for source in sources}
    sync.auth.cad.export = lambda source: (updated, validate_stl(updated))
    second = send(client, body(link))
    assert second["opened"] == 0 and second["reload"] == ["Bracket"] and second["changed"] == 1
    assert path.read_bytes() == updated and len(launches) == 1
    assert send(client, body(link))["changed"] == 0 and len(launches) == 1


def test_slicer_choice_isolated_and_explicit_reopen(local):
    client, sync, launches = local
    link, _ = linked(client)
    send(client, body(link))
    result = send(client, body(link, BAMBU))
    assert result["opened"] == 1 and launches[1][0] == TARGETS["Bambu Studio"]
    assert launches[0][1][0] != launches[1][1][0]
    assert sync.auth.cad.calls.count("export") == 1
    assert send(client, body(link))["opened"] == 0
    assert send(client, body(link, reopen=True))["opened"] == 1
    assert len(launches) == 3


def test_export_and_launch_failure_keep_files_and_allow_recovery(local):
    client, sync, launches = local
    link, _ = linked(client)
    sync.auth.cad.failure = "Onshape unavailable"
    assert send(client, body(link))["status"] == "failed"
    assert not launches
    sync.auth.cad.failure = None
    normal = sync.launch
    sync.launch = lambda *args: (_ for _ in ()).throw(OSError("Slicer not installed"))
    assert send(client, body(link))["status"] == "failed"
    saved = list(sync.root.rglob("*.stl"))
    assert saved and all(path.read_bytes() == DATA for path in saved)
    sync.launch = normal
    assert send(client, body(link))["opened"] == 1
    assert sync.auth.cad.calls.count("export") == 1


def test_interrupted_launch_is_not_blindly_reimported(local):
    client, sync, launches = local
    link, _ = linked(client)
    sync.launch = lambda *args: (_ for _ in ()).throw(RuntimeError("simulated process crash"))
    payload = body(link)
    with pytest.raises(RuntimeError):
        sync.send(ALICE, ORCA, payload["links"], payload["request_id"])
    restarted = Sync(
        sync.store, sync.auth, sync.root, discover=lambda: TARGETS, launch=lambda *args: launches.append(args)
    )
    result = restarted.send(ALICE, ORCA, [link["id"]], uuid.uuid4().hex)
    assert not launches and result["uncertain"] == ["Bracket"]
    assert restarted.send(ALICE, ORCA, payload["links"], payload["request_id"])["status"] == "failed"


def test_local_access_and_command_boundaries(local):
    client, _sync, launches = local
    link, _ = linked(client)
    payload = body(link)
    assert client.post("/api/local/send", json=payload).status_code == 401
    assert (
        client.post(
            "/api/local/send", json=payload, headers={**headers(), "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/local/send", json=payload, headers=headers("b")).status_code == 400
    assert (
        client.post(
            "/api/local/send", json={**payload, "command": ["bad.exe"]}, headers=headers()
        ).status_code
        == 422
    )
    assert client.post("/api/local/send", json=body(link, "a" * 32), headers=headers()).status_code == 400
    assert client.post("/api/local/open", headers=headers()).status_code == 401
    assert not launches
    send(client, payload)
    assert (
        client.post("/api/local/send", json={**payload, "slicer": BAMBU}, headers=headers()).status_code
        == 400
    )


def test_local_browser_one_click_send_and_update(local, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    _, sync, launches = local
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    app = create_local_app(
        Settings(origin, str(sync.store.root), "unused", development=True),
        sync.store,
        sync.auth,
        sync.root,
        sync=sync,
    )
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(channel=os.environ.get("OSL_BROWSER_CHANNEL") or None)
            context = browser.new_context(viewport={"width": 520, "height": 1000})
            context.add_init_script("sessionStorage.setItem('slicer-link-session','a'.repeat(40))")
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(origin)
            playwright.expect(page.get_by_text("Step 1 of 3", exact=True)).to_be_visible()
            assert not page.get_by_label("Onshape document link").is_visible()
            page.get_by_label("Send parts to").select_option(ORCA)
            page.get_by_text("Step 2 of 3", exact=True).wait_for()
            page.get_by_role("button", name="Back", exact=True).click()
            assert page.get_by_label("Send parts to").input_value() == ORCA
            page.get_by_role("button", name="Next", exact=True).click()
            page.get_by_label("Onshape document link").fill(
                "https://cad.onshape.com/documents/" + "1" * 24 + "/w/" + "2" * 24 + "/e/" + "3" * 24
            )
            page.get_by_role("button", name="Connect document").click()
            page.get_by_text("Step 3 of 3", exact=True).wait_for()
            page.get_by_role("button", name="Link part", exact=True).click()
            # An unfinished setup reopens at the beginning while retaining its choices.
            page.reload()
            page.get_by_text("Step 1 of 3", exact=True).wait_for()
            assert page.get_by_label("Send parts to").input_value() == ORCA
            page.get_by_role("button", name="Next", exact=True).click()
            assert "/documents/" in page.get_by_label("Onshape document link").input_value()
            page.get_by_role("button", name="Connect document").click()
            page.get_by_text("Step 3 of 3", exact=True).wait_for()
            page.get_by_role("button", name="Send / Update", exact=True).click()
            playwright.expect(page.locator("#status")).to_contain_text("Sent 1 part to OrcaSlicer")
            assert len(launches) == 1 and launches[0][1][0].read_bytes() == DATA
            playwright.expect(page.locator("#send")).to_be_enabled()
            page.get_by_role("button", name="Send / Update", exact=True).click()
            playwright.expect(page.locator("#status")).to_contain_text("Reload from disk in OrcaSlicer")
            assert len(launches) == 1
            page.reload()
            playwright.expect(page.get_by_role("button", name="Change slicer or document")).to_be_visible()
            assert not page.locator("#setup-progress").is_visible()
            assert page.get_by_role("button", name="Save STL files locally").count() == 0
            page.screenshot(path=str(tmp_path / "local-send.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()


def test_document_connection_remembers_names_and_choice(local):
    client, sync, _ = local
    doc = client.post(
        "/api/local/document",
        headers=headers(),
        json={"url": "https://cad.onshape.com/documents/" + "1" * 24},
    ).json()
    assert doc["name"] == "My printer bracket" and doc["element_id"] == "3" * 24
    assert doc["studios"] == [{"id": "3" * 24, "name": "Main parts"}]
    client.post("/api/local/slicer", headers=headers(), json={"id": BAMBU})
    sync.auth.cad.request = lambda _: (_ for _ in ()).throw(AssertionError("Unexpected idle CAD call"))
    restored = client.get("/api/local/state", headers=headers()).json()
    assert restored["context"] == doc and restored["slicer"] == BAMBU
    assert client.post("/api/local/studio", headers=headers(), json={"id": "4" * 24}).status_code == 400


def test_failed_signin_shows_recovery_without_echoing_oauth_values(local, monkeypatch):
    client, sync, _ = local

    def fail(*args):
        raise LinkError("private-error-content")

    monkeypatch.setattr(sync.auth, "complete", fail, raising=False)
    result = client.get("/auth/callback?state=private-state&code=private-code")
    assert result.status_code == 400
    assert result.headers["content-type"].startswith("text/html")
    assert "Slicer Link connection setup" in result.text
    assert "private-" not in result.text
    assert result.headers["cache-control"] == "no-store"


def test_setup_restart_requires_local_auth_and_exit_requires_native_control(local, monkeypatch):
    from slicer_link import platforms

    _client, sync, _launches = local
    launches, stops = [], []
    monkeypatch.setattr(platforms, "launch", launches.append)
    app = create_local_app(
        Settings("http://127.0.0.1:8767", str(sync.store.root), "unused", development=True),
        sync.store,
        sync.auth,
        sync.root,
        sync=sync,
        control_token="test-native-control",
        stop=lambda: stops.append(True),
    )
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        assert client.post("/api/local/setup").status_code == 401
        hostile = {**headers(), "Origin": "https://evil.example"}
        assert client.post("/api/local/setup", headers=hostile).status_code == 403
        assert not launches
        assert client.post("/api/local/setup", headers=headers()).status_code == 200
        assert launches == [platforms.local_command() + ["--setup"]]
        assert client.post("/api/local/exit", headers=headers()).status_code == 401
        native = {"Authorization": "Bearer test-native-control"}
        assert (
            client.post("/api/local/exit", headers={**native, "Origin": "https://evil.example"}).status_code
            == 403
        )
        assert not stops
        assert client.post("/api/local/exit", headers=native).status_code == 200
        assert stops == [True]


def test_saved_project_sources_update_without_rewriting_project(local, tmp_path):
    from zipfile import ZipFile

    client, sync, launches = local
    link, _ = linked(client)
    send(client, body(link))
    project = tmp_path / "my-project.3mf"
    with ZipFile(project, "w") as archive:
        archive.writestr("Metadata/model_settings.config", "<config/>")
    before = project.read_bytes()
    sync.connect_project(ALICE, ORCA, link["source"], project)
    send(client, body(link))
    assert (project.parent / link["filename"]).read_bytes() == DATA
    assert project.read_bytes() == before and len(launches) == 1
    (project.parent / link["filename"]).write_bytes(b"outside edit")
    result = send(client, body(link))
    assert result["status"] == "failed"
    assert (project.parent / link["filename"]).read_bytes() == b"outside edit"
    assert project.read_bytes() == before


@pytest.mark.parametrize(
    "address",
    [
        "http://localhost:8000/secret",
        "https://evil.example/documents/" + "1" * 24,
        "https://cad.onshape.com@evil.example/documents/" + "1" * 24,
        "https://cad.onshape.com/documents/" + "1" * 24 + "/v/" + "2" * 24,
    ],
)
def test_document_rejects_arbitrary_urls_before_request(address):
    class Client:
        def request(self, path):
            raise AssertionError("Must not fetch this URL")

    with pytest.raises(LinkError):
        resolve(Client(), address)
