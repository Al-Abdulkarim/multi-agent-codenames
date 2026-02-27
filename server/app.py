"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.routes import router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent Codenames", version="0.1.0")

    # API + WebSocket routes
    app.include_router(router)

    # Serve static frontend files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/")
        async def index():
            return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/favicon.ico")
    async def favicon():
        from fastapi.responses import Response
        return Response(status_code=204)

    return app
