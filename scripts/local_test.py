"""Run a free, loopback-only test using Leo's existing Windows test-account grant.

No new OAuth registration, hosting, tunnel, installer, or slicer modification.
This launcher deliberately uses the existing development environment.
"""

import html
import json
import secrets
import socket
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import uvicorn
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from companion.auth_probe import protect, read_config
from companion.export_part import decode_source
from slicer_link.auth import Auth, token_request
from slicer_link.files import atomic_write
from slicer_link.helper import Remote, transfer
from slicer_link.model import digest, require
from slicer_link.onshape import Client
from slicer_link.service import WEB, Settings, create_app
from slicer_link.store import Store

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "artifacts/local-test"
ORIGIN = "http://127.0.0.1:8767"

LOCAL_SCRIPT = r"""
"use strict";
(async () => {
  const hash = new URLSearchParams(location.hash.slice(1));
  if (hash.has("local-code")) {
    history.replaceState(null, "", location.pathname + location.search);
    const response = await fetch("/api/session", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({code: hash.get("local-code"), nonce: hash.get("nonce")})});
    const value = await response.json();
    if (!response.ok) throw new Error("Local sign-in expired. Restart Start local test.cmd.");
    sessionStorage.setItem("slicer-link-session", value.token);
    location.reload(); return;
  }
  document.getElementById("connect").onclick = event => {
    event.stopImmediatePropagation();
    document.getElementById("notice").hidden = false;
    document.getElementById("notice").textContent = "Restart Start local test.cmd to reconnect the existing test account.";
  };
  document.getElementById("local-stop").addEventListener("click", async () => {
    const response = await fetch("/api/local/stop", {method: "POST",
      headers: {Authorization: `Bearer ${sessionStorage.getItem("slicer-link-session")}`}});
    if (response.ok) document.body.textContent = "Local test stopped. Run Start local test.cmd to start again.";
  });
  const handoff = document.getElementById("handoff");
  handoff.textContent = "Save STL files locally";
  handoff.addEventListener("click", async event => {
    event.preventDefault();
    const id = new URL(handoff.href).pathname.slice(1);
    handoff.style.pointerEvents = "none";
    try {
      const response = await fetch(`/api/local/save/${id}`, {method: "POST",
        headers: {Authorization: `Bearer ${sessionStorage.getItem("slicer-link-session")}`}});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || value.detail || "Save failed.");
      document.getElementById("job-status").textContent = "Files saved. Import the STL once, then use Reload from disk after later refreshes.";
    } catch (error) {
      document.getElementById("notice").hidden = false;
      document.getElementById("notice").textContent = error.message;
    } finally { handoff.style.pointerEvents = ""; }
  });
})().catch(error => {
  document.getElementById("notice").hidden = false;
  document.getElementById("notice").textContent = error.message;
});
"""


