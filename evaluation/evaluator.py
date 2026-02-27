"""
AI-vs-AI evaluation framework.

Runs multiple automated games between AI Spymaster + AI Operative
and collects win-rate, average turns, clue quality metrics.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from models.enums import Language, TeamColor, Difficulty, BoardSize
from game.game_manager import GameManager


@dataclass
class GameMetrics:
    game_id: str = ""
    winner: str = ""
    total_turns: int = 0
    red_remaining: int = 0
    blue_remaining: int = 0
    assassin_hit: bool = False
    duration_seconds: float = 0.0
    clues: list[dict] = field(default_factory=list)


@dataclass
class EvalReport:
    total_games: int = 0
    red_wins: int = 0
    blue_wins: int = 0
    avg_turns: float = 0.0
    avg_duration: float = 0.0
    assassin_hits: int = 0
    games: list[GameMetrics] = field(default_factory=list)


class Evaluator:
    """Runs batch AI-vs-AI games and aggregates metrics."""

    def __init__(
        self,
        api_key: str,
        num_games: int = 5,
        board_size: BoardSize = BoardSize.CLASSIC,
        difficulty: Difficulty = Difficulty.MEDIUM,
        language: Language = Language.ENGLISH,
    ):
        self.api_key = api_key
        self.num_games = num_games
        self.board_size = board_size
        self.difficulty = difficulty
        self.language = language

    def run(self) -> EvalReport:
        """Execute all evaluation games and return aggregated report."""
        report = EvalReport()
        all_turns: list[int] = []
        all_durations: list[float] = []

        for i in range(self.num_games):
            print(f"\n{'='*50}")
            print(f"  Evaluation Game {i + 1}/{self.num_games}")
            print(f"{'='*50}")

            metrics = self._run_single_game(i)
            report.games.append(metrics)

            if metrics.winner == "red":
                report.red_wins += 1
            elif metrics.winner == "blue":
                report.blue_wins += 1
            if metrics.assassin_hit:
                report.assassin_hits += 1

            all_turns.append(metrics.total_turns)
            all_durations.append(metrics.duration_seconds)

        report.total_games = self.num_games
        report.avg_turns = sum(all_turns) / len(all_turns) if all_turns else 0
        report.avg_duration = sum(all_durations) / len(all_durations) if all_durations else 0

        return report

    def _run_single_game(self, index: int) -> GameMetrics:
        """Play one full AI-vs-AI game."""
        gm = GameManager()
        state = gm.new_game(
            board_size=self.board_size.value,
            difficulty=self.difficulty.value,
            language=self.language.value,
            human_team="red",
            human_role="spymaster",
            api_key=self.api_key,
            category=None,
        )

        metrics = GameMetrics(game_id=state.id)
        start = time.time()
        turn_count = 0
        max_turns = 50  # safety limit

        while not state.game_over and turn_count < max_turns:
            turn_count += 1
            team = state.current_team

            # AI Clue phase
            try:
                clue_result = gm.run_ai_clue()
                clue_word = clue_result.get("clue", "???")
                clue_num = clue_result.get("number", 0)
                metrics.clues.append({"team": team, "word": clue_word, "number": clue_num})
                print(f"  [{team.upper()}] Clue: \"{clue_word}\" for {clue_num}")
            except Exception as e:
                print(f"  [{team.upper()}] Clue error: {e}")
                gm.pass_turn()
                continue

            if state.game_over:
                break

            # AI Guess phase — guess up to clue_num + 1 times
            max_guesses = clue_num + 1 if clue_num > 0 else 1
            for g in range(max_guesses):
                if state.game_over or state.current_phase != "guess":
                    break
                try:
                    guess_result = gm.run_ai_guess()
                    word = guess_result.get("word", "???")
                    correct = guess_result.get("correct", False)
                    print(f"  [{team.upper()}] Guess: {word} → {'✓' if correct else '✗'}")
                    if not correct:
                        break
                except Exception as e:
                    print(f"  [{team.upper()}] Guess error: {e}")
                    gm.pass_turn()
                    break

        metrics.duration_seconds = round(time.time() - start, 2)
        metrics.total_turns = turn_count
        metrics.winner = state.winner or ""
        metrics.red_remaining = state.red_remaining
        metrics.blue_remaining = state.blue_remaining
        metrics.assassin_hit = state.game_over and not state.winner

        print(f"  Result: {'WINNER=' + metrics.winner.upper() if metrics.winner else 'DRAW/LIMIT'}")
        return metrics

    @staticmethod
    def save_report(report: EvalReport, path: str = "evaluation_results.json"):
        """Save report to JSON file."""
        data = asdict(report)
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport saved to {path}")

    @staticmethod
    def print_summary(report: EvalReport):
        """Print a human-readable summary."""
        print(f"\n{'='*50}")
        print("  EVALUATION SUMMARY")
        print(f"{'='*50}")
        print(f"  Games played : {report.total_games}")
        print(f"  Red wins     : {report.red_wins}")
        print(f"  Blue wins    : {report.blue_wins}")
        print(f"  Avg turns    : {report.avg_turns:.1f}")
        print(f"  Avg duration : {report.avg_duration:.1f}s")
        print(f"  Assassin hits: {report.assassin_hits}")
        print(f"{'='*50}")
