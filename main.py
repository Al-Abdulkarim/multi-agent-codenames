"""
Multi-Agent Codenames — Entry Point
====================================

Usage:
    uv run python main.py --mode server          # Web UI (default)
    uv run python main.py --mode cli             # Terminal game
    uv run python main.py --mode eval --games 5  # AI-vs-AI evaluation
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def run_server(args):
    """Start FastAPI + WebSocket server."""
    import uvicorn
    from server.app import create_app

    app = create_app()
    print(f"\nCodenames server starting on http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def run_cli(args):
    """Start interactive CLI game."""
    api_key = args.api_key or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        print("Error: Provide --api-key or set GOOGLE_API_KEY in .env")
        sys.exit(1)

    from cli.game_cli import run_cli

    run_cli(
        lang=args.lang,
        size=int(args.size),
        difficulty=args.difficulty,
        team=args.team,
        role=args.role,
        category=args.category,
        api_key=api_key,
    )


def run_eval(args):
    """Run AI-vs-AI evaluation."""
    api_key = args.api_key or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        print("Error: Provide --api-key or set GOOGLE_API_KEY in .env")
        sys.exit(1)

    from models.enums import Language, Difficulty, BoardSize
    from evaluation.evaluator import Evaluator

    evaluator = Evaluator(
        api_key=api_key,
        num_games=args.games,
        board_size=BoardSize(int(args.size)),
        difficulty=Difficulty(args.difficulty),
        language=Language(args.lang),
    )
    report = evaluator.run()
    evaluator.print_summary(report)
    evaluator.save_report(report)


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Codenames",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["server", "cli", "eval"],
        default="server",
        help="Run mode (default: server)",
    )
    parser.add_argument("--port", type=int, default=8001, help="Server port")
    parser.add_argument("--api-key", type=str, default=None, help="Google API key")
    parser.add_argument("--lang", choices=["en", "ar"], default="en")
    parser.add_argument("--size", choices=["15", "25", "35"], default="25")
    parser.add_argument(
        "--difficulty", choices=["easy", "medium", "hard"], default="medium"
    )
    parser.add_argument("--team", choices=["red", "blue"], default="red")
    parser.add_argument(
        "--role", choices=["spymaster", "operative"], default="operative"
    )
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--games", type=int, default=5, help="Number of eval games")

    args = parser.parse_args()

    if args.mode == "server":
        run_server(args)
    elif args.mode == "cli":
        run_cli(args)
    elif args.mode == "eval":
        run_eval(args)


if __name__ == "__main__":
    main()
