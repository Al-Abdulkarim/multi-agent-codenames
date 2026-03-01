/* ===================================================
   CODENAMES — Multi-Agent AI Board Game
   Complete JavaScript — API, WebSocket, Game Logic
   =================================================== */

'use strict';

// ─── Configuration ───────────────────────────────────
const API_BASE = '';
const POLL_INTERVAL = 5000;

// ─── State ───────────────────────────────────────────
let gameId = null;
let gameState = null;
let ws = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;
let pollTimer = null;
let guessCount = 0;
let chatAutoScroll = true;
let boardRevealed = false;

// ─── Setup Config ────────────────────────────────────
const config = {
  team: 'red',
  role: 'operative',
  language: 'en',
  board_size: 25,
  difficulty: 'medium',
  category: '',
};

// ─── DOM References (cached on DOMContentLoaded) ─────
let $setupScreen, $gameScreen;
let $setupForm, $startBtn, $startLabel, $startSpinner, $categoryInput;
let $boardArea, $cardGrid, $boardLoading;
let $redRemaining, $blueRemaining, $turnIndicator;
let $clueBanner, $clueWord, $clueNumber, $clueStatus;
let $spymasterInput, $clueWordInput, $clueNumValue, $clueNumDec, $clueNumInc, $giveClueBtn, $spymasterWait;
let $operativeControls, $guessesLeft, $endTurnBtn;
let $logsPanel, $logsList;
let $chatPanel, $chatMessages, $chatInput, $chatSendBtn;
let $gameOverOverlay, $gameOverIcon, $gameOverTitle, $gameOverSubtitle;
let $goRed, $goBlue, $revealBoardBtn, $playAgainBtn, $confettiContainer;
let $toastContainer;

// ─── Initialize ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  cacheDOM();
  bindSetupEvents();
  bindGameEvents();
  showSetupScreen();
});

function cacheDOM() {
  $setupScreen = document.getElementById('setup-screen');
  $gameScreen = document.getElementById('game-screen');
  $setupForm = document.getElementById('setup-form');
  $startBtn = document.getElementById('start-btn');
  $startLabel = $startBtn.querySelector('.start-label');
  $startSpinner = $startBtn.querySelector('.start-spinner');
  $categoryInput = document.getElementById('category-input');

  $boardArea = document.getElementById('board-area');
  $cardGrid = document.getElementById('card-grid');
  $boardLoading = document.getElementById('board-loading');

  $redRemaining = document.getElementById('red-remaining');
  $blueRemaining = document.getElementById('blue-remaining');
  $turnIndicator = document.getElementById('turn-indicator');

  $clueBanner = document.getElementById('clue-banner');
  $clueWord = document.getElementById('clue-word');
  $clueNumber = document.getElementById('clue-number');
  $clueStatus = document.getElementById('clue-status');

  $spymasterInput = document.getElementById('spymaster-input');
  $clueWordInput = document.getElementById('clue-word-input');
  $clueNumValue = document.getElementById('clue-num-value');
  $clueNumDec = document.getElementById('clue-num-dec');
  $clueNumInc = document.getElementById('clue-num-inc');
  $giveClueBtn = document.getElementById('give-clue-btn');
  $spymasterWait = document.getElementById('spymaster-wait');

  $operativeControls = document.getElementById('operative-controls');
  $guessesLeft = document.getElementById('guesses-left');
  $endTurnBtn = document.getElementById('end-turn-btn');

  $logsPanel = document.getElementById('logs-panel');
  $logsList = document.getElementById('logs-list');

  $chatPanel = document.getElementById('chat-panel');
  $chatMessages = document.getElementById('chat-messages');
  $chatInput = document.getElementById('chat-input');
  $chatSendBtn = document.getElementById('chat-send-btn');

  $gameOverOverlay = document.getElementById('game-over-overlay');
  $gameOverIcon = document.getElementById('game-over-icon');
  $gameOverTitle = document.getElementById('game-over-title');
  $gameOverSubtitle = document.getElementById('game-over-subtitle');
  $goRed = document.getElementById('go-red');
  $goBlue = document.getElementById('go-blue');
  $revealBoardBtn = document.getElementById('reveal-board-btn');
  $playAgainBtn = document.getElementById('play-again-btn');
  $confettiContainer = document.getElementById('confetti-container');

  $toastContainer = document.getElementById('toast-container');
}

