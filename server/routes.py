"""FastAPI REST + WebSocket routes for the Codenames game."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
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
    team: str = "red"  # New UI uses 'team' instead of 'human_team'
    role: str = "operative"  # New UI uses 'role' instead of 'human_role'
    api_key: str | None = None


class ClueRequest(BaseModel):
    clue: str
    number: int


class GuessRequest(BaseModel):
    word: str


class ChatRequest(BaseModel):
    message: str


# ── helpers ─────────────────────────────────────────────────────────────


def _get_game(game_id: str) -> GameManager:
    mgr = _games.get(game_id)
    if mgr is None:
        raise ValueError(f"Game {game_id} not found")
    return mgr


def _state_payload(mgr: GameManager) -> dict[str, Any]:
    """Build a JSON-serialisable snapshot of the game state."""
    s = mgr.state
    is_spymaster = s.human_role == PlayerRole.SPYMASTER
    show_full_board = is_spymaster or s.game_over

    # New UI expects 'clue' at top level
    current_clue = None
    if s.current_phase == "guess" and s.turns_history:
        last_turn = s.turns_history[-1]
        if last_turn.clue:
            current_clue = {
                "word": last_turn.clue.word,
                "number": last_turn.clue.number,
            }

    return {
        "game_id": s.game_id,
        "board": [
            {
                "word": c["word"],
                "revealed": c["revealed"],
                "type": c["card_type"],  # UI expects 'type' instead of 'card_type'
            }
            for c in (
                s.get_spymaster_board() if show_full_board else s.get_public_board()
            )
        ],
        "current_turn": s.current_team.value,  # UI expects 'current_turn'
        "status": "game_over" if s.game_over else "playing",  # UI expects 'status'
        "human_team": s.human_team.value,
        "human_role": s.human_role.value,
        "red_remaining": s.red_remaining,
        "blue_remaining": s.blue_remaining,
        "clue": current_clue,
        "guesses_remaining": s.guesses_remaining,
        "turns_history": [t.model_dump() for t in s.turns_history],
        "winner": s.winner.value if s.winner else None,
        "whose_turn": mgr.whose_turn(),
        "chat_messages": [
            {
                "sender": m["agent"].capitalize() if m["agent"] != "human" else "You",
                "team": m["team"],
                "message": m["message"],
                "timestamp": datetime.fromtimestamp(m["timestamp"]).isoformat(),
            }
            for m in mgr.chat_messages
        ],
        "agent_logs": mgr.agent_logs,
    }


async def _run_ai_turns(game_id: str) -> None:
    """Run AI turns in background, broadcasting events via WebSocket."""
    mgr = _get_game(game_id)
    s = mgr.state

    while not s.game_over and not mgr.is_human_turn():
        await ws_manager.broadcast(
            game_id, "ai_thinking", {"team": s.current_team.value}
        )

        # Run the blocking AI turn off the event loop
        turn_result = await asyncio.to_thread(mgr.run_ai_turn)

        await ws_manager.broadcast(game_id, "ai_turn_complete", turn_result)
        await ws_manager.broadcast(game_id, "state_update", _state_payload(mgr))

        if s.game_over:
            await ws_manager.broadcast(
                game_id,
                "game_over",
                {"winner": s.winner.value if s.winner else None},
            )
            break


# ── REST endpoints ──────────────────────────────────────────────────────


@router.post("/api/game/new")
async def new_game(req: NewGameRequest):
    api_key = req.api_key or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key provided. Set GOOGLE_API_KEY in your environment or pass api_key in the request.")

    config = BoardConfig(
        size=BoardSize(req.board_size),
        difficulty=Difficulty(req.difficulty),
        language=Language(req.language),
        category=req.category or None,
    )
    human_team = TeamColor(req.team)
    human_role = PlayerRole(req.role)

    loop = asyncio.get_running_loop()

    try:
        mgr = GameManager(api_key=api_key)

        def handle_log(entry):
            if getattr(mgr, "state", None):
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(mgr.state.game_id, "agent_log", entry), loop
                )

        def handle_chat(chat):
            if getattr(mgr, "state", None):
                payload = {
                    "sender": (
                        chat["agent"].capitalize()
                        if chat["agent"] != "human"
                        else "You"
                    ),
                    "team": chat["team"],
                    "message": chat["message"],
                    "timestamp": datetime.fromtimestamp(chat["timestamp"]).isoformat(),
                }
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(mgr.state.game_id, "chat_message", payload),
                    loop,
                )

        def handle_state():
            if getattr(mgr, "state", None):
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(
                        mgr.state.game_id, "state_update", _state_payload(mgr)
                    ),
                    loop,
                )

        mgr.on_log_callback = handle_log
        mgr.on_chat_callback = handle_chat
        mgr.on_state_callback = handle_state

        state = await asyncio.to_thread(mgr.new_game, config, human_team, human_role)
        _games[state.game_id] = mgr

        # If opponent starts, kick off AI turns in background
        if not mgr.is_human_turn():
            asyncio.create_task(_run_ai_turns(state.game_id))

        return _state_payload(mgr)
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/game/{game_id}/state")
async def get_state(game_id: str):
    try:
        mgr = _get_game(game_id)
    except ValueError as e:
        return {"error": str(e)}
    return _state_payload(mgr)


@router.post("/api/game/{game_id}/clue")
async def submit_clue(game_id: str, req: ClueRequest):
    try:
        mgr = _get_game(game_id)
    except ValueError as e:
        return {"error": str(e)}

    if not mgr.is_human_turn():
        return {"success": False, "error": "Not your turn"}

    result = mgr.submit_human_clue(req.clue, req.number)
    if result.get("success"):
        await ws_manager.broadcast(game_id, "clue_given", result)
        await ws_manager.broadcast(game_id, "state_update", _state_payload(mgr))

        # Generate teammate chat reaction to human clue
        try:
            await asyncio.to_thread(
                mgr._generate_chat,
                "clue_given",
                {
                    "clue": req.clue,
                    "number": req.number,
                    "team": mgr.state.human_team.value,
                },
                "operative",
                mgr.state.human_team.value,
            )
        except Exception:
            pass

        # If AI teammate is the Operative, run its guesses
        if not mgr.is_human_turn() and not mgr.state.game_over:
            asyncio.create_task(_run_ai_turns(game_id))

    return _state_payload(mgr) if result.get("success") else result


@router.post("/api/game/{game_id}/guess")
async def submit_guess(game_id: str, req: GuessRequest):
    try:
        mgr = _get_game(game_id)
    except ValueError as e:
        return {"error": str(e)}

    if not mgr.is_human_turn():
        return {"success": False, "error": "Not your turn"}

    result = mgr.submit_human_guess(req.word)
    if result.get("success"):
        await ws_manager.broadcast(game_id, "guess_made", result)
        await ws_manager.broadcast(game_id, "state_update", _state_payload(mgr))

        # Generate opponent chat reaction to human guess
        event = (
            "good_guess"
            if result.get("correct")
            else ("assassin" if result.get("revealed") == "assassin" else "bad_guess")
        )
        opponent_team = "blue" if mgr.state.human_team.value == "red" else "red"
        try:
            await asyncio.to_thread(
                mgr._generate_chat,
                event,
                {
                    "word": req.word,
                    "correct": result.get("correct"),
                    "team": opponent_team,
                },
                "spymaster",
                opponent_team,
            )
        except Exception:
            pass

        # If turn switched to opponent, run their full turn
        if not mgr.is_human_turn() and not mgr.state.game_over:
            asyncio.create_task(_run_ai_turns(game_id))

    return _state_payload(mgr) if result.get("success") else result


@router.post("/api/game/{game_id}/end_turn")
async def end_turn(game_id: str):
    try:
        mgr = _get_game(game_id)
    except ValueError as e:
        return {"error": str(e)}

    if not mgr.is_human_turn():
        return {"success": False, "error": "Not your turn"}

    result = mgr.pass_turn()
    await ws_manager.broadcast(game_id, "turn_change", result)
    await ws_manager.broadcast(game_id, "state_update", _state_payload(mgr))

    if not mgr.is_human_turn() and not mgr.state.game_over:
        asyncio.create_task(_run_ai_turns(game_id))

    return _state_payload(mgr)


@router.post("/api/game/{game_id}/chat")
async def handle_chat(game_id: str, req: ChatRequest):
    try:
        mgr = _get_game(game_id)
    except ValueError as e:
        return {"error": str(e)}

    # Add human message to chat
    mgr._add_chat("human", mgr.state.human_team.value, req.message)

    return {"success": True}


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
                    await websocket.send_json(
                        {
                            "event": "state_update",
                            "data": _state_payload(mgr),
                        }
                    )
                except ValueError:
                    await websocket.send_json(
                        {"event": "error", "data": "Game not found"}
                    )
    except WebSocketDisconnect:
        ws_manager.disconnect(game_id, websocket)
