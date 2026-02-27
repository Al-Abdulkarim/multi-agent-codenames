/* ── Multi-Agent Codenames — Frontend ─────────────────────── */

// ── i18n ────────────────────────────────────────────────────

const i18n = {
  en: {
    title: "🕵️ Codenames",
    subtitle: "Multi-Agent Board Game",
    "lbl-api": "API Key",
    "lbl-size": "Board Size",
    "lbl-diff": "Difficulty",
    "lbl-cat": "Category",
    "lbl-team": "Team",
    "lbl-role": "Role",
    "lbl-red": "Red",
    "lbl-blue": "Blue",
    "lbl-spy": "Spymaster",
    "lbl-op": "Operative",
    "btn-start-text": "Start Game",
    "lbl-log": "Game Log",
    catPlaceholder: "e.g. Saudi football players, animals …",
    turnClue: "{team} — Clue Phase",
    turnGuess: "{team} — Guess Phase",
    winTitle: "🎉 You Win!",
    loseTitle: "💀 You Lose",
    winMsg: "Congratulations! Your team found all the words.",
    loseMsg: "Better luck next time.",
    aiThinking: "AI is thinking …",
  },
  ar: {
    title: "🕵️ كلمات سرية",
    subtitle: "لعبة لوح متعددة الوكلاء",
    "lbl-api": "مفتاح API",
    "lbl-size": "حجم اللوحة",
    "lbl-diff": "الصعوبة",
    "lbl-cat": "الفئة",
    "lbl-team": "الفريق",
    "lbl-role": "الدور",
    "lbl-red": "أحمر",
    "lbl-blue": "أزرق",
    "lbl-spy": "رئيس الجواسيس",
    "lbl-op": "العميل",
    "btn-start-text": "ابدأ اللعبة",
    "lbl-log": "سجل اللعبة",
    catPlaceholder: "مثال: لاعبي كرة قدم سعوديين، حيوانات …",
    turnClue: "{team} — مرحلة التلميح",
    turnGuess: "{team} — مرحلة التخمين",
    winTitle: "🎉 فزت!",
    loseTitle: "💀 خسرت",
    winMsg: "مبروك! فريقك وجد جميع الكلمات.",
    loseMsg: "حظ أوفر المرة القادمة.",
    aiThinking: "الذكاء الاصطناعي يفكر …",
  },
};

let lang = "en";

function t(key) {
  return (i18n[lang] || i18n.en)[key] || key;
}

function applyLang() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  document.body.dir = lang === "ar" ? "rtl" : "ltr";

  for (const [id, text] of Object.entries(i18n[lang])) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
  const catEl = document.getElementById("category");
  if (catEl) catEl.placeholder = t("catPlaceholder");
}

// ── state ───────────────────────────────────────────────────

let gameId = null;
let gameState = null;
let ws = null;
let pollTimer = null;

// ── DOM refs ────────────────────────────────────────────────

const $setup = document.getElementById("setup-screen");
const $game = document.getElementById("game-screen");
const $board = document.getElementById("board");
const $btnStart = document.getElementById("btn-start");
const $btnStartText = document.getElementById("btn-start-text");
const $btnStartLoading = document.getElementById("btn-start-loading");
const $clueDisplay = document.getElementById("clue-display");
const $clueText = document.getElementById("clue-text");
const $actionBar = document.getElementById("action-bar");
const $clueForm = document.getElementById("clue-form");
const $guessControls = document.getElementById("guess-controls");
const $aiThinking = document.getElementById("ai-thinking");
const $gameOver = document.getElementById("game-over");
const $gameOverTitle = document.getElementById("game-over-title");
const $gameOverMsg = document.getElementById("game-over-msg");
const $logList = document.getElementById("log-list");

// ── setup events ────────────────────────────────────────────

document.querySelectorAll(".btn-lang").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".btn-lang").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    lang = btn.dataset.lang;
    applyLang();
  })
);

document.querySelectorAll('.radio-card input').forEach((inp) =>
  inp.addEventListener("change", () => {
    const group = inp.closest(".radio-group");
    group.querySelectorAll(".radio-card").forEach((c) => c.classList.remove("selected"));
    inp.closest(".radio-card").classList.add("selected");
  })
);

document.getElementById("api-key").addEventListener("input", () => {
  $btnStart.disabled = !document.getElementById("api-key").value.trim();
});

$btnStart.addEventListener("click", startGame);
document.getElementById("btn-clue")?.addEventListener("click", submitClue);
document.getElementById("btn-pass")?.addEventListener("click", passTurn);
document.getElementById("btn-new-game")?.addEventListener("click", () => location.reload());

// ── start game ──────────────────────────────────────────────

async function startGame() {
  $btnStartText.classList.add("hidden");
  $btnStartLoading.classList.remove("hidden");
  $btnStart.disabled = true;

  const body = {
    board_size: parseInt(document.getElementById("board-size").value),
    difficulty: document.getElementById("difficulty").value,
    language: lang,
    category: document.getElementById("category").value || null,
    human_team: document.querySelector('input[name="team"]:checked').value,
    human_role: document.querySelector('input[name="role"]:checked').value,
    api_key: document.getElementById("api-key").value.trim(),
  };

  try {
    const res = await fetch("/api/game/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.error) {
      alert(data.error);
      return;
    }

    gameId = data.game_id;
    gameState = data;

    $setup.classList.remove("active");
    $game.classList.add("active");

    connectWS();
    render();
    startPolling();
  } catch (e) {
    alert("Failed to start game: " + e.message);
  } finally {
    $btnStartText.classList.remove("hidden");
    $btnStartLoading.classList.add("hidden");
    $btnStart.disabled = false;
  }
}

