"""AI Spymaster agent — generates one-word clues for its team.

Difficulty controls:
  • easy  → simple single-link clue, no reasoning
  • medium → reflection-based, targets 2 words
  • hard  → multi-step reasoning, targets 3-4 words
"""

from __future__ import annotations

import json

from crewai import Agent, Task, Crew, Process, LLM
from pydantic import BaseModel

from tools.board_tools import analyze_board


# ── structured output ───────────────────────────────────────────────────


class ClueOutput(BaseModel):
    clue: str
    number: int
    reflection: str  # Explicit thought process for the logs


# ── agent wrapper ───────────────────────────────────────────────────────


class AISpymaster:
    """Creates and runs a Spymaster crew that produces a clue."""

    BACKSTORIES = {
        "easy": (
            "You are a beginner Spymaster. Give simple, safe clues that "
            "link to just 1 of your team's words. Avoid any risk. CRITICAL: "
            "Do not communicate secret info beyond the clue and number. No cheating."
        ),
        "medium": (
            "You are an experienced Spymaster. Find clever clues that link "
            "2 of your team's words while carefully avoiding opponent and "
            "assassin words. CRITICAL: No extra information allowed. No cheating."
        ),
        "hard": (
            "You are a master Spymaster. Find brilliant clues linking 3-4 "
            "words. Analyse every possible interpretation and risk before "
            "committing. Think multiple turns ahead. CRITICAL: No extra info. "
            "No cheating."
        ),
    }

    TARGET_WORDS = {"easy": 1, "medium": 2, "hard": 3}

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
        self.llm = LLM(model=model, api_key=api_key, temperature=0.7)

    # ── factory ─────────────────────────────────────────────────────

    def _build_agent(self) -> Agent:
        return Agent(
            role=f"Codenames Spymaster for {self.team} team",
            goal=(
                "Give the best one-word clue connecting as many of your "
                "team's unrevealed words as possible"
            ),
            backstory=self.BACKSTORIES.get(self.difficulty, self.BACKSTORIES["medium"]),
            llm=self.llm,
            tools=[analyze_board],
            reasoning=self.difficulty in ("medium", "hard"),
            max_reasoning_attempts=3 if self.difficulty == "hard" else 1,
            verbose=False,
        )

    # ── public API ──────────────────────────────────────────────────

    def generate_clue(
        self,
        spymaster_board: list[dict],
        history: list[dict],
        category: str | None = None,
    ) -> ClueOutput:
        """Return a :class:`ClueOutput` using direct LLM call for speed."""
        target = self.TARGET_WORDS.get(self.difficulty, 2)
        board_json = json.dumps(spymaster_board, ensure_ascii=False)
        lang_label = "Arabic" if self.language == "ar" else "English"

        prompt = (
            f"You are a Codenames Spymaster on the {self.team} team. Difficulty: {self.difficulty}.\n"
            f"Board: {board_json}\n"
            f"Previous turns: {json.dumps(history, ensure_ascii=False, default=str)}\n"
            f"Task: Give one-word clue in {lang_label} for {target} words.\n"
            f"IMPORTANT: The clue word MUST be in {lang_label}. The reflection MUST also be in {lang_label}.\n"
            f"Avoid opponent, neutral, and assassin words.\n"
            f"STRICT: No words from the board. No category words like '{category}'.\n"
            f'Format: JSON {{"clue": "...", "number": {target}, "reflection": "..."}}'
        )

        response = self.llm.call([{"role": "user", "content": prompt}])
        try:
            # Simple extractor for JSON in case of markdown wrapping
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            return ClueOutput(**data)
        except Exception:
            fallback_clue = "رابط" if self.language == "ar" else "link"
            fallback_refl = (
                "خطأ في المعالجة" if self.language == "ar" else "Processing error"
            )
            return ClueOutput(clue=fallback_clue, number=1, reflection=fallback_refl)
