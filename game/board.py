"""Board creation and card-reveal logic.  Pure Python — no LLM calls."""

from __future__ import annotations

import random

from models.card import Card, BoardConfig
from models.enums import CardType, TeamColor


def create_board(
    words: list[str],
    config: BoardConfig,
    starting_team: TeamColor = TeamColor.RED,
) -> list[Card]:
    """Assign random :class:`CardType` values to *words* according to *config*."""
    starting, other, neutral, assassin = config.get_distribution()

    starting_type = CardType.RED if starting_team == TeamColor.RED else CardType.BLUE
    other_type = CardType.BLUE if starting_team == TeamColor.RED else CardType.RED

    types: list[CardType] = (
        [starting_type] * starting
        + [other_type] * other
        + [CardType.NEUTRAL] * neutral
        + [CardType.ASSASSIN] * assassin
    )
    random.shuffle(types)

    return [Card(word=w, card_type=t) for w, t in zip(words, types)]


def reveal_card(board: list[Card], word: str) -> Card | None:
    """Mark *word* as revealed.  Returns the card, or ``None`` if not found."""
    for card in board:
        if card.word == word and not card.revealed:
            card.revealed = True
            return card
    return None
