"""One-process Onshape application. Run behind HTTPS with a persistent data volume."""

import json
import logging
import os
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .auth import Auth
from .model import LinkError, Source, digest, link_filename, object_id, require, service_origin
from .onshape import Exporter
from .store import Store

WEB = Path(__file__).with_name("web")
LOG = logging.getLogger(__name__)


@dataclass
class Settings:
    origin: str
    data_dir: str
    encryption_key: str
    client_id: str = ""
    client_secret: str = ""
    development: bool = False

    def __post_init__(self):
        self.origin = service_origin(self.origin, development=self.development)

    @classmethod
    def environment(cls):
        return cls(
            os.environ["OSL_ORIGIN"],
            os.environ.get("OSL_DATA_DIR", "data"),
            os.environ["OSL_ENCRYPTION_KEY"],
            os.environ.get("ONSHAPE_CLIENT_ID", ""),
            os.environ.get("ONSHAPE_CLIENT_SECRET", ""),
            os.environ.get("OSL_DEVELOPMENT") == "1",
        )


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Body):
    code: str = Field(min_length=1, max_length=256)
    nonce: str = Field(min_length=32, max_length=128)


class Pairing(Body):
    name: str = Field(min_length=1, max_length=80)


class PairClaim(Body):
    code: str = Field(min_length=32, max_length=128)


class Selection(Body):
    document_id: str
    workspace_id: str
    element_id: str
    configuration: str = Field(default="", max_length=8192)


class AddLink(Body):
    selection: str = Field(min_length=32, max_length=32)
    part_id: str = Field(min_length=1, max_length=4096)


class Refresh(Body):
    device: str = Field(min_length=32, max_length=32)
    links: list[str] = Field(min_length=1, max_length=100)
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class Receipt(Body):
    changed: int = Field(ge=0, le=100)


