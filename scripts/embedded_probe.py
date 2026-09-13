"""Local-only Onshape iframe probe. No credentials, CAD requests or slicer input."""

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

WEB = Path(__file__).resolve().parents[1] / "experiments" / "embedded"


def create_app():
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.headers.get("host") != "localhost:8768":
            return JSONResponse({"error": "Unexpected local address."}, status_code=403)
        if request.method not in {"GET", "HEAD"}:
            return JSONResponse({"error": "This probe is read-only."}, status_code=405)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
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

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app


if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=8768, access_log=False, proxy_headers=False)
