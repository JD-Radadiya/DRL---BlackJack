import random

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = self._get_value()

    def _get_value(self):
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11
        else:
            return int(self.rank)

    def to_dict(self):
        return {'suit': self.suit, 'rank': self.rank, 'value': self.value}

class Deck:
    def __init__(self, num_decks=6):
        self.num_decks = num_decks
        self.suits = ['hearts', 'diamonds', 'clubs', 'spades']
        self.ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.cards = []
        self.reshuffle()

    def reshuffle(self):
        self.cards = [Card(suit, rank) for _ in range(self.num_decks) for suit in self.suits for rank in self.ranks]
        random.shuffle(self.cards)

    def deal(self):
        # Reshuffle if penetration is too deep (e.g., less than 20% cards remaining)
        if len(self.cards) < (52 * self.num_decks * 0.2):
            self.reshuffle()
            
        if not self.cards:
            self.reshuffle()
            
        return self.cards.pop()

    def get_seen_cards(self):
        # Calculate seen cards based on what's missing from a full shoe
        full_counts = {
            '2': 4 * self.num_decks, '3': 4 * self.num_decks, '4': 4 * self.num_decks,
            '5': 4 * self.num_decks, '6': 4 * self.num_decks, '7': 4 * self.num_decks,
            '8': 4 * self.num_decks, '9': 4 * self.num_decks, '10': 4 * self.num_decks,
            'J': 4 * self.num_decks, 'Q': 4 * self.num_decks, 'K': 4 * self.num_decks,
            'A': 4 * self.num_decks
        }
        
        current_counts = {r: 0 for r in self.ranks}
        for card in self.cards:
            current_counts[card.rank] += 1
            
        seen_counts = {r: full_counts[r] - current_counts[r] for r in self.ranks}
        
        # Convert to vector format expected by RL agent: 2,3,4,5,6,7,8,9,10(inc JQK),A
        vector = [
            seen_counts['2'], seen_counts['3'], seen_counts['4'], seen_counts['5'],
            seen_counts['6'], seen_counts['7'], seen_counts['8'], seen_counts['9'],
            seen_counts['10'] + seen_counts['J'] + seen_counts['Q'] + seen_counts['K'],
            seen_counts['A']
        ]
        return vector

class Hand:
    def __init__(self):
        self.cards = []
        self.bet = 0
        self.status = 'playing' # playing, stood, busted, blackjack
        self.is_split = False

    def add_card(self, card):
        self.cards.append(card)
        self.check_status()

    def get_value(self):
        value = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == 'A')
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def check_status(self):
        value = self.get_value()
        if value > 21:
            self.status = 'busted'
        elif value == 21 and len(self.cards) == 2 and not self.is_split:
            self.status = 'blackjack'

    def can_split(self):
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

    def to_dict(self):
        return {
            'cards': [c.to_dict() for c in self.cards],
            'value': self.get_value(),
            'status': self.status,
            'can_split': self.can_split()
        }

class Player:
    def __init__(self, player_id, is_ai=False):
        self.id = player_id
        self.is_ai = is_ai
        self.hands = [Hand()]
        self.active_hand_index = 0
        self.stats = {'wins': 0, 'losses': 0, 'draws': 0}

    def current_hand(self):
        if 0 <= self.active_hand_index < len(self.hands):
            return self.hands[self.active_hand_index]
        return None

    def is_done(self):
        return self.active_hand_index >= len(self.hands)

    def split_hand(self):
        hand = self.current_hand()
        if hand and hand.can_split():
            new_hand = Hand()
            new_hand.is_split = True
            hand.is_split = True
            
            # Move second card to new hand
            card_to_move = hand.cards.pop()
            new_hand.add_card(card_to_move)
            
            # Insert new hand after current hand
            self.hands.insert(self.active_hand_index + 1, new_hand)
            return True
        return False

    def reset_for_round(self):
        self.hands = [Hand()]
        self.active_hand_index = 0

    def to_dict(self):
        return {
            'id': self.id,
            'is_ai': self.is_ai,
            'hands': [h.to_dict() for h in self.hands],
            'active_hand_index': self.active_hand_index,
            'stats': self.stats
        }