// ── WebSocket ───────────────────────────────────────────────

function connectWS() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws/${gameId}`);
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.event === "state_update") {
      gameState = msg.data;
      render();
    } else if (msg.event === "ai_thinking") {
      $aiThinking.classList.remove("hidden");
    } else if (msg.event === "ai_turn_complete") {
      $aiThinking.classList.add("hidden");
      logEvent(`AI: ${msg.data.clue?.word} for ${msg.data.clue?.number}`);
    } else if (msg.event === "game_over") {
      // handled in render
    }
  };
  ws.onclose = () => { ws = null; };
}

// ── polling fallback ────────────────────────────────────────

function startPolling() {
  pollTimer = setInterval(async () => {
    if (!gameId) return;
    try {
      const res = await fetch(`/api/game/${gameId}/state`);
      const data = await res.json();
      if (!data.error) {
        gameState = data;
        render();
      }
    } catch { /* ignore */ }
  }, 3000);
}

// ── render ──────────────────────────────────────────────────

function render() {
  if (!gameState) return;
  const s = gameState;

  // scores
  document.getElementById("red-count").textContent = s.red_remaining;
  document.getElementById("blue-count").textContent = s.blue_remaining;

  // turn indicator
  const teamLabel = s.current_team.toUpperCase();
  const phaseLabel = s.current_phase === "clue" ? "Clue" : "Guess";
  document.getElementById("turn-indicator").textContent = `${teamLabel} — ${phaseLabel} Phase`;

  // board
  const cols = s.board.length <= 15 ? 5 : s.board.length <= 25 ? 5 : 7;
  $board.className = `board cols-${cols}`;
  $board.innerHTML = "";

  const isSpymaster = s.human_role === "spymaster" && s.current_team === s.human_team;

  s.board.forEach((card) => {
    const div = document.createElement("div");
    div.className = "card";
    div.textContent = card.word;

    if (card.revealed && card.card_type) {
      div.classList.add("revealed", card.card_type);
    } else if (isSpymaster && card.card_type) {
      div.classList.add("hint-" + card.card_type);
    }

    // click to guess
    if (
      !card.revealed &&
      s.whose_turn?.actor === "human" &&
      s.current_phase === "guess" &&
      s.human_role === "operative"
    ) {
      div.addEventListener("click", () => submitGuess(card.word));
    }

    $board.appendChild(div);
  });

  // clue display
  if (s.current_phase === "guess" && s.turns_history.length > 0) {
    const lastTurn = s.turns_history[s.turns_history.length - 1];
    $clueText.textContent = `"${lastTurn.clue.word}" for ${lastTurn.clue.number}  (${s.guesses_remaining} left)`;
    $clueDisplay.classList.remove("hidden");
  } else {
    $clueDisplay.classList.add("hidden");
  }

  // action bar
  if (s.whose_turn?.actor === "human" && !s.game_over) {
    $actionBar.classList.remove("hidden");
    if (s.current_phase === "clue" && s.human_role === "spymaster") {
      $clueForm.classList.remove("hidden");
      $guessControls.classList.add("hidden");
    } else if (s.current_phase === "guess" && s.human_role === "operative") {
      $clueForm.classList.add("hidden");
      $guessControls.classList.remove("hidden");
    } else {
      $actionBar.classList.add("hidden");
    }
  } else {
    $actionBar.classList.add("hidden");
  }

  // AI thinking
  if (s.whose_turn?.actor === "ai" && !s.game_over) {
    $aiThinking.classList.remove("hidden");
  } else {
    $aiThinking.classList.add("hidden");
  }

  // game over
  if (s.game_over) {
    $gameOver.classList.remove("hidden");
    const won = s.winner === s.human_team;
    $gameOverTitle.textContent = won ? t("winTitle") : t("loseTitle");
    $gameOverMsg.textContent = won ? t("winMsg") : t("loseMsg");
    clearInterval(pollTimer);
  }
}

// ── actions ─────────────────────────────────────────────────

async function submitClue() {
  const clue = document.getElementById("clue-input").value.trim();
  const number = parseInt(document.getElementById("clue-number").value);
  if (!clue) return;

  const res = await fetch("/api/game/clue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: gameId, clue, number }),
  });
  const data = await res.json();
  if (data.error) {
    alert(data.error);
  } else {
    document.getElementById("clue-input").value = "";
    logEvent(`You: "${clue}" for ${number}`);
  }
}

async function submitGuess(word) {
  const res = await fetch("/api/game/guess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: gameId, word }),
  });
  const data = await res.json();
  if (data.error) {
    alert(data.error);
  } else {
    const icon = data.correct ? "✅" : "❌";
    logEvent(`${icon} ${word} → ${data.revealed}`);
  }
}

async function passTurn() {
  await fetch("/api/game/pass", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: gameId }),
  });
  logEvent("⏭ Passed turn");
}

function logEvent(text) {
  const li = document.createElement("li");
  li.textContent = text;
  $logList.prepend(li);
}

// ── init ────────────────────────────────────────────────────

applyLang();