// ─── Setup Screen ────────────────────────────────────

function showSetupScreen() {
  $setupScreen.classList.add('active');
  $gameScreen.classList.remove('active');
  disconnectWebSocket();
  clearInterval(pollTimer);
  gameId = null;
  gameState = null;
  guessCount = 0;
  boardRevealed = false;
}

function bindSetupEvents() {
  // Team selection
  document.querySelectorAll('.team-card').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.team-card').forEach(b => {
        b.classList.remove('selected');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('selected');
      btn.setAttribute('aria-pressed', 'true');
      config.team = btn.dataset.team;
    });
  });

  // Role selection
  document.querySelectorAll('.role-card').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.role-card').forEach(b => {
        b.classList.remove('selected');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('selected');
      btn.setAttribute('aria-pressed', 'true');
      config.role = btn.dataset.role;
    });
  });

  // Language
  document.querySelectorAll('[data-lang]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-lang]').forEach(b => {
        b.classList.remove('selected');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('selected');
      btn.setAttribute('aria-pressed', 'true');
      config.language = btn.dataset.lang;
    });
  });

  // Board size
  document.querySelectorAll('[data-size]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-size]').forEach(b => {
        b.classList.remove('selected');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('selected');
      btn.setAttribute('aria-pressed', 'true');
      config.board_size = parseInt(btn.dataset.size, 10);
    });
  });

  // Difficulty
  document.querySelectorAll('[data-diff]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-diff]').forEach(b => {
        b.classList.remove('selected');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('selected');
      btn.setAttribute('aria-pressed', 'true');
      config.difficulty = btn.dataset.diff;
    });
  });

  // Submit
  $setupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    config.category = $categoryInput.value.trim();
    await createNewGame(config);
  });
}

// ─── Create New Game ─────────────────────────────────

