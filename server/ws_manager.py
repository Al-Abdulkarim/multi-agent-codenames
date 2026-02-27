"""WebSocket connection manager for real-time game updates."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    """Track active WebSocket connections per game."""

    def __init__(self) -> None:
        # game_id → set of active websockets
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, game_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(game_id, set()).add(ws)
        log.debug("WS connected: game=%s (total=%d)", game_id, len(self._connections[game_id]))

    def disconnect(self, game_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(game_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del self._connections[game_id]

    async def broadcast(self, game_id: str, event: str, data: Any = None) -> None:
        """Send a JSON message to every client watching *game_id*."""
        message = json.dumps({"event": event, "data": data}, default=str, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in self._connections.get(game_id, set()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(game_id, ws)
