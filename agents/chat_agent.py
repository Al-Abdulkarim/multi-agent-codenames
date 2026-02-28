"""Chat agent — generates fun in-game commentary from AI agents.

Uses Google Gemini directly (lightweight, no CrewAI overhead) to produce
short, personality-filled reactions to game events.
"""

from __future__ import annotations

import os
import random
from google import genai


# ── personality templates ───────────────────────────────────────────────

PERSONALITIES = {
    "spymaster": {
        "en": "a confident, strategic Spymaster who speaks with authority",
        "ar": "رئيس جواسيس واثق واستراتيجي يتحدث بسلطة",
    },
    "operative": {
        "en": "an enthusiastic, bold Operative who loves the thrill of guessing",
        "ar": "عميل متحمس وجريء يحب إثارة التخمين",
    },
}

# Quick fallback reactions if Gemini is unavailable
FALLBACK_REACTIONS = {
    "en": {
        "good_guess": ["Nice one! 🎯", "Brilliant!", "That's what I'm talking about!", "Nailed it! 💪"],
        "bad_guess": ["Oops! 😬", "That hurts...", "Better luck next time!", "Oh no! 😱"],
        "clue_given": ["Interesting clue... 🤔", "Let's see what happens!", "Bold move!", "I see what you did there 👀"],
        "assassin": ["GAME OVER! 💀", "The assassin strikes!", "That was devastating!", "NO WAY! 😱"],
        "turn_start": ["Let's do this! 💪", "Our turn now!", "Time to shine! ✨", "Focus team!"],
        "winning": ["We're crushing it! 🔥", "Victory is near!", "Can't stop us!", "Almost there! 🏆"],
        "losing": ["We can still turn this around!", "Don't give up!", "It's not over yet!", "Come on team! 💪"],
        "taunt": ["I will beat you! 😏", "You don't stand a chance!", "Too easy! 🥱", "Watch and learn!"],
    },
    "ar": {
        "good_guess": ["كفووو! 🎯", "يا سلام!", "هذا اللي أبيه!", "ممتاز! 💪"],
        "bad_guess": ["أووف! 😬", "يا خسارة...", "حظ أوفر!", "لا لا لا! 😱"],
        "clue_given": ["تلميح مثير... 🤔", "نشوف وش يصير!", "حركة جريئة!", "فهمت عليك 👀"],
        "assassin": ["انتهت اللعبة! 💀", "القاتل ضرب!", "كارثة!", "مستحيل! 😱"],
        "turn_start": ["يلا بنا! 💪", "دورنا الحين!", "وقت نتألق! ✨", "ركزوا يا فريق!"],
        "winning": ["نحن ندمر! 🔥", "النصر قريب!", "ما يوقفنا أحد!", "تقريبا وصلنا! 🏆"],
        "losing": ["نقدر نقلب الطاولة!", "لا تستسلمون!", "ما انتهت بعد!", "يلا يا فريق! 💪"],
        "taunt": ["بنفوز عليكم! 😏", "ما عندكم فرصة!", "سهلة مرة! 🥱", "تعلموا مننا!"],
    },
}


class ChatAgent:
    """Generates short, fun in-game comments from AI agent personas."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def react(
        self,
        event_type: str,
        context: dict,
        language: str = "en",
        agent_role: str = "operative",
        agent_team: str = "red",
    ) -> str:
        """Generate a short reaction to a game event.

        Falls back to canned responses if Gemini call fails.
        """
        try:
            return self._generate_reaction(event_type, context, language, agent_role, agent_team)
        except Exception:
            return self._fallback_reaction(event_type, language)

    def _generate_reaction(
        self,
        event_type: str,
        context: dict,
        language: str,
        agent_role: str,
        agent_team: str,
    ) -> str:
        """Call Gemini for a creative reaction."""
        personality = PERSONALITIES.get(agent_role, PERSONALITIES["operative"])
        persona_desc = personality.get(language, personality["en"])

        lang_label = "Arabic" if language == "ar" else "English"
        team_label = agent_team.capitalize()

        prompt = (
            f"You are {persona_desc} on the {team_label} team in a Codenames board game.\n"
            f"React to this event with a SHORT, fun comment (max 15 words) in {lang_label}.\n"
            f"Be competitive, playful, and expressive. Use emoji sometimes.\n"
            f"Event: {event_type}\n"
            f"Context: {context}\n"
            f"Reply with ONLY the comment, nothing else."
        )

        client = self._get_client()
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = response.text.strip().strip('"').strip("'")
        # Limit length
        if len(text) > 100:
            text = text[:97] + "..."
        return text

    @staticmethod
    def _fallback_reaction(event_type: str, language: str) -> str:
        """Return a canned reaction when Gemini is unavailable."""
        reactions = FALLBACK_REACTIONS.get(language, FALLBACK_REACTIONS["en"])
        options = reactions.get(event_type, reactions.get("turn_start", ["..."]))
        return random.choice(options)
