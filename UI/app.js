/* ===================================================
   CODENAMES — Multi-Agent AI Board Game
   Complete JavaScript — API, WebSocket, Game Logic
   =================================================== */

'use strict';

// ─── Configuration ───────────────────────────────────
const API_BASE = '';
const POLL_INTERVAL = 5000;

// ─── Sounds ──────────────────────────────────────────
const sounds = {
  // Short UI Click for card flips
  flip: new Audio('https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3'),
  // Short Success Chime for winning
  win: new Audio('https://assets.mixkit.co/active_storage/sfx/2019/2019-preview.mp3'),
  // Subtle error blub
  error: new Audio('https://assets.mixkit.co/active_storage/sfx/2573/2573-preview.mp3')
};

function playSound(name) {
  if (sounds[name]) {
    sounds[name].currentTime = 0;
    sounds[name].play().catch(e => console.log('Sound blocked:', e));
  }
}

// ─── State ───────────────────────────────────────────
let gameId = null;
let gameState = null;
let ws = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;
let pollTimer = null;
let isPollingPaused = false;
let guessCount = 0;
let lastClueWord = null;
let chatAutoScroll = true;
let logAutoScroll = true;
let boardRevealed = false;
let renderedChatCount = 0;
let renderedLogsCount = 0;

// ─── Setup Config ────────────────────────────────────
const config = {
  team: 'red',
  role: 'operative',
  language: 'en',
  board_size: 25,
  difficulty: 'medium',
  category: '',
};

// ─── Translations ────────────────────────────────────
const TRANSLATIONS = {
  en: {
    game_title: "CODENAMES",
    game_subtitle: "Multi-Agent AI Board Game",
    choose_team: "Choose Your Team",
    red_team: "RED TEAM",
    blue_team: "BLUE TEAM",
    choose_role: "Choose Your Role",
    role_operative: "OPERATIVE",
    desc_operative: "Guess words",
    role_spymaster: "SPYMASTER",
    desc_spymaster: "Give clues",
    language: "Language",
    lang_en: "English",
    lang_ar: "العربية",
    board_size: "Board Size",
    size_15: "15",
    size_25: "25",
    size_35: "35",
    hint_fast: "Fast",
    hint_classic: "Classic",
    hint_large: "Large",
    difficulty: "Difficulty",
    diff_easy: "Easy",
    diff_medium: "Medium",
    diff_hard: "Hard",
    category: "Category",
    optional: "(optional)",
    category_placeholder: "Leave empty for random, or type: animals, countries, sports...",
    start_game: "START GAME",
    creating: "CREATING...",
    red_remaining_text: "Red: {n} remaining",
    blue_remaining_text: "Blue: {n} remaining",
    turn_red: "RED TEAM'S TURN",
    turn_blue: "BLUE TEAM'S TURN",
    waiting: "WAITING...",
    clue_label: "CLUE:",
    spymaster_thinking: "Spymaster is thinking...",
    opponent_turn: "Opponent's turn...",
    end_turn: "End Turn",
    guesses_left: "Guesses left: {n}",
    give_clue: "Give Clue",
    agent_logs: "Agent Logs",
    game_chat: "Game Chat",
    no_activity: "No agent activity yet...",
    no_messages: "No messages yet...",
    type_message: "Type a message...",
    clue_word_placeholder: "Enter your clue word",
    wait_operative: "Waiting for your operative to guess...",
    reveal_board: "Reveal Board",
    play_again: "New Game",
    board_revealed: "Board Revealed",
    victory: "VICTORY! 🎉",
    defeat: "DEFEAT 💔",
    game_over: "GAME OVER",
    new_game: "🔄 New Game",
    quick_restart: "⚡ Quick Restart",
    you: "You",
    thinking: "Thinking",
    clue: "Clue",
    guess: "Guess",
    reflection: "Reflection"
  },
  ar: {
    game_title: "CODENAMES",
    game_subtitle: "لعبة ذكاء اصطناعي متعددة العملاء",
    choose_team: "اختر فريقك",
    red_team: "الفريق الأحمر",
    blue_team: "الفريق الأزرق",
    choose_role: "اختر دورك",
    role_operative: "عميل ميداني",
    desc_operative: "خمّن الكلمات",
    role_spymaster: "رئيس المخابرات",
    desc_spymaster: "أعطِ تلميحات",
    language: "اللغة",
    lang_en: "English",
    lang_ar: "العربية",
    board_size: "حجم اللوحة",
    size_15: "15",
    size_25: "25",
    size_35: "35",
    hint_fast: "سريع",
    hint_classic: "كلاسيك",
    hint_large: "كبير",
    difficulty: "المستوى",
    diff_easy: "سهل",
    diff_medium: "متوسط",
    diff_hard: "صعب",
    category: "الفئة",
    optional: "(اختياري)",
    category_placeholder: "اتركه فارغاً للعشوائية، أو اكتب: حيوانات، دول، رياضة...",
    start_game: "ابدأ اللعبة",
    creating: "جاري الإنشاء...",
    red_remaining_text: "الأحمر متبقي: {n}",
    blue_remaining_text: "الأزرق متبقي: {n}",
    turn_red: "دور الفريق الأحمر",
    turn_blue: "دور الفريق الأزرق",
    waiting: "انتظار...",
    clue_label: "التلميح:",
    spymaster_thinking: "رئيس المخابرات يفكر...",
    opponent_turn: "دور الخصم...",
    end_turn: "إنهاء الدور",
    guesses_left: "التخمينات المتبقية: {n}",
    give_clue: "إرسال التلميح",
    agent_logs: "سجل العملاء",
    game_chat: "دردشة اللعبة",
    no_activity: "لا يوجد نشاط بعد...",
    no_messages: "لا توجد رسائل بعد...",
    type_message: "اكتب رسالة...",
    clue_word_placeholder: "أدخل كلمة التلميح",
    wait_operative: "بانتظار عميلك الميداني للتخمين...",
    reveal_board: "كشف الأوراق",
    play_again: "لعبة جديدة",
    board_revealed: "الأوراق مكشوفة",
    victory: "مبروك! فوز مستحق! 🎉",
    defeat: "للأسف! خسارة! 💔",
    game_over: "انتهت اللعبة",
    new_game: "🔄 لعبة جديدة",
    quick_restart: "⚡ إعادة سريعة",
    you: "أنت",
    thinking: "يفكر",
    clue: "تلميح",
    guess: "تخمين",
    reflection: "تأمل"
  }
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
let $postGameActions, $headerNewGameBtn, $headerQuickRestartBtn;
let $toastContainer;

// ─── Localization Logic ──────────────────────────────

function localizeUI(lang) {
  const dict = TRANSLATIONS[lang] || TRANSLATIONS.en;

  // Update elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });

  // Update placeholders
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    if (dict[key]) {
      el.placeholder = dict[key];
    }
  });

  // RTL support - Using class to avoid flipping entire flexbox layout
  if (lang === 'ar') {
    document.body.classList.add('lang-ar');
    document.body.removeAttribute('dir');
  } else {
    document.body.classList.remove('lang-ar');
    document.body.removeAttribute('dir');
  }
}

