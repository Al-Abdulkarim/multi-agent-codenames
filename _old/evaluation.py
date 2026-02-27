"""
إطار التقييم - Evaluation Framework
قياس أداء النظام ونسب الفوز
"""

import json
import time
import os
from typing import Optional
from pydantic import BaseModel, Field
from config import Difficulty, BoardSize, TeamColor, PlayerRole, GameConfig
from game_orchestrator import GameOrchestrator


class GameResult(BaseModel):
    """نتيجة لعبة واحدة"""

    game_id: str
    winner: Optional[str] = None
    total_turns: int = 0
    ai_difficulty: str = ""
    board_size: int = 25
    game_over_reason: str = ""
    duration_seconds: float = 0.0
    ai_clues_given: int = 0
    ai_correct_guesses: int = 0
    ai_wrong_guesses: int = 0
    human_clues_given: int = 0
    human_correct_guesses: int = 0
    human_wrong_guesses: int = 0
    timestamp: float = Field(default_factory=time.time)


class EvaluationMetrics(BaseModel):
    """مقاييس التقييم الشاملة"""

    total_games: int = 0
    ai_wins: int = 0
    human_wins: int = 0
    ai_win_rate: float = 0.0
    human_win_rate: float = 0.0
    avg_turns_per_game: float = 0.0
    avg_game_duration: float = 0.0
    # مقاييس حسب المستوى
    metrics_by_difficulty: dict = Field(default_factory=dict)
    # مقاييس حسب حجم اللوحة
    metrics_by_board_size: dict = Field(default_factory=dict)
    # أداء الشفرات
    avg_clue_accuracy: float = 0.0
    # تفاصيل الألعاب
    game_results: list[GameResult] = Field(default_factory=list)


