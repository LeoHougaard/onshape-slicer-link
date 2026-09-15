"""Browser interface for a service on this computer. Nothing listens on the LAN."""

import secrets
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import Field
from starlette.routing import Route

from . import platforms
from .documents import resolve
from .model import LinkError, digest, require
from .service import WEB, Body, create_app
from .sync import Sync


class Send(Body):
    slicer: str = Field(pattern=r"^[a-f0-9]{32}$")
    links: list[str] = Field(min_length=1, max_length=100)
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    reopen: bool = False


class SlicerPath(Body):
    name: str
    path: str = Field(min_length=1, max_length=4096)


class Document(Body):
    url: str = Field(min_length=1, max_length=16384)


class Choice(Body):
    id: str = Field(min_length=24, max_length=32)


def login_address(store, owner, origin):
    code, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    store.put("login", digest(code.encode()), owner, {"owner": owner, "nonce": nonce}, ttl=120)
    return origin + "/#" + urlencode({"local-code": code, "nonce": nonce})


def create_local_app(
    settings,
    store,
    auth,
    models,
    *,
    sync=None,
    stop=lambda: None,
    reopen=lambda: None,
    control_token="",
    connected=lambda owner: None,
):
    parsed = urlsplit(settings.origin)
    require(parsed.hostname in {"127.0.0.1", "localhost"}, "The local app must use a loopback address.")
    sync = sync or Sync(store, auth, models)
    app = create_app(settings, store=store, auth=auth, exporter=sync.exporter)
    app.state.sync = sync

    @app.middleware("http")
    async def local_boundary(request, call_next):
        if request.headers.get("host") != parsed.netloc:
            return JSONResponse({"error": "Unexpected local address."}, status_code=403)
        return await call_next(request)

    def account(request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Open Slicer Link from its desktop shortcut to connect.")
        try:
            return auth.owner(authorization[7:])
        except LinkError:
            raise HTTPException(401, "Open Slicer Link from its desktop shortcut to reconnect.") from None

    async def panel(request):
        return FileResponse(WEB / "local.html")

    app.router.routes.insert(0, Route("/", panel))

    def callback(request):
        values = request.query_params
        require(len(values.get("state", "")) <= 256, "Invalid sign-in state.")
        code, nonce = auth.complete(values.get("state", ""), values.get("code", ""))
        pending = store.get("login", digest(code.encode()))
        connected(pending["owner"])
        return RedirectResponse(settings.origin + "/#" + urlencode({"local-code": code, "nonce": nonce}))

    app.router.routes.insert(0, Route("/auth/callback", callback))

    @app.get("/api/local/state")
    def state(request: Request):
        owner = account(request)
        choice = store.get("slicer-choice", owner) or {}
        context = store.get("local-context", owner) or {}
        project = {}
        if context.get("document_id") and choice.get("id"):
            project = store.get("slicer-project", sync.project_key(owner, choice["id"], context)) or {}
        return {
            "slicers": [{"id": t["id"], "name": t["name"]} for t in sync.targets(owner).values()],
            "slicer": choice.get("id", ""),
            "context": context,
            "project": project,
            "setup_complete": bool(store.get("local-onboarding", owner)),
        }

    @app.post("/api/local/slicer-path")
    def slicer_path(body: SlicerPath, request: Request):
        sync.choose_path(account(request), body.path, body.name)
        return {"ok": True}

    @app.post("/api/local/browse-slicer")
    def browse_slicer(request: Request):
        account(request)
        return {"path": platforms.pick_slicer()}

    @app.post("/api/local/project")
    def project(body: Choice, request: Request):
        owner = account(request)
        context = store.get("local-context", owner)
        require(context and context.get("document_id"), "Connect your Onshape document first.")
        path = platforms.pick_slicer("project")
        return sync.connect_project(owner, body.id, context, path) if path else {"cancelled": True}

    @app.post("/api/local/slicer")
    def choose_slicer(body: Choice, request: Request):
        owner = account(request)
        require(body.id in sync.targets(owner), "Choose an installed slicer.")
        store.put("slicer-choice", owner, owner, {"id": body.id})
        return {"ok": True}

    @app.post("/api/local/document")
    def document(body: Document, request: Request):
        owner = account(request)
        context = resolve(auth.client(owner), body.url)
        store.put("local-context", owner, owner, context)
        return context

    @app.post("/api/local/studio")
    def studio(body: Choice, request: Request):
        owner = account(request)
        context = store.get("local-context", owner) or {}
        require(
            any(tab["id"] == body.id for tab in context.get("studios", [])), "Connect the document first."
        )
        if context.get("element_id") != body.id:
            context.update(element_id=body.id, configuration="")
        store.put("local-context", owner, owner, context)
        return context

    @app.post("/api/local/send")
    def send(body: Send, request: Request):
        owner = account(request)
        result = sync.send(owner, body.slicer, body.links, body.request_id, reopen=body.reopen)
        if result["status"] == "ready" and not result["uncertain"]:
            store.put("local-onboarding", owner, owner, {"complete": True})
        return result

    @app.post("/api/local/stop")
    def shutdown(request: Request):
        account(request)
        stop()
        return {"ok": True}

    def launcher(request):
        # Only the native launcher has this secret. A web page cannot request
        # a new authenticated window by visiting the loopback server.
        if not control_token or not secrets.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + control_token
        ):
            raise HTTPException(401, "Use the desktop shortcut to open Slicer Link.")

    @app.post("/api/local/open")
    def open_existing(request: Request):
        launcher(request)
        reopen()
        return {"ok": True}

    @app.post("/api/local/exit")
    def exit_for_setup(request: Request):
        launcher(request)
        stop()
        return {"ok": True}

    @app.post("/api/local/setup")
    def connection_setup(request: Request):
        account(request)
        platforms.launch(platforms.local_command() + ["--setup"])
        return {"ok": True}

    return app
