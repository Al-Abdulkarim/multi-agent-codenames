"""
وكلاء الفريق المنافس (الذكاء الاصطناعي)
AI Team Agents - Spymaster & Operative
مع العزل التقني لضمان عدم الغش
"""

import json
import random
import re
from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import GameConfig, Difficulty, TeamColor, CardType
from game_state import GameState, ThinkingStep
from guardrails import ClueValidator


# ============================================================
# وكيل القائد - Spymaster Agent
# يملك حق الوصول إلى الخريطة السرية
# ============================================================


class AISpymaster:
    """
    وكيل قائد الفريق AI
    لديه حق الوصول إلى الخريطة السرية (أنواع البطاقات)
    مسؤول عن إعطاء الشفرات
    """

    def __init__(self, config: GameConfig, team: TeamColor):
        self.config = config
        self.team = team
        self.difficulty = config.ai_difficulty
        self.llm = ChatGoogleGenerativeAI(
            model=config.gemini_model,
            google_api_key=config.google_api_key,
            temperature=self._get_temperature(),
        )

    def _extract_json(self, content: str) -> Any:
        """استخراج JSON من نص قد يحتوي على كلام إضافي"""
        try:
            match = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(content)
        except Exception as e:
            print(f"❌ JSON Parse Error in AI Team: {e}\nContent: {content}")
            return None

    def _get_temperature(self) -> float:
        temps = {
            Difficulty.EASY: 0.9,
            Difficulty.MEDIUM: 0.6,
            Difficulty.HARD: 0.3,
        }
        return temps[self.difficulty]

    def _get_secret_view(self, game_state: GameState) -> dict:
        """
        الحصول على العرض السري - فقط القائد يمكنه الوصول
        هذه هي البيانات التي لا يجب أن يصل إليها العميل
        """
        team_ct = CardType.RED if self.team == TeamColor.RED else CardType.BLUE
        opp_ct = CardType.BLUE if self.team == TeamColor.RED else CardType.RED

        our_words = [
            c.word
            for c in game_state.board
            if c.card_type == team_ct and not c.revealed
        ]
        opponent_words = [
            c.word for c in game_state.board if c.card_type == opp_ct and not c.revealed
        ]
        neutral_words = [
            c.word
            for c in game_state.board
            if c.card_type == CardType.NEUTRAL and not c.revealed
        ]
        assassin_words = [
            c.word
            for c in game_state.board
            if c.card_type == CardType.ASSASSIN and not c.revealed
        ]

        return {
            "our_words": our_words,
            "opponent_words": opponent_words,
            "neutral_words": neutral_words,
            "assassin_words": assassin_words,
        }

    async def generate_clue(self, game_state: GameState) -> dict:
        """توليد شفرة حسب مستوى الصعوبة"""
        if self.difficulty == Difficulty.EASY:
            return await self._easy_clue(game_state)
        elif self.difficulty == Difficulty.MEDIUM:
            return await self._medium_clue(game_state)
        else:
            return await self._hard_clue(game_state)

    async def _easy_clue(self, game_state: GameState) -> dict:
        """
        المستوى العادي - منطق بسيط
        يحاول ربط كلمة أو كلمتين فقط
        """
        secret = self._get_secret_view(game_state)
        thinking_steps = []
        agent_name = f"مساعدك (قائد {self.difficulty.value})"

        # خطوة التخطيط
        words_list = ", ".join(secret["our_words"])
        thinking_steps.append(
            ThinkingStep(
                agent_name=agent_name,
                step_type="planning",
                content=f"أبحث عن شفرة بسيطة. كلماتنا: {words_list}",
            )
        )

        system_msg = SystemMessage(
            content=f"""أنت قائد فريق Codenames. مستواك: مبتدئ.
تلعب للفريق {'الأحمر' if self.team == TeamColor.RED else 'الأزرق'}.

كلماتنا: {', '.join(secret['our_words'])}
كلمات الخصم: {', '.join(secret['opponent_words'])}
كلمات محايدة: {', '.join(secret['neutral_words'])}
القاتل: {', '.join(secret['assassin_words'])}

المهمة: أعط شفرة (كلمة) ورقم (1). اربط كلمة واحدة مباشرة جداً.
أجب بتنسيق JSON فقط:
{{"clue": "شفرة", "number": 1, "reasoning": "سبب"}}"""
        )

        try:
            response = await self.llm.ainvoke(
                [system_msg, HumanMessage(content="شفرة بسيطة وآمنة.")]
            )
            content = response.content.strip()
            result = self._extract_json(content)
            if not result:
                raise ValueError("فشل تحليل JSON")
            clue_word = result.get("clue", "")
            clue_number = min(result.get("number", 1), 1)

            # التحقق من الشفرة
            validation = ClueValidator.validate_clue(clue_word, clue_number, game_state)
            if not validation["valid"]:
                clue_word = self._fallback_clue(secret["our_words"])
                clue_number = 1

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=(
                        f"اخترت الشفرة: '{clue_word}' - {clue_number}. "
                        f"السبب: {result.get('reasoning', 'ربط بسيط')}"
                    ),
                )
            )

            return {
                "clue": clue_word,
                "number": clue_number,
                "thinking_steps": thinking_steps,
                "reasoning": result.get("reasoning", ""),
            }

        except Exception as e:
            clue_word = self._fallback_clue(secret["our_words"])
            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=f"استخدمت شفرة احتياطية: '{clue_word}' بسبب: {str(e)}",
                )
            )
            return {
                "clue": clue_word,
                "number": 1,
                "thinking_steps": thinking_steps,
            }

    async def _medium_clue(self, game_state: GameState) -> dict:
        """
        المستوى المتوسط - منطق متقدم
        يحاول ربط 2-3 كلمات مع تجنب الفخاخ
        """
        secret = self._get_secret_view(game_state)
        memory_context = game_state.ai_spymaster_memory.get_context()
        thinking_steps = []
        agent_name = f"مساعدك (قائد {self.difficulty.value})"

        # خطوة التفكير Reflection
        r_con = (
            f"أحلل الوضع: لدينا {len(secret['our_words'])} كلمات متبقية. "
            f"الخصم لديه {len(secret['opponent_words'])}. "
            f"تجنب {', '.join(secret['assassin_words'])}."
        )
        thinking_steps.append(
            ThinkingStep(
                agent_name=agent_name,
                step_type="reflection",
                content=r_con,
            )
        )

        # خطوة التخطيط
        thinking_steps.append(
            ThinkingStep(
                agent_name=agent_name,
                step_type="planning",
                content=f"أبحث عن روابط بين: {', '.join(secret['our_words'])}.",
            )
        )

        system_msg = SystemMessage(
            content=f"""أنت قائد فريق متمرس. مستواك: متوسط.
كلمات فريقك: {', '.join(secret['our_words'])}
كلمات الخصم: {', '.join(secret['opponent_words'])}
القاتل: {', '.join(secret['assassin_words'])}

الذاكرة والسياق السابق:
{memory_context if memory_context else 'لا يوجد سياق سابق'}

أعط شفرة تربط كلمتين. الرقم 1 أو 2.
أجب بتنسيق JSON:
{{"clue": "شفرة", "number": 1, "target_words": ["كلمة"], "reasoning": "سبب"}}"""
        )

        try:
            response = await self.llm.ainvoke(
                [system_msg, HumanMessage(content="أعط أفضل شفرة.")]
            )
            result = self._extract_json(response.content)
            if not result:
                raise ValueError("فشل تحليل JSON")
            clue_word = result.get("clue", "")
            clue_number = min(result.get("number", 1), 2)

            v = ClueValidator.validate_clue(clue_word, clue_number, game_state)
            if not v["valid"]:
                clue_word = self._fallback_clue(secret["our_words"])
                clue_number = 1

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=(
                        f"الشفرة: '{clue_word}' - {clue_number}.\n"
                        f"الأهداف: {result.get('target_words', [])}\n"
                        f"التحليل: {result.get('reasoning', '')}"
                    ),
                )
            )

            game_state.ai_spymaster_memory.add_short_term(
                f"شفرة '{clue_word}' - {clue_number}", game_state.turn_number
            )

            return {
                "clue": clue_word,
                "number": clue_number,
                "thinking_steps": thinking_steps,
                "target_words": result.get("target_words", []),
                "reasoning": result.get("reasoning", ""),
            }

        except Exception:
            clue_word = self._fallback_clue(secret["our_words"])
            return {
                "clue": clue_word,
                "number": 1,
                "thinking_steps": thinking_steps,
            }

    async def _hard_clue(self, game_state: GameState) -> dict:
        """
        المستوى المتقدم - سلاسل التفكير والتحليل العميق
        Chain of Thought + Deep Analysis
        يحاول ربط 3-4 كلمات مع تحليل المخاطر
        """
        secret = self._get_secret_view(game_state)
        memory_context = game_state.ai_spymaster_memory.get_context()
        thinking_steps = []
        agent_name = f"مساعدك (قائد {self.difficulty.value})"

        # === خطوة 1: التفكير العميق (Reflection) ===
        reflection_prompt = f"""حلل الوضع الحالي في اللعبة بعمق:
كلمات فريقنا المتبقية: {', '.join(secret['our_words'])}
كلمات الخصم: {', '.join(secret['opponent_words'])}
كلمات محايدة: {', '.join(secret['neutral_words'])}
كلمة القاتل: {', '.join(secret['assassin_words'])}

الذاكرة: {memory_context}

أجب بتحليل مفصل يتضمن:
1. تحليل قوة موقفنا
2. المجموعات الدلالية الممكنة بين كلماتنا
3. الكلمات الخطرة التي يجب تجنبها
4. استراتيجية الدور"""

        try:
            reflection_response = await self.llm.ainvoke(
                [
                    SystemMessage(content="أنت محلل استراتيجي خبير. حلل الوضع بعمق."),
                    HumanMessage(content=reflection_prompt),
                ]
            )

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="reflection",
                    content=f"🔍 التحليل العميق:\n{reflection_response.content[:500]}",
                )
            )

            # === خطوة 2: التخطيط (Planning) ===
            planning_prompt = f"""بناءً على التحليل التالي:
{reflection_response.content}

ضع خطة لأفضل 3 شفرات ممكنة. لكل شفرة:
1. الشفرة والرقم
2. الكلمات المستهدفة
3. نسبة النجاح المتوقعة

أجب بتنسيق JSON:
{{"plans": [
    {{"clue": "شفرة1", "number": 2, "targets": ["كلمة1","كلمة2"], "success_rate": 80}},
    {{"clue": "شفرة2", "number": 3, "targets": ["كلمة1","كلمة2","كلمة3"], "success_rate": 70}}
]}}"""

            planning_response = await self.llm.ainvoke(
                [
                    SystemMessage(content="أنت مخطط استراتيجي. أجب بتنسيق JSON."),
                    HumanMessage(content=planning_prompt),
                ]
            )

            result = self._extract_json(planning_response.content)
            plans = result.get("plans", []) if result else []

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="planning",
                    content=f"📋 الخطط:\n{json.dumps(plans, ensure_ascii=False, indent=2)[:600]}",
                )
            )

            # === خطوة 3: التقييم والاختيار (ReAct) ===
            best_plan = None
            if plans:
                valid_plans = []
                for plan in plans:
                    clue = plan.get("clue", "")
                    number = plan.get("number", 1)
                    v = ClueValidator.validate_clue(clue, number, game_state)
                    if v["valid"]:
                        valid_plans.append(plan)

                if valid_plans:
                    best_plan = max(valid_plans, key=lambda p: p.get("success_rate", 0))

            if best_plan:
                clue_word = best_plan["clue"]
                clue_number = min(best_plan["number"], 3)
                targets = best_plan.get("targets", [])
            else:
                clue_word = self._fallback_clue(secret["our_words"])
                clue_number = 1
                targets = []

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=f"✅ القرار النهائي: '{clue_word}' - {clue_number}\nالأهداف: {targets}",
                )
            )

            return {
                "clue": clue_word,
                "number": clue_number,
                "thinking_steps": thinking_steps,
                "target_words": targets,
                "reasoning": best_plan.get("risks", "") if best_plan else "",
            }

        except Exception as e:
            clue_word = self._fallback_clue(secret["our_words"])
            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=f"⚠️ خطأ: {str(e)}. استخدمت احتياطي: '{clue_word}'",
                )
            )
            return {
                "clue": clue_word,
                "number": 1,
                "thinking_steps": thinking_steps,
            }

    def _fallback_clue(self, our_words: list[str]) -> str:
        """شفرة احتياطية بسيطة"""
        fallback_clues = [
            "شيء",
            "مكان",
            "حياة",
            "عالم",
            "طريق",
            "نور",
            "أرض",
            "زمان",
            "فكرة",
            "ذهب",
        ]
        return random.choice(fallback_clues)


