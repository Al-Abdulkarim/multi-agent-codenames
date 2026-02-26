"""
وكيل مدير اللعبة - Game Master Agent
مسؤول عن إدارة حالة اللوحة وتوزيع الأدوار السرية والتحكم بمنطق الأدوار
"""

import random
from config import GameConfig, CardType, TeamColor, BoardSize
from game_state import GameState, Card


class GameMasterAgent:
    """
    وكيل مدير اللعبة
    المسؤوليات:
    - تهيئة لوحة اللعب بالحجم المطلوب (8 / 16 / 25)
    - توزيع الأدوار السرية (أحمر، أزرق، محايد، قاتل) عشوائياً
    - إدارة المنطق القائم على الأدوار (turn-based)
    - فرض قواعد اللعبة
    """

    def __init__(self, config: GameConfig):
        self.config = config

    def create_board(self, words: list[str]) -> tuple[list[Card], dict]:
        """
        إنشاء لوحة اللعب مع توزيع الأدوار السرية
        Args:
            words: قائمة الكلمات المولّدة من وكيل المحتوى
        Returns:
            (cards, distribution_info)
        """
        board_size = self.config.board_size.value
        assert len(words) >= board_size, (
            f"عدد الكلمات ({len(words)}) أقل من حجم اللوحة المطلوب " f"({board_size})"
        )

        # تحديد الفريق البادئ (حالياً الأحمر دائماً، لكن الكود يدعم التغيير)
        starting_team = TeamColor.RED

        selected_words = words[:board_size]
        distribution = self.config.get_card_distribution(starting_team=starting_team)

        # بناء قائمة الأنواع
        card_types: list[CardType] = []
        for card_type_str, count in distribution.items():
            card_types.extend([CardType(card_type_str)] * count)

        # خلط عشوائي
        random.shuffle(card_types)

        # إنشاء البطاقات
        cards = [
            Card(word=word, card_type=ct)
            for word, ct in zip(selected_words, card_types)
        ]

        distribution_info = {
            "board_size": board_size,
            "red_count": distribution["red"],
            "blue_count": distribution["blue"],
            "neutral_count": distribution["neutral"],
            "assassin_count": distribution["assassin"],
            "starting_team": starting_team.value,
        }

        return cards, distribution_info

    def initialize_game_state(self, words: list[str]) -> GameState:
        """
        تهيئة حالة لعبة جديدة بالكامل
        """
        game_state = GameState(config=self.config)
        cards, dist_info = self.create_board(words)

        game_state.board = cards
        game_state.red_remaining = dist_info["red_count"]
        game_state.blue_remaining = dist_info["blue_count"]
        game_state.current_phase = "clue"
        game_state.current_team = TeamColor(dist_info["starting_team"])

        return game_state

    def validate_turn(self, game_state: GameState, team: TeamColor) -> bool:
        """التحقق من أن الدور يخص الفريق الصحيح"""
        return game_state.current_team == team and not game_state.game_over

    def process_card_reveal(self, game_state: GameState, card_index: int) -> dict:
        """
        معالجة كشف بطاقة - يتحقق من القواعد ويحدث الحالة
        """
        if card_index < 0 or card_index >= len(game_state.board):
            return {"valid": False, "error": "فهرس البطاقة غير صالح"}

        card = game_state.board[card_index]
        if card.revealed:
            return {"valid": False, "error": "البطاقة مكشوفة بالفعل"}

        result = game_state.reveal_card(card_index)
        result["valid"] = True
        return result

    def should_end_turn(self, game_state: GameState, last_guess_correct: bool) -> bool:
        """تحديد ما إذا كان يجب إنهاء الدور"""
        if game_state.game_over:
            return True
        if not last_guess_correct:
            return True
        if game_state.guesses_remaining <= 0:
            return True
        return False

    def get_board_summary(self, game_state: GameState) -> dict:
        """ملخص حالة اللوحة"""
        return {
            "total_cards": len(game_state.board),
            "revealed": sum(1 for c in game_state.board if c.revealed),
            "unrevealed": sum(1 for c in game_state.board if not c.revealed),
            "red_remaining": game_state.red_remaining,
            "blue_remaining": game_state.blue_remaining,
            "current_team": game_state.current_team.value,
            "current_phase": game_state.current_phase,
            "turn_number": game_state.turn_number,
            "game_over": game_state.game_over,
        }

    def get_distribution_info(self, size: BoardSize) -> dict:
        """
        الحصول على معلومات التوزيع لحجم لوحة مختلف
        """
        # نستخدم دالة التوزيع من الإعدادات لضمان المركزية
        temp_config = GameConfig(board_size=size)
        dist = temp_config.get_card_distribution()
        return {
            "size": size.value,
            "distribution": dist,
            "total": sum(dist.values()),
        }
