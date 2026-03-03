"""Centralized project configuration (non-integrated scaffold).

This module mirrors the current configuration values and defaults used across
the project, but it is intentionally not wired into runtime files yet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EnvConfig:
    """Environment-backed settings.

    Notes:
    - Secret keys default to empty strings by design.
    - We keep both current env vars in use and documented env vars for future
      migration into one place.
    """

    google_api_key: str = field(default_factory=lambda: _env_str("GOOGLE_API_KEY", ""))
    tavily_api_key: str = field(default_factory=lambda: _env_str("TAVILY_API_KEY", ""))
    gemini_model_env: str = field(
        default_factory=lambda: _env_str("GEMINI_MODEL", "gemini-3.0-flash")
    )
    host: str = field(default_factory=lambda: _env_str("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("PORT", 8000))
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", True))


@dataclass(frozen=True)
class ServerDefaults:
    """Server defaults currently hardcoded in Python entrypoints."""

    uvicorn_host: str = "0.0.0.0"
    cli_default_port: int = 8001


@dataclass(frozen=True)
class CliDefaults:
    """Argument defaults from `main.py`."""

    mode: str = "server"
    port: int = 8001
    lang: str = "en"
    size: str = "25"
    difficulty: str = "medium"
    team: str = "red"
    role: str = "operative"
    category: str | None = None
    games: int = 5


@dataclass(frozen=True)
class BoardDefaults:
    """Board defaults and size distributions from `models/card.py`."""

    default_size: int = 25
    default_language: str = "en"
    default_difficulty: str = "medium"
    default_category: str | None = None
    distributions: dict[int, tuple[int, int, int, int]] = field(
        default_factory=lambda: {
            15: (5, 4, 5, 1),
            25: (9, 8, 7, 1),
            35: (13, 12, 9, 1),
        }
    )


@dataclass(frozen=True)
class AgentDefaults:
    """Model and generation defaults currently used by agents/tools."""

    card_creator_model: str = "gemini/gemini-2.5-flash"
    card_creator_temperature: float = 2.0

    spymaster_model: str = "gemini/gemini-2.5-flash"
    spymaster_temperature: float = 0.7

    operative_model: str = "gemini/gemini-2.5-flash"
    operative_temperature: float = 0.4

    chat_model: str = "gemini-2.5-flash"
    chat_max_tokens: int = 500
    chat_temperature: float = 1.2
    chat_top_p: float = 0.95
    chat_trim_to_chars: int = 120

    tavily_search_depth: str = "basic"
    tavily_max_results: int = 5
    tavily_include_answer: bool = True
    tavily_snippets_limit: int = 3


@dataclass(frozen=True)
class AppSettings:
    """Composed central settings object for future incremental adoption."""

    env: EnvConfig = field(default_factory=EnvConfig)
    server: ServerDefaults = field(default_factory=ServerDefaults)
    cli: CliDefaults = field(default_factory=CliDefaults)
    board: BoardDefaults = field(default_factory=BoardDefaults)
    agents: AgentDefaults = field(default_factory=AgentDefaults)


def build_settings() -> AppSettings:
    """Build a fresh settings snapshot from current environment variables."""

    return AppSettings()


# Module-level settings snapshot for convenient read-only access.
settings = build_settings()

