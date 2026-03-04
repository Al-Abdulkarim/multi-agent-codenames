# CipherNames — Game Overview

> A multi-agent AI-powered Codenames game where a human plays alongside and against AI agents.

---

## What Is the Game

CipherNames is a digital adaptation of the board game **Codenames**. It is designed for a single human player who cannot find other players — AI agents fill all remaining roles so the full 4-player experience is possible solo.

Two teams compete: **Red** vs **Blue**. Each team has two roles:
- **Spymaster** — knows the secret map; gives one-word clues
- **Operative (Spy)** — sees only the public board; guesses words based on clues

The human picks one team and one role. The remaining three roles are handled by AI agents.

---

## Game Configuration (Setup Screen)

Before the game starts, the human configures:

| Option | Choices |
|---|---|
| Team | Red or Blue |
| Role | Spymaster or Operative |
| Language | English or Arabic |
| Board Size | 15 (Fast), 25 (Classic), 35 (Large) |
| Difficulty | Easy, Medium, Hard |
| Word Category | Optional — leave blank for random, or type a theme (e.g. animals, countries, Saudi football players) |

---

## Phase 1 — Pre-Game: Card Creator Agent

Before the board appears, the **Card Creator Agent** runs once:

- Receives: language, difficulty, board size, optional category
- Task: generate a list of unique words for the board
- If a specific real-world category is given (e.g. "Saudi football players"), the agent uses a **Tavily web search tool** to fetch up-to-date names before building the list
- Difficulty shapes the words:
  - **Easy** → common, well-known words that are easy to distinguish
  - **Medium** → mix of common and less common words
  - **Hard** → obscure words with tricky relationships; the assassin word is deceptively similar to team words
- Output: a clean word list passed to the board builder

---

## Phase 2 — Board Setup

After words are generated, the board is built:

- Words are assigned card types: **Team Red**, **Team Blue**, **Neutral**, **Assassin**
- **Red always starts** (goes first) and has one extra card to compensate
- Exactly **1 Assassin** card exists on every board

### Card Distribution

| Type | 15-Card | 25-Card | 35-Card |
|---|---|---|---|
| Red (starting) | 5 | 9 | 13 |
| Blue | 4 | 8 | 12 |
| Neutral | 5 | 7 | 9 |
| Assassin | 1 | 1 | 1 |

- The **Spymaster** sees the full map (which word belongs to which type)
- The **Operative** sees only word text and which cards have already been revealed

---

## Phase 3 — Turn Flow

Turns alternate between Red and Blue. Each turn has two steps:

### Step 1 — Clue Phase (Spymaster acts)
- The Spymaster gives a **one-word clue** and a **number** (how many cards relate to it)
- The clue must not be any word already on the board
- The clue is displayed publicly as a banner on the board

### Step 2 — Guess Phase (Operative acts)
- The Operative guesses words one at a time
- Maximum guesses per turn: **number + 1**
- Each guess is immediately revealed and classified (own team / opponent team / neutral / assassin)
- The Operative may stop guessing early (end turn voluntarily)
- The turn ends automatically when:
  - A wrong guess is made (non-team card revealed)
  - The guess limit is reached
  - The Operative manually ends the turn

### Turn Switch
After a team's turn ends, it becomes the other team's turn, starting with their Clue Phase.

---

## The 4 AI Agents

### 1. Card Creator Agent
- **When**: pre-game only, runs once before the board is shown
- **Role**: generates themed word lists
- **Tools**: Tavily web search (for real-world category lookups)
- **Model behavior**: uses high temperature for creative word diversity

