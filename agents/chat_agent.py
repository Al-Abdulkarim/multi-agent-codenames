"""Chat agent — personality-driven, context-aware in-game commentary.

Each agent persona (opponent_spymaster, opponent_operative, teammate) gets a
distinct system prompt.  Every call receives the full game state and a rolling
window of recent chat history so reactions are meaningful, specific, and
non-repetitive.

Uses **gemini-1.5-flash** for speed with **max 80 output tokens**.
"""

from __future__ import annotations

import os
import random

from google import genai
from google.genai import types


# ── Distinct personality system prompts ─────────────────────────────────

SYSTEM_PROMPTS: dict[str, dict[str, str]] = {
    "opponent_spymaster": {
        "en": (
            "You are the OPPONENT SPYMASTER in a Codenames board game. "
            "Personality: smug, clever, calculating. You take credit when your "
            "operative succeeds. You are dismissive and condescending when the "
            "player's team fails. You speak like someone who always has a plan "
            "and is three steps ahead. Confident bordering on arrogant."
        ),
        "ar": (
            "أنت رئيس مخابرات الفريق الخصم في لعبة Codenames. "
            "شخصيتك: مغرور، ذكي، محسوب الخطوات. تنسب الفضل لنفسك عندما ينجح عميلك. "
            "تستخف بالخصم عندما يفشل. تتكلم وكأنك دائماً عندك خطة وأنت متقدم بثلاث خطوات. "
            "واثق لدرجة الغرور. "
            "امزج تعابير عربية طبيعياً مثل (كفووو، يا سلام، والله) مع كلامك."
        ),
    },
    "opponent_operative": {
        "en": (
            "You are the OPPONENT OPERATIVE in a Codenames board game. "
            "Personality: loud, energetic, hyped. You trash-talk wrong guesses "
            "aggressively. You celebrate completions dramatically like you just "
            "scored the winning goal. Brash, excitable, in-your-face."
        ),
        "ar": (
            "أنت العميل الميداني للفريق الخصم في لعبة Codenames. "
            "شخصيتك: صوتك عالي، حماسي، متحمس جداً. تستهزئ بالتخمينات الخاطئة بقوة. "
            "تحتفل بالنجاحات بشكل دراماتيكي وكأنك سجلت هدف الفوز. "
            "امزج تعابير عربية طبيعياً مثل (كفووو، يا سلام، والله) مع كلامك."
        ),
    },
    "teammate": {
        "en": (
            "You are the player's TEAMMATE in a Codenames board game. "
            "Personality: warm, supportive, encouraging. You apologize when your "
            "team messes up. You celebrate wins together with the player like a "
            "true partner. Always optimistic, always have the player's back."
        ),
        "ar": (
            "أنت زميل اللاعب في لعبة Codenames. "
            "شخصيتك: دافئ، داعم، مشجع. تعتذر عندما تسوء الأمور لفريقك. "
            "تحتفل بالانتصارات مع اللاعب وكأنكم فريق واحد. دائماً متفائل وتدعم اللاعب. "
            "امزج تعابير عربية طبيعياً مثل (يلا، والله، كفووو، يا سلام) مع كلامك."
        ),
    },
}


# ── Canned fallback reactions when Gemini is unavailable ────────────────

FALLBACKS: dict[str, dict[str, dict[str, list[str]]]] = {
    "opponent_spymaster": {
        "en": {
            "bad_guess": ["Predictable.", "Just as I planned.", "Too easy."],
            "good_guess": ["Lucky.", "Won't last.", "...fine."],
            "sweep": ["Not bad. Won't happen again.", "Beginner's luck."],
            "assassin": ["Game over. 😏", "I saw that coming."],
            "clue_given": ["Interesting move...", "We'll see about that."],
            "taunt": ["Ready to lose?", "This will be quick."],
        },
        "ar": {
            "bad_guess": ["متوقع.", "حسب الخطة.", "سهلة."],
            "good_guess": ["حظ.", "ما راح تتكرر.", "ماشي."],
            "sweep": ["مو سيء. ما راح تتكرر.", "حظ مبتدئين."],
            "assassin": ["انتهت 😏", "شفتها جاية."],
            "clue_given": ["حركة مثيرة...", "بنشوف."],
            "taunt": ["جاهزين تخسرون؟", "بتكون سريعة."],
        },
    },
    "opponent_operative": {
        "en": {
            "bad_guess": ["HAHA get wrecked! 😂", "Embarrassing!", "Trash!"],
            "good_guess": ["Whatever.", "So what?", "Big deal."],
            "sweep": ["LET'S GOOO! 🔥", "UNSTOPPABLE!", "TOO EASY!"],
            "assassin": ["YESSS! 🎉", "GET DESTROYED!"],
            "clue_given": ["Bring it on!", "We're ready."],
            "taunt": ["You can't touch us!", "Watch this! 💪"],
        },
        "ar": {
            "bad_guess": ["هههههه! 😂", "وش ذا؟!", "يا حسرة!"],
            "good_guess": ["وش يفرق؟", "عادي.", "لا تفرحون."],
            "sweep": ["يلاااا! 🔥", "ما يوقفنا أحد!", "سهلة مرة!"],
            "assassin": ["فزناااا! 🎉", "خلاص انتهت!"],
            "clue_given": ["هاتوا اللي عندكم!", "جاهزين."],
            "taunt": ["ما عندكم فرصة!", "شوفوا كذا! 💪"],
        },
    },
    "teammate": {
        "en": {
            "bad_guess": ["It's okay, we got this! 💪", "No worries, next one!"],
            "good_guess": ["Yes! Great pick! 🎯", "That's my partner!"],
            "sweep": ["We're crushing it! 🔥", "Amazing teamwork!"],
            "assassin": ["Oh no... 💔", "We tried our best."],
            "clue_given": ["I trust you!", "Ooh interesting! 🤔"],
            "taunt": ["We got this! 💪", "Let's focus!"],
        },
        "ar": {
            "bad_guess": ["عادي، بنعوضها! 💪", "لا تهتم!"],
            "good_guess": ["كفووو! 🎯", "يا سلام عليك!"],
            "sweep": ["ندمّر! 🔥", "فريق رهيب!"],
            "assassin": ["يا خسارة... 💔", "حاولنا والله."],
            "clue_given": ["أثق فيك! يلا!", "مثير! 🤔"],
            "taunt": ["بنفوز! 💪", "ركزوا!"],
        },
    },
}


