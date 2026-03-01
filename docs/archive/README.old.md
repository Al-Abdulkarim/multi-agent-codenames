# 🕵️ Codenames Arabic - الأسماء الحركية العربية

## نظام متكامل للعبة Codenames باللغة العربية | Multi-Agent AI System

> مشروع تخرج متقدم يعتمد على إطار عمل **LangGraph** لبناء نظام وكلاء ذكاء اصطناعي متعدد لإدارة لعبة الأسماء الحركية باللغة العربية مع واجهة ويب احترافية.

---

## 🏗️ هيكلية النظام (System Architecture)

```
┌──────────────────────────────────────────────────────┐
│                    LangGraph Orchestrator              │
│              (إدارة سير العمل والوكلاء)                │
├──────────────┬───────────────┬────────────────────────┤
│              │               │                        │
│  Content     │  Game Master  │   AI Team (Isolated)   │
│  Creator     │  Agent        │   ┌─────────────────┐  │
│  Agent       │               │   │  AI Spymaster   │  │
│              │  - Board Mgmt │   │  (Secret Access) │  │
│  - Dynamic   │  - Role Assign│   ├─────────────────┤  │
│    Word Gen  │  - Turn Logic │   │  AI Operative   │  │
│  - LLM-based │  - Board Size │   │  (Public Only)  │  │
│              │    (8/16/25)  │   │  ⛔ NO SECRET   │  │
│              │               │   │     ACCESS      │  │
│              │               │   └─────────────────┘  │
├──────────────┴───────────────┴────────────────────────┤
│          Safety Guardrails + Memory Management         │
│          (طبقة الحماية + إدارة الذاكرة)                 │
├───────────────────────────────────────────────────────┤
│              FastAPI + WebSocket Server                 │
├───────────────────────────────────────────────────────┤
│          Arabic RTL Web Interface (الواجهة العربية)      │
└───────────────────────────────────────────────────────┘
```

## ✨ الميزات الرئيسية

### 1. 🤖 نظام الوكلاء المتعددين (Multi-Agent System)
| الوكيل | المسؤولية |
|--------|----------|
| **Content Creator Agent** | توليد ديناميكي وحصري لأسماء عربية فريدة في كل جلسة عبر LLM (لا يوجد كلمات مخزنة محلياً) |
| **Game Master Agent** | إدارة اللوحة وتوزيع الأدوار السرية وتغيير حجم اللوحة |
| **AI Spymaster** | قائد الفريق المنافس - يولّد الشفرات |
| **AI Operative** | عميل الفريق المنافس - يخمّن الكلمات (معزول تقنياً) |

### 2. 🔒 العزل التقني (Strict Process Isolation)
- **AI Spymaster**: يملك وصولاً كاملاً إلى الخريطة السرية (أنواع جميع البطاقات)
- **AI Operative**: لا يرى إلا اللوحة العامة + الشفرة المعطاة
- **لا يوجد أي مسار** لتسريب بيانات القائد إلى العميل

### 3. 🧠 ثلاثة مستويات ذكاء
| المستوى | الوصف | الأنماط المستخدمة |
|---------|-------|------------------|
| **Basic (عادي)** | منطق بسيط، ربط كلمة واحدة | Simple Reasoning |
| **Intermediate (متوسط)** | تحليل + ذاكرة، ربط 2-3 كلمات | Reflection + ReAct + Memory |
| **Advanced (متقدم)** | سلاسل التفكير العميق | Chain-of-Thought + Planning + ReAct + Reflection |

### 4. 👤 Human-in-the-Loop Governance
- **قائد بشري**: أعط شفرات لعميل AI يخمن نيابةً عنك
- **عميل بشري**: استقبل شفرات من قائد AI وخمّن الكلمات

### 5. 📐 أحجام لوحة متعددة
| الحجم | البطاقات | التوزيع |
|-------|---------|--------|
| صغير | 8 | أحمر: 3, أزرق: 2, محايد: 2, قاتل: 1 |
| متوسط | 16 | أحمر: 6, أزرق: 5, محايد: 4, قاتل: 1 |
| كلاسيكي | 25 | أحمر: 9, أزرق: 8, محايد: 7, قاتل: 1 |

### 6. 🛡️ Safety Guardrails (طبقة الحماية)
- التحقق من أن الشفرة كلمة واحدة فقط
- منع استخدام كلمات اللوحة كشفرات
- التحقق من التطابق الجزئي مع الكلمات
- قائمة كلمات محظورة
- التحقق من صلاحية الرقم

