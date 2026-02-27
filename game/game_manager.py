"""GameManager — the central orchestrator for a single Codenames game.

This is pure Python logic (not an LLM agent).  It owns the GameState and
delegates to the AI agent classes when it is an AI player's turn.
"""

from __future__ import annotations

import uuid
import logging
from typing import Any

from models.card import BoardConfig
from models.enums import TeamColor, PlayerRole, CardType
from models.game_state import GameState, Clue, Guess, TurnRecord
from agents.card_creator import CardCreatorAgent
from agents.spymaster import AISpymaster, ClueOutput
from agents.operative import AIOperative, GuessOutput
from game.board import create_board, reveal_card
from game.validators import validate_clue, validate_guess

log = logging.getLogger(__name__)


class GameManager:
    """Orchestrates one full Codenames game.

    *   ``new_game()``  – set up board via CardCreator
    *   ``is_human_turn()`` – check whether the human should act
    *   ``submit_human_clue()`` / ``submit_human_guess()`` – human actions
    *   ``run_ai_clue()`` / ``run_ai_guess()`` – AI actions
    *   ``pass_turn()`` – end the current turn early
    """

    def __init__(self, api_key: str, model: str = "gemini/gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.state: GameState | None = None

    # ── game setup ──────────────────────────────────────────────────

    def new_game(
        self,
        config: BoardConfig,
        human_team: TeamColor,
        human_role: PlayerRole,
    ) -> GameState:
        """Generate words, build board, initialise state."""
        log.info(
            "Creating new game: size=%s lang=%s diff=%s cat=%s",
            config.size.value,
            config.language.value,
            config.difficulty.value,
            config.category,
        )

        creator = CardCreatorAgent(api_key=self.api_key, model=self.model)
        words = creator.generate_words(
            count=config.size.value,
            language=config.language.value,
            category=config.category,
            difficulty=config.difficulty.value,
        )

        board = create_board(words, config, starting_team=TeamColor.RED)

        self.state = GameState(
            game_id=str(uuid.uuid4()),
            board=board,
            config=config,
            human_team=human_team,
            human_role=human_role,
        )
        log.info("Game %s ready — %d cards on the board", self.state.game_id, len(board))
        return self.state

    # ── turn helpers ────────────────────────────────────────────────

    def is_human_turn(self) -> bool:
        """Return True when the game is waiting for the human player."""
        s = self.state
        if s is None or s.game_over:
            return False
        if s.current_team != s.human_team:
            return False
        if s.current_phase == "clue" and s.human_role == PlayerRole.SPYMASTER:
            return True
        if s.current_phase == "guess" and s.human_role == PlayerRole.OPERATIVE:
            return True
        return False

    def whose_turn(self) -> dict[str, str]:
        """Return a human-readable description of who should act next."""
        s = self.state
        if s is None:
            return {"team": "none", "phase": "none", "actor": "none"}
        actor = "human" if self.is_human_turn() else "ai"
        return {
            "team": s.current_team.value,
            "phase": s.current_phase,
            "actor": actor,
        }

    # ── human actions ───────────────────────────────────────────────

    def submit_human_clue(self, clue: str, number: int) -> dict[str, Any]:
        """Validate and record a human Spymaster's clue."""
        s = self.state
        valid, msg = validate_clue(clue, number, s.board, s.config.language)
        if not valid:
            return {"success": False, "error": msg}

        clue_obj = Clue(word=clue, number=number, team=s.current_team)
        s.turns_history.append(TurnRecord(team=s.current_team, clue=clue_obj))
        s.guesses_remaining = number + 1
        s.current_phase = "guess"
        log.info("Clue recorded: '%s' for %d (%s)", clue, number, s.current_team.value)
        return {"success": True, "clue": clue, "number": number}

    def submit_human_guess(self, word: str) -> dict[str, Any]:
        """Validate and resolve a human Operative's guess."""
        s = self.state
        valid, msg = validate_guess(word, s.board)
        if not valid:
            return {"success": False, "error": msg}

        card = reveal_card(s.board, word)
        correct = card.card_type.value == s.current_team.value
        guess = Guess(
            word=word,
            team=s.current_team,
            result=card.card_type,
            correct=correct,
        )
        s.turns_history[-1].guesses.append(guess)
        s.guesses_remaining -= 1

        log.info(
            "Guess: '%s' → %s (%s)",
            word,
            card.card_type.value,
            "correct" if correct else "wrong",
        )

        # assassin → instant loss
        if card.card_type == CardType.ASSASSIN:
            other = TeamColor.BLUE if s.current_team == TeamColor.RED else TeamColor.RED
            s.winner = other
            s.game_over = True
            return {
                "success": True,
                "revealed": card.card_type.value,
                "correct": False,
                "game_over": True,
                "winner": other.value,
            }

        # check whether a team cleared all their cards
        if s.red_remaining == 0:
            s.winner = TeamColor.RED
            s.game_over = True
        elif s.blue_remaining == 0:
            s.winner = TeamColor.BLUE
            s.game_over = True

        # wrong guess or out of guesses → end turn
        if not correct or s.guesses_remaining <= 0:
            self._switch_turn()

        return {
            "success": True,
            "revealed": card.card_type.value,
            "correct": correct,
            "game_over": s.game_over,
            "winner": s.winner.value if s.winner else None,
        }

    # ── AI actions ──────────────────────────────────────────────────

    def run_ai_clue(self) -> ClueOutput:
        """Have the AI Spymaster generate a clue and record it."""
        s = self.state
        spymaster = AISpymaster(
            team=s.current_team.value,
            difficulty=s.config.difficulty.value,
            api_key=self.api_key,
            model=self.model,
        )
        clue = spymaster.generate_clue(
            spymaster_board=s.get_spymaster_board(),
            history=[t.model_dump() for t in s.turns_history],
        )
        # record via the same validation path
        result = self.submit_human_clue(clue.clue, clue.number)
        if not result.get("success"):
            # guardrail passed in agent but failed in validator — retry once
            log.warning("AI clue validation failed: %s — retrying", result.get("error"))
            clue = spymaster.generate_clue(
                spymaster_board=s.get_spymaster_board(),
                history=[t.model_dump() for t in s.turns_history],
            )
            self.submit_human_clue(clue.clue, clue.number)
        return clue

    def run_ai_guess(self) -> list[GuessOutput]:
        """Have the AI Operative guess iteratively until turn ends."""
        s = self.state
        operative = AIOperative(
            team=s.current_team.value,
            difficulty=s.config.difficulty.value,
            api_key=self.api_key,
            model=self.model,
        )
        guesses: list[GuessOutput] = []
        while s.guesses_remaining > 0 and not s.game_over:
            guess = operative.make_guess(
                clue=s.turns_history[-1].clue.word,
                number=s.turns_history[-1].clue.number,
                public_board=s.get_public_board(),
                history=[t.model_dump() for t in s.turns_history],
            )
            result = self.submit_human_guess(guess.word)
            guesses.append(guess)
            if not result.get("correct", False):
                break
        return guesses

    def run_ai_turn(self) -> dict[str, Any]:
        """Run a complete AI turn (clue + guesses).  Returns summary."""
        clue = self.run_ai_clue()
        guesses = self.run_ai_guess()
        return {
            "clue": {"word": clue.clue, "number": clue.number},
            "guesses": [g.model_dump() for g in guesses],
            "game_over": self.state.game_over,
            "winner": self.state.winner.value if self.state.winner else None,
        }

    # ── turn management ─────────────────────────────────────────────

    def pass_turn(self) -> dict[str, str]:
        """End the current team's turn early."""
        self._switch_turn()
        return {"success": True, "current_team": self.state.current_team.value}

    def _switch_turn(self) -> None:
        s = self.state
        s.current_team = (
            TeamColor.BLUE if s.current_team == TeamColor.RED else TeamColor.RED
        )
        s.current_phase = "clue"
        s.guesses_remaining = 0
        log.info("Turn switched → %s clue phase", s.current_team.value)
