"""AI Operative (Spy) agent — guesses words based on the Spymaster's clue.

Process isolation: the Operative **never** receives the secret card types.
It only sees the public board (words + revealed status).
"""

from __future__ import annotations

import json

from crewai import Agent, Task, Crew, Process, LLM
from pydantic import BaseModel


# ── structured output ───────────────────────────────────────────────────


class GuessOutput(BaseModel):
    word: str
    confidence: float
    reasoning: str


# ── agent wrapper ───────────────────────────────────────────────────────


class AIOperative:
    """Creates and runs an Operative crew that produces a single guess."""

    def __init__(
        self,
        team: str,
        difficulty: str,
        language: str,
        api_key: str,
        model: str = "gemini/gemini-2.5-flash",
    ):
        self.team = team
        self.difficulty = difficulty
        self.language = language
        self.llm = LLM(model=model, api_key=api_key, temperature=0.4)

    # ── factory ─────────────────────────────────────────────────────

    def _build_agent(self) -> Agent:
        difficulty_instruction = (
            "You MUST use advanced reasoning and connect 3+ words."
            if self.difficulty == "hard"
            else (
                "You should try to connect 2 words cleverly."
                if self.difficulty == "medium"
                else "Keep it very simple and connect only 1 word."
            )
        )
        return Agent(
            role=f"Codenames Operative for {self.team} team",
            goal=(
                f"Guess words based on the Spymaster's clue while avoiding the assassin. "
                f"Level: {self.difficulty}. {difficulty_instruction}"
            ),
            backstory=(
                "You are a sharp-minded word puzzle solver. You can ONLY "
                "see which words are on the board and which have been "
                "revealed — you do NOT know which unrevealed words belong "
                "to which team. CRITICAL: Do not attempt to guess based on information "
                "you can't see. No cheating."
            ),
            llm=self.llm,
            reasoning=self.difficulty == "hard",
            verbose=False,
        )

    # ── public API ──────────────────────────────────────────────────

    def make_guess(
        self,
        clue: str,
        number: int,
        public_board: list[dict],
        history: list[dict],
    ) -> GuessOutput:
        """Return one :class:`GuessOutput`. Direct LLM call for speed."""
        lang_label = "Arabic" if self.language == "ar" else "English"
        board_json = json.dumps(public_board, ensure_ascii=False)

        prompt = (
            f"You are a Codenames Operative on the {self.team} team. Difficulty: {self.difficulty}.\n"
            f"Spymaster Clue: '{clue}' for {number}.\n"
            f"Board (visible words): {board_json}\n"
            f"Visible history: {json.dumps(history, ensure_ascii=False, default=str)}\n"
            f"Task: Pick exactly ONE unrevealed word from the board as your guess.\n"
            f"IMPORTANT: The reasoning MUST be written entirely in {lang_label}. Not a single word in any other language.\n"
            f"The word you choose must exist on the board and must NOT be already revealed.\n"
            f'Response MUST be valid JSON: {{"word": "...", "confidence": 0.9, "reasoning": "..."}}'
        )

        response = self.llm.call([{"role": "user", "content": prompt}])
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            return GuessOutput(**data)
        except Exception:
            fallback_reason = (
                "خطأ في المعالجة" if self.language == "ar" else "Processing error"
            )
            return GuessOutput(word="", confidence=0.0, reasoning=fallback_reason)
