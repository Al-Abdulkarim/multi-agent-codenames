"""CardCreator agent — generates themed word lists for the Codenames board.

Uses Tavily web search as a tool so the agent can look up real-world data
for specific categories (e.g. "Saudi football players") before curating the
final word list.
"""

from __future__ import annotations

from crewai import Agent, Task, Crew, Process, LLM
from pydantic import BaseModel

from tools.tavily_search import search_category


# ── structured output ───────────────────────────────────────────────────

class WordList(BaseModel):
    words: list[str]


# ── agent wrapper ───────────────────────────────────────────────────────

class CardCreatorAgent:
    """Pre-game agent that generates the word list for the board."""

    def __init__(self, api_key: str, model: str = "gemini/gemini-2.0-flash"):
        self.llm = LLM(model=model, api_key=api_key, temperature=0.8)

    # ── factory ─────────────────────────────────────────────────────

    def _build_agent(self) -> Agent:
        return Agent(
            role="Codenames Word Generator",
            goal="Generate unique, thematically consistent words for a Codenames board",
            backstory=(
                "You are a multilingual vocabulary expert who specialises in creating "
                "word lists for the board game Codenames. You understand cultural context "
                "for both Arabic and English words. You ensure all words are unique, "
                "age-appropriate, and relevant to the requested category. "
                "When the user requests a specific real-world category (players, cities, etc.), "
                "use the search_category tool to find accurate, up-to-date names before "
                "building the word list."
            ),
            llm=self.llm,
            tools=[search_category],
            reasoning=True,
            verbose=False,
        )

    # ── public API ──────────────────────────────────────────────────

    def generate_words(
        self,
        count: int,
        language: str,
        category: str | None,
        difficulty: str,
    ) -> list[str]:
        """Return *count* unique words matching the requested parameters."""
        agent = self._build_agent()

        difficulty_guide = {
            "easy": "Common, well-known words with obvious groupings. Easy to associate.",
            "medium": "Mix of common and uncommon words. Some tricky relationships possible.",
            "hard": "Obscure words, many potential cross-team associations. Deceptive similarities.",
        }

        lang_label = "Arabic" if language == "ar" else "English"
        category_text = f"category '{category}'" if category else "random mixed themes"

        search_instruction = (
            f"IMPORTANT: First use the search_category tool to search for '{category}' "
            f"to get real, accurate names/terms. Then pick {count} from the results."
        ) if category else "Generate words from your own knowledge across mixed themes."

        task = Task(
            description=(
                f"Generate exactly {count} unique words in {lang_label} "
                f"for {category_text}. "
                f"Difficulty: {difficulty} — {difficulty_guide.get(difficulty, '')}. "
                f"{search_instruction} "
                f"Rules: no duplicates, no offensive words, each word must be a "
                f"single word (no spaces)."
            ),
            expected_output=(
                f"A JSON object with a 'words' array containing exactly {count} unique words."
            ),
            agent=agent,
            output_pydantic=WordList,
            guardrail=lambda result: self._validate(result, count),
            guardrail_max_retries=3,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        return result.pydantic.words

    # ── guardrail ───────────────────────────────────────────────────

    @staticmethod
    def _validate(result, expected_count: int):
        try:
            words = result.pydantic.words if hasattr(result, "pydantic") else []
            if len(words) != expected_count:
                return (False, f"Expected {expected_count} words, got {len(words)}")
            if len(set(words)) != len(words):
                return (False, "Duplicate words found")
            return (True, result)
        except Exception as exc:
            return (False, f"Invalid output: {exc}")
