from __future__ import annotations

from pydantic import BaseModel

from .enums import CardType, BoardSize, Language, Difficulty


class Card(BaseModel):
    """Single card on the Codenames board."""

    word: str
    card_type: CardType
    revealed: bool = False


class BoardConfig(BaseModel):
    """Configuration for creating a new board."""

    size: BoardSize = BoardSize.CLASSIC
    language: Language = Language.ENGLISH
    difficulty: Difficulty = Difficulty.MEDIUM
    category: str | None = None  # None → random mixed themes

    def get_distribution(self) -> tuple[int, int, int, int]:
        """Return *(starting_team, other_team, neutral, assassin)* counts.

        The starting team (Red by default) always gets +1 card.
        """
        distributions: dict[BoardSize, tuple[int, int, int, int]] = {
            BoardSize.SMALL: (5, 4, 5, 1),    # 15 total
            BoardSize.CLASSIC: (9, 8, 7, 1),   # 25 total
            BoardSize.LARGE: (13, 12, 9, 1),   # 35 total
        }
        return distributions[self.size]
