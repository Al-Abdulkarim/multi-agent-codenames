from __future__ import annotations
import uuid
import time
from typing import Optional
from pydantic import BaseModel, Field, PrivateAttr
from config import CardType, TeamColor, GameConfig


class Card(BaseModel):
    """نموذج البطاقة"""

    word: str
    card_type: CardType
    revealed: bool = False

    def reveal(self) -> CardType:
        self.revealed = True
        return self.card_type


class Clue(BaseModel):
    """نموذج الشفرة/التلميح"""

    word: str
    number: int
    team: TeamColor
    timestamp: float = Field(default_factory=time.time)


class Guess(BaseModel):
    """نموذج التخمين"""

    word: str
    team: TeamColor
    result: CardType
    correct: bool
    timestamp: float = Field(default_factory=time.time)


class ThinkingStep(BaseModel):
    """خطوة تفكير الوكيل"""

    agent_name: str
    step_type: str  # reflection, react, planning
    team: Optional[TeamColor] = None  # الفريق التابع له
    content: str
    timestamp: float = Field(default_factory=time.time)


class TurnRecord(BaseModel):
    """سجل الدور"""

    turn_number: int
    team: TeamColor
    clue: Optional[Clue] = None
    guesses: list[Guess] = Field(default_factory=list)
    thinking_steps: list[ThinkingStep] = Field(default_factory=list)
    skipped: bool = False


class MemoryEntry(BaseModel):
    """عنصر الذاكرة"""

    entry_type: str  # short_term, long_term
    content: str
    relevance_score: float = 0.0
    turn_number: int = 0
    timestamp: float = Field(default_factory=time.time)


class AgentMemory(BaseModel):
    """ذاكرة الوكيل"""

    short_term: list[MemoryEntry] = Field(default_factory=list)
    long_term: list[MemoryEntry] = Field(default_factory=list)
    max_short_term: int = 10

    def add_short_term(self, content: str, turn: int):
        entry = MemoryEntry(entry_type="short_term", content=content, turn_number=turn)
        self.short_term.append(entry)
        if len(self.short_term) > self.max_short_term:
            # نقل الأقدم للذاكرة طويلة المدى
            oldest = self.short_term.pop(0)
            oldest.entry_type = "long_term"
            self.long_term.append(oldest)

    def add_long_term(self, content: str, turn: int, relevance: float = 0.5):
        entry = MemoryEntry(
            entry_type="long_term",
            content=content,
            turn_number=turn,
            relevance_score=relevance,
        )
        self.long_term.append(entry)

    def get_context(self, max_entries: int = 5) -> str:
        """الحصول على سياق الذاكرة"""
        context_parts = []
        # الذاكرة قصيرة المدى
        for entry in self.short_term[-max_entries:]:
            context_parts.append(f"[دور {entry.turn_number}] {entry.content}")
        # أهم عناصر الذاكرة طويلة المدى
        sorted_lt = sorted(
            self.long_term, key=lambda x: x.relevance_score, reverse=True
        )
        for entry in sorted_lt[:3]:
            context_parts.append(f"[ذاكرة مهمة] {entry.content}")
        return "\n".join(context_parts)