# ============================================================
# وكيل العميل - Operative Agent
# ============================================================


class AIOperative:
    """وكيل العميل الميداني AI"""

    def __init__(self, config: GameConfig, team: TeamColor):
        self.config = config
        self.team = team
        self.difficulty = config.ai_difficulty
        self.llm = ChatGoogleGenerativeAI(
            model=config.gemini_model,
            google_api_key=config.google_api_key,
            temperature=self._get_temperature(),
        )

    def _extract_json(self, content: str) -> Any:
        try:
            match = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(content)
        except Exception:
            return None

    def _get_temperature(self) -> float:
        temps = {
            Difficulty.EASY: 0.9,
            Difficulty.MEDIUM: 0.5,
            Difficulty.HARD: 0.2,
        }
        return temps[self.difficulty]

    def _get_public_view(self, game_state: GameState) -> dict:
        unrevealed = [c.word for c in game_state.board if not c.revealed]
        revealed = [
            {"word": c.word, "type": c.card_type.value}
            for c in game_state.board
            if c.revealed
        ]
        return {
            "unrevealed_words": unrevealed,
            "revealed_cards": revealed,
        }

    async def make_guesses(
        self, game_state: GameState, clue: str, number: int
    ) -> list[dict]:
        if self.difficulty == Difficulty.EASY:
            return await self._easy_guess(game_state, clue, number)
        elif self.difficulty == Difficulty.MEDIUM:
            return await self._medium_guess(game_state, clue, number)
        else:
            return await self._hard_guess(game_state, clue, number)

    async def _easy_guess(
        self, game_state: GameState, clue: str, number: int
    ) -> list[dict]:
        public = self._get_public_view(game_state)
        thinking_steps = []
        agent_name = f"مساعدك (عميل {self.difficulty.value})"

        thinking_steps.append(
            ThinkingStep(
                agent_name=agent_name,
                step_type="planning",
                content=f"أتلقى الشفرة '{clue}' وأبحث عن الكلمة الأكثر وضوحاً التي ترتبط بها في ذهني.",
            )
        )

        system_msg = SystemMessage(
            content=f"""أنت عميل مبتدئ. الشفرة: "{clue}" - {number}.
الكلمات المتاحة: {', '.join(public['unrevealed_words'])}

المهمة: اختر كلمة واحدة فقط مرتبطة بالشفرة.
أجب بتنسيق JSON:
{{
  "guesses": ["كلمة"],
  "reasoning": "اشرح بوضوح وببساطة لماذا اخترت هذه الكلمة وكيف ترتبط بالشفرة"
}}"""
        )

        try:
            resp = await self.llm.ainvoke([system_msg])
            result = self._extract_json(resp.content)
            guesses = result.get("guesses", [])[:1] if result else []
            reasoning = result.get("reasoning", "رابط بسيط") if result else "تحليل فاشل"

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=f"🎯 اختياري: {guesses}\n🧐 السبب: {reasoning}",
                )
            )
            return [
                {
                    "guesses": guesses,
                    "thinking_steps": thinking_steps,
                    "reasoning": reasoning,
                }
            ]
        except Exception:
            guess = (
                [random.choice(public["unrevealed_words"])]
                if public["unrevealed_words"]
                else []
            )
            return [
                {
                    "guesses": guess,
                    "thinking_steps": thinking_steps,
                    "reasoning": "تخمين عشوائي",
                }
            ]

    async def _medium_guess(
        self, game_state: GameState, clue: str, number: int
    ) -> list[dict]:
        public = self._get_public_view(game_state)
        thinking_steps = []
        agent_name = f"مساعدك (عميل {self.difficulty.value})"

        thinking_steps.append(
            ThinkingStep(
                agent_name=agent_name,
                step_type="reflection",
                content=f"أحلل الشفرة '{clue}' وأقارنها بالكلمات: {', '.join(public['unrevealed_words'][:10])}...",
            )
        )

        system_msg = SystemMessage(
            content=f"""أنت عميل متمرس. الشفرة: "{clue}" - {number}.
الكلمات: {', '.join(public['unrevealed_words'])}

المهمة: اختر أفضل الكلمات (حتى {number + 1}).
أجب بتنسيق JSON:
{{
  "guesses": ["كلمة1", "كلمة2"],
  "reasoning": "اشرح منطق الربط لكل كلمة، ولماذا هي الأفضل استراتيجياً"
}}"""
        )

        try:
            resp = await self.llm.ainvoke([system_msg])
            result = self._extract_json(resp.content)
            guesses = result.get("guesses", [])[: number + 1] if result else []
            reasoning = result.get("reasoning", "") if result else ""

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=f"✅ قراراتي: {guesses}\n🔍 التحليل: {reasoning}",
                )
            )
            return [
                {
                    "guesses": guesses,
                    "thinking_steps": thinking_steps,
                    "reasoning": reasoning,
                }
            ]
        except Exception:
            return [{"guesses": [], "thinking_steps": thinking_steps}]

    async def _hard_guess(
        self, game_state: GameState, clue: str, number: int
    ) -> list[dict]:
        public = self._get_public_view(game_state)
        thinking_steps = []
        agent_name = f"مساعدك (عميل {self.difficulty.value})"

        thinking_steps.append(
            ThinkingStep(
                agent_name=agent_name,
                step_type="reflection",
                content=f"🔍 أبدأ تحليلاً استراتيجياً للشفرة '{clue}' والرقم {number}.",
            )
        )

        try:
            # التحليل اللغوي
            analysis_resp = await self.llm.ainvoke(
                [
                    SystemMessage(content="أنت خبير لغوي واستراتيجي."),
                    HumanMessage(
                        content=f"حلل الشفرة '{clue}' مع الكلمات: {', '.join(public['unrevealed_words'])}"
                    ),
                ]
            )

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="reflection",
                    content=f"📖 تحليل الروابط:\n{analysis_resp.content[:300]}",
                )
            )

            # القرار النهائي
            system_msg = SystemMessage(
                content=f"""أنت خبير استراتيجي. الشفرة: "{clue}" - {number}.
الكلمات: {', '.join(public['unrevealed_words'])}

أجب بتنسيق JSON:
{{
  "guesses": ["كلمة"],
  "analysis": "اشرح الاستراتيجية والسبب والتحذيرات من الكلمات الأخرى"
}}"""
            )
            resp = await self.llm.ainvoke([system_msg])
            result = self._extract_json(resp.content)
            guesses = result.get("guesses", [])[: number + 1] if result else []
            analysis = result.get("analysis", "") if result else ""

            thinking_steps.append(
                ThinkingStep(
                    agent_name=agent_name,
                    step_type="react",
                    content=f"✅ القرار الاستراتيجي: {guesses}\n🛡️ المبرر: {analysis}",
                )
            )
            return [
                {
                    "guesses": guesses,
                    "thinking_steps": thinking_steps,
                    "reasoning": analysis,
                }
            ]
        except Exception:
            return [{"guesses": [], "thinking_steps": thinking_steps}]