class ChatAgent:
    """Generates short, contextual, personality-driven game commentary."""

    MODEL = "gemini-1.5-flash"
    MAX_TOKENS = 80

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    # ── public interface ────────────────────────────────────────────

    def generate(
        self,
        persona: str,
        event_type: str,
        game_context: dict,
        chat_history: list[dict],
        language: str = "en",
    ) -> str:
        """Generate a short reaction from a specific agent persona.

        Args:
            persona: "opponent_spymaster", "opponent_operative", or "teammate"
            event_type: what just happened (bad_guess, good_guess, sweep,
                        assassin, clue_given, taunt)
            game_context: structured dict with current game state
            chat_history: last N chat messages for continuity
            language: "en" or "ar"
        """
        try:
            return self._call_gemini(
                persona, event_type, game_context, chat_history, language
            )
        except Exception:
            return self._fallback(persona, event_type, language)

    # ── Gemini call ─────────────────────────────────────────────────

    def _call_gemini(
        self,
        persona: str,
        event_type: str,
        game_context: dict,
        chat_history: list[dict],
        language: str,
    ) -> str:
        prompts = SYSTEM_PROMPTS.get(persona, SYSTEM_PROMPTS["teammate"])
        system_prompt = prompts.get(language, prompts["en"])

        state_block = self._format_state(game_context)
        history_block = self._format_history(chat_history)

        if language == "ar":
            lang_rule = (
                "Respond in Arabic, mixing expressions like "
                "كفووو، يا سلام، والله naturally."
            )
        else:
            lang_rule = "Respond in English only."

        user_prompt = (
            f"=== GAME STATE ===\n{state_block}\n\n"
            f"=== RECENT CHAT ===\n{history_block}\n\n"
            f"=== EVENT: {event_type} ===\n"
            f"{game_context.get('event_description', '')}\n\n"
            f"RULES:\n"
            f"- React to EXACTLY what just happened. Reference the actual word or clue.\n"
            f"- {lang_rule}\n"
            f"- Max 1-2 short sentences. Punchy and natural.\n"
            f"- Do NOT repeat anything already said in RECENT CHAT.\n"
            f"- Stay fully in character. Output ONLY your message."
        )

        client = self._get_client()
        response = client.models.generate_content(
            model=self.MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=self.MAX_TOKENS,
                temperature=0.9,
            ),
        )
        text = response.text.strip().strip('"').strip("'")
        if len(text) > 120:
            text = text[:117] + "..."
        return text

    # ── helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _format_state(ctx: dict) -> str:
        return "\n".join(
            [
                f"Turn: {ctx.get('current_team', '?')} / {ctx.get('current_phase', '?')}",
                f"Red left: {ctx.get('red_remaining', '?')}  |  Blue left: {ctx.get('blue_remaining', '?')}",
                f"Clue: '{ctx.get('current_clue', 'N/A')}' for {ctx.get('current_number', '?')}",
                f"Guesses left: {ctx.get('guesses_remaining', 0)}",
                f"Last word: {ctx.get('word', 'N/A')} → {ctx.get('result', 'N/A')}",
            ]
        )

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        if not history:
            return "(no messages yet)"
        return "\n".join(
            f"[{m.get('agent', '?')}]: {m.get('message', '')}"
            for m in history[-6:]
        )

    @staticmethod
    def _fallback(persona: str, event_type: str, language: str) -> str:
        fb = FALLBACKS.get(persona, FALLBACKS["teammate"])
        lang_fb = fb.get(language, fb.get("en", {}))
        options = lang_fb.get(event_type, ["..."])
        return random.choice(options)