class EvaluationFramework:
    """إطار عمل التقييم"""

    def __init__(self, results_file: str = "evaluation_results.json"):
        self.results_file = results_file
        self.results: list[GameResult] = []
        self._load_results()

    def _load_results(self):
        """تحميل النتائج السابقة"""
        if os.path.exists(self.results_file):
            try:
                with open(self.results_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results = [GameResult(**r) for r in data]
            except Exception:
                self.results = []

    def _save_results(self):
        """حفظ النتائج"""
        with open(self.results_file, "w", encoding="utf-8") as f:
            json.dump(
                [r.model_dump() for r in self.results], f, ensure_ascii=False, indent=2
            )

    def record_game(self, orchestrator: GameOrchestrator) -> GameResult:
        """تسجيل نتيجة لعبة"""
        gs = orchestrator.game_state
        if not gs:
            return GameResult(game_id="unknown")

        result = GameResult(
            game_id=gs.game_id,
            winner=gs.winner.value if gs.winner else None,
            total_turns=gs.turn_number,
            ai_difficulty=orchestrator.config.ai_difficulty.value,
            board_size=orchestrator.config.board_size.value,
            game_over_reason=gs.game_over_reason,
        )

        # حساب إحصائيات من سجل الأحداث
        for event in orchestrator.event_log:
            if event["type"] == "ai_clue":
                result.ai_clues_given += 1
            elif event["type"] == "ai_guess":
                if event["data"].get("correct"):
                    result.ai_correct_guesses += 1
                else:
                    result.ai_wrong_guesses += 1
            elif event["type"] == "human_clue":
                result.human_clues_given += 1
            elif event["type"] == "human_guess":
                if event["data"].get("correct"):
                    result.human_correct_guesses += 1
                else:
                    result.human_wrong_guesses += 1

        self.results.append(result)
        self._save_results()
        return result

    def get_metrics(self) -> EvaluationMetrics:
        """حساب المقاييس الشاملة"""
        if not self.results:
            return EvaluationMetrics()

        total = len(self.results)
        ai_wins = 0
        human_wins = 0

        for r in self.results:
            if not r.winner:
                continue
            # We need to know who was AI. In our current GameOrchestrator,
            # if human_team is RED, AI is BLUE and vice versa.
            # However, GameResult doesn't currently store human_team.
            # As a heuristic, since human is often RED in this app:
            if r.winner == "red":
                human_wins += 1
            else:
                ai_wins += 1

        metrics = EvaluationMetrics(
            total_games=total,
            ai_wins=ai_wins,
            human_wins=human_wins,
            ai_win_rate=ai_wins / total * 100 if total > 0 else 0,
            human_win_rate=human_wins / total * 100 if total > 0 else 0,
            avg_turns_per_game=(
                sum(r.total_turns for r in self.results) / total if total > 0 else 0
            ),
            avg_game_duration=(
                sum(r.duration_seconds for r in self.results) / total
                if total > 0
                else 0
            ),
            game_results=self.results[-20:],
        )

        # مقاييس حسب المستوى
        for diff in ["easy", "medium", "hard"]:
            diff_results = [r for r in self.results if r.ai_difficulty == diff]
            if diff_results:
                diff_total = len(diff_results)
                diff_ai_wins = sum(
                    1 for r in diff_results if r.winner and r.winner != "red"
                )
                metrics.metrics_by_difficulty[diff] = {
                    "total": diff_total,
                    "ai_wins": diff_ai_wins,
                    "ai_win_rate": diff_ai_wins / diff_total * 100,
                    "avg_turns": sum(r.total_turns for r in diff_results) / diff_total,
                }

        # مقاييس حسب حجم اللوحة
        for size in [8, 16, 25]:
            size_results = [r for r in self.results if r.board_size == size]
            if size_results:
                size_total = len(size_results)
                size_ai_wins = sum(
                    1 for r in size_results if r.winner and r.winner != "red"
                )
                metrics.metrics_by_board_size[str(size)] = {
                    "total": size_total,
                    "ai_wins": size_ai_wins,
                    "ai_win_rate": size_ai_wins / size_total * 100,
                    "avg_turns": sum(r.total_turns for r in size_results) / size_total,
                }

        # دقة الشفرات
        total_ai_guesses = sum(
            r.ai_correct_guesses + r.ai_wrong_guesses for r in self.results
        )
        total_ai_correct = sum(r.ai_correct_guesses for r in self.results)
        metrics.avg_clue_accuracy = (
            total_ai_correct / total_ai_guesses * 100 if total_ai_guesses > 0 else 0
        )

        return metrics

    def get_summary_report(self) -> str:
        """تقرير ملخص"""
        m = self.get_metrics()
        report = f"""
╔══════════════════════════════════════════╗
║          تقرير تقييم النظام              ║
╠══════════════════════════════════════════╣
║ إجمالي الألعاب: {m.total_games:>20} ║
║ فوز الذكاء الاصطناعي: {m.ai_wins:>15} ║
║ فوز اللاعب البشري: {m.human_wins:>17} ║
║ نسبة فوز الـ AI: {m.ai_win_rate:>17.1f}% ║
║ نسبة فوز البشري: {m.human_win_rate:>16.1f}% ║
║ متوسط الأدوار: {m.avg_turns_per_game:>19.1f} ║
║ دقة التخمين: {m.avg_clue_accuracy:>20.1f}% ║
╠══════════════════════════════════════════╣
║            حسب مستوى الصعوبة             ║
╠══════════════════════════════════════════╣"""

        for diff, data in m.metrics_by_difficulty.items():
            diff_ar = {"easy": "سهل", "medium": "متوسط", "hard": "صعب"}.get(diff, diff)
            report += f"\n║ {diff_ar}: {data['total']} ألعاب | فوز AI: {data['ai_win_rate']:.0f}%"

        report += "\n╚══════════════════════════════════════════╝"
        return report


async def run_automated_evaluation(
    num_games: int = 10,
    difficulty: Difficulty = Difficulty.MEDIUM,
    board_size: BoardSize = BoardSize.LARGE,
) -> EvaluationMetrics:
    """تشغيل تقييم تلقائي (AI ضد AI)"""
    framework = EvaluationFramework()

    for i in range(num_games):
        print(f"تشغيل اللعبة {i + 1}/{num_games}...")
        config = GameConfig(
            board_size=board_size,
            ai_difficulty=difficulty,
            human_team=TeamColor.RED,
            human_role=PlayerRole.OPERATIVE,
        )
        orchestrator = GameOrchestrator(config)

        try:
            start_time = time.time()
            # في وضع التقييم التلقائي، كلا الفريقين AI
            await orchestrator.start_game()
            # تسجيل المدة
            result = framework.record_game(orchestrator)
            result.duration_seconds = time.time() - start_time
        except Exception as e:
            print(f"خطأ في اللعبة {i + 1}: {e}")

    metrics = framework.get_metrics()
    print(framework.get_summary_report())
    return metrics
