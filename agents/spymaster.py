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


# ── agent wrapper ───────────────────────────────────────────────────────

class AISpymaster:
    """Creates and runs a Spymaster crew that produces a clue."""

    BACKSTORIES = {
        "easy": (
            "You are a beginner Spymaster. Give simple, safe clues that "
            "link to just 1 of your team's words. Avoid any risk."
        ),
        "medium": (
            "You are an experienced Spymaster. Find clever clues that link "
            "2 of your team's words while carefully avoiding opponent and "
            "assassin words."
        ),
        "hard": (
            "You are a master Spymaster. Find brilliant clues linking 3-4 "
            "words. Analyse every possible interpretation and risk before "
            "committing. Think multiple turns ahead."
        ),
    }

    TARGET_WORDS = {"easy": 1, "medium": 2, "hard": 3}

    def __init__(
        self,
        team: str,
        difficulty: str,
        api_key: str,
        model: str = "gemini/gemini-2.5-flash",
    ):
        self.team = team
        self.difficulty = difficulty
        self.llm = LLM(model=model, api_key=api_key, temperature=0.7)

    # ── factory ─────────────────────────────────────────────────────

    def _build_agent(self) -> Agent:
        return Agent(
            role=f"Codenames Spymaster for {self.team} team",
            goal=(
                "Give the best one-word clue connecting as many of your "
                "team's unrevealed words as possible while avoiding the assassin"
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
    ) -> ClueOutput:
        """Return a :class:`ClueOutput` with a single-word clue and number."""
        agent = self._build_agent()
        target = self.TARGET_WORDS.get(self.difficulty, 2)

        board_json = json.dumps(spymaster_board, ensure_ascii=False)

        task = Task(
            description=(
                f"You are the {self.team} Spymaster.\n"
                f"Board (you can see all types): {board_json}\n"
                f"Previous turns: {json.dumps(history, ensure_ascii=False, default=str)}\n"
                f"Target connecting {target} of your team's unrevealed words.\n"
                f"Give a one-word clue and the number of words it relates to.\n"
                f"NEVER use a word that is on the board. Avoid the assassin at all costs."
            ),
            expected_output="JSON with 'clue' (single word) and 'number' (integer)",
            agent=agent,
            output_pydantic=ClueOutput,
            guardrail_max_retries=3,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
            memory=True,
        )
        result = crew.kickoff()
        return result.pydantic
