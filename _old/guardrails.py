"""
طبقة الحماية - Guardrails
التحقق من قانونية الشفرات والتخمينات
"""

from game_state import GameState
from config import TeamColor


class ClueValidator:
    """التحقق من صحة الشفرات"""

    # كلمات محظورة (لا يمكن استخدامها كشفرات)
    BANNED_PATTERNS = [
        "أحمر",
        "أزرق",
        "محايد",
        "قاتل",
        "بطاقة",
        "كرت",
        "لوحة",
        "لعبة",
    ]

    @staticmethod
    def validate_clue(clue_word: str, clue_number: int, game_state: GameState) -> dict:
        """
        التحقق من قانونية الشفرة
        القواعد:
        1. الشفرة كلمة واحدة فقط
        2. لا يمكن أن تكون كلمة موجودة على اللوحة
        3. لا يمكن أن تكون جزءاً من كلمة على اللوحة
        4. الرقم يجب أن يكون بين 0 و 9
        5. لا يمكن استخدام كلمات محظورة
        """
        errors = []

        # التحقق من أن الشفرة كلمة واحدة
        if len(clue_word.split()) > 1:
            errors.append("الشفرة يجب أن تكون كلمة واحدة فقط")

        # التحقق من الكلمات المحظورة
        for banned in ClueValidator.BANNED_PATTERNS:
            if banned in clue_word or clue_word in banned:
                errors.append(f"لا يمكن استخدام '{clue_word}' - كلمة محظورة")
                break

        # التحقق من أن الشفرة ليست على اللوحة
        board_words = [card.word for card in game_state.board]
        if clue_word in board_words:
            errors.append("لا يمكن استخدام كلمة موجودة على اللوحة كشفرة")

        # التحقق من عدم التطابق الجزئي
        unrevealed = game_state.get_unrevealed_words()
        for word in unrevealed:
            if (
                len(clue_word) > 2
                and len(word) > 2
                and (clue_word in word or word in clue_word)
            ):
                errors.append(
                    f"الشفرة '{clue_word}' تتضمن/مشابهة لكلمة '{word}' على اللوحة"
                )
                break

        # التحقق من الرقم
        if not (0 <= clue_number <= 9):
            errors.append("الرقم يجب أن يكون بين 0 و 9")

        # التحقق أنه هناك كلمات كافية متبقية
        remaining = (
            game_state.red_remaining
            if game_state.current_team == TeamColor.RED
            else game_state.blue_remaining
        )
        if clue_number > remaining:
            errors.append(
                f"الرقم ({clue_number}) أكبر من عدد الكلمات المتبقية ({remaining})"
            )

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "errors": errors,
            "clue": clue_word,
            "number": clue_number,
        }


class GuessValidator:
    """التحقق من صحة التخمين"""

    @staticmethod
    def validate_guess(word: str, game_state: GameState) -> dict:
        """التحقق من أن التخمين صالح"""
        errors = []

        # التحقق من أن الكلمة موجودة على اللوحة
        board_words = {card.word: i for i, card in enumerate(game_state.board)}
        if word not in board_words:
            errors.append(f"الكلمة '{word}' غير موجودة على اللوحة")
            return {"valid": False, "errors": errors}

        # التحقق من أن البطاقة لم تُكشف بعد
        card_index = board_words[word]
        if game_state.board[card_index].revealed:
            errors.append(f"البطاقة '{word}' مكشوفة بالفعل")

        # التحقق من أن هناك تخمينات متبقية
        if game_state.guesses_remaining <= 0:
            errors.append("لا توجد تخمينات متبقية في هذا الدور")

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "errors": errors,
            "word": word,
            "card_index": card_index if word in board_words else None,
        }
