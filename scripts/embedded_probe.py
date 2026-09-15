"""Local development Onshape panel and authenticated isolated desktop proxy."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from scripts.embedded_runtime import PORTS, authorization
from slicer_link.model import LinkError

WEB = Path(__file__).resolve().parents[1] / "experiments" / "embedded"
LOG = logging.getLogger(__name__)


class AddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: list[dict[str, str]] = Field(min_length=1, max_length=20)
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")


def desktop_path(kind, path):
    # Reject alternate spellings that an upstream proxy could normalize into
    # its private automation API. Starlette already decodes percent escapes.
    return (
        kind in PORTS
        and not path.startswith(("pelorus", "/"))
        and not any(value in path for value in ("..", "//", "\\", "%"))
    )


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        app.state.authorization = authorization()
        app.state.csrf = secrets.token_urlsafe(32)
        app.state.busy = False
        app.state.cad = None
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            app.state.client = client
            yield
        if app.state.cad:
            app.state.cad.close()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.headers.get("host") != "localhost:8768":
            return JSONResponse({"error": "Unexpected local address."}, status_code=403)
        if request.method not in {"GET", "HEAD"}:
            if request.method != "POST" or request.url.path not in {"/api/orca/add", "/api/bambu/add"}:
                return JSONResponse({"error": "Unsupported operation."}, status_code=405)
            if request.headers.get("origin") != "http://localhost:8768" or not secrets.compare_digest(
                request.headers.get("x-osl-session", ""), app.state.csrf
            ):
                return JSONResponse({"error": "Open Slicer Link to continue."}, status_code=403)
        response = await call_next(request)
        desktop = request.url.path.startswith("/desktop/")
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    "default-src 'self' blob: data:; script-src 'self' blob: 'unsafe-inline' 'wasm-unsafe-eval'; "
                    "style-src 'self' 'unsafe-inline'; connect-src 'self' blob: data: ws://localhost:8768; "
                    "object-src 'none'; base-uri 'none'; frame-ancestors 'self' https://cad.onshape.com"
                    if desktop
                    else "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                    "base-uri 'none'; frame-ancestors https://cad.onshape.com"
                ),
            }
        )
        return response

    @app.get("/")
    def panel():
        return FileResponse(WEB / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "embedding-probe"}

    @app.get("/api/session")
    def session():
        return {"session": app.state.csrf}

    @app.post("/api/{kind}/add")
    async def add(kind: str, body: AddRequest):
        if app.state.busy:
            return JSONResponse({"error": "A slicer operation is already running."}, status_code=409)
        app.state.busy = True
        try:
            if app.state.cad is None:
                from scripts.embedded_cad import Cad

                app.state.cad = Cad()
            return await asyncio.to_thread(app.state.cad.add, kind, body.selections, body.request_id)
        except LinkError as error:
            return JSONResponse({"error": str(error)}, status_code=400)
        except (KeyError, TypeError, ValueError):
            return JSONResponse({"error": "Choose the part again in Onshape."}, status_code=400)
        except Exception:
            LOG.exception("Dedicated slicer import failed")
            return JSONResponse(
                {"error": "Import stopped. Inspect the dedicated slicer before trying again."},
                status_code=500,
            )
        finally:
            app.state.busy = False

    @app.get("/desktop/{kind}/{path:path}")
    async def desktop(request: Request, kind: str, path: str):
        if not desktop_path(kind, path):
            return Response(status_code=404)
        try:
            upstream = await app.state.client.get(
                f"http://127.0.0.1:{PORTS[kind]}/desktop/{kind}/{path}",
                params=request.query_params,
                headers={"Authorization": app.state.authorization},
            )
            return Response(
                upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type"),
            )
        except httpx.HTTPError:
            return Response("The dedicated slicer is not running.", status_code=503)

    @app.websocket("/desktop/{kind}/{path:path}")
    async def desktop_socket(socket: WebSocket, kind: str, path: str):
        if (
            not desktop_path(kind, path)
            or socket.headers.get("host") != "localhost:8768"
            or socket.headers.get("origin") != "http://localhost:8768"
        ):
            await socket.close(code=1008)
            return
        tasks = []
        try:
            async with connect(
                f"ws://127.0.0.1:{PORTS[kind]}/desktop/{kind}/{path}?{socket.url.query}",
                additional_headers={"Authorization": app.state.authorization},
                max_size=32 * 1024 * 1024,
            ) as upstream:
                await socket.accept()

                async def receive():
                    while True:
                        message = await socket.receive()
                        if message["type"] == "websocket.disconnect":
                            return
                        if app.state.busy:
                            continue
                        await upstream.send(
                            message.get("bytes") if message.get("bytes") is not None else message["text"]
                        )

                async def send():
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await socket.send_bytes(message)
                        else:
                            await socket.send_text(message)

                tasks = [asyncio.create_task(receive()), asyncio.create_task(send())]
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
        except (OSError, RuntimeError, ConnectionClosed, InvalidHandshake):
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await socket.close()
            except RuntimeError:
                pass

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app


if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=8768, access_log=False, proxy_headers=False)
