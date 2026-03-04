"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.routes import router
from server.tts_service import TTSService
from config import settings

STATIC_DIR = Path(__file__).resolve().parent.parent / "UI"


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

    # Serve persisted TTS WAV files if TTS is configured.
    tts_service = TTSService(settings.tts)
    app.mount(
        tts_service.serve_base_path,
        StaticFiles(directory=str(tts_service.persist_dir)),
        name="tts-media",
    )

    @app.on_event("startup")
    async def _cleanup_tts_audio() -> None:
        tts_service.cleanup_old_files()

    @app.get("/favicon.ico")
    async def favicon():
        from fastapi.responses import Response

        return Response(status_code=204)

    return app