async function createNewGame(cfg) {
  $startBtn.disabled = true;
  $startLabel.textContent = 'CREATING...';
  $startSpinner.classList.remove('hidden');

  try {
    const res = await fetch(`${API_BASE}/api/game/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        board_size: cfg.board_size,
        language: cfg.language,
        difficulty: cfg.difficulty,
        category: cfg.category,
        team: cfg.team,
        role: cfg.role,
      }),
    });

    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    gameId = data.game_id;
    gameState = data;
    guessCount = 0;

    // RTL support
    if (cfg.language === 'ar') {
      document.body.setAttribute('dir', 'rtl');
    } else {
      document.body.removeAttribute('dir');
    }

    showGameScreen();
    connectWebSocket(gameId);
    startPolling();
    renderFullState(gameState);
  } catch (err) {
    showToast('Failed to create game: ' + err.message, 'error');
  } finally {
    $startBtn.disabled = false;
    $startLabel.textContent = 'START GAME';
    $startSpinner.classList.add('hidden');
  }
}

// ─── Game Screen ─────────────────────────────────────

function showGameScreen() {
  $setupScreen.classList.remove('active');
  $gameScreen.classList.add('active');
  $gameOverOverlay.classList.add('hidden');
  $boardLoading.classList.remove('hidden');
  $cardGrid.innerHTML = '';
}

function bindGameEvents() {
  // End turn
  $endTurnBtn.addEventListener('click', handleEndTurn);

  // Give clue (spymaster)
  $giveClueBtn.addEventListener('click', () => {
    const word = $clueWordInput.value.trim();
    const number = parseInt($clueNumValue.textContent, 10);
    handleGiveClue(word, number);
  });

  // Clue number +/-
  $clueNumDec.addEventListener('click', () => {
    let val = parseInt($clueNumValue.textContent, 10);
    if (val > 1) $clueNumValue.textContent = val - 1;
  });
  $clueNumInc.addEventListener('click', () => {
    let val = parseInt($clueNumValue.textContent, 10);
    const max = gameState ? getTeamRemaining() : 9;
    if (val < max) $clueNumValue.textContent = val + 1;
  });

  // Chat send
  $chatSendBtn.addEventListener('click', () => {
    const text = $chatInput.value.trim();
    if (text) sendChatMessage(text);
  });
  $chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const text = $chatInput.value.trim();
      if (text) sendChatMessage(text);
    }
  });

  // Panel toggles
  document.querySelectorAll('.panel-toggle').forEach(btn => {
    btn.addEventListener('click', () => togglePanel(btn.dataset.panel));
  });
  document.querySelectorAll('.mobile-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const panel = btn.dataset.panel;
      togglePanel(panel);
      btn.classList.toggle('active');
      // Close other
      document.querySelectorAll('.mobile-toggle-btn').forEach(b => {
        if (b !== btn) b.classList.remove('active');
      });
    });
  });

  // Chat auto-scroll detection
  $chatMessages.addEventListener('scroll', () => {
    const el = $chatMessages;
    chatAutoScroll = (el.scrollHeight - el.scrollTop - el.clientHeight) < 40;
  });

  // Game over buttons
  $playAgainBtn.addEventListener('click', () => {
    showSetupScreen();
  });
  $revealBoardBtn.addEventListener('click', () => {
    boardRevealed = true;
    if (gameState) renderBoard(gameState);
    $revealBoardBtn.disabled = true;
    $revealBoardBtn.textContent = 'Board Revealed';
  });
}

function togglePanel(panelId) {
  const panel = panelId === 'logs' ? $logsPanel : $chatPanel;
  const isSmall = window.innerWidth <= 1200;

  if (isSmall) {
    // Mobile: toggle open class
    const isOpen = panel.classList.contains('open');
    // Close all panels first
    document.querySelectorAll('.side-panel').forEach(p => p.classList.remove('open'));
    if (!isOpen) panel.classList.add('open');
  } else {
    panel.classList.toggle('collapsed');
  }
}

// ─── Render Full State ───────────────────────────────

function renderFullState(state) {
  $boardLoading.classList.add('hidden');
  updateScores(state);
  updateTurnIndicator(state);
  updateClue(state);
  renderBoard(state);
  renderControls(state);
  renderChat(state.chat_messages || []);
  renderLogs(state.agent_logs || []);

  if (state.status !== 'playing') {
    showGameOver(state);
  }
}

// ─── Scores ──────────────────────────────────────────

function updateScores(state) {
  const oldRed = $redRemaining.textContent;
  const oldBlue = $blueRemaining.textContent;

  $redRemaining.textContent = state.red_remaining;
  $blueRemaining.textContent = state.blue_remaining;

  if (oldRed !== '' + state.red_remaining) {
    $redRemaining.classList.remove('score-bounce');
    void $redRemaining.offsetWidth; // force reflow
    $redRemaining.classList.add('score-bounce');
  }
  if (oldBlue !== '' + state.blue_remaining) {
    $blueRemaining.classList.remove('score-bounce');
    void $blueRemaining.offsetWidth;
    $blueRemaining.classList.add('score-bounce');
  }
}

// ─── Turn Indicator ──────────────────────────────────

function updateTurnIndicator(state) {
  $turnIndicator.className = 'turn-indicator';
  if (state.current_turn === 'red') {
    $turnIndicator.textContent = "RED TEAM'S TURN";
    $turnIndicator.classList.add('red-turn');
  } else {
    $turnIndicator.textContent = "BLUE TEAM'S TURN";
    $turnIndicator.classList.add('blue-turn');
  }
}

// ─── Clue Display ────────────────────────────────────

function updateClue(state) {
  const clue = state.clue;
  const isMyTurn = state.current_turn === config.team;
  const isOperative = config.role === 'operative';
  const isSpymaster = config.role === 'spymaster';

  $clueBanner.classList.add('hidden');
  $clueStatus.classList.add('hidden');

  if (clue && clue.word) {
    $clueBanner.classList.remove('hidden');
    $clueWord.textContent = clue.word;
    $clueNumber.textContent = clue.number;
  } else if (isMyTurn && isOperative) {
    $clueStatus.classList.remove('hidden');
    $clueStatus.innerHTML = '<span class="wait-spinner" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:8px;"></span> Spymaster is thinking...';
  } else if (!isMyTurn) {
    $clueStatus.classList.remove('hidden');
    $clueStatus.textContent = "\u23F3 Opponent's turn...";
  }
}

// ─── Board Rendering ─────────────────────────────────

function renderBoard(state) {
  $cardGrid.innerHTML = '';
  const board = state.board || [];
  const cols = board.length <= 15 ? 5 : (board.length <= 25 ? 5 : 7);

  $cardGrid.className = 'card-grid';
  $cardGrid.classList.add(`grid-${cols}`);

  const isSpymaster = config.role === 'spymaster';
  const isMyTurn = state.current_turn === config.team;
  const hasClue = state.clue && state.clue.word;
  const canGuess = config.role === 'operative' && isMyTurn && hasClue && state.status === 'playing';

  board.forEach((card, index) => {
    const el = document.createElement('div');
    el.className = 'board-card';
    el.setAttribute('role', 'gridcell');

    const inner = document.createElement('div');
    inner.className = 'card-inner';

    const wordEl = document.createElement('span');
    wordEl.className = 'card-word';
    wordEl.textContent = card.word;

    if (card.revealed || boardRevealed) {
      inner.classList.add('revealed', `type-${card.type}`);
      if (card.type === 'assassin') {
        const skull = document.createElement('span');
        skull.className = 'card-skull';
        skull.textContent = '\u2620\uFE0F';
        inner.appendChild(skull);
      }
    } else {
      inner.classList.add('unrevealed');

      // Spymaster sees all card types
      if (isSpymaster) {
        inner.classList.add(`spy-${card.type}`);
        if (card.type === 'assassin') {
          const skull = document.createElement('span');
          skull.className = 'card-skull';
          skull.textContent = '\u2620\uFE0F';
          inner.appendChild(skull);
        }
      }

      // Operative can click
      if (canGuess && !isSpymaster) {
        inner.classList.add('clickable');
        el.addEventListener('click', () => handleCardClick(card.word, el));
      } else if (!isSpymaster) {
        inner.classList.add('disabled');
      } else {
        // Spymaster can never click
        inner.classList.add('disabled');
      }
    }

    inner.appendChild(wordEl);
    el.appendChild(inner);
    $cardGrid.appendChild(el);
  });
}

// ─── Controls ────────────────────────────────────────

function renderControls(state) {
  const isMyTurn = state.current_turn === config.team;
  const isSpymaster = config.role === 'spymaster';
  const hasClue = state.clue && state.clue.word;

  // Hide all controls first
  $spymasterInput.classList.add('hidden');
  $operativeControls.classList.add('hidden');

  if (state.status !== 'playing') return;

  if (isSpymaster) {
    $spymasterInput.classList.remove('hidden');
    if (isMyTurn && !hasClue) {
      // Show clue form
      $giveClueBtn.closest('.clue-form').style.display = 'flex';
      $spymasterWait.classList.add('hidden');
    } else if (isMyTurn && hasClue) {
      // Waiting for operative to guess
      $giveClueBtn.closest('.clue-form').style.display = 'none';
      $spymasterWait.classList.remove('hidden');
    } else {
      // Not your turn
      $giveClueBtn.closest('.clue-form').style.display = 'none';
      $spymasterWait.classList.add('hidden');
    }
  } else {
    // Operative
    if (isMyTurn && hasClue) {
      $operativeControls.classList.remove('hidden');
      const clueNum = state.clue.number || 0;
      const maxGuesses = clueNum + 1;
      const left = maxGuesses - guessCount;
      $guessesLeft.textContent = `Guesses left: ${left > 0 ? left : 0}`;
      $endTurnBtn.disabled = guessCount === 0;
    }
  }
}

function getTeamRemaining() {
  if (!gameState) return 9;
  return config.team === 'red' ? gameState.red_remaining : gameState.blue_remaining;
}

// ─── Card Click (Operative) ──────────────────────────

async function handleCardClick(word, cardEl) {
  const inner = cardEl.querySelector('.card-inner');
  if (!inner.classList.contains('clickable')) return;

  // Disable further clicks temporarily
  inner.classList.remove('clickable');
  inner.classList.add('disabled');

  // Start flip animation
  inner.classList.add('flipping');

  try {
    const res = await fetch(`${API_BASE}/api/game/${gameId}/guess`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word }),
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    gameState = data;
    guessCount++;

    // Find the guessed card to see its type
    const guessedCard = data.board.find(c => c.word === word);
    if (guessedCard && guessedCard.type === 'assassin') {
      document.body.classList.add('assassin-flash');
      setTimeout(() => document.body.classList.remove('assassin-flash'), 500);
    }

    // Wait for flip animation to complete then re-render
    setTimeout(() => {
      renderFullState(gameState);
    }, 300);
  } catch (err) {
    showToast('Failed to submit guess: ' + err.message, 'error');
    inner.classList.remove('flipping');
    inner.classList.add('clickable');
    inner.classList.remove('disabled');
  }
}

// ─── Give Clue (Spymaster) ───────────────────────────

async function handleGiveClue(word, number) {
  if (!word) {
    showToast('Please enter a clue word', 'error');
    return;
  }
  if (word.includes(' ')) {
    showToast('Clue must be a single word (no spaces)', 'error');
    return;
  }

  $giveClueBtn.disabled = true;
  const spinner = $giveClueBtn.querySelector('.btn-spinner');
  spinner.classList.remove('hidden');

  try {
    const res = await fetch(`${API_BASE}/api/game/${gameId}/clue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word, number }),
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    gameState = data;
    $clueWordInput.value = '';
    $clueNumValue.textContent = '1';
    renderFullState(data);
  } catch (err) {
    showToast('Failed to give clue: ' + err.message, 'error');
  } finally {
    $giveClueBtn.disabled = false;
    spinner.classList.add('hidden');
  }
}