### 2. AI Spymaster
- **When**: whenever a Spymaster turn belongs to an AI (opponent team's turn, or human chose Operative role)
- **Sees**: the **full secret board map** — knows every card's type
- **Task**: analyze the board and produce the best one-word clue + number
- **Tool**: `analyze_board` — structured inspection of all card relationships
- **Reasoning scales with difficulty**:
  - Easy → simple, single-word link; no deep reasoning
  - Medium → reflection-based; targets 2 team words
  - Hard → multi-step reasoning; targets 3–4 words; thinks multiple turns ahead
- **Output**: clue word, number, and a reflection string (shown in agent logs)

### 3. AI Operative
- **When**: whenever an Operative turn belongs to an AI (opponent team's turn, or human chose Spymaster role)
- **Sees**: the **public board only** — word text and revealed status, nothing else
- **Does NOT see**: card types or the secret map (strictly isolated)
- **Task**: given the clue and number, decide the best word to guess
- **Reasoning scales with difficulty**:
  - Easy → connects 1 word
  - Medium → tries to connect 2 words cleverly
  - Hard → advanced reasoning, connects 3+ words
- **Output**: guessed word, confidence score, reasoning string (shown in logs)
- Makes one guess at a time; the game loop calls it repeatedly until the turn ends

### 4. Chat Agent (Teammate + Opponents)
- **When**: continuously throughout the game, triggered by game events
- **Not a gameplay agent** — purely commentary and personality
- Plays **three distinct personas**:
  - **Opponent Spymaster** — smug, clever, slightly arrogant
  - **Opponent Operative** — loud, hype, trash-talk energy
  - **Teammate** — warm, supportive, celebrates with the human
- **Event triggers** (what makes agents speak):
  - Bad guess → opponents mock, teammate comforts
  - Good guess → teammate cheers, opponents may react
  - Sweep (all clue words guessed) → big reactions
  - Assassin hit → dramatic reactions from all sides
  - Clue given → teammate may comment
  - Human sends a chat message → one agent always replies
- **Language aware**: all three personas speak in the chosen language
  - Arabic personas use Gulf/Saudi youth slang naturally
- Cooldown system prevents the same persona from spamming

---

## Text-to-Speech (TTS)

Every AI chat message is spoken aloud in addition to appearing as text in the chat panel.

- **Who speaks**: only AI agents speak — the three chat personas (Opponent Spymaster, Opponent Operative, Teammate). Human messages are never read aloud.
- **Distinct voices**: each persona has its own assigned voice so they sound clearly different from each other
- **How it works**: when an AI chat message is generated, the server sends the text to an external TTS endpoint, which returns a WAV audio file. The file is served to the browser and plays automatically.
- **Language support**: voices work for both English and Arabic messages; the audio naturally follows whichever language the game is set to
- **Optional**: if no TTS endpoint is configured, the feature disables itself gracefully and chat remains text-only
- **Audio storage**: generated WAV files are saved on the server temporarily. Old files are cleaned up automatically based on a configurable retention period and maximum file count.

---

## Information Flow Between Agents

```
CardCreator → word list → Board Builder → board state

                        ┌─────────────────────────────┐
                        │         Board State          │
                        │  (public view + secret map)  │
                        └────────────┬────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
     AI Spymaster              AI Operative            Chat Agent
   (sees secret map)         (sees public only)    (sees game context)
              │                      │                      │
         gives clue            makes guess           sends message
```

---

## Win and Loss Conditions

| Condition | Result |
|---|---|
| A team reveals ALL their assigned cards | That team wins |
| A team's Operative guesses the **Assassin** card | That team loses instantly |

---

## UI Layout

The game screen has three panels:

- **Left panel — Agent Logs**: shows every AI action with reasoning and reflection, turn by turn. Can be toggled.
- **Center — Game Board**: the card grid, score bar, clue banner, and input controls
- **Right panel — Game Chat**: live messages from AI agent personas; human can also type messages

### Score Bar
- Shows remaining cards for each team
- Displays whose turn it is (team + phase)

### Clue Banner
- Appears during guess phase
- Shows the clue word and number

### Input Controls
- **Spymaster view**: text input for clue word + number picker + submit button; while waiting for operative, shows a waiting spinner
- **Operative view**: remaining guesses counter + end turn button; cards are clickable to guess

---

## Agent Logs Panel

Every AI action is logged with:
- Agent name and team color
- Action type (thinking, clue generated, guess made, retry, etc.)
- Detail (what the clue/guess was)
- Reflection (the agent's stated reasoning for the decision)

---

## Tech Stack (Non-Code Summary)

| Layer | Technology |
|---|---|
| AI Framework | CrewAI |
| Language Model | Google Gemini 2.5 Flash |
| Web Search | Tavily API (Card Creator only) |
| Backend | FastAPI (Python) |
| Frontend | Vanilla HTML / CSS / JavaScript |
| Real-time Updates | WebSocket |
| Package Manager | uv |

---

## Agent Flow Summary

```
Player configures game
        ↓
Card Creator Agent generates words
        ↓
Board is built and assigned (Red/Blue/Neutral/Assassin)
        ↓
Red team starts — Clue Phase
  → If AI Spymaster: analyzes board, produces clue + reflection
  → If Human Spymaster: human types clue and number
        ↓
Guess Phase
  → If AI Operative: receives clue, guesses one word at a time
  → If Human Operative: human clicks cards to guess; can end turn early
        ↓
Chat Agent reacts to events (bad guess, good guess, assassin, etc.)
        ↓
Turn switches to Blue team — same flow repeats
        ↓
Game ends when a team clears all their cards or someone hits the Assassin
```
