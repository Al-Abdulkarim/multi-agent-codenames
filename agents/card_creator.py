"""CardCreator agent — generates themed word lists for the Codenames board.

Uses Tavily web search as a tool so the agent can look up real-world data
for specific categories (e.g. "Saudi football players") before curating the
final word list.
"""

from __future__ import annotations

import json
from crewai import Agent, LLM
from pydantic import BaseModel

from tools.tavily_search import search_category


# ── structured output ───────────────────────────────────────────────────


class WordList(BaseModel):
    words: list[str]


# ── agent wrapper ───────────────────────────────────────────────────────


class CardCreatorAgent:
    """Pre-game agent that generates the word list for the board."""

    def __init__(self, api_key: str, model: str = "gemini/gemini-2.5-flash"):
        self.llm = LLM(model=model, api_key=api_key, temperature=2)

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
        """Return *count* unique words using direct LLM call for speed."""
        difficulty_guide = {
            "easy": "Common, well-known words.",
            "medium": "Mix of common and uncommon words.",
            "hard": "Obscure words, tricky relationships.",
        }
        lang_label = "Arabic" if language == "ar" else "English"
        category_text = f"category '{category}'" if category else "random themes"

        prompt = (
            f"Generate exactly {count} unique {lang_label} words for Codenames.\n"
            f"Theme: {category_text}. Difficulty: {difficulty} ({difficulty_guide.get(difficulty, '')}).\n"
            f"Rules: NO duplicates, NO spaces, NO offensive words.\n"
            f'Response MUST be a JSON array of strings: ["word1", "word2", ...]'
        )

        response = self.llm.call([{"role": "user", "content": prompt}])
        try:
            text = response.strip()
            # Extract JSON if wrapped in markdown
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            words = json.loads(text)
            if isinstance(words, dict) and "words" in words:
                words = words["words"]

            # Ensure we have the right count and no duplicates
            words = list(dict.fromkeys(words))[:count]
            return words
        except Exception:
            # Absolute fallback
            return ["apple", "banana", "cherry", "date", "elderberry"][:count]

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