// ─── End Turn ────────────────────────────────────────

async function handleEndTurn() {
  $endTurnBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/game/${gameId}/end_turn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    gameState = data;
    guessCount = 0;
    renderFullState(data);
  } catch (err) {
    showToast('Failed to end turn: ' + err.message, 'error');
    $endTurnBtn.disabled = false;
  }
}

// ─── Chat ────────────────────────────────────────────

function renderChat(messages) {
  if (!messages || messages.length === 0) {
    $chatMessages.innerHTML = '<div class="empty-state">No messages yet...</div>';
    return;
  }

  $chatMessages.innerHTML = '';
  messages.forEach(msg => appendChatBubble(msg));
  scrollChatIfNeeded();
}

function appendChatBubble(msg) {
  // Remove empty state
  const empty = $chatMessages.querySelector('.empty-state');
  if (empty) empty.remove();

  const div = document.createElement('div');
  const isRed = msg.team === 'red';
  const isHuman = msg.sender === 'You' || msg.sender === 'Human';

  div.className = `chat-msg ${isRed ? 'red-msg' : 'blue-msg'} ${isHuman ? 'human-msg' : ''}`;

  const sender = document.createElement('span');
  sender.className = 'chat-sender';
  sender.textContent = msg.sender || 'Agent';

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = msg.message;

  const time = document.createElement('span');
  time.className = 'chat-time';
  time.textContent = formatTime(msg.timestamp);

  div.appendChild(sender);
  div.appendChild(bubble);
  div.appendChild(time);
  $chatMessages.appendChild(div);
}

