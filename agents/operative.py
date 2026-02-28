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
        api_key: str,
        model: str = "gemini/gemini-2.5-flash",
    ):
        self.team = team
        self.difficulty = difficulty
        self.llm = LLM(model=model, api_key=api_key, temperature=0.4)

    # ── factory ─────────────────────────────────────────────────────

    def _build_agent(self) -> Agent:
        return Agent(
            role=f"Codenames Operative for {self.team} team",
            goal=(
                "Guess the correct words based on the Spymaster's clue "
                "while avoiding the assassin"
            ),
            backstory=(
                "You are a sharp-minded word puzzle solver. You can ONLY "
                "see which words are on the board and which have been "
                "revealed — you do NOT know which unrevealed words belong "
                "to which team. Think carefully about word associations."
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
        """Return one :class:`GuessOutput`.  Call iteratively for multiple guesses."""
        agent = self._build_agent()

        task = Task(
            description=(
                f"The Spymaster's clue is '{clue}' for {number}.\n"
                f"Visible board (you CANNOT see unrevealed types): "
                f"{json.dumps(public_board, ensure_ascii=False)}\n"
                f"Previous turns: {json.dumps(history, ensure_ascii=False, default=str)}\n"
                f"Pick your BEST single guess from the unrevealed words on the board. "
                f"Return the exact word as it appears on the board."
            ),
            expected_output=(
                "JSON with 'word' (exact board word), 'confidence' (0-1), "
                "and 'reasoning' (brief explanation)"
            ),
            agent=agent,
            output_pydantic=GuessOutput,
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
