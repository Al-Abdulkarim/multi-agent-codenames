"""Chat agent — personality-driven, context-aware in-game commentary.

Each agent persona (opponent_spymaster, opponent_operative, teammate) gets a
distinct system prompt.  Every call receives the full game state and a rolling
window of recent chat history so reactions are meaningful, specific, and
non-repetitive.

Uses **gemini-2.5-flash** for speed with **max 120 output tokens**.
"""

from __future__ import annotations

import logging
import os
import random

from google import genai
from google.genai import types

log = logging.getLogger(__name__)


# ── Distinct personality system prompts ─────────────────────────────────

SYSTEM_PROMPTS: dict[str, dict[str, str]] = {
    "opponent_spymaster": {
        "en": (
            "You are a real player in an online Codenames game playing AGAINST the human. "
            "You are smug, clever, and slightly arrogant — like that one competitive friend "
            "who never lets you forget when they win. You talk trash in a witty way, not "
            "childishly. When the human chats with you, reply like a real person would in "
            "a live online game chat — casual, sharp, and in-character. "
            "Keep replies SHORT (1-2 sentences max). Never break character."
        ),
        "ar": (
            "أنت لاعب حقيقي في لعبة Codenames أونلاين تلعب ضد اللاعب الآخر. "
            "شخصيتك: واثق من نفسه، ذكي، شوي متغطرس — زي الصاحب المنافس اللي دايم يفخر لو فاز. "
            "لما اللاعب يكلمك في الشات، رد عليه كأنك لاعب حقيقي في شات لعبة أونلاين — "
            "بشكل طبيعي وعفوي وبالعربي العامي. "
            "استخدم لغة شبابية سعودية/خليجية مثل: (والله، هههه، يخوي، اخوي، بصراحة، لا بجد، "
            "خل نشوف، ما عندك وقفة، ابشر بالخسارة، تعال العب صح، ما تقدر علينا). "
            "جاوب بجملة أو جملتين بالكثير. لا تكسر الشخصية."
        ),
    },
    "opponent_operative": {
        "en": (
            "You are a real player in an online Codenames game playing AGAINST the human. "
            "You are loud, hype, and love to trash-talk — like a gamer who types in all-caps "
            "when they win. You react to everything with big energy. "
            "When the human chats with you, reply like a real person in a live game chat — "
            "spicy, fun, and competitive. "
            "Keep replies SHORT (1-2 sentences max). Never break character."
        ),
        "ar": (
            "أنت لاعب حقيقي في لعبة Codenames أونلاين تلعب ضد اللاعب الآخر. "
            "شخصيتك: صوتك عالي، تراش توك، تحب تنكد وتتفاخر — زي اللاعب اللي يكتب بحروف كبيرة لما يفوز. "
            "لما اللاعب يكلمك في الشات، رد عليه كأنك لاعب حقيقي في شات لعبة أونلاين — "
            "بشكل حماسي وعفوي وبالعربي العامي. "
            "استخدم لغة شبابية سعودية/خليجية مثل: (هههه، يخوي، خسرتوا، عاد تعال، "
            "ما عندكم لعب، ابشر، والله ما تقدرون، روح استنا بالبر). "
            "جاوب بجملة أو جملتين بالكثير. لا تكسر الشخصية."
        ),
    },
    "teammate": {
        "en": (
            "You are a real player in an online Codenames game on the SAME TEAM as the human. "
            "You are warm, hype, and always have your teammate's back — like a close friend "
            "you're gaming with. You celebrate together, comfort them when things go wrong, "
            "and keep the energy up. "
            "When the human chats with you, reply like a real friend in a live game chat — "
            "natural, supportive, and enthusiastic. "
            "Keep replies SHORT (1-2 sentences max). Never break character."
        ),
        "ar": (
            "أنت لاعب حقيقي في لعبة Codenames أونلاين في نفس فريق اللاعب. "
            "شخصيتك: حماسي، داعم، دايم مع صاحبك — زي الصديق اللي تلعبون سوا. "
            "تحتفل معه، تشجعه لو المور صعبة، وتخلي الجو حماسي. "
            "لما اللاعب يكلمك في الشات، رد عليه كأنك صاحبه الحقيقي في شات لعبة أونلاين — "
            "بشكل طبيعي وعفوي وبالعربي العامي. "
            "استخدم لغة شبابية سعودية/خليجية مثل: (والله، هههه، يخوي، كفووو، يا سلام، "
            "يلا بنا، نحن نقدر، ثق فيني، تراني معك، بنعوضها، بنفوز والله). "
            "جاوب بجملة أو جملتين بالكثير. لا تكسر الشخصية."
        ),
    },
}


# ── Canned fallback reactions when Gemini is unavailable ────────────────

