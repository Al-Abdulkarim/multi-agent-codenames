"""Board-analysis tool for Spymaster agents.

Provides a structured breakdown of the current board so the Spymaster can
plan clues methodically.
"""

from __future__ import annotations

from crewai.tools import tool


@tool("analyze_board")
def analyze_board(board_json: str) -> str:
    """Parse a Spymaster board (JSON list of cards) and return a structured
    breakdown: own-team words, opponent words, neutrals, assassin."""
    import json

    try:
        cards = json.loads(board_json)
    except (json.JSONDecodeError, TypeError):
        return "ERROR: could not parse board JSON."

    groups: dict[str, list[str]] = {
        "red": [],
        "blue": [],
        "neutral": [],
        "assassin": [],
    }
    for card in cards:
        ctype = card.get("card_type", "neutral")
        revealed = card.get("revealed", False)
        word = card.get("word", "?")
        label = f"{word} [REVEALED]" if revealed else word
        groups.setdefault(ctype, []).append(label)

    lines: list[str] = []
    for group, words in groups.items():
        unrevealed = [w for w in words if "[REVEALED]" not in w]
        lines.append(f"{group.upper()} ({len(unrevealed)} left): {', '.join(words)}")
    return "\n".join(lines)