def create_app(settings, *, store=None, auth=None, exporter=None):
    own_store = store is None
    store = store or Store(settings.data_dir, settings.encryption_key)
    auth = auth or Auth(store, settings.client_id, settings.client_secret, settings.origin)
    exporter = exporter or Exporter(store)
    lock = threading.RLock()
    # A queued job interrupted by a restart requires an explicit new refresh.
    for job in store.list("job"):
        if job["status"] == "preparing":
            job.update(
                status="failed", error="The service restarted. Refresh again; existing files were retained."
            )
            store.put("job", job["id"], job["owner"], job, ttl=86400)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if own_store:
            store.close()

    app = FastAPI(title="Onshape Slicer Link", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.store, app.state.auth = store, auth

    @app.middleware("http")
    async def boundaries(request, call_next):
        # All app writes use bearer authorization. Cross-origin browser writes
        # are also rejected; there is intentionally no CORS configuration.
        if request.method not in {"GET", "HEAD"}:
            if request.headers.get("origin") not in {None, settings.origin}:
                return JSONResponse({"error": "Unexpected application origin."}, status_code=403)
            # Bound chunked requests too. Restore the body for FastAPI parsing.
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 128 * 1024:
                    return JSONResponse({"error": "Request is too large."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors https://cad.onshape.com; form-action 'self'"
        )
        return response

    @app.exception_handler(LinkError)
    async def link_error(request, error):
        return JSONResponse({"error": str(error)}, status_code=400)

    def bearer(request):
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer ") or not 32 <= len(value[7:]) <= 256:
            raise HTTPException(401, "Connect to continue.")
        return value[7:]

    def owner(request):
        try:
            return auth.owner(bearer(request))
        except LinkError:
            raise HTTPException(401, "Connect to Onshape to continue.") from None

    def device(request, *, paired=True):
        record = store.get("device", digest(bearer(request).encode()))
        if not record or (paired and not record.get("owner")):
            raise HTTPException(401, "Pair this computer with Onshape first.")
        return record

    def owned(kind, identity, account):
        record = store.get(kind, identity)
        if not record or record.get("owner") != account:
            raise HTTPException(404, "Item not found.")
        return record

    def throttle(key, count, seconds):
        # Persist limits across restarts; clean expired records with each write.
        with lock:
            record = store.get("limit", key) or {"count": 0, "until": time.time() + seconds}
            if record["count"] >= count:
                raise HTTPException(429, "Wait before trying again.")
            record["count"] += 1
            store.put("limit", key, "", record, ttl=max(1, record["until"] - time.time()))

    @app.get("/health")
    def health():
        return {"status": "ok", "protocol": 1}

    @app.get("/")
    @app.get("/pair")
    def panel():
        return FileResponse(WEB / "index.html")

    @app.get("/auth/start")
    def start(request: Request, nonce: str):
        throttle("login:" + (request.client.host if request.client else "unknown"), 20, 600)
        return {"url": auth.begin(nonce)}

    @app.get("/auth/callback", response_class=HTMLResponse)
    def callback(state: str = "", code: str = ""):
        require(len(state) <= 256, "Invalid sign-in state.")
        login, nonce = auth.complete(state, code)
        # JSON is carried in an escaped attribute, never executable inline JS.
        import html

        payload = html.escape(json.dumps({"code": login, "nonce": nonce}), quote=True)
        return HTMLResponse(
            f'<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<title>Connected</title><body data-login="{payload}">'
            "<p>Completing sign-in. You can close this window after it finishes.</p>"
            '<script src="/static/callback.js"></script></body></html>'
        )

    @app.post("/api/session")
    def session(body: Login):
        return {"token": auth.exchange(body.code, body.nonce)}

    @app.delete("/api/session")
    def logout(request: Request):
        store.delete("session", digest(bearer(request).encode()))
        return {"ok": True}

    @app.get("/api/state")
    def state(request: Request):
        account = owner(request)
        devices = [{k: row[k] for k in ("id", "name")} for row in store.list("device", account)]
        return {
            "account": account,
            "links": store.list("link", account),
            "devices": devices,
            "usage": store.usage(account),
        }

    @app.post("/api/devices")
    def pair_begin(body: Pairing, request: Request):
        throttle("pair:" + (request.client.host if request.client else "unknown"), 10, 600)
        token, code, identity = secrets.token_urlsafe(32), secrets.token_urlsafe(32), uuid.uuid4().hex
        key = digest(token.encode())
        store.put("device", key, "", {"id": identity, "name": body.name, "owner": ""}, ttl=600)
        store.put("pair", digest(code.encode()), "", {"key": key}, ttl=600)
        return {"token": token, "id": identity, "url": settings.origin + "/pair#" + code}

    @app.post("/api/devices/claim")
    def pair_claim(body: PairClaim, request: Request):
        account = owner(request)
        with lock:
            require(len(store.list("device", account)) < 10, "Remove an old computer before adding another.")
            pair = store.consume("pair", digest(body.code.encode()))
            require(pair, "Pairing expired or was already used. Start setup again.")
            record = store.get("device", pair["key"])
            require(record and not record["owner"], "This computer is already paired.")
            record["owner"] = account
            store.put("device", pair["key"], account, record)
            # Index without the token hash, for account-authorized lookup.
            store.put("computer", record["id"], account, {"owner": account, "key": pair["key"]})
            return {"id": record["id"], "name": record["name"]}

    @app.get("/api/device")
    def device_status(request: Request):
        return device(request, paired=False)

    @app.delete("/api/devices/{identity}")
    def device_remove(identity: str, request: Request):
        record = owned("computer", identity, owner(request))
        store.delete("device", record["key"])
        store.delete("computer", identity)
        return {"ok": True}

    @app.post("/api/selection")
    def selection(body: Selection, request: Request):
        account = owner(request)
        throttle("selection:" + account, 20, 60)
        client = auth.client(account)
        document, workspace, element = map(object_id, (body.document_id, body.workspace_id, body.element_id))
        revision = client.microversion(document, workspace)
        source = Source(document, workspace, element, revision, "placeholder", body.configuration)
        parts = client.parts(source)
        catalog = []
        for part in parts:
            # A mesh export requires a solid body. Sheets and composites need an explicit later design.
            if (
                part.get("bodyType") == "solid"
                and not part.get("isMesh")
                and not part.get("isComposite")
                and isinstance(part.get("partId"), str)
            ):
                selected = replace(source, part_id=part["partId"])
                catalog.append({"id": selected.part_id, "name": str(part.get("name", "Part"))[:200]})
        identity = uuid.uuid4().hex
        store.put(
            "selection",
            identity,
            account,
            {"owner": account, "source": source.to_dict(), "parts": catalog},
            ttl=900,
        )
        return {"id": identity, "parts": catalog}

    @app.post("/api/links")
    def link_add(body: AddLink, request: Request):
        account = owner(request)
        with lock:
            catalog = owned("selection", body.selection, account)
            selected = next((part for part in catalog["parts"] if part["id"] == body.part_id), None)
            require(selected, "Load the parts again and choose a solid part.")
            source = replace(Source(**catalog["source"]), part_id=body.part_id)
            links = store.list("link", account)
            for link in links:
                if link["source"] == source.to_dict():
                    return link
            require(len(links) < 100, "This account already has 100 links.")
            identity = uuid.uuid4().hex
            link = {
                "id": identity,
                "owner": account,
                "name": selected["name"],
                "filename": link_filename(selected["name"], identity),
                "source": source.to_dict(),
            }
            store.put("link", identity, account, link)
            return link

    @app.delete("/api/links/{identity}")
    def link_remove(identity: str, request: Request):
        owned("link", identity, owner(request))
        store.delete("link", identity)
        return {"ok": True}

    def prepare(job):
        try:
            prepared = exporter.refresh(job["owner"], auth.client(job["owner"]), job["links"])
            job.update(status="prepared", links=prepared)
        except LinkError as error:
            job.update(status="failed", error=str(error))
        except Exception:
            LOG.exception("Export failed for job %s", job["id"])
            job.update(status="failed", error="The export failed. Existing files were retained. Try again.")
        store.put("job", job["id"], job["owner"], job, ttl=86400)

    @app.post("/api/jobs")
    def refresh(body: Refresh, request: Request, tasks: BackgroundTasks):
        account = owner(request)
        with lock:
            owned("computer", body.device, account)
            previous = store.get("job", body.request_id)
            if previous:
                require(
                    previous["owner"] == account
                    and previous["device"] == body.device
                    and [row["id"] for row in previous["links"]] == body.links,
                    "Refresh identifier was already used.",
                )
                return {"id": previous["id"], "status": previous["status"]}
            require(len(set(body.links)) == len(body.links), "A refresh includes a duplicated link.")
            require(
                not any(job["status"] == "preparing" for job in store.list("job", account)),
                "A refresh is already running. Wait for it to finish.",
            )
            throttle("refresh:" + account, 10, 60)
            links = [owned("link", identity, account) for identity in body.links]
            job = {
                "id": body.request_id,
                "owner": account,
                "device": body.device,
                "links": links,
                "status": "preparing",
                "created": time.time(),
            }
            store.put("job", job["id"], account, job, ttl=86400)
            tasks.add_task(prepare, job)
            return {"id": job["id"], "status": "preparing"}

    def transfer(identity, request):
        computer = device(request)
        job = owned("job", identity, computer["owner"])
        if job["device"] != computer["id"]:
            raise HTTPException(404, "Transfer not found.")
        return job

    @app.get("/api/jobs/{identity}")
    def job_status(identity: str, request: Request):
        job = owned("job", identity, owner(request))
        return {key: job[key] for key in ("id", "status", "error", "changed") if key in job}

    @app.get("/api/transfers/{identity}")
    def job_transfer(identity: str, request: Request):
        return transfer(identity, request)

    @app.get("/api/transfers/{identity}/meshes/{sha}")
    def mesh(identity: str, sha: str, request: Request):
        job = transfer(identity, request)
        require(
            job["status"] in {"prepared", "delivered"}
            and any(row.get("sha256") == sha for row in job["links"]),
            "Model is not part of this transfer.",
        )
        return FileResponse(exporter.meshes / (sha + ".stl"), media_type="application/octet-stream")

    @app.post("/api/transfers/{identity}/receipt")
    def receipt(identity: str, body: Receipt, request: Request):
        with lock:
            job = transfer(identity, request)
            require(job["status"] in {"prepared", "delivered"}, "This transfer is not ready.")
            if job["status"] != "delivered":
                job.update(status="delivered", changed=body.changed)
                store.put("job", job["id"], job["owner"], job, ttl=86400)
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app


def main():
    import uvicorn

    uvicorn.run(
        create_app(Settings.environment()),
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8767")),
        access_log=False,
    )


if __name__ == "__main__":
    main()