class BlackjackGame:
    def __init__(self):
        self.deck = Deck(num_decks=6)
        self.dealer_hand = Hand()
        self.players = []
        self.current_player_index = 0
        self.game_over = False
        self.game_started = False

    def start_game(self, num_players, ai_players=0):
        # We assume start_game is a hard reset, so we reset the deck too?
        # User said "In new rounds we don't re-shuffle".
        # But "start_game" usually implies a fresh session.
        # Let's keep a persistent deck if possible, or reset it here.
        # Given the UI has "New Game" and "Next Round", "New Game" likely means fresh deck.
        self.deck = Deck(num_decks=6)
        self.dealer_hand = Hand()
        self.players = [Player(i+1) for i in range(num_players)]
        for i in range(ai_players):
            self.players.append(Player(num_players + i + 1, is_ai=True))
        self.current_player_index = 0
        self.game_over = False
        self.game_started = True

        # Initial deal
        for _ in range(2):
            for player in self.players:
                player.hands[0].add_card(self.deck.deal())
            self.dealer_hand.add_card(self.deck.deal())

        self._update_turn()

    def next_round(self):
        # Do NOT reset self.deck here
        self.dealer_hand = Hand()
        self.current_player_index = 0
        self.game_over = False
        
        for player in self.players:
            player.reset_for_round()
            
        # Initial deal
        for _ in range(2):
            for player in self.players:
                player.hands[0].add_card(self.deck.deal())
            self.dealer_hand.add_card(self.deck.deal())
            
        self._update_turn()

    def _update_turn(self):
        # Find next active player/hand
        while self.current_player_index < len(self.players):
            player = self.players[self.current_player_index]
            if not player.is_done():
                # Check if current hand is already done (e.g. Blackjack or Bust from initial deal?)
                # Actually, initial deal blackjack should be checked.
                hand = player.current_hand()
                if hand.status in ['blackjack', 'busted', 'stood']:
                     player.active_hand_index += 1
                     continue
                return # Found active player
            self.current_player_index += 1
        
        # If all players done, dealer plays
        self.dealer_play()

    def hit(self, player_id):
        player = self.players[player_id - 1]
        hand = player.current_hand()
        if hand:
            hand.add_card(self.deck.deal())
            if hand.status in ['busted', 'blackjack']:
                player.active_hand_index += 1
                self._update_turn()
            return True
        return False

    def stand(self, player_id):
        player = self.players[player_id - 1]
        hand = player.current_hand()
        if hand:
            hand.status = 'stood'
            player.active_hand_index += 1
            self._update_turn()
            return True
        return False

    def split(self, player_id):
        player = self.players[player_id - 1]
        if player.split_hand():
            # Deal one card to each split hand
            player.hands[player.active_hand_index].add_card(self.deck.deal())
            player.hands[player.active_hand_index + 1].add_card(self.deck.deal())
            # Don't advance turn, player plays first split hand
            return True
        return False

    def dealer_play(self):
        while self.dealer_hand.get_value() < 17:
            self.dealer_hand.add_card(self.deck.deal())
        self.dealer_hand.check_status() # Update status to busted if > 21
        self.resolve_game()

    def resolve_game(self):
        dealer_value = self.dealer_hand.get_value()
        dealer_busted = self.dealer_hand.status == 'busted'
        dealer_blackjack = self.dealer_hand.status == 'blackjack'

        for player in self.players:
            for hand in player.hands:
                player_value = hand.get_value()
                player_blackjack = hand.status == 'blackjack'

                if hand.status == 'busted':
                    hand.result = 'loss'
                    player.stats['losses'] += 1
                elif player_blackjack:
                    if dealer_blackjack:
                        hand.result = 'draw'
                        player.stats['draws'] += 1
                    else:
                        hand.result = 'win'
                        player.stats['wins'] += 1
                elif dealer_blackjack:
                    # Player not blackjack (checked above)
                    hand.result = 'loss'
                    player.stats['losses'] += 1
                elif dealer_busted:
                    hand.result = 'win'
                    player.stats['wins'] += 1
                elif player_value > dealer_value:
                    hand.result = 'win'
                    player.stats['wins'] += 1
                elif player_value < dealer_value:
                    hand.result = 'loss'
                    player.stats['losses'] += 1
                else:
                    # Draw condition: Player Value == Dealer Value (and neither blackjack)
                    hand.result = 'draw'
                    player.stats['draws'] += 1
        
        self.game_over = True

    def get_state(self):
        dealer_hand_state = self.dealer_hand.to_dict()
        
        # Mask dealer card if game is not over
        if not self.game_over and len(dealer_hand_state['cards']) >= 2:
            # Only show first card
            visible_card = dealer_hand_state['cards'][0]
            dealer_hand_state['cards'] = [visible_card, {'suit': 'hidden', 'rank': '?', 'value': 0}]
            dealer_hand_state['value'] = visible_card['value'] # Only show value of visible card

        return {
            'dealer_hand': dealer_hand_state,
            'players': [p.to_dict() for p in self.players],
            'current_player_index': self.current_player_index,
            'game_over': self.game_over,
            'game_started': self.game_started
        }

    def get_ai_observation(self, player_id):
        player = self.players[player_id - 1]
        hand = player.current_hand()
        if not hand:
            return None
            
        # [Player Sum (0-32), Dealer Upcard (0-11), Usable Ace (0-1), 
        #  Seen Cards Hist (10 ints), Decks Remaining (float)]
        
        player_val = hand.get_value()
        
        # Dealer Upcard
        dealer_up_val = self.dealer_hand.cards[0].value if self.dealer_hand.cards else 0
        
        # Usable Ace
        aces = sum(1 for c in hand.cards if c.rank == 'A')
        # Simple check: if value <= 21 and we have an ace that could be 11
        # Actually, get_value() already reduces aces. If we have an ace and value <= 21,
        # we need to know if one is countable as 11.
        # Re-calculate soft value
        soft_val = sum(c.value for c in hand.cards) # Aces are 11
        usable_ace = 1 if (soft_val <= 21 and aces > 0) else 0
        
        seen_cards = self.deck.get_seen_cards()
        decks_remaining = len(self.deck.cards) / 52.0
        
        # Normalize
        obs = [
            player_val / 21.0,
            dealer_up_val / 10.0,
            float(usable_ace),
        ]
        # Normalize seen cards
        obs.extend([x / (6 * 4.0) for x in seen_cards]) # 6 decks
        obs.append(decks_remaining / 6.0)
        
        return obs
