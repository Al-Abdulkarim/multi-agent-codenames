/* ── Multi-Agent Codenames — Frontend ─────────────────────── */

// ── i18n ────────────────────────────────────────────────────

const i18n = {
  en: {
    title: "🕵️ Codenames",
    subtitle: "Multi-Agent Board Game",
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
    "lbl-log": "🧠 Agent Logs",
    "lbl-chat": "💬 Agent Chat",
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
    "lbl-log": "🧠 سجل الوكلاء",
    "lbl-chat": "💬 محادثة الوكلاء",
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
let chatIdx = 0;  // track which chat messages we've rendered
let logIdx = 0;   // track which log entries we've rendered

// ── DOM refs ────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const $setup = $("#setup-screen");
const $game = $("#game-screen");
const $board = $("#board");
const $btnStart = $("#btn-start");
const $btnStartText = $("#btn-start-text");
const $btnStartLoading = $("#btn-start-loading");
const $clueDisplay = $("#clue-display");
const $clueText = $("#clue-text");
const $actionBar = $("#action-bar");
const $clueForm = $("#clue-form");
const $guessControls = $("#guess-controls");
const $aiThinking = $("#ai-thinking");
const $gameOver = $("#game-over");
const $gameOverTitle = $("#game-over-title");
const $gameOverMsg = $("#game-over-msg");
const $logList = $("#log-list");
const $logPanel = $("#log-panel");
const $chatPanel = $("#chat-panel");
const $chatMessages = $("#chat-messages");
const $btnToggleLog = $("#btn-toggle-log");
const $btnShowLog = $("#btn-show-log");
const $btnShowChat = $("#btn-show-chat");

// ── setup events ────────────────────────────────────────────

$$(".btn-lang").forEach((btn) =>
  btn.addEventListener("click", () => {
    $$(".btn-lang").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    lang = btn.dataset.lang;
    applyLang();
  })
);

$$(".radio-card input").forEach((inp) =>
  inp.addEventListener("change", () => {
    const group = inp.closest(".radio-group");
    group.querySelectorAll(".radio-card").forEach((c) => c.classList.remove("selected"));
    inp.closest(".radio-card").classList.add("selected");
  })
);

// Allow starting without API key (server will use env var)
$btnStart.addEventListener("click", startGame);
$("#btn-clue")?.addEventListener("click", submitClue);
$("#btn-pass")?.addEventListener("click", passTurn);
$("#btn-new-game")?.addEventListener("click", () => location.reload());

// ── panel toggles ───────────────────────────────────────────

$btnToggleLog.addEventListener("click", () => {
  $logPanel.classList.add("collapsed");
  $btnShowLog.classList.remove("hidden");
});

$btnShowLog.addEventListener("click", () => {
  $logPanel.classList.remove("collapsed");
  $btnShowLog.classList.add("hidden");
});

$btnShowChat.addEventListener("click", () => {
  $chatPanel.classList.remove("collapsed");
  $btnShowChat.classList.add("hidden");
});

// ── start game ──────────────────────────────────────────────

async function startGame() {
  $btnStartText.classList.add("hidden");
  $btnStartLoading.classList.remove("hidden");
  $btnStart.disabled = true;

  const body = {
    board_size: parseInt($("#board-size").value),
    difficulty: $("#difficulty").value,
    language: lang,
    category: $("#category").value || null,
    human_team: $('input[name="team"]:checked').value,
    human_role: $('input[name="role"]:checked').value,
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
    chatIdx = 0;
    logIdx = 0;

    $setup.classList.remove("active");
    $game.classList.add("active");

    connectWS();
    render();
    renderChat();
    renderLogs();
    startPolling();

    // Welcome chat message
    addSystemChat(lang === "ar" ? "بدأت اللعبة! حظاً موفقاً 🎮" : "Game started! Good luck 🎮");
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

    switch (msg.event) {
      case "state_update":
        gameState = msg.data;
        render();
        renderChat();
        renderLogs();
        break;

      case "ai_thinking":
        $aiThinking.classList.remove("hidden");
        break;

      case "ai_turn_complete":
        $aiThinking.classList.add("hidden");
        break;

      case "chat_message":
        if (msg.data) appendChatMessage(msg.data);
        break;

      case "agent_log":
        if (msg.data) appendLogEntry(msg.data);
        break;

      case "game_over":
        // handled in render
        break;
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
        renderChat();
        renderLogs();
      }
    } catch { /* ignore */ }
  }, 3000);
}

// ── render game board ───────────────────────────────────────

