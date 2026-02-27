# Multi-Agent Codenames — Implementation Plan

> **Framework**: CrewAI + Google Gemini (`gemini-2.0-flash`)  
> **Languages**: Arabic + English (bilingual)  
> **Interfaces**: Web UI + CLI

---

## Table of Contents

- [Game Overview](#game-overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Card Modes & Distribution](#card-modes--distribution)
- [Implementation Steps](#implementation-steps)
  - [Step 1 — Enums & Data Models](#step-1--enums--data-models)
  - [Step 2 — CardCreator Agent](#step-2--cardcreator-agent)
  - [Step 3 — Board Logic](#step-3--board-logic)
  - [Step 4 — Guardrails / Validators](#step-4--guardrails--validators)
  - [Step 5 — AI Spymaster Agent](#step-5--ai-spymaster-agent)
  - [Step 6 — AI Operative Agent](#step-6--ai-operative-agent)
  - [Step 7 — Game Manager](#step-7--game-manager)
  - [Step 8 — FastAPI Server](#step-8--fastapi-server)
  - [Step 9 — CLI Interface](#step-9--cli-interface)
  - [Step 10 — Web Frontend](#step-10--web-frontend)
  - [Step 11 — Evaluation Framework](#step-11--evaluation-framework)
  - [Step 12 — Configuration Files](#step-12--configuration-files)
  - [Step 13 — Dependencies](#step-13--dependencies)
- [Best Practices](#best-practices)
- [Verification & Testing](#verification--testing)
- [Key Decisions](#key-decisions)
- [How to Run](#how-to-run)

---

## Game Overview

Codenames is a word-association party game for two teams (Red vs Blue). The original game requires 4 players — since you can't play single-player, this project uses **AI agents** to fill the remaining roles.

### Rules

- A board of word cards is laid out (15, 25, or 35 cards)
- Each team has a **Spymaster** (gives clues) and an **Operative / Spy** (guesses words)
- The Spymaster sees which cards belong to which team (secret map)
- The Spymaster gives a **one-word clue** and a **number** (how many cards relate to that clue)
- The Operative guesses up to **number + 1** words per turn
- Guessing the **assassin card** = instant loss
- First team to reveal all their cards wins
- Red team always goes first (and gets +1 card to compensate)

### What the Player Can Do

- Choose **Red** or **Blue** team
- Choose to be **Spymaster** (give clues) or **Spy/Operative** (guess words)
- Use **random** word generation or pick a **specific category** (e.g., Saudi football players, European countries, animals, etc.)
- Play in **Arabic** or **English**
- Pick board size: **15** (fast), **25** (classic), **35** (large)
- Pick difficulty: **Easy**, **Medium**, **Hard**

### The 4 Agents

| Agent | When | Purpose |
|---|---|---|
| **CardCreator** | Pre-game only | Generates words by category, language, and difficulty |
| **AI Spymaster** | During game | Gives clues (for opponent team OR as human's AI teammate) |
| **AI Operative** | During game | Guesses words (for opponent team OR as human's AI teammate) |
| **Game Master** | Not an LLM agent — pure Python | Validates moves, manages state, enforces rules |

```
Human (Spy or Spymaster) + AI Teammate Agent
              vs.
   AI Spymaster + AI Operative (opponent team)

Pre-game: CardCreator Agent → generates themed board
```

---

## Architecture

```
┌─────────────────── Pre-Game ───────────────────┐
│                                                 │
│   Human selects: lang, category, size,          │
│   difficulty, team, role                        │
│              │                                  │
│              ▼                                  │
│   ┌─────────────────────┐                       │
│   │  CardCreator Agent  │  (CrewAI + Gemini)    │
│   │  - language          │                       │
│   │  - category          │                       │
│   │  - difficulty        │                       │
│   │  - count             │                       │
│   └────────┬────────────┘                       │
│            ▼                                    │
│   Board class assigns CardTypes randomly        │
│   (red, blue, neutral, assassin)                │
│                                                 │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────── Game Loop ──────────────────┐
│                                                 │
│   RED Clue Phase ──► RED Guess Phase            │
│        │                    │                   │
│   (Human or AI          (Human or AI            │
│    Spymaster)            Operative)             │
│        │                    │                   │
│        ▼                    ▼                   │
│   BLUE Clue Phase ──► BLUE Guess Phase          │
│        │                    │                   │
│   (Human or AI          (Human or AI            │
│    Spymaster)            Operative)             │
│        │                    │                   │
│        ▼                    ▼                   │
│   Check: game over? ──► repeat                  │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Project Structure

```
multi-agent-codenames/
├── config/
│   ├── agents.yaml          # CrewAI agent definitions (role, goal, backstory)
│   └── tasks.yaml           # CrewAI task definitions
├── agents/
│   ├── __init__.py
│   ├── card_creator.py      # CardCreator agent + crew
│   ├── spymaster.py         # AI Spymaster agent
│   └── operative.py         # AI Operative agent
├── tools/
│   ├── __init__.py
│   ├── board_tools.py       # Board analysis tool (visible words, categories)
│   └── word_tools.py        # Word association/relationship tool
├── crews/
│   ├── __init__.py
│   ├── card_crew.py         # Pre-game card generation crew
│   ├── clue_crew.py         # Spymaster clue-giving crew
│   └── guess_crew.py        # Operative guessing crew
├── models/
│   ├── __init__.py
│   ├── card.py              # Card, CardType, BoardConfig
│   ├── game_state.py        # GameState, TurnRecord, Clue, Guess
│   └── enums.py             # TeamColor, PlayerRole, Difficulty, BoardSize, Language
├── game/
│   ├── __init__.py
│   ├── game_manager.py      # GameManager — orchestrates full game loop
│   ├── board.py             # Board creation, card assignment, reveal logic
│   └── validators.py        # Clue & guess guardrails (pure Python)
├── server/
│   ├── __init__.py
│   ├── app.py               # FastAPI app + WebSocket
│   ├── routes.py            # API endpoints
│   └── ws_manager.py        # WebSocket connection manager
├── static/
│   ├── index.html           # Bilingual UI (AR/EN toggle)
│   ├── app.js               # Frontend game logic
│   └── styles.css           # Dark theme, RTL/LTR support
├── cli/
│   └── game_cli.py          # Terminal-based gameplay
├── evaluation/
│   ├── evaluator.py         # AI-vs-AI batch testing
│   └── results.json         # Persisted metrics
├── docs/
│   └── implementation-plan.md  # This file
├── .env                     # GOOGLE_API_KEY, GEMINI_MODEL
├── main.py                  # Entry point (CLI or server)
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Card Modes & Distribution

### 15-card mode (small / fast)

| Type | Count |
|---|---|
| 🔴 Starting team (Red) | **5** |
| 🔵 Other team (Blue) | **4** |
| ⚪ Neutral | **5** |
| ⚫ Assassin | **1** |
| **Total** | **15** |

### 25-card mode (classic)

| Type | Count |
|---|---|
| 🔴 Starting team (Red) | **9** |
| 🔵 Other team (Blue) | **8** |
| ⚪ Neutral | **7** |
| ⚫ Assassin | **1** |
| **Total** | **25** |

### 35-card mode (largest)

| Type | Count |
|---|---|
| 🔴 Starting team (Red) | **13** |
| 🔵 Other team (Blue) | **12** |
| ⚪ Neutral | **9** |
| ⚫ Assassin | **1** |
| **Total** | **35** |

> **Note**: Red always starts and gets +1 card. If the human chooses Blue, the starting team's card counts are swapped (Blue gets +1 instead).

---

## Implementation Steps

### Step 1 — Enums & Data Models

**`models/enums.py`**

```python
from enum import Enum

class Language(str, Enum):
    ARABIC = "ar"
    ENGLISH = "en"

class TeamColor(str, Enum):
    RED = "red"
    BLUE = "blue"

class PlayerRole(str, Enum):
    SPYMASTER = "spymaster"
    OPERATIVE = "operative"  # a.k.a. "Spy"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class BoardSize(int, Enum):
    SMALL = 15
    CLASSIC = 25
    LARGE = 35

class CardType(str, Enum):
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"
    ASSASSIN = "assassin"
```

**`models/card.py`**

```python
from pydantic import BaseModel
from .enums import CardType, BoardSize, Language, Difficulty

class Card(BaseModel):
    word: str
    card_type: CardType
    revealed: bool = False

class BoardConfig(BaseModel):
    size: BoardSize
    language: Language
    difficulty: Difficulty
    category: str | None = None  # None = random mixed theme

    def get_distribution(self, starting_team_is_red: bool = True):
        """Returns (starting_team, other_team, neutral, assassin) counts."""
        distributions = {
            BoardSize.SMALL:   (5, 4, 5, 1),
            BoardSize.CLASSIC: (9, 8, 7, 1),
            BoardSize.LARGE:   (13, 12, 9, 1),
        }
        return distributions[self.size]
```

**`models/game_state.py`**

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal
from .enums import TeamColor, PlayerRole, CardType
from .card import Card, BoardConfig

class Clue(BaseModel):
    word: str
    number: int
    team: TeamColor
    timestamp: datetime = datetime.now()

class Guess(BaseModel):
    word: str
    team: TeamColor
    result: CardType
    correct: bool

class TurnRecord(BaseModel):
    team: TeamColor
    clue: Clue
    guesses: list[Guess] = []

class GameState(BaseModel):
    game_id: str
    board: list[Card]
    config: BoardConfig
    current_team: TeamColor = TeamColor.RED  # Red starts
    current_phase: Literal["clue", "guess"] = "clue"
    human_team: TeamColor
    human_role: PlayerRole
    turns_history: list[TurnRecord] = []
    guesses_remaining: int = 0
    winner: TeamColor | None = None
    game_over: bool = False

    @property
    def red_remaining(self) -> int:
        return sum(1 for c in self.board if c.card_type == CardType.RED and not c.revealed)

    @property
    def blue_remaining(self) -> int:
        return sum(1 for c in self.board if c.card_type == CardType.BLUE and not c.revealed)

    def get_public_board(self) -> list[dict]:
        """Operative view — no card types for unrevealed cards."""
        return [
            {"word": c.word, "revealed": c.revealed, "card_type": c.card_type if c.revealed else None}
            for c in self.board
        ]

    def get_spymaster_board(self) -> list[dict]:
        """Spymaster view — all card types visible."""
        return [
            {"word": c.word, "revealed": c.revealed, "card_type": c.card_type}
            for c in self.board
        ]
```

---

### Step 2 — CardCreator Agent

**`agents/card_creator.py`**

The pre-game agent. Runs once to generate the word list.

```python
from crewai import Agent, Task, Crew, Process, LLM
from pydantic import BaseModel

class WordList(BaseModel):
    words: list[str]

class CardCreatorAgent:
    def __init__(self, api_key: str, model: str = "gemini/gemini-2.0-flash"):
        self.llm = LLM(model=model, api_key=api_key, temperature=0.8)

    def create_agent(self) -> Agent:
        return Agent(
            role="Codenames Word Generator",
            goal="Generate unique, thematically consistent words for a Codenames board",
            backstory=(
                "You are a multilingual vocabulary expert who specializes in creating "
                "word lists for the board game Codenames. You understand cultural context "
                "for both Arabic and English words. You ensure all words are unique, "
                "age-appropriate, and relevant to the requested category."
            ),
            llm=self.llm,
            reasoning=True,
            verbose=False,
        )

    def generate_words(self, count: int, language: str, category: str | None, difficulty: str) -> list[str]:
        agent = self.create_agent()

        difficulty_guide = {
            "easy": "Common, well-known words with obvious groupings. Easy to associate.",
            "medium": "Mix of common and uncommon words. Some tricky relationships possible.",
            "hard": "Obscure words, many potential cross-team associations. Deceptive similarities.",
        }

        category_text = f"category '{category}'" if category else "random mixed themes"

        task = Task(
            description=(
                f"Generate exactly {count} unique words in {'Arabic' if language == 'ar' else 'English'} "
                f"for {category_text}. Difficulty: {difficulty} — {difficulty_guide.get(difficulty, '')}. "
                f"Rules: no duplicates, no offensive words, each word must be a single word (no spaces)."
            ),
            expected_output=f"A JSON object with a 'words' array containing exactly {count} unique words.",
            agent=agent,
            output_pydantic=WordList,
            guardrail=lambda result: self._validate_words(result, count),
            guardrail_max_retries=3,
        )

        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()
        return result.pydantic.words

    def _validate_words(self, result, expected_count):
        try:
            words = result.pydantic.words if hasattr(result, 'pydantic') else []
            if len(words) != expected_count:
                return (False, f"Expected {expected_count} words, got {len(words)}")
            if len(set(words)) != len(words):
                return (False, "Duplicate words found")
            return (True, result)
        except Exception as e:
            return (False, f"Invalid output: {e}")
```

---

### Step 3 — Board Logic

**`game/board.py`** — Pure Python, no LLM.

```python
import random
from models.card import Card, BoardConfig
from models.enums import CardType, TeamColor

def create_board(words: list[str], config: BoardConfig, starting_team: TeamColor = TeamColor.RED) -> list[Card]:
    starting, other, neutral, assassin = config.get_distribution()

    starting_type = CardType.RED if starting_team == TeamColor.RED else CardType.BLUE
    other_type = CardType.BLUE if starting_team == TeamColor.RED else CardType.RED

    types = (
        [starting_type] * starting +
        [other_type] * other +
        [CardType.NEUTRAL] * neutral +
        [CardType.ASSASSIN] * assassin
    )
    random.shuffle(types)

    return [Card(word=w, card_type=t) for w, t in zip(words, types)]

def reveal_card(board: list[Card], word: str) -> Card | None:
    for card in board:
        if card.word == word and not card.revealed:
            card.revealed = True
            return card
    return None
```

---

### Step 4 — Guardrails / Validators

**`game/validators.py`** — Pure Python validation.

```python
from models.card import Card
from models.enums import Language

BANNED_WORDS = {
    "ar": {"أحمر", "أزرق", "تمرير", "محايد", "قاتل"},
    "en": {"red", "blue", "pass", "neutral", "assassin"},
}

def validate_clue(clue: str, number: int, board: list[Card], language: Language) -> tuple[bool, str]:
    if " " in clue.strip():
        return False, "Clue must be a single word"

    board_words = [c.word.lower() for c in board]
    if clue.lower() in board_words:
        return False, "Clue cannot be a word on the board"

    for bw in board_words:
        if clue.lower() in bw.lower() or bw.lower() in clue.lower():
            return False, f"Clue cannot be a substring of board word '{bw}'"

    if clue.lower() in BANNED_WORDS.get(language.value, set()):
        return False, "Clue is a banned game term"

    if not (0 <= number <= 9):
        return False, "Number must be between 0 and 9"

    return True, "Valid"

def validate_guess(word: str, board: list[Card]) -> tuple[bool, str]:
    card = next((c for c in board if c.word == word), None)
    if card is None:
        return False, "Word is not on the board"
    if card.revealed:
        return False, "Word is already revealed"
    return True, "Valid"
```

---

### Step 5 — AI Spymaster Agent

**`agents/spymaster.py`**

```python
from crewai import Agent, Task, Crew, Process, LLM
from pydantic import BaseModel

class ClueOutput(BaseModel):
    clue: str
    number: int

class AISpymaster:
    def __init__(self, team: str, difficulty: str, api_key: str, model: str = "gemini/gemini-2.0-flash"):
        self.team = team
        self.difficulty = difficulty
        self.llm = LLM(model=model, api_key=api_key, temperature=0.7)

    def create_agent(self) -> Agent:
        backstories = {
            "easy": "You are a beginner Spymaster. Give simple, safe clues that link to just 1 word.",
            "medium": "You are an experienced Spymaster. Find clues linking 2 words while avoiding traps.",
            "hard": "You are a master Spymaster. Find brilliant clues linking 3-4 words. Analyze every risk.",
        }
        return Agent(
            role=f"Codenames Spymaster for {self.team} team",
            goal="Give the best one-word clue connecting your team's unrevealed words",
            backstory=backstories.get(self.difficulty, backstories["medium"]),
            llm=self.llm,
            reasoning=(self.difficulty in ("medium", "hard")),
            max_reasoning_attempts=3 if self.difficulty == "hard" else 1,
            verbose=False,
        )

    def generate_clue(self, spymaster_board: list[dict], history: list[dict]) -> ClueOutput:
        agent = self.create_agent()
        targets = {"easy": 1, "medium": 2, "hard": 3}

        task = Task(
            description=(
                f"You are the {self.team} Spymaster.\n"
                f"Board (you can see all types): {spymaster_board}\n"
                f"Previous turns: {history}\n"
                f"Target connecting {targets.get(self.difficulty, 2)} of your team's words.\n"
                f"Give a one-word clue and the number of words it relates to.\n"
                f"NEVER use a word that is on the board. Avoid the assassin at all costs."
            ),
            expected_output="JSON with 'clue' (single word) and 'number' (integer)",
            agent=agent,
            output_pydantic=ClueOutput,
            guardrail_max_retries=3,
        )

        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False, memory=True)
        result = crew.kickoff()
        return result.pydantic
```

---

### Step 6 — AI Operative Agent

**`agents/operative.py`**

```python
from crewai import Agent, Task, Crew, Process, LLM
from pydantic import BaseModel

class GuessOutput(BaseModel):
    word: str
    confidence: float
    reasoning: str

class AIOperative:
    def __init__(self, team: str, difficulty: str, api_key: str, model: str = "gemini/gemini-2.0-flash"):
        self.team = team
        self.difficulty = difficulty
        self.llm = LLM(model=model, api_key=api_key, temperature=0.4)

    def create_agent(self) -> Agent:
        return Agent(
            role=f"Codenames Operative for {self.team} team",
            goal="Guess the correct words based on the Spymaster's clue while avoiding the assassin",
            backstory=(
                "You are a sharp-minded word puzzle solver. You can ONLY see which words "
                "are on the board and which have been revealed — you do NOT know which "
                "unrevealed words belong to which team."
            ),
            llm=self.llm,
            reasoning=(self.difficulty == "hard"),
            verbose=False,
        )

    def make_guess(self, clue: str, number: int, public_board: list[dict], history: list[dict]) -> GuessOutput:
        """Called once per guess. Invoke iteratively up to number+1 times."""
        agent = self.create_agent()

        task = Task(
            description=(
                f"The Spymaster's clue is '{clue}' for {number}.\n"
                f"Visible board (you cannot see unrevealed types): {public_board}\n"
                f"Previous turns: {history}\n"
                f"Pick your BEST single guess from the unrevealed words."
            ),
            expected_output="JSON with 'word', 'confidence' (0-1), and 'reasoning'",
            agent=agent,
            output_pydantic=GuessOutput,
        )

        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False, memory=True)
        result = crew.kickoff()
        return result.pydantic
```

> **Process Isolation**: The Operative receives `get_public_board()` — never the secret card types. This mirrors real Codenames rules.

---

### Step 7 — Game Manager

**`game/game_manager.py`** — Pure Python orchestrator (not an LLM agent).

```python
import uuid
from models.game_state import GameState, Clue, Guess, TurnRecord
from models.card import BoardConfig
from models.enums import TeamColor, PlayerRole, CardType
from agents.card_creator import CardCreatorAgent
from agents.spymaster import AISpymaster
from agents.operative import AIOperative
from game.board import create_board, reveal_card
from game.validators import validate_clue, validate_guess

class GameManager:
    def __init__(self, api_key: str, model: str = "gemini/gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.state: GameState | None = None

    def new_game(self, config: BoardConfig, human_team: TeamColor, human_role: PlayerRole) -> GameState:
        # 1. Generate words via CardCreator
        creator = CardCreatorAgent(api_key=self.api_key, model=self.model)
        words = creator.generate_words(
            count=config.size.value,
            language=config.language.value,
            category=config.category,
            difficulty=config.difficulty.value,
        )

        # 2. Build board
        board = create_board(words, config, starting_team=TeamColor.RED)

        # 3. Initialize state
        self.state = GameState(
            game_id=str(uuid.uuid4()),
            board=board,
            config=config,
            human_team=human_team,
            human_role=human_role,
        )
        return self.state

    def is_human_turn(self) -> bool:
        if self.state.current_team != self.state.human_team:
            return False
        if self.state.current_phase == "clue" and self.state.human_role == PlayerRole.SPYMASTER:
            return True
        if self.state.current_phase == "guess" and self.state.human_role == PlayerRole.OPERATIVE:
            return True
        return False

    def submit_human_clue(self, clue: str, number: int) -> dict:
        valid, msg = validate_clue(clue, number, self.state.board, self.state.config.language)
        if not valid:
            return {"success": False, "error": msg}

        clue_obj = Clue(word=clue, number=number, team=self.state.current_team)
        self.state.turns_history.append(TurnRecord(team=self.state.current_team, clue=clue_obj))
        self.state.guesses_remaining = number + 1
        self.state.current_phase = "guess"
        return {"success": True}

    def submit_human_guess(self, word: str) -> dict:
        valid, msg = validate_guess(word, self.state.board)
        if not valid:
            return {"success": False, "error": msg}

        card = reveal_card(self.state.board, word)
        correct = card.card_type.value == self.state.current_team.value
        guess = Guess(word=word, team=self.state.current_team, result=card.card_type, correct=correct)
        self.state.turns_history[-1].guesses.append(guess)
        self.state.guesses_remaining -= 1

        # Check game-over conditions
        if card.card_type == CardType.ASSASSIN:
            other = TeamColor.BLUE if self.state.current_team == TeamColor.RED else TeamColor.RED
            self.state.winner = other
            self.state.game_over = True
            return {"success": True, "revealed": card.card_type, "game_over": True, "winner": other}

        if self.state.red_remaining == 0:
            self.state.winner = TeamColor.RED
            self.state.game_over = True
        elif self.state.blue_remaining == 0:
            self.state.winner = TeamColor.BLUE
            self.state.game_over = True

        # Wrong guess or out of guesses → end turn
        if not correct or self.state.guesses_remaining <= 0:
            self._switch_turn()

        return {"success": True, "revealed": card.card_type, "correct": correct, "game_over": self.state.game_over}

    def run_ai_clue(self) -> ClueOutput:
        spymaster = AISpymaster(
            team=self.state.current_team.value,
            difficulty=self.state.config.difficulty.value,
            api_key=self.api_key,
            model=self.model,
        )
        clue = spymaster.generate_clue(
            spymaster_board=self.state.get_spymaster_board(),
            history=[t.model_dump() for t in self.state.turns_history],
        )
        # Record the clue
        self.submit_human_clue(clue.clue, clue.number)  # reuses validation logic
        return clue

    def run_ai_guess(self) -> list[GuessOutput]:
        operative = AIOperative(
            team=self.state.current_team.value,
            difficulty=self.state.config.difficulty.value,
            api_key=self.api_key,
            model=self.model,
        )
        guesses = []
        while self.state.guesses_remaining > 0 and not self.state.game_over:
            guess = operative.make_guess(
                clue=self.state.turns_history[-1].clue.word,
                number=self.state.turns_history[-1].clue.number,
                public_board=self.state.get_public_board(),
                history=[t.model_dump() for t in self.state.turns_history],
            )
            result = self.submit_human_guess(guess.word)
            guesses.append(guess)
            if not result.get("correct", False):
                break
        return guesses

    def pass_turn(self):
        self._switch_turn()

    def _switch_turn(self):
        self.state.current_team = (
            TeamColor.BLUE if self.state.current_team == TeamColor.RED else TeamColor.RED
        )
        self.state.current_phase = "clue"
        self.state.guesses_remaining = 0
```

---

### Step 8 — FastAPI Server

**`server/app.py`** — Main server file.

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/api/game/new` | `{board_size, difficulty, language, category, human_team, human_role, api_key}` | Create new game |
| `GET` | `/api/game/{id}/state` | — | Get game state (filtered by role) |
| `POST` | `/api/game/{id}/clue` | `{clue, number}` | Human submits clue |
| `POST` | `/api/game/{id}/guess` | `{word}` | Human submits guess |
| `POST` | `/api/game/{id}/pass` | — | Pass / end turn |
| `WS` | `/ws/{id}` | — | Real-time updates |

After human input, AI turns run in a **background task** (`asyncio.create_task`) and push updates via WebSocket.

**`server/ws_manager.py`** — Broadcast events:
- `board_update` — after any card reveal
- `clue_given` — after Spymaster gives a clue
- `guess_made` — after each guess
- `turn_change` — when active team switches
- `game_over` — winner announcement
- `ai_thinking` — while AI agents are processing

---

### Step 9 — CLI Interface

**`cli/game_cli.py`** — Terminal-based gameplay.

```python
# Usage:
# python main.py --mode cli --lang ar --size 25 --difficulty medium --team blue --role operative
```

Features:
- Colored board grid (ANSI colors via `colorama`)
- Spymaster view shows card types; Operative view shows blank cards
- Text prompts for clue input (word + number) or guess input (word)
- AI actions printed as they happen
- Supports Arabic terminal output

---

### Step 10 — Web Frontend

**`static/index.html`** — Bilingual single-page app.

**Setup screen:**
- Language toggle (AR ↔ EN)
- API key input
- Board size selector (15 / 25 / 35)
- Difficulty selector (Easy / Medium / Hard)
- Category input (free text — e.g., "Saudi football players", "animals")
- Team color picker (Red / Blue)
- Role picker (Spymaster / Operative)

**Game screen:**
- Board grid (3×5, 5×5, or 5×7 depending on size)
- Score header (Red remaining vs Blue remaining)
- Current clue display
- Action bar (clue form or guess buttons or pass button)
- AI thinking indicator
- Turn history sidebar

**Styling:**
- Dark theme with CSS custom properties
- `dir="rtl"` for Arabic, `dir="ltr"` for English (toggled dynamically)
- Cairo/Tajawal fonts for Arabic, system fonts for English
- Card reveal animations
- Responsive breakpoints at 1024px, 768px, 480px

---

### Step 11 — Evaluation Framework

**`evaluation/evaluator.py`**

- `run_ai_vs_ai(config, num_games)` — both teams fully AI, no human input
- Metrics tracked:
  - Win rate by team / difficulty / board size
  - Average turns to win
  - Clue accuracy (% correct guesses per clue)
  - Assassin hit rate
- Results persisted to `evaluation/results.json`

---

### Step 12 — Configuration Files

**`config/agents.yaml`**

```yaml
card_creator:
  role: "Codenames Word Generator"
  goal: "Generate {count} unique, thematic words in {language} for category '{category}'"
  backstory: >
    You are a multilingual vocabulary expert who specializes in creating 
    word lists for the board game Codenames. You ensure all words are unique, 
    age-appropriate, and relevant to the requested category.

spymaster:
  role: "Codenames Spymaster for {team} team"
  goal: "Give the best one-word clue connecting your team's unrevealed words"
  backstory: "Strategic word-association master. Difficulty: {difficulty}."

operative:
  role: "Codenames Operative for {team} team"
  goal: "Guess the correct words based on the Spymaster's clue"
  backstory: "Sharp-minded word puzzle solver. Cannot see secret card types."
```

**`config/tasks.yaml`**

```yaml
generate_words:
  description: >
    Generate exactly {count} unique words in {language} for {category}. 
    Difficulty: {difficulty}. No duplicates, no offensive words.
  expected_output: "A JSON object with a 'words' array of {count} unique words"

give_clue:
  description: >
    You are the {team} Spymaster. Analyze the board and give a one-word clue 
    that connects as many of your team's words as possible. Avoid the assassin.
  expected_output: "JSON: {clue, number}"

make_guess:
  description: >
    The clue is '{clue}' for {number}. Pick the best word from the unrevealed 
    words on the board.
  expected_output: "JSON: {word, confidence, reasoning}"
```

---

### Step 13 — Dependencies

**`requirements.txt`**

```
crewai>=0.100.0
crewai[tools]
fastapi>=0.115.0
uvicorn>=0.32.0
pydantic>=2.0.0
python-dotenv>=1.0.0
websockets>=13.0
colorama>=0.4.0
```

No `langchain`, `langgraph`, or `langchain-google-genai` needed — CrewAI has native Gemini support.

---

## Best Practices

| Practice | Where | Why |
|---|---|---|
| **Process isolation** | Operative never sees `CardType` of unrevealed cards | Prevents cheating; mirrors real Codenames rules |
| **Guardrails as CrewAI task guards** | `validate_clue` / `validate_guess` as `guardrail=` param | Auto-retry on invalid output, no manual loops |
| **Pydantic output models** | `output_pydantic=` on every task | Structured, typed outputs — no fragile string parsing |
| **YAML agent/task config** | `config/agents.yaml`, `config/tasks.yaml` | Separate prompts from code; easy to tune |
| **Memory scoping** | Per-team memory on crews | Prevents cross-team information leakage |
| **Difficulty via backstory** | Change agent `backstory` + `reasoning` flag per difficulty | Same agent class, different strategic depth |
| **Background AI turns** | `asyncio.create_task` for opponent turns | Non-blocking HTTP responses; real-time updates |
| **Idempotent game state** | `GameState` is a Pydantic model, fully serializable | Easy to persist, restore, and transmit via API |
| **Board as single source of truth** | All reveals go through `GameManager.reveal_card()` | No state inconsistency |
| **Language as first-class config** | `Language` enum flows through CardCreator → UI → validators | Bilingual from day one |
| **Category-driven generation** | Category passed to CardCreator prompt | Infinite variety without hardcoded word lists |
| **Guardrail retries** | `guardrail_max_retries=3` on all LLM tasks | LLMs sometimes produce invalid output |
| **GameManager is pure Python** | Not an LLM agent | Game rules must be deterministic, not probabilistic |
| **One guess per crew kickoff** | Invoke guess crew iteratively | Board state updates between guesses |

---

## Verification & Testing

| Test | What to verify |
|---|---|
| **Unit: BoardConfig** | `get_distribution()` returns correct counts for all 3 sizes |
| **Unit: Validators** | Edge cases — substrings, banned words, already revealed cards |
| **Unit: Board** | Card type assignment matches distribution; shuffle randomness |
| **Integration: CardCreator** | `category="Saudi football players"` returns correct count of Arabic words |
| **AI-vs-AI smoke test** | 5 games per difficulty/size combo via evaluator — no crashes, reasonable win rates |
| **Manual: Web** | Start server → play as Blue Operative on 25-card Easy → full game completes |
| **Manual: CLI** | Run CLI → play as Red Spymaster on 15-card Easy → full game completes |

---

## Key Decisions

| Decision | Rationale |
|---|---|
| CrewAI over LangGraph | `guardrail` + `output_pydantic` + YAML config are a better fit for structured game tasks |
| Gemini over OpenAI | User preference; CrewAI supports Gemini natively via `"gemini/gemini-2.0-flash"` |
| No hardcoded word lists | LLM generates all words dynamically per category — infinite variety |
| Red always starts | Standard Codenames rule; Red gets +1 card to compensate |
| GameManager is pure Python | Game rules should be deterministic, not probabilistic |
| One guess per crew kickoff | Board state updates between guesses for accurate context |

---

## How to Run

### Prerequisites

1. **Python 3.11+** installed
2. **Google API Key** with Gemini access — get one at [Google AI Studio](https://aistudio.google.com/apikey)

### Installation

```bash
# Clone / navigate to the project
cd multi-agent-codenames

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Setup

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your-google-api-key-here
GEMINI_MODEL=gemini/gemini-2.0-flash
```

### Running the Web Server

```bash
python main.py --mode server --port 8000
```

Then open your browser at **http://localhost:8000**

1. Enter your Google API Key (or it uses the one from `.env`)
2. Select language (Arabic / English)
3. Pick board size (15 / 25 / 35)
4. Pick difficulty (Easy / Medium / Hard)
5. Optionally enter a category (e.g., "Saudi football players", "European countries")
6. Choose your team (Red / Blue) and role (Spymaster / Operative)
7. Click **Start Game**

The AI agents will handle the rest — your opponent's turns run automatically, and your AI teammate fills the role you didn't pick.

### Running the CLI

```bash
# Full options
python main.py --mode cli --lang ar --size 25 --difficulty medium --team blue --role operative

# Quick start with defaults (English, 25 cards, medium, red team, operative)
python main.py --mode cli
```

**CLI flags:**

| Flag | Options | Default |
|---|---|---|
| `--mode` | `cli`, `server` | `server` |
| `--lang` | `ar`, `en` | `en` |
| `--size` | `15`, `25`, `35` | `25` |
| `--difficulty` | `easy`, `medium`, `hard` | `medium` |
| `--team` | `red`, `blue` | `red` |
| `--role` | `spymaster`, `operative` | `operative` |
| `--category` | any text | `None` (random) |
| `--port` | integer | `8000` (server mode only) |

### Running AI-vs-AI Evaluation

```bash
python -m evaluation.evaluator --games 10 --difficulty medium --size 25
```

Results are saved to `evaluation/results.json`.
