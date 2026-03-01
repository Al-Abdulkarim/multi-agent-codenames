"""GameManager — the central orchestrator for a single Codenames game.

This is pure Python logic (not an LLM agent).  It owns the GameState and
delegates to the AI agent classes when it is an AI player's turn.
Now includes chat commentary and agent-log tracking.
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Any
from models.card import BoardConfig
from models.enums import TeamColor, PlayerRole, CardType
from models.game_state import GameState, Clue, Guess, TurnRecord
from agents.card_creator import CardCreatorAgent
from agents.spymaster import AISpymaster
from agents.operative import AIOperative
from agents.chat_agent import ChatAgent
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

    def __init__(self, api_key: str, model: str = "gemini/gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.state: GameState | None = None

        # Chat commentary agent
        self.chat_agent = ChatAgent(api_key=api_key)

        # Agent logs — list of {timestamp, agent, action, detail, reflection}
        self.chat_messages: list[dict] = []
        # Chat messages — list of {timestamp, agent, team, message}
        self.agent_logs: list[dict] = []

    # ── logging helpers ─────────────────────────────────────────────

    def _add_log(
        self, agent: str, action: str, detail: str, reflection: str = ""
    ) -> dict:
        entry = {
            "timestamp": time.time(),
            "agent": agent,
            "action": action,
            "detail": detail,
            "reflection": reflection,
        }
        self.agent_logs.append(entry)
        return entry

    def _add_chat(self, agent: str, team: str, message: str) -> dict:
        entry = {
            "timestamp": time.time(),
            "agent": agent,
            "team": team,
            "message": message,
        }
        self.chat_messages.append(entry)
        return entry

    def _generate_chat(
        self, event_type: str, context: dict, agent_role: str, agent_team: str
    ) -> dict | None:
        """Generate a chat message and return the entry."""
        try:
            lang = self.state.config.language.value if self.state else "en"
            # Localized role names for the chat sender
            lang_roles = {
                "en": {
                    "spymaster": "Spymaster",
                    "operative": "Operative",
                    "ai_spymaster": "AI Spymaster",
                    "ai_operative": "AI Operative",
                },
                "ar": {
                    "spymaster": "رئيس المخابرات",
                    "operative": "العميل الميداني",
                    "ai_spymaster": "رئيس المخابرات (آلي)",
                    "ai_operative": "العميل الميداني (آلي)",
                },
            }
            role_map = lang_roles.get(lang, lang_roles["en"])

            # Determine if this agent is on the human's team
            is_same_team = agent_team == self.state.human_team.value

            # SILENCE duplicates: If agent is on human's team AND has the same
            # role the human chose, SILENCE it — the human fills that role.
            clean_role = agent_role.replace("ai_", "")
            if is_same_team and clean_role == self.state.human_role.value:
                return None

            # Build the display label for the chat sender
            if lang == "ar":
                if is_same_team:
                    r_name = role_map.get(clean_role, "مساعد")
                    localized_role = f"زميلك ({r_name})"
                else:
                    team_name = "الأحمر" if agent_team == "red" else "الأزرق"
                    translated_role = role_map.get(clean_role, "وكيل")
                    localized_role = f"خصمك {translated_role} ({team_name})"
            else:
                if is_same_team:
                    p_name = role_map.get(clean_role, "Agent")
                    localized_role = f"Partner ({p_name})"
                else:
                    role_word = role_map.get(clean_role, "Agent")
                    t_cap = agent_team.capitalize()
                    localized_role = f"Opponent {role_word} ({t_cap})"

            msg = self.chat_agent.react(
                event_type=event_type,
                context=context,
                language=lang,
                agent_role=agent_role,
                agent_team=agent_team,
            )
            return self._add_chat(localized_role, agent_team, msg)
        except Exception as e:
            log.warning("Chat generation failed: %s", e)
            return None

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

        self._add_log(
            "CardCreator",
            "starting",
            f"Generating {config.size.value} words (lang={config.language.value}, "
            f"diff={config.difficulty.value}, cat={config.category})",
        )

        creator = CardCreatorAgent(api_key=self.api_key, model=self.model)
        words = creator.generate_words(
            count=config.size.value,
            language=config.language.value,
            category=config.category,
            difficulty=config.difficulty.value,
        )

        self._add_log(
            "CardCreator",
            "completed",
            f"Generated {len(words)} words",
            "Words look thematically consistent",
        )

        board = create_board(words, config, starting_team=TeamColor.RED)

        # Double-check: exactly 1 assassin card
        assassin_count = sum(1 for c in board if c.card_type == CardType.ASSASSIN)
        if assassin_count != 1:
            log.error(
                "Board has %d assassin cards instead of 1! Fixing...", assassin_count
            )
            # Fix: ensure exactly 1 assassin
            found_first = False
            for c in board:
                if c.card_type == CardType.ASSASSIN:
                    if found_first:
                        c.card_type = CardType.NEUTRAL
                    else:
                        found_first = True
            if not found_first:
                # No assassin at all — assign one to a neutral card
                for c in board:
                    if c.card_type == CardType.NEUTRAL:
                        c.card_type = CardType.ASSASSIN
                        break

        self.state = GameState(
            game_id=str(uuid.uuid4()),
            board=board,
            config=config,
            human_team=human_team,
            human_role=human_role,
        )
        log.info(
            "Game %s ready — %d cards on the board",
            self.state.game_id,
            len(board),
        )
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

        # Generate teammate chat reaction (the AI operative on human's team)
        self._generate_chat(
            "clue_given",
            {
                "clue": clue,
                "number": number,
                "actor": "human",
                "team": s.current_team.value,
            },
            "ai_operative",
            s.current_team.value,
        )
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

        # Partner reaction (teammate AI agent)
        self._generate_chat(
            "good_guess" if correct else "bad_guess",
            {
                "word": word,
                "correct": correct,
                "actor": "human",
                "team": s.human_team.value,
            },
            "ai_spymaster" if s.human_role == PlayerRole.OPERATIVE else "ai_operative",
            s.human_team.value,
        )

        return {
            "success": True,
            "revealed": card.card_type.value,
            "correct": correct,
            "game_over": s.game_over,
            "winner": s.winner.value if s.winner else None,
        }

    # ── AI actions ──────────────────────────────────────────────────

    def run_ai_clue(self) -> dict[str, Any]:
        """Have the AI Spymaster generate a clue and record it.  Returns dict with clue + logs + chat."""
        s = self.state
        team = s.current_team.value

        lang = s.config.language.value
        thinking_msg = (
            "جاري تحليل اللوحة للحصول على أفضل تلميح..."
            if lang == "ar"
            else "Analyzing board for best clue..."
        )
        reflection_msg = (
            "تقييم علاقات الكلمات والمخاطر"
            if lang == "ar"
            else "Evaluating word relationships and risks"
        )

        self._add_log(
            f"{team} Spymaster",
            "thinking",
            thinking_msg,
            reflection_msg,
        )

        spymaster = AISpymaster(
            team=team,
            difficulty=s.config.difficulty.value,
            language=lang,
            api_key=self.api_key,
            model=self.model,
        )
        clue = spymaster.generate_clue(
            spymaster_board=s.get_spymaster_board(),
            history=[t.model_dump() for t in s.turns_history],
            category=s.config.category,
        )

        # record via the same validation path
        result = self.submit_human_clue(clue.clue, clue.number)
        if not result.get("success"):
            log.warning("AI clue validation failed: %s — retrying", result.get("error"))
            self._add_log(
                f"{team} Spymaster",
                "retry",
                f"Clue rejected: {result.get('error')}",
                "Generating alternative clue",
            )
            clue = spymaster.generate_clue(
                spymaster_board=s.get_spymaster_board(),
                history=[t.model_dump() for t in s.turns_history],
            )
            self.submit_human_clue(clue.clue, clue.number)

        # Update log with actual reflection from agent
        self._add_log(
            f"{team} Spymaster",
            "clue_generated",
            f"Clue: '{clue.clue}' for {clue.number}",
            clue.reflection,
        )

        # Generate chat comment from this spymaster
        chat_entry = self._generate_chat(
            "clue_given",
            {"clue": clue.clue, "number": clue.number, "team": team},
            "ai_spymaster",
            team,
        )

        return {
            "clue": clue.clue,
            "number": clue.number,
            "log": self.agent_logs[-1] if self.agent_logs else None,
            "chat": chat_entry,
        }

    def run_ai_guess(self) -> list[dict[str, Any]]:
        """Have the AI Operative guess iteratively until turn ends.  Returns list of dicts with guess + logs + chat."""
        s = self.state
        team = s.current_team.value
        lang = s.config.language.value

        operative = AIOperative(
            team=team,
            difficulty=s.config.difficulty.value,
            language=lang,
            api_key=self.api_key,
            model=self.model,
        )
        guesses: list[dict[str, Any]] = []

        while s.guesses_remaining > 0 and not s.game_over:
            thinking_msg = (
                f"يفكر في تخمين للتلميح '{s.turns_history[-1].clue.word}'"
                if lang == "ar"
                else f"Considering guess for clue '{s.turns_history[-1].clue.word}'"
            )
            reflection_msg = (
                "تقييم ترابط الكلمات على اللوحة"
                if lang == "ar"
                else "Evaluating word associations on the board"
            )

            self._add_log(
                f"{team} Operative",
                "thinking",
                thinking_msg,
                reflection_msg,
            )

            guess = operative.make_guess(
                clue=s.turns_history[-1].clue.word,
                number=s.turns_history[-1].clue.number,
                public_board=s.get_public_board(),
                history=[t.model_dump() for t in s.turns_history],
            )

            guess_msg = (
                f"خمن '{guess.word}' (الثقة: {guess.confidence:.0%})"
                if lang == "ar"
                else f"Guessed '{guess.word}' (confidence: {guess.confidence:.0%})"
            )
            self._add_log(
                f"{team} Operative",
                "guess_made",
                guess_msg,
                guess.reasoning,
            )

            result = self.submit_human_guess(guess.word)
            correct = result.get("correct", False)

            # Generate chat reaction from this operative
            event = (
                "good_guess"
                if correct
                else (
                    "assassin" if result.get("revealed") == "assassin" else "bad_guess"
                )
            )
            chat_entry = self._generate_chat(
                event,
                {"word": guess.word, "correct": correct, "team": team},
                "ai_operative",
                team,
            )

            guesses.append(
                {
                    "word": guess.word,
                    "confidence": guess.confidence,
                    "reasoning": guess.reasoning,
                    "correct": correct,
                    "revealed": result.get("revealed"),
                    "log": self.agent_logs[-1] if self.agent_logs else None,
                    "chat": chat_entry,
                }
            )

            if not correct:
                break

        return guesses

    def run_ai_turn(self) -> dict[str, Any]:
        """Run the appropriate AI action(s) for the current phase. Returns summary with chat and logs."""
        s = self.state
        team = s.current_team.value
        opponent_team = "blue" if team == "red" else "red"

        # Taunt only at the start of a clue phase and if it's the opponent team
        if s.current_phase == "clue" and team != s.human_team.value:
            self._generate_chat(
                (
                    "taunt"
                    if s.red_remaining > 2 and s.blue_remaining > 2
                    else "turn_start"
                ),
                {
                    "team": team,
                    "red_left": s.red_remaining,
                    "blue_left": s.blue_remaining,
                    "is_my_team": False,
                },
                "ai_spymaster",
                team,
            )

        clue_result = None
        guesses = []

        if s.current_phase == "clue":
            if self.is_human_turn():
                log.info("Skipping AI clue: it is human's turn.")
                return {"clue": None, "guesses": [], "game_over": s.game_over}
            clue_result = self.run_ai_clue()

        # Re-check human turn: if human is Operative, they must take over now
        if s.current_phase == "guess":
            if self.is_human_turn():
                log.info("Skipping AI guess: it is human's turn.")
                return {"clue": None, "guesses": [], "game_over": s.game_over}
            if not s.game_over:
                guesses = self.run_ai_guess()

        # Post-turn status chat from the other team
        # Only do this if the team actually switched (meaning we finished guessing)
        if s.current_phase == "clue" and s.current_team.value != team:
            my_remaining = s.red_remaining if team == "red" else s.blue_remaining
            opp_remaining = s.blue_remaining if team == "red" else s.red_remaining
            status_event = "winning" if my_remaining < opp_remaining else "losing"
            self._generate_chat(
                status_event,
                {
                    "team": opponent_team,
                    "my_remaining": opp_remaining,
                    "opp_remaining": my_remaining,
                },
                "operative",
                opponent_team,
            )

        return {
            "clue": (
                {"word": clue_result["clue"], "number": clue_result["number"]}
                if clue_result
                else None
            ),
            "guesses": guesses,
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