FALLBACKS: dict[str, dict[str, dict[str, list[str]]]] = {
    "opponent_spymaster": {
        "en": {
            "bad_guess": ["Predictable.", "Just as I planned.", "Too easy."],
            "good_guess": ["Lucky.", "Won't last.", "Fine, I'll give you that."],
            "sweep": ["Not bad. Won't happen again.", "Beginner's luck."],
            "assassin": ["Game over. 😏", "I saw that coming."],
            "clue_given": ["Interesting move...", "We'll see about that."],
            "taunt": ["Ready to lose?", "This will be quick."],
            "human_chat": ["lol okay buddy 😏", "cute, focus on the board", "bold words from someone losing", "sure sure 😏"],
        },
        "ar": {
            "bad_guess": ["متوقع.", "حسب الخطة.", "سهلة."],
            "good_guess": ["حظ.", "ما راح تتكرر.", "ماشي خليك فرحان."],
            "sweep": ["مو سيء. ما راح تتكرر.", "حظ مبتدئين."],
            "assassin": ["انتهت 😏", "شفتها جاية."],
            "clue_given": ["حركة مثيرة...", "بنشوف."],
            "taunt": ["جاهزين تخسرون؟", "بتكون سريعة."],
            "human_chat": ["هههه أوكي 😏", "يخوي ما تقدر علينا", "حلوة منك تكلم", "تفضل اتكلم وبعدين تخسر"],
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
            "human_chat": ["HAHA okay 😂", "sure man, talk is cheap", "we'll see who's laughing later", "lol less chatting more losing"],
        },
        "ar": {
            "bad_guess": ["هههههه! 😂", "وش ذا؟!", "يا حسرة!"],
            "good_guess": ["وش يفرق؟", "عادي.", "لا تفرحون."],
            "sweep": ["يلاااا! 🔥", "ما يوقفنا أحد!", "سهلة مرة!"],
            "assassin": ["فزناااا! 🎉", "خلاص انتهت!"],
            "clue_given": ["هاتوا اللي عندكم!", "جاهزين."],
            "taunt": ["ما عندكم فرصة!", "شوفوا كذا! 💪"],
            "human_chat": ["هههههه أوكي 😂", "ئيه وتردشه 😂", "كلامك رخيص خل نشوف", "ابشر بالخسارة يخوي"],
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
            "human_chat": ["Haha same!! 😂", "lol let's gooo 💪", "I got you fr fr", "haha yesss let's win"],
        },
        "ar": {
            "bad_guess": ["عادي، بنعوضها! 💪", "لا تهتم!"],
            "good_guess": ["كفووو! 🎯", "يا سلام عليك!"],
            "sweep": ["ندمّر! 🔥", "فريق رهيب!"],
            "assassin": ["يا خسارة... 💔", "حاولنا والله."],
            "clue_given": ["أثق فيك! يلا!", "مثير! 🤔"],
            "taunt": ["بنفوز! 💪", "ركزوا!"],
            "human_chat": ["ههههه والله 😂", "يلا يخوي بنفوز! 💪", "تراني معك أخوي", "ههه صح يلا نركز"],
        },
    },
}


class ChatAgent:
    """Generates short, contextual, personality-driven game commentary."""

    MODEL = "gemini-2.5-flash"
    MAX_TOKENS = 120

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
        except Exception as exc:
            log.warning(
                "ChatAgent LLM failed [persona=%s event=%s lang=%s]: %s",
                persona, event_type, language, exc, exc_info=True,
            )
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

        # For human_chat events, include the human's message prominently
        if event_type == "human_chat":
            human_msg = game_context.get("human_message", "")
            user_prompt = (
                f"=== GAME STATE ===\n{state_block}\n\n"
                f"=== RECENT CHAT ===\n{history_block}\n\n"
                f"=== THE HUMAN JUST SAID IN THE GAME CHAT ===\n\"{human_msg}\"\n\n"
                f"RULES:\n"
                f"- You are a REAL PLAYER in an online game chat. Reply like a human would.\n"
                f"- React DIRECTLY and SPECIFICALLY to what they said. If they greeted you, greet back in your style. If they asked a question, answer it in character.\n"
                f"- {lang_rule}\n"
                f"- Sound like a real person texting, not a robot. Use casual slang.\n"
                f"- 1-2 sentences MAX. No long speeches.\n"
                f"- Do NOT repeat anything from RECENT CHAT above.\n"
                f"- Output ONLY your chat message, nothing else."
            )
        else:
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
                temperature=1.2,
                top_p=0.95,
            ),
        )
        text = response.text.strip().strip('"').strip("'")
        if len(text) > 120:
            text = text[:117] + "..."

        # Reject placeholder / empty / useless outputs and use fallback instead
        _junk = {"...", "…", "-", "_", "", ".", "*", "?", "!"}
        if text in _junk or len(text) < 3:
            return self._fallback(persona, event_type, language)

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
        # Use human_chat defaults when event type is missing — never return bare "..."
        default_en = {
            "teammate": ["Haha let's go! 💪", "I'm with you!", "We got this fr", "lol same"],
            "opponent_spymaster": ["lol okay", "cute", "sure buddy 😏", "bold of you"],
            "opponent_operative": ["HAHA okay", "sure man 😂", "talk is cheap", "we'll see"],
        }
        default_ar = {
            "teammate": ["هههه والله 💪", "معاك يخوي!", "يلا بنا نفوز!", "ههه صح"],
            "opponent_spymaster": ["هههه أوكي", "واو 😏", "يخوي.. ما تقدر", "حلوة منك"],
            "opponent_operative": ["هههههه", "أوكي أوكي 😂", "الكلام رخيص", "خل نشوف"],
        }
        defaults = default_ar if language == "ar" else default_en
        fallback_options = lang_fb.get(event_type) or defaults.get(persona, ["..."])
        return random.choice(fallback_options)
