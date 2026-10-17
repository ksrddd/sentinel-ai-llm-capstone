"""FastAPI application factory. Run: ``uvicorn app.main:create_app --factory --port 8000``."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import MAX_REQUEST_BYTES, ROOT_DIR, Settings
from app.core.container import build_container
from app.llm.client import ChatModel

WEB_DIR = ROOT_DIR / "web"

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
# Swagger/ReDoc pages ship an inline bootstrap script and load assets from jsDelivr; the relaxed
# policy is scoped to those two developer pages only, the dashboard keeps the strict CSP.
DOCS_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data: https://fastapi.tiangolo.com "
            "https://cdn.redoc.ly; connect-src 'self'; worker-src blob:; frame-ancestors 'none'; base-uri 'none'")
DOCS_PATHS = ("/docs", "/redoc")


class BodySizeLimit:
    """ASGI middleware: reject request bodies above ``max_bytes`` with 413 before they are parsed.

    Checks the declared Content-Length and also counts streamed (chunked) bodies.
    """

    def __init__(self, app, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    too_big = int(value) > self.max_bytes
                except ValueError:
                    too_big = True
                if too_big:
                    return await self._reject(scope, receive, send)
        if scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        # Buffer at most max_bytes (64 KiB), then replay to the app; covers chunked bodies too.
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                return await self._reject(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body, sent = b"".join(chunks), False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def _reject(self, scope, receive, send):
        response = JSONResponse({"detail": f"request body exceeds {self.max_bytes} bytes"}, status_code=413)
        await response(scope, receive, send)


def create_app(settings: Settings | None = None, llm: ChatModel | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = settings or Settings.from_env()
    app = FastAPI(title="SentinelAI", version="0.1.0",
                  description="LLM-assisted SOC incident triage copilot (academic prototype, synthetic data)")
    app.state.container = build_container(settings, llm)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else \
            response.headers.get("Cache-Control", "no-cache")
        response.headers["Content-Security-Policy"] = DOCS_CSP if request.url.path in DOCS_PATHS else CSP
        return response

    app.add_middleware(BodySizeLimit, max_bytes=MAX_REQUEST_BYTES)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    return app
