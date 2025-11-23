const setupScreen = document.getElementById('setup-screen');
const gameScreen = document.getElementById('game-screen');
const numPlayersInput = document.getElementById('num-players');
const startBtn = document.getElementById('start-btn');
const dealerCardsDiv = document.getElementById('dealer-cards');
const dealerScoreDiv = document.getElementById('dealer-score');
const playersArea = document.getElementById('players-area');
const controlsArea = document.getElementById('controls-area');
const hitBtn = document.getElementById('hit-btn');
const standBtn = document.getElementById('stand-btn');
const splitBtn = document.getElementById('split-btn');
const gameMessage = document.getElementById('game-message');
const endGameControls = document.getElementById('end-game-controls');
const nextRoundBtn = document.getElementById('next-round-btn');
const newGameBtn = document.getElementById('new-game-btn');

let gameState = null;

startBtn.addEventListener('click', startGame);
hitBtn.addEventListener('click', () => sendAction('hit'));
standBtn.addEventListener('click', () => sendAction('stand'));
splitBtn.addEventListener('click', () => sendAction('split'));

nextRoundBtn.addEventListener('click', async () => {
    const response = await fetch('/next_round', { method: 'POST' });
    gameState = await response.json();
    renderGame();
});

newGameBtn.addEventListener('click', () => {
    gameScreen.classList.add('hidden');
    setupScreen.classList.remove('hidden');
    gameMessage.classList.add('hidden');
    endGameControls.classList.add('hidden');
});

async function startGame() {
    const numPlayers = parseInt(numPlayersInput.value);
    const response = await fetch('/start_game', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ num_players: numPlayers })
    });
    gameState = await response.json();
    setupScreen.classList.add('hidden');
    gameScreen.classList.remove('hidden');
    renderGame();
}

async function sendAction(action) {
    if (!gameState) return;

    // Find active player and hand
    const player = gameState.players[gameState.current_player_index];

    const response = await fetch('/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: action,
            player_id: player.id
        })
    });
    const result = await response.json();
    if (result.success) {
        gameState = result.state;
        renderGame();
    }
}

function renderGame() {
    if (!gameState) return;

    // Render Dealer
    renderHand(gameState.dealer_hand, dealerCardsDiv, dealerScoreDiv, true);

    // Render Players
    playersArea.innerHTML = '';
    gameState.players.forEach((player, index) => {
        const playerBox = document.createElement('div');
        playerBox.className = `player-box ${index === gameState.current_player_index && !gameState.game_over ? 'active' : ''}`;

        const title = document.createElement('h3');
        title.innerText = `Player ${player.id}`;
        playerBox.appendChild(title);

        const stats = document.createElement('div');
        stats.className = 'score';
        stats.innerText = `W: ${player.stats.wins} | L: ${player.stats.losses} | D: ${player.stats.draws}`;
        playerBox.appendChild(stats);

        player.hands.forEach((hand, handIndex) => {
            const handContainer = document.createElement('div');
            handContainer.className = `hand-container ${index === gameState.current_player_index && handIndex === player.active_hand_index && !gameState.game_over ? 'active-hand' : ''}`;

            const cardsDiv = document.createElement('div');
            cardsDiv.className = 'cards-container';

            const scoreDiv = document.createElement('div');
            scoreDiv.className = 'score';

            renderHand(hand, cardsDiv, scoreDiv);

            // Result status
            if (hand.result) {
                const statusDiv = document.createElement('div');
                statusDiv.className = `status ${hand.result}`;
                statusDiv.innerText = hand.result.toUpperCase();
                handContainer.appendChild(statusDiv);
            } else if (hand.status !== 'playing') {
                const statusDiv = document.createElement('div');
                statusDiv.className = 'status';
                statusDiv.innerText = hand.status.toUpperCase();
                handContainer.appendChild(statusDiv);
            }

            handContainer.appendChild(cardsDiv);
            handContainer.appendChild(scoreDiv);
            playerBox.appendChild(handContainer);
        });

        playersArea.appendChild(playerBox);
    });

    // Update Controls
    if (gameState.game_over) {
        controlsArea.classList.add('hidden');
        gameMessage.innerText = "Round Over";
        gameMessage.classList.remove('hidden');
        endGameControls.classList.remove('hidden');
    } else {
        controlsArea.classList.remove('hidden');
        gameMessage.classList.add('hidden');
        endGameControls.classList.add('hidden');

        // Check for split availability
        const activePlayer = gameState.players[gameState.current_player_index];
        const activeHand = activePlayer.hands[activePlayer.active_hand_index];

        if (activeHand && activeHand.can_split) {
            splitBtn.classList.remove('hidden');
        } else {
            splitBtn.classList.add('hidden');
        }
    }
}

function renderHand(hand, container, scoreContainer, isDealer = false) {
    container.innerHTML = '';
    hand.cards.forEach(card => {
        const cardDiv = document.createElement('div');

        if (card.suit === 'hidden') {
            cardDiv.className = 'card hidden';
        } else {
            const isRed = ['hearts', 'diamonds'].includes(card.suit);
            cardDiv.className = `card ${isRed ? 'red' : 'black'}`;

            const suitSymbol = getSuitSymbol(card.suit);
            cardDiv.innerHTML = `<div>${card.rank}</div><div>${suitSymbol}</div>`;
        }
        container.appendChild(cardDiv);
    });

    scoreContainer.innerText = `Score: ${hand.value}`;
}

function getSuitSymbol(suit) {
    switch (suit) {
        case 'hearts': return '♥';
        case 'diamonds': return '♦';
        case 'clubs': return '♣';
        case 'spades': return '♠';
        default: return '';
    }
}