function addChatMessage(msg) {
  appendChatBubble(msg);
  scrollChatIfNeeded();
}

function scrollChatIfNeeded() {
  if (chatAutoScroll) {
    $chatMessages.scrollTop = $chatMessages.scrollHeight;
  }
}

async function sendChatMessage(text) {
  $chatInput.value = '';

  // Show immediately as local message
  addChatMessage({
    sender: 'You',
    team: config.team,
    message: text,
    timestamp: new Date().toISOString(),
  });

  try {
    await fetch(`${API_BASE}/api/game/${gameId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
  } catch (err) {
    showToast('Failed to send message', 'error');
  }
}

// ─── Logs ────────────────────────────────────────────

function renderLogs(logs) {
  if (!logs || logs.length === 0) {
    $logsList.innerHTML = '<div class="empty-state">No agent activity yet...</div>';
    return;
  }

  $logsList.innerHTML = '';
  // Show newest first
  const reversed = [...logs].reverse();
  reversed.forEach(log => appendLogEntry(log));
}

function appendLogEntry(log) {
  // Remove empty state
  const empty = $logsList.querySelector('.empty-state');
  if (empty) empty.remove();

  const div = document.createElement('div');
  const team = (log.agent || '').toLowerCase().includes('red') ? 'red' : 'blue';
  div.className = `log-entry ${team}-log`;

  // Agent name
  const agentEl = document.createElement('div');
  agentEl.className = 'log-agent';
  agentEl.innerHTML = `<span class="log-dot ${team}"></span> ${escapeHTML(log.agent || 'Agent')}`;

  // Badge
  const action = (log.action || 'info').toLowerCase();
  let badgeClass = '';
  let badgeText = action.replace(/_/g, ' ').toUpperCase();
  if (action.includes('think') || action.includes('generat')) badgeClass = 'thinking';
  else if (action.includes('clue')) badgeClass = 'clue';
  else if (action.includes('guess')) badgeClass = 'guess';
  else if (action.includes('reflect')) badgeClass = 'reflection';

  const badge = document.createElement('span');
  badge.className = `log-badge ${badgeClass}`;
  badge.textContent = badgeText;
  agentEl.appendChild(badge);

  div.appendChild(agentEl);

  // Detail
  if (log.detail) {
    const detail = document.createElement('div');
    detail.className = 'log-detail';
    detail.textContent = log.detail;
    div.appendChild(detail);
  }

  // Reflection
  if (log.reflection) {
    const refl = document.createElement('div');
    refl.className = 'log-reflection';
    refl.textContent = '\uD83D\uDCA1 ' + log.reflection;
    div.appendChild(refl);
  }

  // Time
  const time = document.createElement('div');
  time.className = 'log-time';
  time.textContent = formatTime(log.timestamp);
  div.appendChild(time);

  $logsList.prepend(div);
}

function addLogEntry(log) {
  appendLogEntry(log);
}

// ─── WebSocket ───────────────────────────────────────

function connectWebSocket(id) {
  disconnectWebSocket();

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/${id}`;

  try {
    ws = new WebSocket(wsUrl);
  } catch (err) {
    console.warn('WebSocket connection failed:', err);
    return;
  }

  ws.onopen = () => {
    wsReconnectAttempts = 0;
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleWebSocketMessage(msg);
    } catch (err) {
      console.warn('Bad WS message:', err);
    }
  };

  ws.onclose = () => {
    ws = null;
    if (gameId) reconnectWebSocket(id);
  };

  ws.onerror = () => {
    // Will trigger onclose
  };
}

function handleWebSocketMessage(msg) {
  switch (msg.type) {
    case 'state_update':
      gameState = msg.data;
      // Reset guess count on turn change
      if (msg.data.current_turn !== config.team) {
        guessCount = 0;
      }
      renderFullState(msg.data);
      break;

    case 'chat_message':
      addChatMessage(msg.data);
      break;

    case 'agent_log':
      addLogEntry(msg.data);
      break;
  }
}

function disconnectWebSocket() {
  if (ws) {
    ws.onclose = null;
    ws.close();
    ws = null;
  }
  clearTimeout(wsReconnectTimer);
}

function reconnectWebSocket(id) {
  wsReconnectAttempts++;
  const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000);
  wsReconnectTimer = setTimeout(() => {
    if (gameId === id) connectWebSocket(id);
  }, delay);
}

