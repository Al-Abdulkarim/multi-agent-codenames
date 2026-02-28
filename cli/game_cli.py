"""Terminal-based Codenames game interface."""

from __future__ import annotations

import os
import sys

# ── colour helpers (works without colorama if unavailable) ──────────────

try:
    from colorama import init as _colorama_init, Fore, Style

    _colorama_init()
except ImportError:  # pragma: no cover
    class _Dummy:
        RED = BLUE = WHITE = YELLOW = GREEN = CYAN = MAGENTA = ""
        RESET_ALL = BRIGHT = ""
    Fore = Style = _Dummy()  # type: ignore[assignment]


# Map card types to terminal colours
_CARD_COLOURS = {
    "red": Fore.RED,
    "blue": Fore.BLUE,
    "neutral": Fore.WHITE,
    "assassin": f"{Fore.MAGENTA}{Style.BRIGHT}",
}


def _coloured(text: str, card_type: str | None = None) -> str:
    if card_type is None:
        return text
    colour = _CARD_COLOURS.get(card_type, "")
    return f"{colour}{text}{Style.RESET_ALL}"


# ── board display ───────────────────────────────────────────────────────

def _print_board(board: list[dict], *, is_spymaster: bool, cols: int = 5) -> None:
    """Print the board as a coloured grid."""
    max_width = max(len(c["word"]) for c in board) + 2

    for i, card in enumerate(board):
        word = card["word"]
        revealed = card.get("revealed", False)
        ctype = card.get("card_type")

        if revealed:
            display = _coloured(f"[{word}]", ctype)
        elif is_spymaster and ctype:
            display = _coloured(word.center(max_width), ctype)
        else:
            display = word.center(max_width)

        end = "\n" if (i + 1) % cols == 0 else "  "
        print(display, end=end)

    print()


# ── main game loop ──────────────────────────────────────────────────────

def run_cli(
    lang: str = "en",
    size: int = 25,
    difficulty: str = "medium",
    team: str = "blue",
    role: str = "operative",
    category: str | None = None,
    api_key: str | None = None,
) -> None:
    """Run an interactive CLI Codenames game."""
    from dotenv import load_dotenv

    load_dotenv()

    api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        print(f"{Fore.RED}ERROR: No API key. Set GOOGLE_API_KEY in .env or pass --api-key{Style.RESET_ALL}")
        sys.exit(1)

    from models.enums import BoardSize, Difficulty, Language, TeamColor, PlayerRole
    from models.card import BoardConfig
    from game.game_manager import GameManager

    config = BoardConfig(
        size=BoardSize(size),
        difficulty=Difficulty(difficulty),
        language=Language(lang),
        category=category or None,
    )
    human_team = TeamColor(team)
    human_role = PlayerRole(role)

    mgr = GameManager(api_key=api_key)

    print(f"\n{Style.BRIGHT}🎲  Generating board …{Style.RESET_ALL}")
    mgr.new_game(config, human_team, human_role)
    s = mgr.state

    cols = {15: 5, 25: 5, 35: 7}.get(size, 5)

    # ── game loop ──────────────────────────────────────────────────

    while not s.game_over:
        print(f"\n{'=' * 50}")
        print(
            f"  {Fore.RED}Red: {s.red_remaining}{Style.RESET_ALL}  |  "
            f"{Fore.BLUE}Blue: {s.blue_remaining}{Style.RESET_ALL}  |  "
            f"Turn: {_coloured(s.current_team.value.upper(), s.current_team.value)} "
            f"({s.current_phase})"
        )
        print(f"{'=' * 50}\n")

        is_spymaster_view = (
            s.current_team == human_team and human_role == PlayerRole.SPYMASTER
        )
        board_view = s.get_spymaster_board() if is_spymaster_view else s.get_public_board()
        _print_board(board_view, is_spymaster=is_spymaster_view, cols=cols)

        if mgr.is_human_turn():
            if s.current_phase == "clue":
                # Human is Spymaster → give clue
                print(f"\n{Fore.CYAN}Your turn (Spymaster) — give a clue:{Style.RESET_ALL}")
                while True:
                    clue_word = input("  Clue word: ").strip()
                    try:
                        clue_num = int(input("  Number: ").strip())
                    except ValueError:
                        print(f"  {Fore.RED}Number must be an integer.{Style.RESET_ALL}")
                        continue
                    result = mgr.submit_human_clue(clue_word, clue_num)
                    if result.get("success"):
                        print(f"  ✅ Clue accepted: '{clue_word}' for {clue_num}")
                        break
                    print(f"  {Fore.RED}✗ {result.get('error')}{Style.RESET_ALL}")

                # Now the AI teammate guesses
                if not mgr.is_human_turn() and not s.game_over:
                    print(f"\n{Fore.YELLOW}🤖 AI Operative is guessing …{Style.RESET_ALL}")
                    guesses = mgr.run_ai_guess()
                    for g in guesses:
                        word = g["word"]
                        conf = g.get("confidence", 0)
                        correct = g.get("correct", False)
                        correct_mark = "✅" if correct else "❌"
                        print(f"  → {word} (confidence: {conf:.0%}) {correct_mark}")

            else:
                # Human is Operative → guess
                clue = s.turns_history[-1].clue
                print(
                    f"\n{Fore.CYAN}Clue: '{clue.word}' for {clue.number}  "
                    f"(guesses left: {s.guesses_remaining}){Style.RESET_ALL}"
                )
                while s.guesses_remaining > 0 and not s.game_over:
                    word = input("  Your guess (or 'pass'): ").strip()
                    if word.lower() == "pass":
                        mgr.pass_turn()
                        print("  ⏭ Passed.")
                        break
                    result = mgr.submit_human_guess(word)
                    if not result.get("success"):
                        print(f"  {Fore.RED}✗ {result.get('error')}{Style.RESET_ALL}")
                        continue
                    revealed = result.get("revealed", "")
                    if result.get("correct"):
                        print(f"  ✅ Correct! ({revealed})")
                    else:
                        print(f"  ❌ Wrong — it was {_coloured(revealed, revealed)}")
                        break
        else:
            # AI's turn
            team_name = s.current_team.value.upper()
            print(f"\n{Fore.YELLOW}🤖 {team_name} AI is playing …{Style.RESET_ALL}")
            turn_result = mgr.run_ai_turn()
            clue_data = turn_result["clue"]
            print(f"  Clue: '{clue_data['word']}' for {clue_data['number']}")
            for g in turn_result["guesses"]:
                print(f"  → guessed '{g['word']}' (confidence: {g['confidence']:.0%})")

    # ── game over ──────────────────────────────────────────────────

    print(f"\n{'🎉' * 10}")
    winner = s.winner.value.upper() if s.winner else "NOBODY"
    if s.winner == human_team:
        print(f"{Fore.GREEN}{Style.BRIGHT}  YOU WIN!  ({winner}){Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}{Style.BRIGHT}  YOU LOSE.  ({winner} wins){Style.RESET_ALL}")
    print(f"{'🎉' * 10}\n")
