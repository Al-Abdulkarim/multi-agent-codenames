"""Central project configuration for Multi-Agent Codenames.

This file is intentionally not wired into runtime code yet.
It serves as the single source of truth for defaults and future integration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelsConfig:
    default: str = "gemini-3-flash-preview"
    available: tuple[str, ...] = (
        "gemini-3-flash-preview",
        "gemini/gemini-2.5-flash",
        
    )
    by_agent: dict[str, str] | None = None


@dataclass(frozen=True)
class GameDefaults:
    board_size: int = 25
    difficulty: str = "medium"
    language: str = "en"
    category: str | None = None


@dataclass(frozen=True)
class PlayerDefaults:
    human_team: str = "red"
    human_role: str = "operative"


@dataclass(frozen=True)
class AIDefaults:
    model: str = "gemini-3-flash-preview"
    temperature_overrides: dict[str, float] | None = None


@dataclass(frozen=True)
class ServerDefaults:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True


@dataclass(frozen=True)
class CLIDefaults:
    mode: str = "cli"
    lang: str = "en"
    size: int = 25
    difficulty: str = "medium"
    team: str = "red"
    role: str = "operative"
    category: str | None = None


@dataclass(frozen=True)
class EvalDefaults:
    mode: str = "eval"
    games: int = 5
    size: int = 25
    difficulty: str = "medium"
    lang: str = "en"


MODELS = ModelsConfig()
GAME_DEFAULTS = GameDefaults()
PLAYER_DEFAULTS = PlayerDefaults()
AI_DEFAULTS = AIDefaults()
SERVER_DEFAULTS = ServerDefaults()
CLI_DEFAULTS = CLIDefaults()
EVAL_DEFAULTS = EvalDefaults()

