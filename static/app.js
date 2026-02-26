/**
 * Codenames Arabic - Frontend Application
 * تطبيق واجهة المستخدم للعبة الأسماء الحركية العربية
 */

// ============= State =============
let gameState = null;
let gameId = null;
let selectedSettings = {
    boardSize: 25,
    difficulty: 'medium',
    humanTeam: 'red',
    humanRole: 'operative',
    apiKey: '',
};
let socket = null;
let isSubmitting = false;  // منع الضغط المزدوج
let renderDebounceTimer = null;

const API_BASE = '';

// ============= Initialization =============

document.addEventListener('DOMContentLoaded', () => {
    initOptionCards();
    createToastContainer();
});

function initOptionCards() {
    // Board size options
    document.querySelectorAll('#board-size-options .option-card').forEach(card => {
        card.addEventListener('click', () => {
            selectOption('board-size-options', card);
            selectedSettings.boardSize = parseInt(card.dataset.value);
        });
    });

    // Difficulty options
    document.querySelectorAll('#difficulty-options .option-card').forEach(card => {
        card.addEventListener('click', () => {
            selectOption('difficulty-options', card);
            selectedSettings.difficulty = card.dataset.value;
        });
    });

    // Role options
    document.querySelectorAll('#role-options .option-card').forEach(card => {
        card.addEventListener('click', () => {
            selectOption('role-options', card);
            selectedSettings.humanRole = card.dataset.value;
        });
    });

    // Team options
    document.querySelectorAll('#team-options .option-card').forEach(card => {
        card.addEventListener('click', () => {
            selectOption('team-options', card);
            selectedSettings.humanTeam = card.dataset.value;
        });
    });
}

function selectOption(groupId, selectedCard) {
    document.querySelectorAll(`#${groupId} .option-card`).forEach(c => {
        c.classList.remove('selected');
    });
    selectedCard.classList.add('selected');
}

// ============= Toast Notifications =============

function createToastContainer() {
    if (!document.querySelector('.toast-container')) {
        const container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
}

function showToast(message, type = 'info') {
    const container = document.querySelector('.toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ============= Screen Management =============

function showSetup() {
    document.getElementById('setup-screen').classList.add('active');
    document.getElementById('game-screen').classList.remove('active');
    document.getElementById('game-over-overlay').style.display = 'none';
    gameState = null;
    gameId = null;
}

function showGame() {
    document.getElementById('setup-screen').classList.remove('active');
    document.getElementById('game-screen').classList.add('active');
}

// ============= API Calls =============

async function apiCall(endpoint, method = 'GET', body = null, timeoutMs = 60000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
            signal: controller.signal,
        };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(`${API_BASE}${endpoint}`, options);
        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'خطأ في الاتصال' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('انتهت مهلة الاتصال (60 ثانية) - يرجى المحاولة مجدداً');
        }
        console.error('API Error:', error);
        throw error;
    }
}

// ============= Game Actions =============

