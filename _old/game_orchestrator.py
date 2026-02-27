"""
مُنسّق اللعبة باستخدام LangGraph
Game Orchestrator using LangGraph
يدير تدفق اللعبة بين الوكلاء المختلفين مع إدارة سير العمل
"""

import asyncio
import time
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from config import GameConfig, TeamColor, PlayerRole, CardType
from game_state import GameState, Guess
from agents.content_agent import ContentCreationAgent
from agents.game_master import GameMasterAgent
from agents.ai_team import AISpymaster, AIOperative
from guardrails import ClueValidator, GuessValidator


class GraphState(TypedDict):
    """حالة الرسم البياني لـ LangGraph"""

    game_state: GameState
    current_action: str
    action_result: dict
    waiting_for_human: bool
    human_input: Optional[str]
    error: Optional[str]


class GameOrchestrator:
    """
    مُنسّق اللعبة الرئيسي - يدير سير العمل باستخدام LangGraph
    الوكلاء المشاركون:
    1. Content Creator Agent - توليد كلمات ديناميكياً
    2. Game Master Agent - إدارة اللوحة والأدوار
    3. AI Spymaster - قائد الفريق المنافس
    4. AI Operative - عميل الفريق المنافس (معزول تقنياً)
    """

    def __init__(self, config: GameConfig, on_update=None):
        self.config = config
        self.content_agent = ContentCreationAgent(config)
        self.game_master = GameMasterAgent(config)
        self.game_state: Optional[GameState] = None
        self.on_update = on_update

        # تحديد فريق AI
        self.ai_team = self._determine_ai_team()
        self.ai_agents = {}

        # بناء الرسم البياني
        self.graph = self._build_graph()

        # سجل الأحداث
        self.event_log: list[dict] = []
        self.start_time: float = 0
        self.is_processing = False
        self._lock = asyncio.Lock()

    def _determine_ai_team(self) -> TeamColor:
        """تحديد فريق الـ AI (الفريق المنافس الكامل)"""
        return (
            TeamColor.BLUE if self.config.human_team == TeamColor.RED else TeamColor.RED
        )

    def _initialize_ai_agents(self):
        """تهيئة وكلاء للفرق (الأحمر والأزرق) لضمان اتساق المستوى"""
        self.ai_agents = {
            TeamColor.RED: {
                "spymaster": AISpymaster(self.config, TeamColor.RED),
                "operative": AIOperative(self.config, TeamColor.RED),
            },
            TeamColor.BLUE: {
                "spymaster": AISpymaster(self.config, TeamColor.BLUE),
                "operative": AIOperative(self.config, TeamColor.BLUE),
            },
        }

    def _build_graph(self) -> StateGraph:
        """بناء رسم LangGraph لإدارة سير العمل"""
        workflow = StateGraph(GraphState)

        # إضافة العقد
        workflow.add_node("initialize", self._node_initialize)
        workflow.add_node("check_turn", self._node_check_turn)
        workflow.add_node("human_spymaster_turn", self._node_human_spymaster)
        workflow.add_node("human_operative_turn", self._node_human_operative)
        workflow.add_node("ai_spymaster_turn", self._node_ai_spymaster)
        workflow.add_node("ai_operative_turn", self._node_ai_operative)
        workflow.add_node("process_guess", self._node_process_guess)
        workflow.add_node("end_turn", self._node_end_turn)
        workflow.add_node("game_over", self._node_game_over)

        # نقطة البداية
        workflow.set_entry_point("initialize")

        # الأضلاع
        workflow.add_edge("initialize", "check_turn")

        # توجيه مشروط
        workflow.add_conditional_edges(
            "check_turn",
            self._route_turn,
            {
                "human_spymaster": "human_spymaster_turn",
                "human_operative": "human_operative_turn",
                "ai_spymaster": "ai_spymaster_turn",
                "ai_operative": "ai_operative_turn",
                "game_over": "game_over",
            },
        )

        workflow.add_edge("human_spymaster_turn", "check_turn")
        workflow.add_edge("human_operative_turn", "process_guess")
        workflow.add_edge("ai_spymaster_turn", "check_turn")
        workflow.add_edge("ai_operative_turn", "process_guess")

        workflow.add_conditional_edges(
            "process_guess",
            self._route_after_guess,
            {
                "continue_guessing": "check_turn",
                "end_turn": "end_turn",
                "game_over": "game_over",
            },
        )

        workflow.add_edge("end_turn", "check_turn")
        workflow.add_edge("game_over", END)

        return workflow.compile()

    # ============= Graph Nodes =============

    async def _node_initialize(self, state: GraphState) -> GraphState:
        """
        تهيئة اللعبة:
        1. Content Creator يولّد الكلمات ديناميكياً
        2. Game Master يبني اللوحة ويوزع الأدوار السرية
        """
        self._log_event("system", "🔄 وكيل المحتوى يولّد كلمات عربية جديدة...", {})

        # Step 1: Content Creator generates words dynamically via LLM
        words = await self.content_agent.generate_word_list(
            count=self.config.board_size.value
        )

        self._log_event(
            "system",
            f"✅ تم توليد {len(words)} كلمة عربية فريدة",
            {
                "sample": words[:5],
            },
        )

        # Step 2: Game Master creates board and assigns secret roles
        game_state = self.game_master.initialize_game_state(words)
        self._initialize_ai_agents()
        self.game_state = game_state
        self.start_time = time.time()

        board_summary = self.game_master.get_board_summary(game_state)
        self._log_event(
            "system",
            "🎮 تم تهيئة اللعبة بنجاح",
            {
                "board_size": self.config.board_size.value,
                "difficulty": self.config.ai_difficulty.value,
                "human_team": self.config.human_team.value,
                "human_role": self.config.human_role.value,
                "board_summary": board_summary,
            },
        )

        return {
            **state,
            "game_state": game_state,
            "current_action": "initialized",
            "action_result": {"status": "game_initialized"},
            "waiting_for_human": False,
        }

    async def _node_check_turn(self, state: GraphState) -> GraphState:
        """التحقق من الدور الحالي"""
        return {
            **state,
            "current_action": "checking_turn",
            "waiting_for_human": False,
        }

    def _route_turn(self, state: GraphState) -> str:
        """
        توجيه مشروط حسب الدور والمرحلة:
        - فريق البشري: Human-in-the-Loop (القائد أو العميل بشري)
        - فريق AI المنافس: كلاهما وكلاء مستقلون
        """
        gs = state["game_state"]

        if gs.game_over:
            return "game_over"

        is_human_team = gs.current_team == self.config.human_team

        if gs.current_phase == "clue":
            if is_human_team:
                if self.config.human_role == PlayerRole.SPYMASTER:
                    # البشري هو القائد → ينتظر مدخلاته
                    return "human_spymaster"
                else:
                    # البشري عميل → AI يعطي الشفرة لفريق البشري
                    return "ai_spymaster"
            else:
                # فريق AI المنافس → قائد AI
                return "ai_spymaster"
        elif gs.current_phase == "guess":
            if is_human_team:
                if self.config.human_role == PlayerRole.OPERATIVE:
                    # البشري هو العميل → ينتظر تخمينه
                    return "human_operative"
                else:
                    # البشري قائد → عميل AI يخمن
                    return "ai_operative"
            else:
                # فريق AI المنافس → عميل AI
                return "ai_operative"

        return "game_over"

    async def _node_human_spymaster(self, state: GraphState) -> GraphState:
        """Human-in-the-Loop: انتظار شفرة القائد البشري"""
        return {
            **state,
            "current_action": "waiting_human_clue",
            "waiting_for_human": True,
        }

    async def _node_human_operative(self, state: GraphState) -> GraphState:
        """Human-in-the-Loop: انتظار تخمين العميل البشري"""
        return {
            **state,
            "current_action": "waiting_human_guess",
            "waiting_for_human": True,
        }

    async def _node_ai_spymaster(self, state: GraphState) -> GraphState:
        """
        دور قائد AI - يستخدم ReAct + Reflection + Planning
        حسب المستوى المختار
        """
        gs = state["game_state"]
        team_label = "المنافس" if gs.current_team == self.ai_team else "مساعدك"

        self._log_event(
            "ai_thinking",
            f"🤔 قائد AI فريق {team_label} يفكر في الشفرة...",
            {
                "team": gs.current_team.value,
                "difficulty": self.config.ai_difficulty.value,
            },
        )

        agent = self.ai_agents[gs.current_team]["spymaster"]
        result = await agent.generate_clue(gs)

        clue_word = result["clue"]
        clue_number = result["number"]

        gs.set_clue(clue_word, clue_number)

        # تسجيل خطوات التفكير
        for step in result.get("thinking_steps", []):
            gs.add_thinking_step(
                step.agent_name,
                step.step_type,
                step.content,
                team=step.team or gs.current_team,
            )

        self._log_event(
            "ai_clue",
            f"📝 قائد AI أعطى: '{clue_word}' - {clue_number}",
            {
                "clue": clue_word,
                "number": clue_number,
                "reasoning": result.get("reasoning", ""),
                "team": gs.current_team.value,
            },
        )

        result = {
            **state,
            "game_state": gs,
            "current_action": "ai_clue_given",
            "action_result": {"clue": clue_word, "number": clue_number},
            "waiting_for_human": False,
        }

        if self.on_update:
            await self.on_update(self._get_game_status())
            await asyncio.sleep(1)

        return result

    async def _node_ai_operative(self, state: GraphState) -> GraphState:
        """
        دور عميل AI - معزول تقنياً عن بيانات القائد
        Process Isolation: لا يرى إلا اللوحة العامة + الشفرة
        """
        gs = state["game_state"]

        if not gs.current_clue:
            return {**state, "current_action": "error", "error": "لا توجد شفرة"}

        team_label = "المنافس" if gs.current_team == self.ai_team else "مساعدك"

        self._log_event(
            "ai_thinking",
            f"🔍 عميل AI فريق {team_label} يحلل الشفرة...",
            {
                "clue": gs.current_clue.word,
                "number": gs.current_clue.number,
            },
        )

        agent = self.ai_agents[gs.current_team]["operative"]
        results = await agent.make_guesses(
            gs, gs.current_clue.word, gs.current_clue.number
        )

        guess_results = []
        if results and results[0].get("guesses"):
            for step in results[0].get("thinking_steps", []):
                gs.add_thinking_step(
                    step.agent_name,
                    step.step_type,
                    step.content,
                    team=step.team or gs.current_team,
                )

            for word in results[0]["guesses"]:
                if gs.game_over or gs.guesses_remaining <= 0:
                    break

                validation = GuessValidator.validate_guess(word, gs)
                if not validation["valid"]:
                    continue

                card_index = validation["card_index"]
                reveal_result = gs.reveal_card(card_index)
                correct = reveal_result.get("correct", False)

                guess_record = Guess(
                    word=word,
                    team=gs.current_team,
                    result=CardType(reveal_result["card_type"]),
                    correct=correct,
                )
                guess_results.append(guess_record)
                gs.guesses_remaining -= 1

                if reveal_result["card_type"] == CardType.NEUTRAL.value:
                    msg = f"⚪ عميل AI خمّن كلمة محايدة: '{word}' (ينتهي الدور)"
                elif not correct:
                    msg = f"❌ عميل AI خمّن كلمة للفريق الآخر: '{word}' (ينتهي الدور)"
                else:
                    msg = f"✅ عميل AI خمّن كلمة صحيحة: '{word}'"

                self._log_event(
                    "ai_guess",
                    msg,
                    {
                        "word": word,
                        "correct": correct,
                        "card_type": reveal_result["card_type"],
                    },
                )

                if self.on_update:
                    await self.on_update(self._get_game_status())
                    await asyncio.sleep(1.2)  # مهلة بين كشف كل بطاقة

                if not correct:
                    break

        if self.on_update:
            await self.on_update(self._get_game_status())

        result = {
            **state,
            "game_state": gs,
            "current_action": "ai_guesses_done",
            "action_result": {
                "guesses": [g.model_dump() for g in guess_results],
            },
            "waiting_for_human": False,
        }
        return result

    async def _node_process_guess(self, state: GraphState) -> GraphState:
        return state

    def _route_after_guess(self, state: GraphState) -> str:
        """التوجيه بعد التخمين"""
        gs = state["game_state"]

        if gs.game_over:
            return "game_over"

        if gs.guesses_remaining > 0 and gs.current_phase == "guess":
            action_result = state.get("action_result", {})
            guesses = action_result.get("guesses", [])
            if guesses:
                last_guess = guesses[-1]
                if last_guess.get("correct", False):
                    return "continue_guessing"

        return "end_turn"

    async def _node_end_turn(self, state: GraphState) -> GraphState:
        """إنهاء الدور"""
        gs = state["game_state"]
        gs.end_turn()

        team_ar = "الأحمر" if gs.current_team == TeamColor.RED else "الأزرق"
        self._log_event(
            "turn_end",
            f"🔄 انتهى الدور → الفريق {team_ar}",
            {
                "next_team": gs.current_team.value,
                "turn_number": gs.turn_number,
                "red_remaining": gs.red_remaining,
                "blue_remaining": gs.blue_remaining,
            },
        )

        return {
            **state,
            "game_state": gs,
            "current_action": "turn_ended",
            "waiting_for_human": False,
        }

    async def _node_game_over(self, state: GraphState) -> GraphState:
        """انتهاء اللعبة"""
        gs = state["game_state"]
        winner_ar = (
            "الأحمر"
            if gs.winner == TeamColor.RED
            else "الأزرق" if gs.winner else "غير محدد"
        )
        self._log_event(
            "game_over",
            f"🏁 انتهت اللعبة! الفائز: الفريق {winner_ar}",
            {
                "winner": gs.winner.value if gs.winner else None,
                "reason": gs.game_over_reason,
                "total_turns": gs.turn_number,
                "duration": time.time() - self.start_time if self.start_time else 0,
            },
        )

        return {
            **state,
            "game_state": gs,
            "current_action": "game_over",
        }

    # ============= Public API =============

    async def start_game(self) -> dict:
        """بدء لعبة كاملة (تزامنياً - قد يعلق)"""
        await self.start_game_initial()
        await self._run_auto_turns()
        return self._get_game_status()

    async def start_game_initial(self) -> dict:
        """تهيئة اللعبة فقط بدون تشغيل الأدوار (سريع)"""
        initial_state: GraphState = {
            "game_state": GameState(config=self.config),
            "current_action": "start",
            "action_result": {},
            "waiting_for_human": False,
            "human_input": None,
            "error": None,
        }

        result = await self._node_initialize(initial_state)
        self.game_state = result["game_state"]
        return self._get_game_status()

    async def _run_auto_turns(self):
        """تشغيل أدوار AI تلقائياً حتى الوصول لدور بشري"""
        if self.is_processing:
            return
        self.is_processing = True

        try:
            gs = self.game_state
            max_iterations = 25

            for iter_count in range(max_iterations):
                if gs.game_over:
                    break

                is_human_team = gs.current_team == self.config.human_team
                needs_human = False

                if is_human_team:
                    if (
                        gs.current_phase == "clue"
                        and self.config.human_role == PlayerRole.SPYMASTER
                    ):
                        needs_human = True
                    elif (
                        gs.current_phase == "guess"
                        and self.config.human_role == PlayerRole.OPERATIVE
                    ):
                        needs_human = True

                if needs_human:
                    break

                if gs.current_phase == "clue":
                    state = {
                        "game_state": gs,
                        "current_action": "",
                        "action_result": {},
                        "waiting_for_human": False,
                        "human_input": None,
                        "error": None,
                    }
                    # Allow other tasks to run
                    await asyncio.sleep(0.1)
                    result = await self._node_ai_spymaster(state)
                    gs = result["game_state"]
                    self.game_state = gs

                elif gs.current_phase == "guess":
                    state = {
                        "game_state": gs,
                        "current_action": "",
                        "action_result": {},
                        "waiting_for_human": False,
                        "human_input": None,
                        "error": None,
                    }
                    await asyncio.sleep(0.1)
                    result = await self._node_ai_operative(state)
                    gs = result["game_state"]
                    self.game_state = gs

                    if not gs.game_over:
                        gs.end_turn()
                        self.game_state = gs

                # Emit updates frequently
                if self.on_update:
                    await self.on_update(self._get_game_status())

                # Pause between phases
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"CRITICAL ERROR in AI execution: {e}")
            import traceback

            traceback.print_exc()
            if self.on_update:
                status = self._get_game_status()
                status["error"] = f"خطأ في عمل الذكاء الاصطناعي: {str(e)}"
                await self.on_update(status)
        finally:
            self.is_processing = False
            if self.on_update:
                await self.on_update(self._get_game_status())

    async def submit_human_clue(self, clue_word: str, clue_number: int) -> dict:
        """Human-in-the-Loop: تقديم شفرة من القائد البشري"""
        async with self._lock:
            gs = self.game_state
            if not gs or gs.game_over:
                return {"error": "اللعبة غير نشطة"}

            # Safety Guardrails: التحقق من الشفرة
            validation = ClueValidator.validate_clue(clue_word, clue_number, gs)
            if not validation["valid"]:
                return {"error": "شفرة غير صالحة", "details": validation["errors"]}

            gs.set_clue(clue_word, clue_number)

            self._log_event(
                "human_clue",
                f"📝 القائد البشري أعطى: '{clue_word}' - {clue_number}",
                {
                    "clue": clue_word,
                    "number": clue_number,
                },
            )

        # إذا البشري قائد → عميل AI يخمن (في الخلفية)
        if self.config.human_role == PlayerRole.SPYMASTER:
            asyncio.create_task(self._run_auto_turns())

        return self._get_game_status()

    async def submit_human_guess(self, word: str) -> dict:
        """Human-in-the-Loop: تقديم تخمين من العميل البشري"""
        async with self._lock:
            gs = self.game_state
            if not gs or gs.game_over:
                return {"error": "اللعبة غير نشطة"}

            validation = GuessValidator.validate_guess(word, gs)
            if not validation["valid"]:
                return {"error": "تخمين غير صالح", "details": validation["errors"]}

            card_index = validation["card_index"]
            reveal_result = gs.reveal_card(card_index)
            correct = reveal_result.get("correct", False)
            gs.guesses_remaining -= 1

            if reveal_result["card_type"] == CardType.NEUTRAL.value:
                msg = f"⚪ خمنت كلمة محايدة: '{word}' (ينتهي الدور)"
            elif not correct:
                msg = f"❌ خمنت كلمة للفريق الآخر: '{word}' (ينتهي الدور)"
            else:
                msg = f"✅ خمنت كلمة صحيحة: '{word}'"

            self._log_event(
                "human_guess",
                msg,
                {
                    "word": word,
                    "correct": correct,
                    "card_type": reveal_result["card_type"],
                },
            )

            result = self._get_game_status()
            result["last_guess"] = {
                "word": word,
                "correct": correct,
                "card_type": reveal_result["card_type"],
            }

            if gs.game_over:
                return result

            if not correct or gs.guesses_remaining <= 0:
                gs.end_turn()
                asyncio.create_task(self._run_auto_turns())
                result = self._get_game_status()
                result["last_guess"] = {
                    "word": word,
                    "correct": correct,
                    "card_type": reveal_result["card_type"],
                }

            return result

    async def pass_turn(self) -> dict:
        """تمرير الدور"""
        async with self._lock:
            gs = self.game_state
            if not gs or gs.game_over:
                return {"error": "اللعبة غير نشطة"}

            gs.end_turn()
            self._log_event("pass", "⏭️ تم تمرير الدور", {})
            asyncio.create_task(self._run_auto_turns())
            return self._get_game_status()

    def _get_game_status(self) -> dict:
        """الحصول على الحالة الكاملة للعبة"""
        gs = self.game_state
        if not gs:
            return {"error": "لا توجد لعبة نشطة"}

        # اللوحة حسب دور البشري
        if gs.game_over:
            # عند نهاية اللعبة، اظهر جميع البطاقات مع توضيح هل تم تخمينها أم لا
            board = gs.get_spymaster_board(self.config.human_team)
        elif self.config.human_role == PlayerRole.SPYMASTER:
            board = gs.get_spymaster_board(self.config.human_team)
        else:
            board = gs.get_public_board()

        return {
            "game_id": gs.game_id,
            "board": board,
            "board_size": self.config.board_size.value,
            "current_team": gs.current_team.value,
            "current_phase": gs.current_phase,
            "turn_number": gs.turn_number,
            "red_remaining": gs.red_remaining,
            "blue_remaining": gs.blue_remaining,
            "current_clue": (
                {
                    "word": gs.current_clue.word,
                    "number": gs.current_clue.number,
                }
                if gs.current_clue
                else None
            ),
            "guesses_remaining": gs.guesses_remaining,
            "game_over": gs.game_over,
            "winner": gs.winner.value if gs.winner else None,
            "game_over_reason": gs.game_over_reason,
            "human_team": self.config.human_team.value,
            "human_role": self.config.human_role.value,
            "ai_difficulty": self.config.ai_difficulty.value,
            "thinking_log": [
                {
                    "agent_name": s.agent_name,
                    "step_type": s.step_type,
                    "team": s.team.value if s.team else None,
                    "content": s.content,
                    "timestamp": s.timestamp,
                }
                for s in gs.thinking_log[-20:]
            ],
            "clue_history": [
                {
                    "turn": t.turn_number,
                    "team": t.team.value,
                    "word": t.clue.word,
                    "number": t.clue.number,
                    "guesses": [g.model_dump() for g in t.guesses],
                }
                for t in gs.turns_history
                if t.clue
            ],
            "event_log": self.event_log[-30:],
        }

    def _log_event(self, event_type: str, message: str, data: dict):
        """تسجيل حدث في السجل"""
        self.event_log.append(
            {
                "type": event_type,
                "message": message,
                "data": data,
                "timestamp": time.time(),
            }
        )
