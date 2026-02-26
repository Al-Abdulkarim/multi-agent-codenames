"""
وكيل إنشاء المحتوى - Content Creator Agent
مسؤول عن التوليد الديناميكي لقوائم أسماء عربية فريدة لكل جلسة
Dynamically generates a unique pool of Arabic nouns for each session using LLM
"""

import random
import json
import re
from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import GameConfig


class ContentCreationAgent:
    """
    وكيل إنشاء المحتوى
    المسؤولية الأساسية: توليد قائمة أسماء عربية فريدة ديناميكياً في كل جلسة
    يستخدم LLM كمصدر أساسي والقوائم المخزنة كخطة بديلة فقط
    """

    # Themes to cycle through for diverse word generation
    THEMES = [
        "طبيعة وبيئة وجغرافيا",
        "تكنولوجيا وعلوم واختراعات",
        "تاريخ وحضارات وآثار",
        "رياضة ومسابقات وألعاب",
        "فنون وموسيقى وأدب",
        "طعام ومطبخ ومشروبات",
        "حيوانات وطيور وحشرات",
        "مهن وحرف ومهارات",
        "سفر وسياحة واستكشاف",
        "عمارة ومباني ومعالم",
        "فضاء وفلك ونجوم",
        "بحار ومحيطات وسفن",
    ]

    SYSTEM_PROMPT = """أنت خبير لغوي متخصص لمهمة توليد كلمات Codenames.

## القواعد الصارمة:
1. كل كلمة يجب أن تكون **اسماً مفرداً** بالعربية الفصحى.
2. الكلمات يجب أن تكون **متنوعة** وتغطي مجالات مختلفة.
3. يجب أن تكون الكلمات **مفهومة** (لا كلمات نادرة).
4. كل كلمة تتكون من **كلمة واحدة فقط** (بدون مركبات).
5. يجب أن تكون هناك **روابط دلالية خفية** لمتعة اللعب.
6. لا تكرر أي كلمة وتجنب الكلمات الحساسة.

## تنسيق الإخراج:
أعد النتيجة كمصفوفة JSON فقط بدون أي نص إضافي.
مثال: ["شمس", "جبل", "سيف", "قهوة"]"""

    def __init__(self, config: GameConfig):
        self.config = config
        self.llm = ChatGoogleGenerativeAI(
            model=config.gemini_model,
            google_api_key=config.google_api_key,
            temperature=0.9,  # High creativity for diverse words
        )
        self.used_words_history: list[set] = []

    async def generate_word_list(self, count: int = 25) -> list[str]:
        """
        التوليد الديناميكي الأساسي للكلمات
        يولّد قائمة فريدة في كل استدعاء باستخدام LLM
        يستخدم القائمة المخزنة كخطة بديلة فقط عند الفشل
        """
        # Build exclusion list from recent games
        recently_used = set()
        for used_set in self.used_words_history[-5:]:
            recently_used.update(used_set)

        # Pick 2-3 random themes for diversity
        selected_themes = random.sample(self.THEMES, min(3, len(self.THEMES)))
        theme_str = " و ".join(selected_themes)

        exclusion_note = ""
        if recently_used:
            sample_excluded = list(recently_used)[:15]
            exclusion_note = f"\n\nتجنب هذه الكلمات مؤخراً: {', '.join(sample_excluded)}"

        human_msg = HumanMessage(
            content=(
                f"أنت خبير لغوي لمهمة توليد {count + 5} اسم عربي متنوع.\n"
                f"المجالات: {theme_str}\n"
                f"أدخل مجالات أخرى للتنوع.\n"
                f"يجب أن تكون بعض الكلمات مترابطة دلالياً."
                f"{exclusion_note}\n\n"
                f"أعد مصفوفة JSON فقط."
            )
        )

        try:
            response = await self.llm.ainvoke(
                [SystemMessage(content=self.SYSTEM_PROMPT), human_msg]
            )

            content = response.content.strip()
            words = self._extract_json(content)
            if not words:
                raise ValueError("فشل تحليل JSON من رد القائد")

            if isinstance(words, list) and len(words) >= count:
                # Validate: filter out multi-word entries and duplicates
                valid_words = []
                seen = set()
                for w in words:
                    w = str(w).strip()
                    if (
                        w
                        and len(w.split()) == 1
                        and w not in seen
                        and w not in recently_used
                    ):
                        valid_words.append(w)
                        seen.add(w)

                if len(valid_words) >= count:
                    result = valid_words[:count]
                    self.used_words_history.append(set(result))
                    return result

            # Not enough valid words from LLM, supplement
            return await self._supplement_from_llm(
                words if isinstance(words, list) else [], count, recently_used
            )

        except Exception as e:
            print(f"⚠️ LLM word generation failed: {e}")
            raise Exception(f"فشل توليد الكلمات من الذكاء الاصطناعي: {str(e)}")

    def _extract_json(self, content: str) -> Any:
        """استخراج JSON من نص قد يحتوي على كلام إضافي"""
        try:
            # محاولة البحث عن بلوك JSON
            match = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(content)
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}\nContent: {content}")
            return None

    async def _supplement_from_llm(
        self, partial_words: list[str], count: int, exclude: set
    ) -> list[str]:
        """محاولة ثانية لتكملة النقص من LLM، ثم القائمة المحلية"""
        valid = [
            w.strip()
            for w in partial_words
            if isinstance(w, str) and w.strip() and w.strip() not in exclude
        ]
        needed = count - len(valid)

        if needed > 0:
            # Try one more LLM call for the remaining words
            try:
                resp = await self.llm.ainvoke(
                    [
                        SystemMessage(content=self.SYSTEM_PROMPT),
                        HumanMessage(
                            content=(
                                f"أنشئ {needed + 3} اسم عربي إضافي مختلف عن: "
                                f"{', '.join(valid[:10])}\n"
                                f"أعد مصفوفة JSON فقط."
                            )
                        ),
                    ]
                )
                extra = self._extract_json(resp.content.strip())
                if isinstance(extra, list):
                    for w in extra:
                        w = str(w).strip()
                        if w and w not in set(valid) and w not in exclude:
                            valid.append(w)
                            if len(valid) >= count:
                                break
            except Exception:
                pass

        # Still not enough? Raise error (User requested no fallback)
        if len(valid) < count:
            err_msg = f"الذكاء الاصطناعي لم يولد كافياً (مطلوب: {count})"
            raise Exception(err_msg)

        result = valid[:count]
        self.used_words_history.append(set(result))
        return result

    async def generate_thematic_words(self, count: int, theme: str) -> list[str]:
        """توليد كلمات حسب موضوع محدد من المستخدم"""
        try:
            resp = await self.llm.ainvoke(
                [
                    SystemMessage(content=self.SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            f"أنشئ {count + 3} اسم عربي مرتبط بموضوع: {theme}\n"
                            f"مع بعض الكلمات من مجالات أخرى للتنويع.\n"
                            f"أعد مصفوفة JSON فقط."
                        )
                    ),
                ]
            )
            content = resp.content.strip()
            words = self._extract_json(content)
            if isinstance(words, list) and len(words) >= count:
                return words[:count]
            raise ValueError(
                f"عدد الكلمات غير كافٍ ({len(words) if words else 0}/{count})"
            )
        except Exception as e:
            raise Exception(f"فشل توليد كلمات النمط: {str(e)}")
