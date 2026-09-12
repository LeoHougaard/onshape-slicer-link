"""Real browser + HTTP service + helper file transfer, with a fake CAD provider."""

import os
import socket
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
import uvicorn
from cryptography.fernet import Fernet
from test_service import paired
from test_service import system as system  # noqa: PLC0414 -- re-export the pytest fixture

from slicer_link.auth import Auth
from slicer_link.helper import Remote, transfer
from slicer_link.service import Settings, create_app
from slicer_link.store import Store


def test_panel_through_real_http_and_helper(system, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    client, store, auth = system
    pair = paired(client)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    app = create_app(Settings(origin, str(store.root), "unused", development=True), store=store, auth=auth)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as runner:
            browser = runner.chromium.launch(channel=os.environ.get("OSL_BROWSER_CHANNEL") or None)
            context = browser.new_context(viewport={"width": 360, "height": 1000}, reduced_motion="reduce")
            context.add_init_script("sessionStorage.setItem('slicer-link-session', 'a'.repeat(40))")
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(
                origin + "/?documentId=" + "1" * 24 + "&workspaceId=" + "2" * 24 + "&elementId=" + "3" * 24
            )
            page.get_by_role("button", name="Choose parts").click()
            page.get_by_role("button", name="Link part", exact=True).click()
            page.get_by_label("Bracket Default configuration").wait_for()
            page.get_by_role("button", name="Refresh selected parts").click()
            handoff = page.get_by_role("link", name="Open helper")
            playwright.expect(handoff).to_have_attribute(
                "href", __import__("re").compile("onshape-slicer-link://job/[a-f0-9]{32}")
            )
            identity = handoff.get_attribute("href").rsplit("/", 1)[1]
            remote = Remote(origin, pair["token"], development=True)
            result = transfer(remote, identity, tmp_path / "project")
            assert result["acknowledged"] and result["changed"] == 1
            playwright.expect(page.locator("#job-status")).to_contain_text(
                "1 source file updated", timeout=10000
            )
            assert auth.cad.calls == ["revision", "parts", "revision", "export"]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            output = Path("artifacts/stock/browser")
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / "panel-360.png"), full_page=True)
            page.set_viewport_size({"width": 320, "height": 900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()


def test_popup_oauth_and_pairing_without_cookies(tmp_path, monkeypatch):
    playwright = pytest.importorskip("playwright.sync_api")
    from slicer_link import auth as auth_module

    monkeypatch.setattr(auth_module.Client, "request", lambda client, path: {"id": "a" * 24})
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    store = Store(tmp_path / "auth", Fernet.generate_key())
    auth = Auth(
        store,
        "test-client",
        "test-secret",
        origin,
        lambda fields: {
            "access_token": "cad-access-must-stay-server-side",
            "refresh_token": "cad-refresh",
            "expires_in": 3600,
        },
    )
    app = create_app(Settings(origin, str(store.root), "unused", development=True), store=store, auth=auth)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as runner:
            browser = runner.chromium.launch(channel=os.environ.get("OSL_BROWSER_CHANNEL") or None)
            context = browser.new_context()

            # Emulate only the provider consent response. Our state, callback,
            # popup messaging, nonce exchange, sessions, and pairing are real.
            def consent(route):
                state = parse_qs(urlsplit(route.request.url).query)["state"][0]
                route.fulfill(
                    status=302,
                    headers={
                        "Location": origin
                        + "/auth/callback?"
                        + urlencode({"state": state, "code": "test-code"})
                    },
                )

            context.route("https://oauth.onshape.com/oauth/authorize**", consent)
            pair = Remote(origin, development=True).request("/api/devices", {"name": "My paired PC"})
            page = context.new_page()
            page.goto(pair["url"])
            page.get_by_role("button", name="Connect to Onshape").click()
            page.get_by_role("button", name="Pair this computer").click()
            playwright.expect(page.locator("#notice")).to_contain_text("My paired PC is connected")
            assert Remote(origin, pair["token"], development=True).request("/api/device")["owner"] == "a" * 24
            assert not context.cookies()
            assert "cad-access" not in page.evaluate("JSON.stringify(sessionStorage)")
            assert page.evaluate("sessionStorage.getItem('slicer-link-session').length") >= 32
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        store.close()
