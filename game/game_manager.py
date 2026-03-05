"""GameManager — the central orchestrator for a single Codenames game.

This is pure Python logic (not an LLM agent).  It owns the GameState and
delegates to the AI agent classes when it is an AI player's turn.
Now includes chat commentary and agent-log tracking.
"""

from __future__ import annotations

import random
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

        # Callbacks for instant streaming
        self.on_log_callback = None
        self.on_chat_callback = None
        self.on_state_callback = None

        # Flag: suppress intermediate state callbacks during AI turns
        # (the outer _run_ai_turns sends a final state_update instead)
        self._ai_turn_in_progress: bool = False

        # Agent logs — list of {timestamp, agent, action, detail, reflection}
        self.chat_messages: list[dict] = []
        # Chat messages — list of {timestamp, agent, team, message}
        self.agent_logs: list[dict] = []
        # Cooldown: prevent same persona from speaking twice in rapid succession
        self._persona_cooldowns: dict[str, float] = {}
        # Chat message ID counter for dedup
        self._chat_id_counter: int = 0

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
        if self.on_log_callback:
            self.on_log_callback(entry)
        return entry

    def _add_chat(
        self,
        agent: str,
        team: str,
        message: str,
        speaker_key: str | None = None,
    ) -> dict:
        self._chat_id_counter += 1
        entry = {
            "id": self._chat_id_counter,
            "timestamp": time.time(),
            "agent": agent,
            "team": team,
            "message": message,
            "speaker_key": speaker_key,
        }
        # Run callback (TTS + WebSocket broadcast) BEFORE appending so that
        # the entry is not visible to state-polling until audio is attached.
        if self.on_chat_callback:
            try:
                self.on_chat_callback(entry)
            except Exception:
                log.warning("Chat callback failed", exc_info=True)
        self.chat_messages.append(entry)
        return entry

    def _build_game_context(self, extra: dict | None = None) -> dict:
        """Build a structured game-state dict for chat agent prompts."""
        s = self.state
        ctx: dict = {
            "current_team": s.current_team.value if s else "?",
            "current_phase": s.current_phase if s else "?",
            "red_remaining": s.red_remaining if s else 0,
            "blue_remaining": s.blue_remaining if s else 0,
            "guesses_remaining": s.guesses_remaining if s else 0,
            "current_clue": "N/A",
            "current_number": 0,
            "human_team": s.human_team.value if s else "?",
        }
        if s and s.turns_history:
            last = s.turns_history[-1]
            if last.clue:
                ctx["current_clue"] = last.clue.word
                ctx["current_number"] = last.clue.number
        if extra:
            ctx.update(extra)
        return ctx

    def _persona_to_label(self, persona: str, lang: str) -> str:
        """Map a persona key to a human-readable chat sender label."""
        opp_team = "blue" if self.state.human_team.value == "red" else "red"
        if lang == "ar":
            t_name = "الأحمر" if opp_team == "red" else "الأزرق"
            labels = {
                "opponent_spymaster": f"خصمك رئيس المخابرات ({t_name})",
                "opponent_operative": f"خصمك العميل الميداني ({t_name})",
                "teammate": "زميلك",
            }
        else:
            t_cap = opp_team.capitalize()
            labels = {
                "opponent_spymaster": f"Opponent Spymaster ({t_cap})",
                "opponent_operative": f"Opponent Operative ({t_cap})",
                "teammate": "Partner",
            }
        return labels.get(persona, persona)

    def _pick_speakers(self, event_type: str, ctx: dict) -> list[str]:
        """Apply trigger rules to decide who speaks.  Max 2 per event."""
        speakers: list[str] = []
        is_opponent = ctx.get("is_opponent_action", False)
        actor = ctx.get("actor", "human")

        if event_type == "bad_guess":
            if is_opponent:
                speakers.append("teammate")
            else:
                speakers.append(
                    random.choice(["opponent_spymaster", "opponent_operative"])
                )
                if random.random() < 0.35:
                    speakers.append("teammate")

        elif event_type == "good_guess":
            if is_opponent:
                if random.random() < 0.3:
                    speakers.append(
                        random.choice(["opponent_spymaster", "opponent_operative"])
                    )
            else:
                speakers.append("teammate")
                if random.random() < 0.25:
                    speakers.append(
                        random.choice(["opponent_spymaster", "opponent_operative"])
                    )

        elif event_type == "sweep":
            if is_opponent:
                speakers.append("opponent_operative")
                if random.random() < 0.6:
                    speakers.append("opponent_spymaster")
            else:
                speakers.append("teammate")

        elif event_type == "assassin":
            if is_opponent:
                speakers.append("teammate")
            else:
                speakers.append(
                    random.choice(["opponent_spymaster", "opponent_operative"])
                )
                speakers.append("teammate")

        elif event_type == "clue_given":
            if is_opponent:
                if random.random() < 0.5:
                    speakers.append("teammate")
            else:
                if random.random() < 0.6:
                    speakers.append("teammate")

        elif event_type == "taunt":
            speakers.append(
                random.choice(["opponent_spymaster", "opponent_operative"])
            )

        elif event_type == "human_chat":
            # Always exactly one reply to a direct human message
            speakers.append(
                random.choice(["teammate", "opponent_spymaster", "opponent_operative"])
            )

        # ── filters ─────────────────────────────────────────────────────
        # 1. Don't let the acting agent react to its own action
        if actor == "ai_teammate":
            speakers = [s for s in speakers if s != "teammate"]
        # 2. Cooldown: skip personas that spoke in the last 3 seconds
        #    EXCEPTION: human_chat always gets a reply regardless of cooldown
        if event_type != "human_chat":
            now = time.time()
            speakers = [
                s for s in speakers
                if now - self._persona_cooldowns.get(s, 0) > 3.0
            ]

        return speakers[:2]  # hard cap at 2 messages per event

    def _emit_chat_reactions(
        self, event_type: str, event_ctx: dict
    ) -> list[dict]:
        """Decide who speaks, generate messages with delays.  Returns chat entries."""
        s = self.state
        if s is None:
            return []

        speakers = self._pick_speakers(event_type, event_ctx)
        if not speakers:
            return []

        lang = s.config.language.value
        opp_team = "blue" if s.human_team.value == "red" else "red"
        game_ctx = self._build_game_context(event_ctx)

        entries: list[dict] = []
        for i, persona in enumerate(speakers):
            if i > 0:
                time.sleep(random.uniform(0.3, 0.5))  # 300-500 ms delay

            label = self._persona_to_label(persona, lang)
            team = opp_team if persona.startswith("opponent") else s.human_team.value

            try:
                msg = self.chat_agent.generate(
                    persona=persona,
                    event_type=event_type,
                    game_context=game_ctx,
                    chat_history=self.chat_messages[-6:],
                    language=lang,
                )
                entry = self._add_chat(label, team, msg, speaker_key=persona)
                entries.append(entry)
                self._persona_cooldowns[persona] = time.time()
            except Exception as e:
                log.warning("Chat generation failed for %s: %s", persona, e)

        return entries

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

        if self.on_state_callback and not self._ai_turn_in_progress:
            self.on_state_callback()

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

        if self.on_state_callback and not self._ai_turn_in_progress:
            self.on_state_callback()

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

        # Emit chat reactions for this clue
        is_opponent = team != s.human_team.value
        chat_entries = self._emit_chat_reactions(
            "clue_given",
            {
                "clue": clue.clue,
                "number": clue.number,
                "is_opponent_action": is_opponent,
                "actor": "ai_opponent" if is_opponent else "ai_teammate",
                "event_description": (
                    f"{'Opponent' if is_opponent else 'Teammate'} Spymaster "
                    f"gave clue '{clue.clue}' for {clue.number}"
                ),
            },
        )

        return {
            "clue": clue.clue,
            "number": clue.number,
            "log": self.agent_logs[-1] if self.agent_logs else None,
            "chat": chat_entries,
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
        clue_number = s.turns_history[-1].clue.number if s.turns_history else 0
        is_opponent = team != s.human_team.value

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

            guesses.append(
                {
                    "word": guess.word,
                    "confidence": guess.confidence,
                    "reasoning": guess.reasoning,
                    "correct": correct,
                    "revealed": result.get("revealed"),
                    "log": self.agent_logs[-1] if self.agent_logs else None,
                    "chat": None,
                }
            )

            if not correct:
                # Wrong guess or assassin — emit reaction
                event = (
                    "assassin"
                    if result.get("revealed") == "assassin"
                    else "bad_guess"
                )
                chat_entries = self._emit_chat_reactions(
                    event,
                    {
                        "word": guess.word,
                        "correct": False,
                        "is_opponent_action": is_opponent,
                        "actor": "ai_opponent" if is_opponent else "ai_teammate",
                        "result": result.get("revealed", "wrong"),
                        "event_description": (
                            f"{'Opponent' if is_opponent else 'Teammate'} operative "
                            f"guessed '{guess.word}' — {result.get('revealed', 'wrong')}!"
                        ),
                    },
                )
                guesses[-1]["chat"] = chat_entries
                break

        # Sweep detection: did operative nail all clue words?
        correct_count = sum(1 for g in guesses if g["correct"])
        if correct_count > 0 and correct_count >= clue_number:
            chat_entries = self._emit_chat_reactions(
                "sweep",
                {
                    "correct_count": correct_count,
                    "clue_number": clue_number,
                    "is_opponent_action": is_opponent,
                    "actor": "ai_opponent" if is_opponent else "ai_teammate",
                    "event_description": (
                        f"{'Opponent' if is_opponent else 'Teammate'} operative "
                        f"nailed all {correct_count} words from the clue!"
                    ),
                },
            )
            if guesses:
                guesses[-1]["chat"] = chat_entries

        return guesses

    def run_ai_turn(self) -> dict[str, Any]:
        """Run the appropriate AI action(s) for the current phase. Returns summary with chat and logs."""
        self._ai_turn_in_progress = True
        try:
            return self._run_ai_turn_inner()
        finally:
            self._ai_turn_in_progress = False

    def _run_ai_turn_inner(self) -> dict[str, Any]:
        """Internal implementation — called with _ai_turn_in_progress=True."""
        s = self.state
        team = s.current_team.value

        # Taunt at the start of opponent's clue phase
        if s.current_phase == "clue" and team != s.human_team.value:
            self._emit_chat_reactions(
                "taunt",
                {
                    "is_opponent_action": True,
                    "actor": "ai_opponent",
                    "event_description": "Opponent's turn is starting.",
                },
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
        if self.on_state_callback:
            self.on_state_callback()
        return {"success": True, "current_team": self.state.current_team.value}

    def _switch_turn(self) -> None:
        s = self.state
        s.current_team = (
            TeamColor.BLUE if s.current_team == TeamColor.RED else TeamColor.RED
        )
        s.current_phase = "clue"
        s.guesses_remaining = 0
        log.info("Turn switched → %s clue phase", s.current_team.value)