async function startGame() {
    const apiKey = document.getElementById('api-key-input').value.trim();
    if (!apiKey) {
        showToast('يرجى إدخال مفتاح Google API', 'error');
        return;
    }

    selectedSettings.apiKey = apiKey;

    const btn = document.getElementById('start-game-btn');
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = 'جاري التحميل...';

    showLoading('جاري تهيئة اللعبة...');

    try {
        const data = await apiCall('/api/game/new', 'POST', {
            board_size: selectedSettings.boardSize,
            difficulty: selectedSettings.difficulty,
            human_team: selectedSettings.humanTeam,
            human_role: selectedSettings.humanRole,
            api_key: selectedSettings.apiKey,
        });

        gameState = data;
        gameId = data.game_id;

        showGame();
        renderGame();
        showToast('بدأت اللعبة! حظاً سعيداً 🎮', 'success');
    } catch (error) {
        showToast(`خطأ: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').textContent = 'ابدأ اللعبة';
        hideLoading();
        if (gameId) {
            setupWebSocket(gameId);
        }
    }
}

async function submitClue() {
    if (isSubmitting) return;
    const clueWord = document.getElementById('clue-input').value.trim();
    const clueNumber = parseInt(document.getElementById('clue-number-input').value);

    if (!clueWord) {
        showToast('يرجى كتابة الشفرة', 'error');
        return;
    }

    isSubmitting = true;
    showAIThinking('الذكاء الاصطناعي يعالج الشفرة...');

    try {
        const data = await apiCall('/api/game/clue', 'POST', {
            game_id: gameId,
            clue: clueWord,
            number: clueNumber,
        });

        gameState = data;
        document.getElementById('clue-input').value = '';
        renderGame();
        showToast('تم إرسال الشفرة ✅', 'success');
    } catch (error) {
        showToast(`خطأ: ${error.message}`, 'error');
    } finally {
        isSubmitting = false;
        hideAIThinking();
    }
}

async function submitGuess(word) {
    if (isSubmitting) return;
    if (!gameState || gameState.game_over) return;
    if (gameState.current_phase !== 'guess') return;

    // Check if it's the human's turn to guess
    const isHumanTeam = gameState.current_team === selectedSettings.humanTeam;
    if (!isHumanTeam || selectedSettings.humanRole !== 'operative') return;

    isSubmitting = true;

    try {
        const data = await apiCall('/api/game/guess', 'POST', {
            game_id: gameId,
            word: word,
        });

        gameState = data;

        // Show guess result
        if (data.last_guess) {
            const { correct, card_type } = data.last_guess;
            const typeAr = {
                'red': 'أحمر 🔴',
                'blue': 'أزرق 🔵',
                'neutral': 'محايد ⚪',
                'assassin': 'قاتل ☠️'
            }[card_type] || card_type;

            if (correct) {
                showToast(`✅ صحيح! "${word}" - ${typeAr}`, 'success');
            } else {
                showToast(`❌ خطأ! "${word}" - ${typeAr}`, 'error');
            }
        }

        renderGame();

        // إذا انتهى دور الإنسان، أوضح أن الـ AI يعمل
        if (gameState && !gameState.game_over &&
            (gameState.current_team !== selectedSettings.humanTeam ||
                gameState.current_phase === 'clue' && selectedSettings.humanRole !== 'spymaster')) {
            showAIThinking('الذكاء الاصطناعي يفكر...');
        }
    } catch (error) {
        showToast(`خطأ: ${error.message}`, 'error');
    } finally {
        isSubmitting = false;
    }
}

async function passTurn() {
    if (!gameId || isSubmitting) return;

    isSubmitting = true;
    showAIThinking('جاري تمرير الدور...');

    try {
        const data = await apiCall('/api/game/pass', 'POST', { game_id: gameId });
        gameState = data;
        renderGame();
        showToast('تم تمرير الدور ⏭️');
    } catch (error) {
        showToast(`خطأ: ${error.message}`, 'error');
    } finally {
        isSubmitting = false;
        hideAIThinking();
    }
}

// ============= Rendering =============

function renderGame() {
    if (!gameState) return;

    renderHeader();
    renderBoard();
    renderClue();
    renderActions();
    renderThinkingLog();
    renderEventLog();
    renderClueHistory();

    // Always check game over, but the function will handle the delay
    checkGameOver();
}

function renderHeader() {
    // Scores
    document.getElementById('red-remaining').textContent = gameState.red_remaining;
    document.getElementById('blue-remaining').textContent = gameState.blue_remaining;

    // Turn indicator
    const indicator = document.getElementById('turn-indicator');
    const teamDisplay = document.getElementById('current-team-display');
    const phaseDisplay = document.getElementById('current-phase-display');

    indicator.className = `turn-indicator team-${gameState.current_team}`;
    teamDisplay.textContent = gameState.current_team === 'red' ? 'الأحمر' : 'الأزرق';

    const phaseLabels = {
        'clue': '📝 الشفرة',
        'guess': '🎯 التخمين',
        'game_over': '🏁 انتهت',
    };
    phaseDisplay.textContent = phaseLabels[gameState.current_phase] || gameState.current_phase;
}

function renderBoard() {
    const boardEl = document.getElementById('game-board');
    const size = gameState.board_size;

    // Set grid class
    boardEl.className = `game-board size-${size}`;
    boardEl.innerHTML = '';

    const isSpymaster = selectedSettings.humanRole === 'spymaster';
    const isHumanGuessTurn = (
        gameState.current_team === selectedSettings.humanTeam &&
        gameState.current_phase === 'guess' &&
        selectedSettings.humanRole === 'operative'
    );

    gameState.board.forEach((card, index) => {
        const cardEl = document.createElement('div');
        cardEl.className = 'card';
        cardEl.setAttribute('id', `card-${index}`);

        if (card.revealed) {
            cardEl.classList.add('revealed', `type-${card.card_type}`);

            // Add "Correct" mark on game over for ALL revealed (guessed) cards
            if (gameState.game_over) {
                const marker = document.createElement('span');
                marker.className = 'card-status-marker correct';
                marker.textContent = '✅';
                cardEl.appendChild(marker);
            }
        } else {
            // Game Over: show all types but NO markers (requested by user)
            if (gameState.game_over) {
                cardEl.classList.add(`spy-${card.card_type}`);
            } else if (isSpymaster && card.card_type) {
                // Spymaster sees card types
                cardEl.classList.add(`spy-${card.card_type}`);

                // Add type dot
                const dot = document.createElement('span');
                dot.className = `card-type-dot dot-${card.card_type}`;
                cardEl.appendChild(dot);
            }

            // Clickable for operative during guess phase
            if (isHumanGuessTurn && !gameState.game_over) {
                cardEl.addEventListener('click', () => submitGuess(card.word));
                cardEl.style.cursor = 'pointer';
            } else {
                cardEl.classList.add('disabled');
            }
        }

        const wordEl = document.createElement('span');
        wordEl.className = 'card-word';
        wordEl.textContent = card.word;
        cardEl.appendChild(wordEl);

        boardEl.appendChild(cardEl);
    });
}

function renderClue() {
    const clueDisplay = document.getElementById('clue-display');

    if (gameState.current_clue) {
        clueDisplay.style.display = 'flex';
        document.getElementById('clue-word').textContent = gameState.current_clue.word;
        document.getElementById('clue-number').textContent = gameState.current_clue.number;
        document.getElementById('guesses-remaining').textContent =
            `تخمينات متبقية: ${gameState.guesses_remaining}`;
    } else {
        clueDisplay.style.display = 'none';
    }
}

function renderActions() {
    const clueForm = document.getElementById('clue-form');
    const passBtn = document.getElementById('pass-btn');

    const isHumanTeam = gameState.current_team === selectedSettings.humanTeam;

    // Show clue form for human spymaster
    if (isHumanTeam &&
        gameState.current_phase === 'clue' &&
        selectedSettings.humanRole === 'spymaster') {
        clueForm.style.display = 'flex';
    } else {
        clueForm.style.display = 'none';
    }

    // Show pass button for human operative during guess phase
    if (isHumanTeam &&
        gameState.current_phase === 'guess' &&
        selectedSettings.humanRole === 'operative') {
        passBtn.style.display = 'inline-flex';
    } else {
        passBtn.style.display = 'none';
    }
}

function renderThinkingLog() {
    const logEl = document.getElementById('thinking-log');
    const steps = gameState.thinking_log || [];

    if (steps.length === 0) {
        logEl.innerHTML = '<div class="thinking-empty">ستظهر هنا عمليات تفكير الوكلاء...</div>';
        return;
    }

    logEl.innerHTML = '';

    steps.forEach(step => {
        const stepEl = document.createElement('div');
        const teamClass = step.team ? `team-${step.team}` : '';
        stepEl.className = `thinking-step type-${step.step_type} ${teamClass}`;

        const typeLabels = {
            'reflection': 'تأمل',
            'react': 'تنفيذ',
            'planning': 'تخطيط',
        };

        stepEl.innerHTML = `
            <div class="thinking-step-header">
                <span class="thinking-agent-name">${escapeHtml(step.agent_name)}</span>
                <span class="thinking-type-badge badge-${step.step_type}">
                    ${typeLabels[step.step_type] || step.step_type}
                </span>
            </div>
            <div class="thinking-content">${escapeHtml(step.content)}</div>
        `;

        logEl.appendChild(stepEl);
    });

    // Auto-scroll to bottom
    logEl.scrollTop = logEl.scrollHeight;
}

function renderClueHistory() {
    const historyEl = document.getElementById('clue-history-list');
    const history = gameState.clue_history || [];

    if (history.length === 0) {
        historyEl.innerHTML = '<div class="history-empty">لا توجد شفرات سابقة</div>';
        return;
    }

    historyEl.innerHTML = '';

    // Sort reverse to show newest first
    const sortedHistory = [...history].reverse();

    sortedHistory.forEach(item => {
        const itemEl = document.createElement('div');
        itemEl.className = `history-item team-${item.team}`;

        const guessesHtml = item.guesses.map(g =>
            `<span class="history-guess ${g.correct ? 'correct' : 'wrong'}">${escapeHtml(g.word)}</span>`
        ).join(' ');

        itemEl.innerHTML = `
            <div class="history-header">
                <span class="history-team-dot"></span>
                <span class="history-turn">الدور ${item.turn}</span>
            </div>
            <div class="history-clue">
                <strong>${escapeHtml(item.word)}</strong> - ${item.number}
            </div>
            <div class="history-guesses">
                ${guessesHtml || '<span class="history-no-guesses">لا توجد تخمينات</span>'}
            </div>
        `;
        historyEl.appendChild(itemEl);
    });
}

function renderEventLog() {
    const logEl = document.getElementById('event-log');
    const events = gameState.event_log || [];

    logEl.innerHTML = '';

    events.forEach(event => {
        const eventEl = document.createElement('div');
        eventEl.className = `event-item type-${event.type}`;
        eventEl.textContent = event.message;
        logEl.appendChild(eventEl);
    });

    logEl.scrollTop = logEl.scrollHeight;
}

function checkGameOver() {
    if (!gameState.game_over) {
        document.getElementById('game-over-overlay').style.display = 'none';
        return;
    }

    // Show board first, then delay overlay
    setTimeout(() => {
        // Double check if still game over and not reset
        if (!gameState || !gameState.game_over) return;

        const overlay = document.getElementById('game-over-overlay');
        const icon = document.getElementById('game-over-icon');
        const title = document.getElementById('game-over-title');
        const reason = document.getElementById('game-over-reason');
        const stats = document.getElementById('game-over-stats');

        const isWinner = gameState.winner === selectedSettings.humanTeam;

        icon.textContent = isWinner ? '🏆' : '😔';
        title.textContent = isWinner ? '🎉 فزت! مبروك!' : '😞 خسرت! حظاً أفضل';
        title.style.color = isWinner ? 'var(--accent-gold)' : 'var(--red-primary)';
        reason.textContent = gameState.game_over_reason;

        stats.innerHTML = `
            <div>
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--red-primary);">${gameState.red_remaining}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">أحمر متبقي</div>
            </div>
            <div>
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--blue-primary);">${gameState.blue_remaining}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">أزرق متبقي</div>
            </div>
            <div>
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--text-primary);">${gameState.turn_number}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">عدد الأدوار</div>
            </div>
        `;

        overlay.style.display = 'flex';
    }, 2000); // 2 second delay to review board
}

function closeGameOver() {
    document.getElementById('game-over-overlay').style.display = 'none';
}

// ============= UI Helpers =============

// ============= Non-blocking AI indicator =============

function showAIThinking(text = 'الذكاء الاصطناعي يفكر...') {
    let indicator = document.getElementById('ai-thinking-bar');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'ai-thinking-bar';
        indicator.innerHTML = `
            <div class="ai-bar-spinner"></div>
            <span id="ai-bar-text">${text}</span>
        `;
        document.body.appendChild(indicator);
    }
    document.getElementById('ai-bar-text').textContent = text;
    indicator.style.display = 'flex';
}

function hideAIThinking() {
    const indicator = document.getElementById('ai-thinking-bar');
    if (indicator) indicator.style.display = 'none';
}

// إبقاء الدوال القديمة للتوافق
function showLoading(text = 'جاري التحميل...') {
    showAIThinking(text);
}

function hideLoading() {
    hideAIThinking();
}

function toggleThinkingPanel() {
    const panel = document.getElementById('thinking-panel');
    panel.classList.toggle('collapsed');
    panel.classList.toggle('open');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============= Keyboard Shortcuts =============

document.addEventListener('keydown', (e) => {
    // Enter to submit clue
    if (e.key === 'Enter' && document.getElementById('clue-form').style.display !== 'none') {
        e.preventDefault();
        submitClue();
    }

    // Escape to pass turn
    if (e.key === 'Escape' && document.getElementById('pass-btn').style.display !== 'none') {
        passTurn();
    }
});
function setupWebSocket(id) {
    if (socket) {
        socket.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${id}`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log('Connected to WebSocket for game:', id);
        // Start polling as a safety backup
        startPolling();
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.error) {
            console.error('WS Error:', data.error);
            showToast(data.error, 'error');
            return;
        }

        gameState = data;
        hideAIThinking();
        isSubmitting = false;

        if (renderDebounceTimer) clearTimeout(renderDebounceTimer);
        renderDebounceTimer = setTimeout(() => {
            renderGame();
        }, 150);
    };

    socket.onclose = () => {
        console.log('WebSocket disconnected');
    };

    socket.onerror = (error) => {
        console.error('WebSocket Error:', error);
    };
}