// ─── Polling Fallback ────────────────────────────────

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (!gameId) return;
    try {
      const res = await fetch(`${API_BASE}/api/game/${gameId}/state`);
      if (!res.ok) return;
      const data = await res.json();
      gameState = data;
      renderFullState(data);
    } catch (err) {
      // Silent fail — WebSocket is primary
    }
  }, POLL_INTERVAL);
}

// ─── Game Over ───────────────────────────────────────

function showGameOver(state) {
  $gameOverOverlay.classList.remove('hidden');
  boardRevealed = false;
  $revealBoardBtn.disabled = false;
  $revealBoardBtn.textContent = 'Reveal Board';

  $goRed.textContent = state.red_remaining;
  $goBlue.textContent = state.blue_remaining;

  const status = (state.status || '').toLowerCase();

  if (status.includes('assassin') || status.includes('lost')) {
    // Assassin hit
    const loser = status.includes('red') ? 'Red' : (status.includes('blue') ? 'Blue' : 'A team');
    $gameOverIcon.textContent = '\uD83D\uDC80';
    $gameOverTitle.textContent = 'GAME OVER';
    $gameOverTitle.className = 'game-over-title assassin-end';
    $gameOverSubtitle.textContent = `${loser} hit the Assassin!`;
    document.body.classList.add('assassin-flash');
    setTimeout(() => document.body.classList.remove('assassin-flash'), 600);
  } else if (status.includes('red_win') || status.includes('red win')) {
    $gameOverIcon.textContent = '\uD83C\uDF89';
    $gameOverTitle.textContent = 'RED WINS!';
    $gameOverTitle.className = 'game-over-title red-win';
    $gameOverSubtitle.textContent = 'Red team found all their agents!';
    showConfetti();
  } else if (status.includes('blue_win') || status.includes('blue win')) {
    $gameOverIcon.textContent = '\uD83C\uDF89';
    $gameOverTitle.textContent = 'BLUE WINS!';
    $gameOverTitle.className = 'game-over-title blue-win';
    $gameOverSubtitle.textContent = 'Blue team found all their agents!';
    showConfetti();
  } else {
    // Generic win
    $gameOverIcon.textContent = '\uD83C\uDF89';
    $gameOverTitle.textContent = 'GAME OVER';
    $gameOverTitle.className = 'game-over-title';
    $gameOverSubtitle.textContent = state.status;
    showConfetti();
  }
}

function showConfetti() {
  $confettiContainer.classList.remove('hidden');
  $confettiContainer.innerHTML = '';

  const colors = ['#c0392b', '#2980b9', '#f39c12', '#27ae60', '#9b59b6', '#e74c3c', '#3498db'];
  for (let i = 0; i < 60; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    piece.style.left = Math.random() * 100 + '%';
    piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDuration = (Math.random() * 2 + 2) + 's';
    piece.style.animationDelay = (Math.random() * 1.5) + 's';
    piece.style.width = (Math.random() * 8 + 6) + 'px';
    piece.style.height = (Math.random() * 8 + 6) + 'px';
    piece.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
    $confettiContainer.appendChild(piece);
  }

  // Clean up after animation
  setTimeout(() => {
    $confettiContainer.classList.add('hidden');
    $confettiContainer.innerHTML = '';
  }, 5000);
}

// ─── Toast Notifications ─────────────────────────────

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  $toastContainer.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) toast.remove();
  }, 5000);
}

// ─── Helpers ─────────────────────────────────────────

function formatTime(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '';
  }
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