// ─── Initialize ──────────────────────────────────────
function init() {
  cacheDOM();
  bindSetupEvents();
  bindGameEvents();
  showSetupScreen();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

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

  $postGameActions = document.getElementById('post-game-actions');
  $headerNewGameBtn = document.getElementById('header-new-game-btn');
  $headerQuickRestartBtn = document.getElementById('header-quick-restart-btn');

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
  renderedChatCount = 0;
  renderedLogsCount = 0;
  $chatMessages.innerHTML = `<div class="empty-state">${TRANSLATIONS[config.language]?.no_messages || 'No messages yet...'}</div>`;
  $logsList.innerHTML = `<div class="empty-state">${TRANSLATIONS[config.language]?.no_activity || 'No agent activity yet...'}</div>`;
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

      // Immediate localization
      localizeUI(config.language);
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
  const dict = TRANSLATIONS[cfg.language] || TRANSLATIONS.en;
  $startLabel.textContent = dict.creating || 'CREATING...';
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

    if (!res.ok) {
      let errTxt = await res.text();
      try {
        const errJson = JSON.parse(errTxt);
        errTxt = errJson.detail || errJson.error || errTxt;
      } catch (e) { } // Ignore
      throw new Error(errTxt);
    }
    const data = await res.json();
    gameId = data.game_id;
    gameState = data;
    guessCount = 0;

    // Localization
    localizeUI(cfg.language);

    showGameScreen();
    connectWebSocket(gameId);
    startPolling();
    renderFullState(gameState);
  } catch (err) {
    showToast('Failed to create game: ' + err.message, 'error');
  } finally {
    $startBtn.disabled = false;
    const dict = TRANSLATIONS[cfg.language] || TRANSLATIONS.en;
    $startLabel.textContent = dict.start_game || 'START GAME';
    $startSpinner.classList.add('hidden');
  }
}