### 7. 🧪 Evaluation Framework
- تتبع نسب الفوز لكل مستوى صعوبة
- إحصائيات حسب حجم اللوحة
- قياس دقة تخمينات AI
- تقارير تفصيلية

---

## 📁 هيكل المشروع

```
capstone/
├── config.py               # التكوين المركزي
├── game_state.py            # نموذج حالة اللعبة والذاكرة
├── guardrails.py            # طبقة الحماية (Safety Guardrails)
├── game_orchestrator.py     # مُنسّق LangGraph
├── evaluation.py            # إطار التقييم
├── server.py                # خادم FastAPI + WebSocket
├── requirements.txt         # المتطلبات
├── .env.example             # نموذج متغيرات البيئة
├── agents/
│   ├── __init__.py
│   ├── content_agent.py     # وكيل إنشاء المحتوى (LLM-based - 100% Dynamic)
│   ├── game_master.py       # وكيل مدير اللعبة
│   └── ai_team.py           # وكلاء الفريق المنافس
└── static/
    ├── index.html           # الواجهة الرئيسية (RTL)
    ├── styles.css           # التصميم الاحترافي
    └── app.js               # منطق الواجهة
```

---

## 🚀 التشغيل

### 1. تثبيت المتطلبات
```bash
pip install -r requirements.txt
```

### 2. إعداد مفتاح API
```bash
cp .env.example .env
# عدّل .env وأضف مفتاح OpenAI API
```

### 3. تشغيل الخادم
```bash
python server.py
```

### 4. فتح اللعبة
افتح المتصفح على: `http://localhost:8000`

---

## 🔧 أنماط التصميم المستخدمة (Design Patterns)

### LangGraph Workflow
```
Initialize → Check Turn → [Human/AI Spymaster] → Check Turn
                       → [Human/AI Operative] → Process Guess
                       → End Turn → Check Turn
                       → Game Over → END
```

### Reflection Pattern
يُستخدم في المستوى المتوسط والمتقدم لتحليل الوضع الحالي قبل اتخاذ القرار.

### ReAct Pattern (Reasoning + Acting)
يُستخدم في جميع المستويات لربط التفكير بالأفعال.

### Planning Pattern
يُستخدم في المستوى المتقدم لوضع خطط متعددة واختيار الأفضل.

### Chain-of-Thought
يُستخدم في المستوى المتقدم لتحليل الشفرات بعمق عبر خطوات متسلسلة.

### Memory Management
- **ذاكرة قصيرة المدى**: آخر 10 أحداث
- **ذاكرة طويلة المدى**: أنماط مهمة وتعلمات (auto-promoted)

---

## 📊 تشغيل التقييم التلقائي

```python
from evaluation import run_automated_evaluation
from config import Difficulty, BoardSize

import asyncio
metrics = asyncio.run(run_automated_evaluation(
    num_games=10,
    difficulty=Difficulty.MEDIUM,
    board_size=BoardSize.LARGE,
))
```

---

## 🛠️ التقنيات المستخدمة

| التقنية | الاستخدام |
|---------|----------|
| **LangGraph** | إدارة سير عمل الوكلاء |
| **LangChain** | التكامل مع نماذج اللغة |
| **OpenAI GPT-4o-mini** | محرك الذكاء الاصطناعي |
| **FastAPI** | الخادم الخلفي |
| **WebSocket** | التحديثات المباشرة |
| **Pydantic** | نمذجة البيانات |
| **HTML/CSS/JS** | واجهة الويب (RTL) |

---

## 📝 معايير مشروع التخرج المُحققة

- [x] ✅ نظام وكلاء متعددين باستخدام LangGraph
- [x] ✅ وكيل إنشاء محتوى ديناميكي (LLM-based)
- [x] ✅ وكيل مدير لعبة مع أحجام لوحة متعددة
- [x] ✅ عزل تقني بين القائد والعميل
- [x] ✅ ثلاثة مستويات ذكاء (Basic / Intermediate / Advanced)
- [x] ✅ Human-in-the-Loop (قائد أو عميل بشري)
- [x] ✅ واجهة ويب RTL عربية احترافية
- [x] ✅ عرض عمليات تفكير الوكلاء (Reflection, ReAct, Planning)
- [x] ✅ إدارة ذاكرة قصيرة وطويلة المدى
- [x] ✅ طبقة حماية (Safety Guardrails)
- [x] ✅ إطار تقييم الأداء ونسب الفوز
- [x] ✅ سلاسل التفكير (Chain-of-Thought)
- [x] ✅ WebSocket للتحديثات المباشرة

---

**تم التطوير كمشروع تخرج متقدم | Tuwaiq Academy Capstone Project**
