"""Tavily web-search tool for the CardCreator agent.

When the user picks a real-world category (football players, cities, etc.)
the agent calls this tool to ground its word list in actual web data.
"""

from __future__ import annotations

import os

from crewai.tools import tool


@tool("search_category")
def search_category(query: str) -> str:
    """Search the web for words / names related to a Codenames category.

    Use this when the category requires real-world knowledge
    (e.g. football players, cities, historical figures).
    Returns a summary and source snippets.
    """
    # Lazy import so the rest of the app loads even without tavily
    from tavily import TavilyClient  # type: ignore[import-untyped]

    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return "ERROR: TAVILY_API_KEY is not set in the environment."

    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        search_depth="basic",
        max_results=5,
        include_answer=True,
    )

    answer = response.get("answer", "")
    snippets = [r.get("content", "") for r in response.get("results", [])[:3]]
    return f"Answer: {answer}\n\nSources:\n" + "\n---\n".join(snippets)