def main():
    # Reserve the address before reading credentials or modifying local state.
    listener = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", 8767))
        listener.listen()
    except OSError:
        listener.close()
        raise SystemExit("Port 8767 is already in use. Close the existing local test first.") from None

    evidence = json.loads((ROOT / "artifacts/onshape/auth-results.json").read_text())
    require(
        evidence.get("account_context", "").startswith("Replacement test application; previous credentials"),
        "Only the confirmed replacement test account may be used.",
    )
    client_id, client_secret, base = read_config(ROOT / ".env")
    token_file = ROOT / "artifacts/onshape/tokens.dpapi"
    stored = json.loads(protect(token_file.read_bytes(), decrypt=True))
    require(
        stored["client_id"] == client_id and stored["base_url"] == base == "https://cad.onshape.com",
        "The test application and stored grant do not match.",
    )
    DATA.mkdir(parents=True, exist_ok=True)
    key_file = DATA / "key.dpapi"
    if not key_file.exists():
        atomic_write(key_file, protect(Fernet.generate_key()))
    key = protect(key_file.read_bytes(), decrypt=True)
    store = Store(DATA / "service", key)

    def transport(fields):
        tokens = token_request(fields)
        if "access_token" in tokens and "refresh_token" in tokens:
            stored.update(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                expires_at=time.time() + tokens["expires_in"],
            )
            atomic_write(token_file, protect(json.dumps(stored).encode()))
        return tokens

    if stored["expires_at"] <= time.time() + 120:
        transport(
            {
                "grant_type": "refresh_token",
                "refresh_token": stored["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
    identity = store.get("local", "identity")
    if not identity:
        info = Client(stored["access_token"]).request("/api/v16/users/sessioninfo")
        owner = info.get("id") or info.get("userId")
        require(isinstance(owner, str) and len(owner) == 24, "Onshape did not identify the test account.")
        identity = {"owner": owner, "client_id": client_id}
        store.put("local", "identity", owner, identity)
        store.record_request(owner, 200)
    require(identity["client_id"] == client_id, "This local test belongs to a different application.")
    owner = identity["owner"]
    store.put(
        "account",
        owner,
        owner,
        {
            "id": owner,
            "tokens": store.encrypt(
                {field: stored[field] for field in ("access_token", "refresh_token", "expires_at")}
            ),
        },
    )
    auth = Auth(store, client_id, client_secret, ORIGIN, transport=transport)
    device_token = secrets.token_urlsafe(32)
    device_id = uuid.uuid5(uuid.NAMESPACE_URL, ORIGIN + owner).hex
    previous = store.get("computer", device_id)
    if previous:
        store.delete("device", previous["key"])
    device_key = digest(device_token.encode())
    store.put("device", device_key, owner, {"id": device_id, "name": "This computer", "owner": owner})
    store.put("computer", device_id, owner, {"owner": owner, "key": device_key})
    folder = DATA / "project"
    folder.mkdir(exist_ok=True)
    app = create_app(Settings(ORIGIN, str(store.root), key, development=True), store=store, auth=auth)

    @app.middleware("http")
    async def local_host(request, call_next):
        if request.headers.get("host") != "127.0.0.1:8767":
            return JSONResponse({"error": "Unexpected local address."}, status_code=403)
        return await call_next(request)

    async def panel(request):
        content = (WEB / "index.html").read_text(encoding="utf-8")
        note = (
            "<section><p>Local test. Save STL files to "
            + html.escape(str(folder))
            + ". Keep this test running while you refresh.</p>"
            + '<button id="local-stop">Stop local test</button></section>'
        )
        content = content.replace("<footer>", note + "<footer>")
        content = content.replace("</body>", '<script src="/local-script.js"></script></body>')
        return HTMLResponse(content)

    app.router.routes.insert(0, Route("/", panel))

    @app.get("/local-script.js")
    def local_script():
        return Response(LOCAL_SCRIPT, media_type="text/javascript")

    @app.post("/api/local/save/{job}")
    def save(job: str, request: Request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or auth.owner(authorization[7:]) != owner:
            raise HTTPException(401, "Restart the local test to reconnect.")
        return transfer(Remote(ORIGIN, device_token, development=True), job, folder)

    code, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    store.put("login", digest(code.encode()), owner, {"owner": owner, "nonce": nonce}, ttl=120)
    source = decode_source(json.loads((ROOT / "artifacts/onshape/linked-part/current.json").read_text()))
    query = urlencode(
        {
            "documentId": source["document_id"],
            "workspaceId": source["workspace_id"],
            "elementId": source["element_id"],
            "configuration": source["configuration"],
        }
    )
    address = ORIGIN + "/?" + query + "#" + urlencode({"local-code": code, "nonce": nonce})
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False, proxy_headers=False))

    @app.post("/api/local/stop")
    def stop(request: Request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or auth.owner(authorization[7:]) != owner:
            raise HTTPException(401, "Sign in to stop the local test.")
        # Uvicorn waits for active transfers to finish before shutting down.
        server.should_exit = True
        return {"ok": True}

    def open_browser():
        for _ in range(200):
            if server.started:
                webbrowser.open(address)
                return
            time.sleep(0.1)

    threading.Thread(target=open_browser, daemon=True).start()
    print(
        f"Local test: {ORIGIN}\nSTL folder: {folder}\nClose this window or press Ctrl+C to stop.", flush=True
    )
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        store.close()


if __name__ == "__main__":
    main()
