from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .card import Card, BoardConfig
from .enums import TeamColor, PlayerRole, CardType


class Clue(BaseModel):
    """A spymaster's one-word clue."""

    word: str
    number: int
    team: TeamColor
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Guess(BaseModel):
    """A single operative guess and its outcome."""

    word: str
    team: TeamColor
    result: CardType
    correct: bool


class TurnRecord(BaseModel):
    """One full turn: a clue followed by zero or more guesses."""

    team: TeamColor
    clue: Clue
    guesses: list[Guess] = []


class GameState(BaseModel):
    """Complete, serialisable snapshot of a running game."""

    game_id: str
    board: list[Card]
    config: BoardConfig

    current_team: TeamColor = TeamColor.RED  # Red always starts
    current_phase: Literal["clue", "guess"] = "clue"

    human_team: TeamColor = TeamColor.BLUE
    human_role: PlayerRole = PlayerRole.OPERATIVE

    turns_history: list[TurnRecord] = []
    guesses_remaining: int = 0

    winner: TeamColor | None = None
    game_over: bool = False

    # ── computed helpers ────────────────────────────────────────────

    @property
    def red_remaining(self) -> int:
        return sum(
            1 for c in self.board if c.card_type == CardType.RED and not c.revealed
        )

    @property
    def blue_remaining(self) -> int:
        return sum(
            1 for c in self.board if c.card_type == CardType.BLUE and not c.revealed
        )

    # ── board views ─────────────────────────────────────────────────

    def get_public_board(self) -> list[dict]:
        """Operative view — unrevealed cards have *no* type info."""
        return [
            {
                "word": c.word,
                "revealed": c.revealed,
                "card_type": c.card_type.value if c.revealed else None,
            }
            for c in self.board
        ]

    def get_spymaster_board(self) -> list[dict]:
        """Spymaster view — all card types visible."""
        return [
            {
                "word": c.word,
                "revealed": c.revealed,
                "card_type": c.card_type.value,
            }
            for c in self.board
        ]
