"""FastAPI REST + WebSocket routes for the Codenames game."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from models.enums import BoardSize, Difficulty, Language, TeamColor, PlayerRole
from models.card import BoardConfig
from game.game_manager import GameManager
from server.ws_manager import ConnectionManager

log = logging.getLogger(__name__)
router = APIRouter()
ws_manager = ConnectionManager()

# In-memory game store  (game_id -> GameManager)
_games: dict[str, GameManager] = {}


# ── request bodies ──────────────────────────────────────────────────────

class NewGameRequest(BaseModel):
    board_size: int = 25
    difficulty: str = "medium"
    language: str = "en"
    category: str | None = None
    human_team: str = "blue"
    human_role: str = "operative"
    api_key: str | None = None


class ClueRequest(BaseModel):
    game_id: str
    clue: str
    number: int


class GuessRequest(BaseModel):
    game_id: str
    word: str


class PassRequest(BaseModel):
    game_id: str


# ── helpers ─────────────────────────────────────────────────────────────

def _get_game(game_id: str) -> GameManager:
    mgr = _games.get(game_id)
    if mgr is None:
        raise ValueError(f"Game {game_id} not found")
    return mgr


def _state_payload(mgr: GameManager) -> dict[str, Any]:
    """Build a JSON-serialisable snapshot of the game state."""
    s = mgr.state
    is_spymaster = (
        s.current_team == s.human_team
        and s.human_role == PlayerRole.SPYMASTER
    )
    return {
        "game_id": s.game_id,
        "board": s.get_spymaster_board() if is_spymaster else s.get_public_board(),
        "current_team": s.current_team.value,
        "current_phase": s.current_phase,
        "human_team": s.human_team.value,
        "human_role": s.human_role.value,
        "red_remaining": s.red_remaining,
        "blue_remaining": s.blue_remaining,
        "guesses_remaining": s.guesses_remaining,
        "turns_history": [t.model_dump() for t in s.turns_history],
        "game_over": s.game_over,
        "winner": s.winner.value if s.winner else None,
        "whose_turn": mgr.whose_turn(),
    }


async def _run_ai_turns(game_id: str) -> None:
    """Run AI turns in background, broadcasting events via WebSocket."""
    mgr = _get_game(game_id)
    s = mgr.state

    while not s.game_over and not mgr.is_human_turn():
        await ws_manager.broadcast(game_id, "ai_thinking", {"team": s.current_team.value})

        # Run the blocking AI turn off the event loop
        turn_result = await asyncio.to_thread(mgr.run_ai_turn)

        await ws_manager.broadcast(game_id, "ai_turn_complete", turn_result)
        await ws_manager.broadcast(game_id, "state_update", _state_payload(mgr))

        if s.game_over:
            await ws_manager.broadcast(
                game_id, "game_over",
                {"winner": s.winner.value if s.winner else None},
            )
            break


# ── REST endpoints ──────────────────────────────────────────────────────

@router.post("/api/game/new")
async def new_game(req: NewGameRequest):
    api_key = req.api_key or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return {"error": "No API key provided"}

    config = BoardConfig(
        size=BoardSize(req.board_size),
        difficulty=Difficulty(req.difficulty),
        language=Language(req.language),
        category=req.category or None,
    )
    human_team = TeamColor(req.human_team)
    human_role = PlayerRole(req.human_role)

    mgr = GameManager(api_key=api_key)
    state = await asyncio.to_thread(mgr.new_game, config, human_team, human_role)
    _games[state.game_id] = mgr

    # If opponent starts, kick off AI turns in background
    if not mgr.is_human_turn():
        asyncio.create_task(_run_ai_turns(state.game_id))

    return _state_payload(mgr)


@router.get("/api/game/{game_id}/state")
async def get_state(game_id: str):
    try:
        mgr = _get_game(game_id)
    except ValueError as e:
        return {"error": str(e)}
    return _state_payload(mgr)


@router.post("/api/game/clue")
async def submit_clue(req: ClueRequest):
    try:
        mgr = _get_game(req.game_id)
    except ValueError as e:
        return {"error": str(e)}

    result = mgr.submit_human_clue(req.clue, req.number)
    if result.get("success"):
        await ws_manager.broadcast(req.game_id, "clue_given", result)
        await ws_manager.broadcast(req.game_id, "state_update", _state_payload(mgr))

        # If AI teammate is the Operative, run its guesses
        if not mgr.is_human_turn() and not mgr.state.game_over:
            asyncio.create_task(_run_ai_turns(req.game_id))

    return result


@router.post("/api/game/guess")
async def submit_guess(req: GuessRequest):
    try:
        mgr = _get_game(req.game_id)
    except ValueError as e:
        return {"error": str(e)}

    result = mgr.submit_human_guess(req.word)
    if result.get("success"):
        await ws_manager.broadcast(req.game_id, "guess_made", result)
        await ws_manager.broadcast(req.game_id, "state_update", _state_payload(mgr))

        # If turn switched to opponent, run their full turn
        if not mgr.is_human_turn() and not mgr.state.game_over:
            asyncio.create_task(_run_ai_turns(req.game_id))

    return result


@router.post("/api/game/pass")
async def pass_turn(req: PassRequest):
    try:
        mgr = _get_game(req.game_id)
    except ValueError as e:
        return {"error": str(e)}

    result = mgr.pass_turn()
    await ws_manager.broadcast(req.game_id, "turn_change", result)
    await ws_manager.broadcast(req.game_id, "state_update", _state_payload(mgr))

    if not mgr.is_human_turn() and not mgr.state.game_over:
        asyncio.create_task(_run_ai_turns(req.game_id))

    return result


# ── WebSocket ───────────────────────────────────────────────────────────

@router.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await ws_manager.connect(game_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "status":
                try:
                    mgr = _get_game(game_id)
                    await websocket.send_json({
                        "event": "state_update",
                        "data": _state_payload(mgr),
                    })
                except ValueError:
                    await websocket.send_json({"event": "error", "data": "Game not found"})
    except WebSocketDisconnect:
        ws_manager.disconnect(game_id, websocket)
