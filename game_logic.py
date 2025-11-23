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
    def __init__(self):
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.cards = [Card(suit, rank) for suit in suits for rank in ranks]
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        if not self.cards:
            return None # Should handle reshuffle or empty deck
        return self.cards.pop()

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
    def __init__(self, player_id):
        self.id = player_id
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
            'hands': [h.to_dict() for h in self.hands],
            'active_hand_index': self.active_hand_index,
            'stats': self.stats
        }

class BlackjackGame:
    def __init__(self):
        self.deck = Deck()
        self.dealer_hand = Hand()
        self.players = []
        self.current_player_index = 0
        self.game_over = False
        self.game_started = False

    def start_game(self, num_players):
        self.deck = Deck()
        self.dealer_hand = Hand()
        self.players = [Player(i+1) for i in range(num_players)]
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
        self.deck = Deck()
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