function render() {
  if (!gameState) return;
  const s = gameState;

  // scores
  $("#red-count").textContent = s.red_remaining;
  $("#blue-count").textContent = s.blue_remaining;

  // turn indicator
  const teamLabel = s.current_team.toUpperCase();
  const phaseLabel = s.current_phase === "clue" ? "Clue" : "Guess";
  $("#turn-indicator").textContent = `${teamLabel} — ${phaseLabel} Phase`;

  // board
  const cols = s.board.length <= 15 ? 5 : s.board.length <= 25 ? 5 : 7;
  $board.className = `board cols-${cols}`;
  $board.innerHTML = "";

  const isSpymaster = s.human_role === "spymaster" && s.current_team === s.human_team;
  const canGuess = !s.game_over && s.whose_turn?.actor === "human" && s.current_phase === "guess" && s.human_role === "operative";

  s.board.forEach((card) => {
    const div = document.createElement("div");
    div.className = "card";
    div.textContent = card.word;

    if (card.revealed && card.card_type) {
      div.classList.add("revealed", card.card_type);
    } else if (isSpymaster && card.card_type) {
      div.classList.add("hint-" + card.card_type);
    }

    if (canGuess && !card.revealed) {
      div.classList.add("clickable");
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

// ── render chat panel ───────────────────────────────────────

function renderChat() {
  if (!gameState?.chat_messages) return;

  const messages = gameState.chat_messages;
  while (chatIdx < messages.length) {
    appendChatMessage(messages[chatIdx]);
    chatIdx++;
  }
}

function appendChatMessage(msg) {
  const div = document.createElement("div");
  const team = msg.team || "system";
  div.className = `chat-msg ${team}-team`;

  const sender = document.createElement("span");
  sender.className = "chat-sender";
  const roleLabel = msg.agent === "spymaster" ? "🎩 Spymaster" : "🕵️ Operative";
  sender.textContent = `${team.toUpperCase()} ${roleLabel}`;

  const text = document.createElement("span");
  text.textContent = msg.message;

  div.appendChild(sender);
  div.appendChild(text);
  $chatMessages.appendChild(div);
  $chatMessages.scrollTop = $chatMessages.scrollHeight;
}

function addSystemChat(text) {
  const div = document.createElement("div");
  div.className = "chat-msg system-msg";
  div.textContent = text;
  $chatMessages.appendChild(div);
  $chatMessages.scrollTop = $chatMessages.scrollHeight;
}

// ── render agent logs panel ─────────────────────────────────

function renderLogs() {
  if (!gameState?.agent_logs) return;

  const logs = gameState.agent_logs;
  while (logIdx < logs.length) {
    appendLogEntry(logs[logIdx]);
    logIdx++;
  }
}

function appendLogEntry(entry) {
  const li = document.createElement("li");

  // Classify for styling
  if (entry.action?.includes("thinking")) li.className = "thinking";
  else if (entry.action?.includes("clue")) li.className = "clue";
  else if (entry.action?.includes("guess") && entry.detail?.includes("correct")) li.className = "guess-correct";
  else if (entry.action?.includes("guess")) li.className = "guess-wrong";

  const agentDiv = document.createElement("div");
  agentDiv.className = "log-agent";
  agentDiv.textContent = entry.agent || "System";

  const actionDiv = document.createElement("div");
  actionDiv.className = "log-action";
  actionDiv.textContent = entry.action || "";

  const detailDiv = document.createElement("div");
  detailDiv.className = "log-detail";
  detailDiv.textContent = entry.detail || "";

  li.appendChild(agentDiv);
  li.appendChild(actionDiv);
  li.appendChild(detailDiv);

  if (entry.reflection) {
    const reflDiv = document.createElement("div");
    reflDiv.className = "log-reflection";
    reflDiv.textContent = `💭 ${entry.reflection}`;
    li.appendChild(reflDiv);
  }

  $logList.prepend(li);
}

// ── actions ─────────────────────────────────────────────────

async function submitClue() {
  const clue = $("#clue-input").value.trim();
  const number = parseInt($("#clue-number").value);
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
    $("#clue-input").value = "";
    addSystemChat(lang === "ar" ? `أعطيت تلميح: "${clue}" لـ ${number}` : `You gave clue: "${clue}" for ${number}`);
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
    addSystemChat(`${icon} ${word} → ${data.revealed}`);
  }
}

async function passTurn() {
  await fetch("/api/game/pass", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: gameId }),
  });
  addSystemChat(lang === "ar" ? "⏭ تم تمرير الدور" : "⏭ Passed turn");
}

// ── init ────────────────────────────────────────────────────

applyLang();