class GameState(BaseModel):
    """حالة اللعبة الرئيسية"""

    game_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    config: GameConfig = Field(default_factory=GameConfig)
    board: list[Card] = Field(default_factory=list)
    current_team: TeamColor = TeamColor.RED
    current_phase: str = "setup"  # setup, clue, guess, game_over
    turn_number: int = 0
    turns_history: list[TurnRecord] = Field(default_factory=list)
    current_clue: Optional[Clue] = None
    guesses_remaining: int = 0
    red_remaining: int = 0
    blue_remaining: int = 0
    winner: Optional[TeamColor] = None
    game_over: bool = False
    game_over_reason: str = ""
    thinking_log: list[ThinkingStep] = Field(default_factory=list)
    # ذاكرة الوكلاء
    ai_spymaster_memory: AgentMemory = Field(default_factory=AgentMemory)
    ai_operative_memory: AgentMemory = Field(default_factory=AgentMemory)
    # قائمة مؤقتة لتخمينات الدور الحالي
    _current_turn_guesses: list[Guess] = PrivateAttr(default_factory=list)

    def get_public_board(self) -> list[dict]:
        """اللوحة العامة - الكلمات فقط مع الحالة المكشوفة"""
        return [
            {
                "word": card.word,
                "revealed": card.revealed,
                "card_type": card.card_type.value if card.revealed else None,
                "index": i,
            }
            for i, card in enumerate(self.board)
        ]

    def get_spymaster_board(self, team: TeamColor) -> list[dict]:
        """لوحة قائد الفريق - تكشف جميع أنواع البطاقات"""
        return [
            {
                "word": card.word,
                "card_type": card.card_type.value,
                "revealed": card.revealed,
                "index": i,
            }
            for i, card in enumerate(self.board)
        ]

    def reveal_card(self, index: int) -> dict:
        """كشف بطاقة"""
        if index < 0 or index >= len(self.board):
            return {"error": "فهرس غير صالح"}

        card = self.board[index]
        if card.revealed:
            return {"error": "البطاقة مكشوفة بالفعل"}

        card.reveal()
        reveal_result = {
            "word": card.word,
            "card_type": card.card_type.value,
            "correct": card.card_type.value == self.current_team.value,
        }

        # تسجيل التخمين
        guess = Guess(
            word=card.word,
            team=self.current_team,
            result=card.card_type,
            correct=reveal_result["correct"],
        )
        self._current_turn_guesses.append(guess)

        # تحديث العداد
        if card.card_type == CardType.RED:
            self.red_remaining -= 1
        elif card.card_type == CardType.BLUE:
            self.blue_remaining -= 1

        # التحقق من انتهاء اللعبة
        if card.card_type == CardType.ASSASSIN:
            self.game_over = True
            enemy_team = (
                TeamColor.BLUE if self.current_team == TeamColor.RED else TeamColor.RED
            )
            self.winner = enemy_team
            self.game_over_reason = (
                f"الفريق {self.current_team.value} اختار بطاقة القاتل!"
            )
            self.current_phase = "game_over"
        elif self.red_remaining == 0:
            self.game_over = True
            self.winner = TeamColor.RED
            self.game_over_reason = "الفريق الأحمر كشف جميع كلماته!"
            self.current_phase = "game_over"
        elif self.blue_remaining == 0:
            self.game_over = True
            self.winner = TeamColor.BLUE
            self.game_over_reason = "الفريق الأزرق كشف جميع كلماته!"
            self.current_phase = "game_over"

        return reveal_result

    def set_clue(self, word: str, number: int) -> dict:
        """تعيين الشفرة"""
        clue = Clue(word=word, number=number, team=self.current_team)
        self.current_clue = clue
        self.guesses_remaining = number + 1  # +1 مكافأة
        self.current_phase = "guess"
        return {"clue": word, "number": number}

    def end_turn(self):
        """إنهاء الدور وصيانة السجل"""
        # إضافة سجل الدور للتاريخ
        record = TurnRecord(
            turn_number=self.turn_number,
            team=self.current_team,
            clue=self.current_clue,
            guesses=list(self._current_turn_guesses),
        )
        self.turns_history.append(record)
        self._current_turn_guesses = []

        self.current_team = (
            TeamColor.BLUE if self.current_team == TeamColor.RED else TeamColor.RED
        )
        self.current_clue = None
        self.guesses_remaining = 0
        self.turn_number += 1
        self.current_phase = "clue"

    def add_thinking_step(
        self,
        agent_name: str,
        step_type: str,
        content: str,
        team: Optional[TeamColor] = None,
    ):
        """إضافة خطوة تفكير"""
        step = ThinkingStep(
            agent_name=agent_name,
            step_type=step_type,
            team=team or self.current_team,
            content=content,
        )
        self.thinking_log.append(step)
        return step

    def get_unrevealed_words(self) -> list[str]:
        """الحصول على الكلمات غير المكشوفة"""
        return [card.word for card in self.board if not card.revealed]

    def get_team_words(self, team: TeamColor, revealed_only: bool = False) -> list[str]:
        """الحصول على كلمات فريق معين"""
        ct = CardType.RED if team == TeamColor.RED else CardType.BLUE
        return [
            card.word
            for card in self.board
            if card.card_type == ct and (not revealed_only or card.revealed)
        ]
