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
        "ar": "رئيس مخابرات واثق واستراتيجي يتحدث بذكاء",
    },
    "ai_spymaster": {
        "en": "a confident, strategic AI Spymaster who speaks with authority",
        "ar": "رئيس مخابرات آلي واثق واستراتيجي يتحدث بذكاء",
    },
    "operative": {
        "en": "a sharp-minded Operative who is eager and reactive",
        "ar": "عميل ميداني ذكي ومتحمس وسريع التفاعل",
    },
    "ai_operative": {
        "en": "an enthusiastic AI Operative teammate",
        "ar": "عميل ميداني (ذكاء اصطناعي) متحمس",
    },
}

# Quick fallback reactions if Gemini is unavailable
FALLBACK_REACTIONS = {
    "en": {
        "good_guess": {
            "own": [
                "Nice one! 🎯",
                "Brilliant!",
                "That's what I'm talking about!",
                "Nailed it! 💪",
            ],
            "opp": [
                "Lucky guess...",
                "That was way too easy",
                "Don't get used to it",
                "Pure luck",
            ],
        },
        "bad_guess": {
            "own": ["Oops! 😬", "That hurts...", "Better luck next time!", "Oh no! 😱"],
            "opp": [
                "Hahaha! Thanks!",
                "Nice gift!",
                "Are you guys even trying?",
                "I'll take it!",
            ],
        },
        "clue_given": {
            "own": ["Interesting clue... 🤔", "Let's see!", "Bold move!"],
            "opp": [
                "Hmm, let's see what they do...",
                "Interesting...",
                "We'll handle this.",
            ],
        },
        "assassin": {
            "own": ["GAME OVER! 💀", "The assassin strikes! Nooo!"],
            "opp": ["GAME OVER! 💀", "They hit the assassin! We win!"],
        },
        "turn_start": ["Let's do this! 💪", "Our turn now!"],
        "winning": {
            "own": ["Victory is close! 😎", "We got this!"],
            "opp": ["They're ahead... we need to step up!", "Not over yet!"],
        },
        "losing": {
            "own": ["We need a comeback!", "Don't give up!"],
            "opp": ["Ha! We're dominating!", "Keep struggling! 😏"],
        },
        "taunt": [
            "I will beat you! 😏",
            "You don't stand a chance!",
            "Too easy!",
            "Watch and learn!",
        ],
    },
    "ar": {
        "good_guess": {
            "own": ["كفووو! 🎯", "يا سلام!", "هذا اللي أبيه!", "ممتاز! 💪"],
            "opp": [
                "حظ مبتدئين...",
                "ما راح تتكرر",
                "باقي طريق طويل يا بطل",
                "يا خسارة، ليش جبتوها صح؟",
                "لا تفرحون كثير...",
            ],
        },
        "bad_guess": {
            "own": ["أووف! 😬", "يا خسارة...", "حظ أوفر!", "لا لا لا! 😱"],
            "opp": [
                "ههههههه! أحسن!",
                "شكراً على الهدية!",
                "واضح إنكم ضايعين",
                "هذا مستواكم؟",
                "شكراً! كمّلوا كذا 😂",
            ],
        },
        "clue_given": {
            "own": ["تلميح مثير... 🤔", "نشوف وش يصير!", "حركة جريئة!"],
            "opp": [
                "وش عندهم؟ خلونا نشوف...",
                "إن شاء الله تنفعهم 😏",
                "مهما يحاولون!",
            ],
        },
        "assassin": {
            "own": ["انتهت اللعبة! 💀", "القاتل ضرب! خسارة!"],
            "opp": ["القاتل ضرب! فزنا! 🎉", "ههههه ضربوا القاتل! أحسن!"],
        },
        "turn_start": ["يلا بنا! 💪", "دورنا الحين!"],
        "winning": {
            "own": ["نحن ندمّر! 🔥", "النصر قريب!"],
            "opp": ["هم متقدمين... لازم نضغط!", "باقي أمل!"],
        },
        "losing": {
            "own": ["نقدر نقلب الطاولة!", "لا تستسلمون!"],
            "opp": ["نحن متقدمين! 😎", "كمّلوا خسارتكم! 😂"],
        },
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
        """Generate a short reaction to a game event."""
        acting_team = context.get("team")
        is_my_team = True
        if acting_team:
            is_my_team = acting_team == agent_team

        try:
            return self._generate_reaction(
                event_type, context, language, agent_role, agent_team, is_my_team
            )
        except Exception:
            return self._fallback_reaction(event_type, language, is_my_team)

    def _generate_reaction(
        self,
        event_type: str,
        context: dict,
        language: str,
        agent_role: str,
        agent_team: str,
        is_my_team: bool,
    ) -> str:
        """Call Gemini for a creative reaction."""
        personality = PERSONALITIES.get(agent_role, PERSONALITIES["ai_operative"])
        persona_desc = personality.get(language, personality["en"])

        lang_label = "Arabic" if language == "ar" else "English"
        team_label = agent_team.capitalize()
        opp_team = "Blue" if agent_team == "red" else "Red"

        # Build a clear situational context
        situation_desc = self._build_situation(
            event_type, context, is_my_team, language
        )

        prompt = (
            f"You are {persona_desc} on the {team_label} team. "
            f"The opposing team is {opp_team}.\n"
            f"Event: {event_type}.\n"
            f"Situation: {situation_desc}\n"
            f"STRICT RULES:\n"
            f"1. You MUST respond ONLY in {lang_label}. Not a single word in any other language.\n"
            f"2. If {is_my_team} is True: The event benefits YOUR team. "
            f"Be supportive and excited. Examples: 'Great job!', 'Nailed it!'.\n"
            f"3. If {is_my_team} is False: The event benefits the OPPONENT. "
            f"Be competitive, mock them, be frustrated. "
            f"NEVER congratulate the opponent. "
            f"Examples: 'Lucky guess...', 'Won't happen again', 'Whatever'.\n"
            f"4. Keep it under 10 words. Be natural and fun.\n"
            f"5. Reply ONLY with the comment text, nothing else."
        )

        client = self._get_client()
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = response.text.strip().strip('"').strip("'")
        if len(text) > 100:
            text = text[:97] + "..."
        return text

    @staticmethod
    def _build_situation(
        event_type: str, context: dict, is_my_team: bool, language: str
    ) -> str:
        """Build a clear human-readable situation description for the prompt."""
        word = context.get("word", "")
        clue = context.get("clue", "")
        correct = context.get("correct", None)

        if language == "ar":
            if event_type == "good_guess":
                if is_my_team:
                    return f"فريقي خمّن الكلمة '{word}' صح! نحن في طريقنا للفوز."
                else:
                    return f"الخصم خمّن الكلمة '{word}' صح. هذا مزعج."
            elif event_type == "bad_guess":
                if is_my_team:
                    return f"فريقي خمّن الكلمة '{word}' غلط! هذا مؤلم."
                else:
                    return f"الخصم خمّن الكلمة '{word}' غلط! هذا مضحك ويفيدنا."
            elif event_type == "assassin":
                if is_my_team:
                    return "فريقي أصاب بطاقة الاغتيال! خسرنا اللعبة!"
                else:
                    return "الخصم أصاب بطاقة الاغتيال! فزنا!"
            elif event_type == "clue_given":
                if is_my_team:
                    return f"أعطينا التلميح '{clue}'. نأمل فريقنا يفهم."
                else:
                    return f"الخصم أعطى تلميح. نشوف وش يسوون."
            elif event_type == "taunt":
                return "بداية دور جديد. وقت التحدي."
            elif event_type == "winning":
                if is_my_team:
                    return "نحن متقدمين! النصر قريب."
                else:
                    return "الخصم متقدم. لازم نضغط أكثر."
            elif event_type == "losing":
                if is_my_team:
                    return "نحن متأخرين. لازم نركز أكثر."
                else:
                    return "نحن متقدمين على الخصم!"
            else:
                return "حدث في اللعبة."
        else:
            if event_type == "good_guess":
                if is_my_team:
                    return f"My team guessed '{word}' correctly! We're on fire."
                else:
                    return f"The opponent guessed '{word}' correctly. Annoying."
            elif event_type == "bad_guess":
                if is_my_team:
                    return f"My team guessed '{word}' wrong! That hurts."
                else:
                    return f"The opponent guessed '{word}' wrong! Hilarious, helps us."
            elif event_type == "assassin":
                if is_my_team:
                    return "My team hit the assassin card! We lost!"
                else:
                    return "The opponent hit the assassin! We win!"
            elif event_type == "clue_given":
                if is_my_team:
                    return f"We gave the clue '{clue}'. Hoping the team gets it."
                else:
                    return f"The opponent gave a clue. Let's see what they do."
            elif event_type == "taunt":
                return "New turn starting. Time to show them."
            elif event_type == "winning":
                if is_my_team:
                    return "We're ahead! Victory is near."
                else:
                    return "The opponent is ahead. Need to step up."
            elif event_type == "losing":
                if is_my_team:
                    return "We're behind. Need to focus."
                else:
                    return "We're dominating the opponent!"
            else:
                return "A game event happened."

    @staticmethod
    def _fallback_reaction(event_type: str, language: str, is_my_team: bool) -> str:
        """Return a canned reaction when Gemini is unavailable."""
        reactions = FALLBACK_REACTIONS.get(language, FALLBACK_REACTIONS["en"])
        options = reactions.get(event_type, reactions.get("turn_start", ["..."]))

        if isinstance(options, dict):
            side = "own" if is_my_team else "opp"
            options = options.get(side, ["..."])

        return random.choice(options)