// ─── Game Screen ─────────────────────────────────────

function showGameScreen() {
  $setupScreen.classList.remove('active');
  $gameScreen.classList.add('active');
  $gameOverOverlay.classList.add('hidden');
  $postGameActions.classList.add('hidden');
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
    $gameOverOverlay.classList.add('hidden');
    $postGameActions.classList.remove('hidden');
    boardRevealed = true;
    renderBoard(gameState);
  });
  $headerNewGameBtn.addEventListener('click', showSetupScreen);
  $headerQuickRestartBtn.addEventListener('click', handleQuickRestart);
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

  if (chatAutoScroll) scrollChatIfNeeded();
  if (logAutoScroll) scrollLogsIfNeeded();

  if (state.status !== 'playing') {
    showGameOver(state);
  }
}

// ─── Scores ──────────────────────────────────────────

function updateScores(state) {
  const oldRed = $redRemaining.textContent;
  const oldBlue = $blueRemaining.textContent;

  const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
  $redRemaining.textContent = dict.red_remaining_text ? dict.red_remaining_text.replace('{n}', state.red_remaining) : state.red_remaining;
  $blueRemaining.textContent = dict.blue_remaining_text ? dict.blue_remaining_text.replace('{n}', state.blue_remaining) : state.blue_remaining;

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
  const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
  if (state.current_turn === 'red') {
    $turnIndicator.textContent = dict.turn_red || "RED TEAM'S TURN";
    $turnIndicator.classList.add('red-turn');
  } else {
    $turnIndicator.textContent = dict.turn_blue || "BLUE TEAM'S TURN";
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

  const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;

  if (clue && clue.word) {
    $clueBanner.classList.remove('hidden');
    $clueWord.textContent = clue.word;
    $clueNumber.textContent = clue.number;
  } else if (isMyTurn && isOperative) {
    $clueStatus.classList.remove('hidden');
    const waitingMsg = dict.spymaster_thinking || 'Spymaster is thinking...';
    $clueStatus.innerHTML = `<span class="wait-spinner" style="display:inline-block;width:16px;height:16px;vertical-align:middle;margin-right:8px;"></span> ${waitingMsg}`;
  } else if (!isMyTurn) {
    $clueStatus.classList.remove('hidden');
    $clueStatus.textContent = dict.opponent_turn || "\u23F3 Opponent's turn...";
  }
}

// ─── Board Rendering ─────────────────────────────────

function renderBoard(state) {
  const board = state.board || [];
  const cols = board.length <= 15 ? 5 : (board.length <= 25 ? 5 : 7);

  $cardGrid.className = 'card-grid';
  $cardGrid.classList.add(`grid-${cols}`);

  const isSpymaster = config.role === 'spymaster';
  const isMyTurn = state.current_turn === config.team;
  const hasClue = state.clue && state.clue.word;
  const canGuess = config.role === 'operative' && isMyTurn && hasClue && state.status === 'playing';

  // If grid is empty or size changed, rebuild
  if ($cardGrid.children.length !== board.length) {
    $cardGrid.innerHTML = '';
    board.forEach((card, index) => {
      const el = document.createElement('div');
      el.className = 'board-card';
      el.dataset.index = index;
      const inner = document.createElement('div');
      inner.className = 'card-inner';
      const wordEl = document.createElement('span');
      wordEl.className = 'card-word';
      inner.appendChild(wordEl);
      el.appendChild(inner);
      $cardGrid.appendChild(el);
    });
  }

  // Update existing elements (Anti-flicker)
  const cardEls = $cardGrid.querySelectorAll('.board-card');
  board.forEach((card, index) => {
    const el = cardEls[index];
    const inner = el.querySelector('.card-inner');
    const wordEl = el.querySelector('.card-word');

    // Only update text if needed
    if (wordEl.textContent !== card.word) wordEl.textContent = card.word;

    // Build classes
    let classes = ['card-inner'];
    if (card.revealed || boardRevealed) {
      classes.push('revealed', `type-${card.type}`);
      // Remove spinner if revealed
      const spinner = el.querySelector('.guess-spinner');
      if (spinner) spinner.remove();
    } else {
      classes.push('unrevealed');
      if (isSpymaster) {
        classes.push(`spy-${card.type}`, 'spymaster-view');
      }
      if (canGuess && !isSpymaster) {
        classes.push('clickable');
        // Add listener only once
        if (!el._hasListener) {
          el.addEventListener('click', () => handleCardClick(card.word, el));
          el._hasListener = true;
        }
      } else {
        classes.push('disabled');
      }
    }

    const newClassName = classes.join(' ');
    if (inner.className !== newClassName) inner.className = newClassName;

    // Special icons
    if ((card.revealed || boardRevealed || isSpymaster) && card.type === 'assassin') {
      if (!inner.querySelector('.card-skull')) {
        const skull = document.createElement('span');
        skull.className = 'card-skull';
        skull.textContent = '\u2620\uFE0F';
        inner.appendChild(skull);
      }
    }
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
      const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
      $guessesLeft.textContent = dict.guesses_left ? dict.guesses_left.replace('{n}', left > 0 ? left : 0) : `Guesses left: ${left > 0 ? left : 0}`;
      $endTurnBtn.disabled = guessCount === 0;
    }
  }
}

function getTeamRemaining() {
  if (!gameState) return 9;
  return config.team === 'red' ? gameState.red_remaining : gameState.blue_remaining;
}

async function handleQuickRestart() {
  if (!config.team) return;

  $headerQuickRestartBtn.disabled = true;
  const originalText = $headerQuickRestartBtn.textContent;
  $headerQuickRestartBtn.textContent = (config.language === 'ar' ? 'جاري البدء...' : 'Restarting...');

  try {
    const res = await fetch(`${API_BASE}/api/game/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        board_size: config.board_size,
        language: config.language,
        difficulty: config.difficulty,
        category: config.category,
        team: config.team,
        role: config.role
      })
    });

    if (!res.ok) throw new Error('Server error');
    const data = await res.json();
    gameId = data.game_id;
    gameState = data;

    // Reset state
    boardRevealed = false;
    isPollingPaused = false;
    guessCount = 0;
    lastClueWord = null;

    $postGameActions.classList.add('hidden');
    $gameOverOverlay.classList.add('hidden');

    showGameScreen();
    connectWebSocket(gameId);
    startPolling();
    renderFullState(data);
    showToast((config.language === 'ar' ? 'بدأت لعبة جديدة!' : 'New game started!'), 'info');
  } catch (err) {
    showToast('Failed to restart: ' + err.message, 'error');
  } finally {
    $headerQuickRestartBtn.disabled = false;
    $headerQuickRestartBtn.textContent = originalText;
  }
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
    playSound('flip');

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
      body: JSON.stringify({ clue: word, number }),
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
    const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
    showToast((dict.error_end_turn || 'Failed to end turn') + ': ' + err.message, 'error');
    $endTurnBtn.disabled = false;
  }
}

// ─── Chat ────────────────────────────────────────────

function renderChat(messages) {
  if (!messages || messages.length === 0) {
    if (renderedChatCount === 0) {
      const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
      $chatMessages.innerHTML = `<div class="empty-state">${dict.no_messages || 'No messages yet...'}</div>`;
    }
    return;
  }

  // Only render new messages
  const newMessages = messages.slice(renderedChatCount);
  if (newMessages.length > 0) {
    renderedChatCount += newMessages.length;
    newMessages.forEach(msg => appendChatBubble(msg));
    scrollChatIfNeeded();
  }
}

function appendChatBubble(msg) {
  // Remove empty state
  const empty = $chatMessages.querySelector('.empty-state');
  if (empty) empty.remove();

  const div = document.createElement('div');
  const isRed = msg.team === 'red';
  const isHuman = msg.sender === 'You' || msg.sender === 'Human';
  const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;

  div.className = `chat-msg ${isRed ? 'red-msg' : 'blue-msg'} ${isHuman ? 'human-msg' : ''}`;

  const sender = document.createElement('span');
  sender.className = 'chat-sender';
  let senderName = msg.sender || 'Agent';
  if (isHuman && dict.you) senderName = dict.you;
  sender.textContent = senderName;

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
  if (chatAutoScroll && $chatMessages) {
    $chatMessages.scrollTop = $chatMessages.scrollHeight;
  }
}

function scrollLogsIfNeeded() {
  if (logAutoScroll && $logsList) {
    $logsList.scrollTop = $logsList.scrollHeight;
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
    const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
    showToast(dict.error_send || 'Failed to send message', 'error');
  }
}

// ─── Logs ────────────────────────────────────────────

function renderLogs(logs) {
  if (!logs || logs.length === 0) {
    if (renderedLogsCount === 0) {
      const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
      $logsList.innerHTML = `<div class="empty-state">${dict.no_activity || 'No agent activity yet...'}</div>`;
    }
    return;
  }

  // Only render new logs
  const newLogs = logs.slice(renderedLogsCount);
  if (newLogs.length > 0) {
    renderedLogsCount += newLogs.length;
    newLogs.forEach(log => appendLogEntry(log));
    scrollLogsIfNeeded();
  }
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
  const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
  let badgeClass = '';
  let badgeKey = action.includes('think') ? 'thinking' :
    (action.includes('clue') ? 'clue' :
      (action.includes('guess') ? 'guess' :
        (action.includes('reflect') ? 'reflection' : '')));

  let badgeText = dict[badgeKey] ? dict[badgeKey].toUpperCase() : action.replace(/_/g, ' ').toUpperCase();

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

  $logsList.appendChild(div);
}

function addLogEntry(log) {
  renderedLogsCount++;
  appendLogEntry(log);
  if (logAutoScroll) scrollLogsIfNeeded();
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
  switch (msg.type || msg.event) {
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
  // Polling disabled to prevent UI refresh flicker/AI thinking spam
}

// ─── Game Over ───────────────────────────────────────

function showGameOver(state) {
  // If user already clicked "Reveal Board", don't show the overlay again
  if (boardRevealed) return;

  $gameOverOverlay.classList.remove('hidden');
  $revealBoardBtn.disabled = false;

  const dict = TRANSLATIONS[config.language] || TRANSLATIONS.en;
  $revealBoardBtn.textContent = dict.reveal_board || 'Reveal Board';
  $playAgainBtn.textContent = dict.play_again || 'New Game';

  $goRed.textContent = state.red_remaining;
  $goBlue.textContent = state.blue_remaining;

  const humanTeam = config.team;
  const winner = state.winner;

  // Determine if human won
  const didHumanWin = winner === humanTeam;

  // Check if assassin was hit (look at the board for revealed assassin)
  const assassinHit = state.board && state.board.some(c => c.type === 'assassin' && c.revealed);

  if (assassinHit) {
    // Assassin ending
    $gameOverIcon.textContent = '\uD83D\uDC80';
    $gameOverTitle.className = 'game-over-title assassin-end';

    if (didHumanWin) {
      // Opponent hit the assassin — human wins
      if (config.language === 'ar') {
        $gameOverTitle.textContent = 'مبروك! فوز مستحق! 🎉';
        $gameOverSubtitle.textContent = 'الخصم أصاب بطاقة الاغتيال! أنت الفائز!';
      } else {
        $gameOverTitle.textContent = 'VICTORY! 🎉';
        $gameOverSubtitle.textContent = 'The opponent hit the Assassin! You win!';
      }
      playSound('win');
      showConfetti();
    } else {
      // Human's team hit the assassin — human loses
      if (config.language === 'ar') {
        $gameOverTitle.textContent = 'انتهت اللعبة 💀';
        $gameOverSubtitle.textContent = 'فريقك أصاب بطاقة الاغتيال! خسارة!';
      } else {
        $gameOverTitle.textContent = 'GAME OVER 💀';
        $gameOverSubtitle.textContent = 'Your team hit the Assassin! You lose!';
      }
      document.body.classList.add('assassin-flash');
      setTimeout(() => document.body.classList.remove('assassin-flash'), 600);
    }
  } else {
    // Normal win/loss (all cards revealed)
    if (didHumanWin) {
      $gameOverIcon.textContent = '\uD83C\uDF89';
      $gameOverTitle.className = 'game-over-title human-win pulse';
      if (config.language === 'ar') {
        $gameOverTitle.textContent = 'مبروك! فوز مستحق! 🎉';
        $gameOverSubtitle.textContent = 'فريقك كشف جميع العملاء بنجاح!';
      } else {
        $gameOverTitle.textContent = 'VICTORY! 🎉';
        $gameOverSubtitle.textContent = 'Your team found all their agents!';
      }
      playSound('win');
      showConfetti();
    } else {
      $gameOverIcon.textContent = '\uD83D\uDE1E';
      $gameOverTitle.className = 'game-over-title human-loss';
      if (config.language === 'ar') {
        $gameOverTitle.textContent = 'للأسف! خسارة! 💔';
        $gameOverSubtitle.textContent = 'الخصم كشف جميع عملائه أولاً!';
      } else {
        $gameOverTitle.textContent = 'DEFEAT 💔';
        $gameOverSubtitle.textContent = 'The opponent found all their agents first.';
      }
    }
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
