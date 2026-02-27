"""Clue and guess guardrails.  Pure Python — no LLM calls."""

from __future__ import annotations

from models.card import Card
from models.enums import Language


# ── banned game-related words ───────────────────────────────────────────

BANNED_WORDS: dict[str, set[str]] = {
    "ar": {"أحمر", "أزرق", "تمرير", "محايد", "قاتل", "جاسوس", "كلمة"},
    "en": {"red", "blue", "pass", "neutral", "assassin", "spy", "clue"},
}


# ── clue validation ─────────────────────────────────────────────────────

def validate_clue(
    clue: str,
    number: int,
    board: list[Card],
    language: Language,
) -> tuple[bool, str]:
    """Return ``(True, "Valid")`` or ``(False, reason)``."""
    clue = clue.strip()

    if not clue:
        return False, "Clue cannot be empty"

    if " " in clue:
        return False, "Clue must be a single word (no spaces)"

    board_words_lower = [c.word.lower() for c in board]

    if clue.lower() in board_words_lower:
        return False, "Clue cannot be a word on the board"

    # substring check
    for bw in board_words_lower:
        if clue.lower() in bw or bw in clue.lower():
            return False, f"Clue cannot be a substring of board word '{bw}'"

    banned = BANNED_WORDS.get(language.value, set())
    if clue.lower() in banned:
        return False, "Clue is a banned game term"

    if not (0 <= number <= 9):
        return False, "Number must be between 0 and 9"

    return True, "Valid"


# ── guess validation ────────────────────────────────────────────────────

def validate_guess(word: str, board: list[Card]) -> tuple[bool, str]:
    """Return ``(True, "Valid")`` or ``(False, reason)``."""
    card = next((c for c in board if c.word == word), None)
    if card is None:
        return False, "Word is not on the board"
    if card.revealed:
        return False, "Word is already revealed"
    return True, "Valid"