// ============= Smart Polling (backup when AI is working) =============
let pollingInterval = null;

function startPolling() {
    if (pollingInterval) return;
    pollingInterval = setInterval(async () => {
        if (!gameId || !gameState) return;
        if (gameState.game_over) { stopPolling(); return; }

        try {
            const data = await fetch(`/api/game/${gameId}/status`).then(r => r.json());
            if (!data || !data.game_id) return;

            const changed = JSON.stringify(data.board) !== JSON.stringify(gameState.board)
                || data.current_phase !== gameState.current_phase
                || data.current_team !== gameState.current_team
                || data.game_over !== gameState.game_over;

            if (changed) {
                gameState = data;
                hideAIThinking();
                isSubmitting = false;
                if (renderDebounceTimer) clearTimeout(renderDebounceTimer);
                renderDebounceTimer = setTimeout(() => renderGame(), 150);
            }

            // وصل دور البشري أو انتهت اللعبة → أوقف الـ polling
            const isMyTurn = (
                data.current_team === selectedSettings.humanTeam && (
                    (data.current_phase === 'clue' && selectedSettings.humanRole === 'spymaster') ||
                    (data.current_phase === 'guess' && selectedSettings.humanRole === 'operative')
                )
            );
            if (isMyTurn || data.game_over) {
                stopPolling();
                hideAIThinking();
                isSubmitting = false;
            }
        } catch (e) { /* تجاهل أخطاء الـ polling */ }
    }, 3000);
}

function stopPolling() {
    if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
}

