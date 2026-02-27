# Multi-Agent Codenames — User Guide

> **CrewAI + Google Gemini** powered Codenames board game with bilingual support (English / Arabic), three board sizes, and three difficulty levels.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Web UI](#running-the-web-ui)
5. [Running the CLI](#running-the-cli)
6. [Running AI-vs-AI Evaluation](#running-ai-vs-ai-evaluation)
7. [How to Play (Web)](#how-to-play-web)
8. [How to Play (CLI)](#how-to-play-cli)
9. [Game Options](#game-options)
10. [API Reference](#api-reference)
11. [Project Structure](#project-structure)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.11+ | Runtime |
| **uv** | latest | Package manager ([install guide](getting-started-with-uv.md)) |
| **Google API Key** | — | Gemini LLM access |
| **Tavily API Key** | _(optional)_ | Category-based word research |

### Getting API Keys

1. **Google Gemini** — Go to [Google AI Studio](https://aistudio.google.com/apikey) → Create an API key.
2. **Tavily** _(optional)_ — Go to [tavily.com](https://tavily.com) → Sign up → Copy your API key. This is used by the Card Creator agent to search for real-world words in a given category (e.g. "Saudi football players").

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd multi-agent-codenames

# 2. Install all dependencies with uv
uv sync

# 3. Copy the environment template
cp .env.example .env        # Linux / macOS
copy .env.example .env       # Windows
```

Edit `.env` and paste your keys:

```dotenv
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
TAVILY_API_KEY=your_tavily_api_key_here   # optional
```

That's it — no `pip install`, no virtual-env juggling. `uv sync` handles everything.

---

## Configuration

All configuration lives in the `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | **Yes** | — | Your Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model name |
| `TAVILY_API_KEY` | No | — | Tavily search key for category research |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server port |
| `DEBUG` | No | `true` | Enable debug logging |

---

## Running the Web UI

```bash
uv run python main.py --mode server
```

Then open your browser at **http://localhost:8000**.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8000` | Change the server port |

Example on a custom port:

```bash
uv run python main.py --mode server --port 3000
```

### What you'll see

1. **Setup Screen** — Enter your API key, choose board size, difficulty, category, team, and role.
2. **Game Board** — Interactive card grid with real-time updates via WebSocket.

---

## Running the CLI

```bash
uv run python main.py --mode cli --api-key YOUR_KEY
```

Or set `GOOGLE_API_KEY` in `.env` and omit `--api-key`:

```bash
uv run python main.py --mode cli
```

### CLI Options

| Flag | Choices | Default | Description |
|------|---------|---------|-------------|
| `--api-key` | _text_ | from `.env` | Google API key |
| `--lang` | `en`, `ar` | `en` | Game language |
| `--size` | `15`, `25`, `35` | `25` | Number of cards |
| `--difficulty` | `easy`, `medium`, `hard` | `medium` | AI difficulty |
| `--team` | `red`, `blue` | `red` | Your team color |
| `--role` | `spymaster`, `operative` | `operative` | Your role |
| `--category` | _text_ | `None` | Word category (e.g. "animals") |

### Examples

```bash
# English, 25 cards, medium, play as Red Operative
uv run python main.py --mode cli

# Arabic, 35 cards, hard, play as Blue Spymaster, football category
uv run python main.py --mode cli --lang ar --size 35 --difficulty hard --team blue --role spymaster --category "لاعبي كرة قدم"

# Small board, easy AI
uv run python main.py --mode cli --size 15 --difficulty easy
```

---

## Running AI-vs-AI Evaluation

Run batch games where AI plays both sides to measure performance:

```bash
uv run python main.py --mode eval --games 10 --api-key YOUR_KEY
```

### Eval Options

| Flag | Default | Description |
|------|---------|-------------|
| `--games` | `5` | Number of games to simulate |
| `--size` | `25` | Board size |
| `--difficulty` | `medium` | AI difficulty level |
| `--lang` | `en` | Language |

Results are saved to `evaluation_results.json` with metrics on win rates, average turns, and assassin hits.

---

## How to Play (Web)

### 1. Setup

When the page loads you'll see the **Setup Screen**:

1. **Paste your Google API Key** (required to start).
2. **Choose Board Size**: 15 (quick), 25 (classic), or 35 (extended).
3. **Choose Difficulty**: Easy, Medium, or Hard — affects how clever the AI's clues are.
4. **Category** _(optional)_: Type a theme like `"animals"`, `"Saudi football players"`, or `"مدن عربية"`. The AI Card Creator will use Tavily to research real-world words for that category. Leave blank for general words.
5. **Choose Team**: Red or Blue.
6. **Choose Role**: Spymaster (you give clues) or Operative (you guess).
7. Click **Start Game**.

### 2. Gameplay

#### If you are the **Spymaster**:

- You see the board with **colour hints** on each card (your team's cards are highlighted).
- When it's your turn, type a **one-word clue** and a **number** indicating how many cards it relates to.
- The AI Operative will then guess based on your clue.
- The clue cannot be a word on the board, and must be a single word.

#### If you are the **Operative**:

- You see the board **without colour hints** — just words.
- When the AI Spymaster gives a clue (shown above the board), **click cards** to guess.
- You get `clue_number + 1` guesses maximum.
- Click **Pass** to end your guessing early and hand the turn over.

#### Card Results:

| Card Type | What Happens |
|-----------|-------------|
| 🟥 **Your team** | Correct! Card flips to your colour. Keep guessing. |
| 🟦 **Opponent** | Wrong — card flips to opponent's colour. Turn ends. |
| ⬜ **Neutral** | Bystander. Turn ends. |
| ⬛ **Assassin** | Instant loss! Game over. |

### 3. Winning

- Your team wins when **all your team's cards** are revealed.
- You lose if the opponent reveals all theirs first, or you hit the **assassin**.

### 4. Game Log

The right sidebar shows a live **event log** of all clues and guesses.

### 5. Language Toggle

Use the **EN / AR** buttons in the top-right of the setup screen to switch the interface between English and Arabic. The board words will be generated in the selected language.

---

## How to Play (CLI)

The terminal version uses coloured text output:

1. **Board Display** — Cards are printed in a coloured grid:
   - 🟥 Red = Red team
   - 🟦 Blue = Blue team
   - ⬜ White = Neutral
   - ⬛ Dark = Assassin
   - Revealed cards show `[WORD]` in brackets

2. **As Spymaster** — You see the full board with card types. Type your clue as `word number` (e.g., `ocean 3`).

3. **As Operative** — You see only revealed cards. Type the word you want to guess, or type `pass` to end your turn.

4. The AI partner takes its turn automatically and results are printed in the terminal.

---

## Game Options

### Board Sizes

| Size | Grid | Red | Blue | Neutral | Assassin |
|------|------|-----|------|---------|----------|
| **15** | 5×3 | 5 | 4 | 5 | 1 |
| **25** | 5×5 | 9 | 8 | 7 | 1 |
| **35** | 7×5 | 13 | 12 | 9 | 1 |

_(Red always starts and gets one extra card.)_

### Difficulty Levels

| Level | Description |
|-------|-------------|
| **Easy** | AI gives broad, simple clues. Forgiving gameplay. |
| **Medium** | Balanced clues. AI avoids obvious traps. |
| **Hard** | AI gives tight, multi-word clues. High risk, high reward. |

---

## API Reference

The server exposes these REST + WebSocket endpoints:

### `POST /api/game/new`

Create a new game.

**Request Body:**

```json
{
  "board_size": 25,
  "difficulty": "medium",
  "language": "en",
  "category": "animals",
  "human_team": "red",
  "human_role": "operative",
  "api_key": "your-key"
}
```

**Response:** Full game state (board, scores, turn info).

---

### `GET /api/game/{game_id}/state`

Get current game state.

---

### `POST /api/game/clue`

Submit a human spymaster's clue.

```json
{
  "game_id": "abc123",
  "clue": "ocean",
  "number": 3
}
```

---

### `POST /api/game/guess`

Submit a human operative's guess.

```json
{
  "game_id": "abc123",
  "word": "whale"
}
```

---

### `POST /api/game/pass`

End the current guessing phase early.

```json
{
  "game_id": "abc123"
}
```

---

### `WebSocket /ws/{game_id}`

Real-time game updates. Events:

| Event | Data | Description |
|-------|------|-------------|
| `state_update` | game state | Board/score changed |
| `ai_thinking` | `{}` | AI agent is processing |
| `ai_turn_complete` | clue/guess result | AI finished its turn |
| `game_over` | `{winner: "red"}` | Game ended |

---

## Project Structure

```
multi-agent-codenames/
├── main.py                  # Entry point (--mode server|cli|eval)
├── pyproject.toml           # Dependencies (managed by uv)
├── .env.example             # Environment template
│
├── models/                  # Pydantic data models
│   ├── enums.py             # Language, TeamColor, BoardSize, Difficulty
│   ├── card.py              # Card, BoardConfig
│   └── game_state.py        # GameState, Clue, Guess, TurnRecord
│
├── agents/                  # CrewAI AI agents
│   ├── card_creator.py      # Generates board words (uses Tavily)
│   ├── spymaster.py         # Gives clues based on board analysis
│   └── operative.py         # Guesses words from clues
│
├── tools/                   # CrewAI @tool wrappers
│   ├── tavily_search.py     # Web search for category research
│   └── board_tools.py       # Board state analysis
│
├── game/                    # Core game logic (pure Python)
│   ├── board.py             # Board creation & card reveal
│   ├── validators.py        # Clue & guess validation rules
│   └── game_manager.py      # Turn orchestration
│
├── server/                  # FastAPI web server
│   ├── app.py               # App factory + static files
│   ├── routes.py            # REST + WebSocket endpoints
│   └── ws_manager.py        # WebSocket connection manager
│
├── cli/                     # Terminal interface
│   └── game_cli.py          # Colorama-based CLI game loop
│
├── evaluation/              # AI testing framework
│   └── evaluator.py         # Batch AI-vs-AI with metrics
│
├── config/                  # Agent/task YAML definitions
│   ├── agents.yaml          # Agent roles per difficulty
│   └── tasks.yaml           # Task templates
│
├── static/                  # Web frontend
│   ├── index.html           # Bilingual UI (EN/AR)
│   ├── styles.css           # Dark theme styles
│   └── app.js               # Frontend logic + WebSocket
│
└── docs/                    # Documentation
    ├── README.md             # ← You are here
    ├── implementation-plan.md
    └── getting-started-with-uv.md
```

---

## Troubleshooting

### "No API key provided"

Make sure `GOOGLE_API_KEY` is set in your `.env` file, or pass `--api-key` on the command line.

### `uv: command not found`

Install uv first. See [getting-started-with-uv.md](getting-started-with-uv.md) or run:

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Dependencies fail to install

```bash
# Remove stale lock and re-sync
Remove-Item uv.lock      # Windows
rm uv.lock                # macOS/Linux
uv sync
```

### WebSocket not connecting

- Make sure you're accessing via `http://localhost:8000` (not a file:// URL).
- The app falls back to HTTP polling every 3 seconds if WebSocket fails.

### Board words aren't in the right language

Check that you selected the correct language (`en` or `ar`) in the setup screen or `--lang` flag. The Card Creator agent generates words in the chosen language via its LLM prompt.

### AI takes too long

- The first turn may take 10–20 seconds as CrewAI initializes.
- Subsequent turns are faster. The web UI shows an "AI is thinking…" indicator.
- If using `--difficulty hard`, clues take longer because the AI does deeper analysis.

### Port already in use

```bash
uv run python main.py --mode server --port 3000
```
