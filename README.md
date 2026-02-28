# 🕵️ Codenames — Multi-Agent AI Board Game

## Overview

**Codenames** is a word-association party game for two teams — **Red** vs **Blue**.  
The original game requires 4 players. Since you can't play single-player, this project uses **AI agents** to fill the remaining roles so you can enjoy the full experience solo.

---

## 🎯 Game Rules

1. A board of **word cards** is laid out (15, 25, or 35 cards).
2. Each team has a **Spymaster** (gives clues) and an **Operative / Spy** (guesses words).
3. The Spymaster sees a **secret map** showing which cards belong to which team.
4. The Spymaster gives a **one-word clue** and a **number** (how many cards relate to that clue).
5. The Operative guesses up to **number + 1** words per turn.
6. Guessing the **Assassin card** = **instant loss**.
7. The first team to reveal **all their cards** wins.
8. **Red team always goes first** (and gets +1 card to compensate).

---

## 🃏 Card Modes & Distribution

### 15-Card Mode (Small / Fast)

| Type | Count |
|------|-------|
| 🔴 Starting Team (Red) | **5** |
| 🔵 Other Team (Blue) | **4** |
| ⚪ Neutral | **5** |
| ⚫ Assassin | **1** |
| **Total** | **15** |

### 25-Card Mode (Classic)

| Type | Count |
|------|-------|
| 🔴 Starting Team (Red) | **9** |
| 🔵 Other Team (Blue) | **8** |
| ⚪ Neutral | **7** |
| ⚫ Assassin | **1** |
| **Total** | **25** |

### 35-Card Mode (Large)

| Type | Count |
|------|-------|
| 🔴 Starting Team (Red) | **13** |
| 🔵 Other Team (Blue) | **12** |
| ⚪ Neutral | **9** |
| ⚫ Assassin | **1** |
| **Total** | **35** |

---

## 🎮 What the Player Can Do

- **Choose a team** — Red or Blue
- **Choose a role** — Spymaster (give clues) or Spy/Operative (guess words)
- **Pick a language** — Arabic or English
- **Pick a board size** — 15 (fast), 25 (classic), or 35 (large)
- **Pick a difficulty** — Easy, Medium, or Hard
- **Choose word category** — Random generation, or a specific category (e.g., Saudi football players, European countries, animals, etc.)

---

## 🤖 AI Agents (4 Total)

The game is powered by **four AI agents**:

### 1. Card Creator Agent (Pre-Game)
- Runs **before** the game starts.
- Generates the word cards for the board.
- Accepts parameters:
  - **Language** — Arabic or English
  - **Difficulty** — Easy, Medium, or Hard
    - On harder difficulties, card words are more closely related to each other (trickier to distinguish) and the Assassin word is designed to be deceptively similar to team words.
  - **Category** — Optional specific theme for the words

### 2. Opponent Spymaster Agent
- Acts as the **opposing team's Spymaster**.
- Has full access to the **secret map** (knows all card types).
- Generates clever one-word clues and a number for its Operative.

### 3. Opponent Operative Agent
- Acts as the **opposing team's Operative / Spy**.
- Can only see the **public board** and the clue given by its Spymaster.
- **Strictly isolated** — has no access to the secret map.

### 4. Your Teammate Agent
- Fills the role you **did not** choose.
- If you are the **Spymaster** → this agent is your **Operative** (guesses based on your clues).
- If you are the **Operative** → this agent is your **Spymaster** (gives you clues).

---

## 💬 In-Game Chat

The AI agents have personality — they **comment on the game** in a fun, competitive way:

- Trash talk and encouragement (e.g., *"I will beat you!"*)
- Arabic expressions (e.g., *"كفووو"*, *"يا سلام"*)
- Reactions to good or bad guesses
- Team banter between agents

---

## 📋 Agent Log Panel

A dedicated **log panel** shows what the AI agents are doing behind the scenes:

- **Agent reasoning** — how the Spymaster picks clues, how the Operative decides guesses
- **Reflection pattern** — agents reflect on previous turns to improve strategy
- **Turn-by-turn tracking** — full history of actions and decisions
- **Toggle visibility** — the log panel can be **shown or hidden** at any time

---

## 📝 Requirements Summary

| Requirement | Details |
|-------------|---------|
| Teams | Red vs Blue |
| Roles | Spymaster & Operative per team |
| Board Sizes | 15 / 25 / 35 cards |
| Languages | Arabic, English |
| Difficulty | Easy, Medium, Hard |
| Word Categories | Random or themed (animals, countries, etc.) |
| AI Agents | 4 — Card Creator, Opponent Spymaster, Opponent Operative, Teammate |
| Agent Chat | Fun in-game commentary from agents |
| Agent Logs | Toggleable panel showing agent reasoning, reflection, and tracking |
| Win Condition | First team to reveal all their cards, or opponent guesses the Assassin |
