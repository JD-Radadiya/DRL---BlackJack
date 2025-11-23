import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random

# Card values
CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10, 'A': 11
}

# Rank to index mapping for "Seen Cards Vector"
RANK_TO_INDEX = {
    '2': 0, '3': 1, '4': 2, '5': 3, '6': 4, '7': 5, '8': 6, '9': 7,
    '10': 8, 'J': 8, 'Q': 8, 'K': 8, 'A': 9
}

class BlackjackEnv(gym.Env):
    def __init__(self, num_decks=6, overshoot_weight=0.1, undershoot_weight=0.05):
        super(BlackjackEnv, self).__init__()
        self.num_decks = num_decks
        self.overshoot_weight = overshoot_weight
        self.undershoot_weight = undershoot_weight
        
        # Action Space: 0: Stand, 1: Hit, 2: Double
        self.action_space = spaces.Discrete(3)
        
        # Observation Space:
        # [Player Sum (0-32), Dealer Upcard (0-11), Usable Ace (0-1), 
        #  Seen Cards Hist (10 ints), Decks Remaining (float)]
        # Total size: 1 + 1 + 1 + 10 + 1 = 14
        self.observation_space = spaces.Box(
            low=0, high=1000, shape=(14,), dtype=np.float32
        )
        
        self.deck = []
        self.seen_cards = np.zeros(10, dtype=np.float32)
        self.reshuffle()

    def reshuffle(self):
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.deck = [{'rank': r, 'value': CARD_VALUES[r]} for _ in range(self.num_decks) for _ in suits for r in ranks]
        random.shuffle(self.deck)
        self.seen_cards = np.zeros(10, dtype=np.float32)

    def deal_card(self):
        # Reshuffle if penetration > 80% (less than 20% remaining)
        if len(self.deck) < (52 * self.num_decks * 0.2):
            self.reshuffle()
        
        if not self.deck:
            self.reshuffle()
            
        card = self.deck.pop()
        # Update seen cards
        idx = RANK_TO_INDEX[card['rank']]
        self.seen_cards[idx] += 1
        return card

    def get_hand_value(self, hand):
        value = sum(c['value'] for c in hand)
        aces = sum(1 for c in hand if c['rank'] == 'A')
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def has_usable_ace(self, hand):
        value = sum(c['value'] for c in hand)
        aces = sum(1 for c in hand if c['rank'] == 'A')
        # If we have an Ace and value <= 21 using Ace as 11, it's usable.
        # Actually, the loop above reduces Aces until value <= 21.
        # If after that loop, we still have an Ace counted as 11 (which means we didn't reduce all of them),
        # then we have a usable ace.
        # Simpler check:
        soft_value = sum(c['value'] for c in hand) # Aces are 11 by default
        return 1 if (soft_value <= 21 and aces > 0) else 0

    def get_obs(self):
        player_val = self.get_hand_value(self.player_hand)
        dealer_val = self.dealer_upcard['value']
        usable_ace = self.has_usable_ace(self.player_hand)
        decks_remaining = len(self.deck) / 52.0
        
        # Normalize somewhat for NN stability
        obs = np.concatenate([
            [player_val / 21.0],
            [dealer_val / 10.0],
            [float(usable_ace)],
            self.seen_cards / (self.num_decks * 4.0), # Normalize by max possible count of a rank
            [decks_remaining / self.num_decks]
        ])
        return obs.astype(np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.player_hand = []
        self.dealer_hand = []
        
        # Deal initial cards
        self.player_hand.append(self.deal_card())
        self.dealer_hand.append(self.deal_card()) # Upcard
        self.player_hand.append(self.deal_card())
        self.dealer_hand.append(self.deal_card()) # Hole card (hidden from obs, but dealt)
        
        self.dealer_upcard = self.dealer_hand[0]
        
        # Check for natural blackjack immediately?
        # Standard Gym envs usually return state and let agent act, even if 21.
        # But if player has 21, they usually stand automatically or win immediately.
        # For simplicity, we'll let the agent see 21 and decide (it should learn to Stand).
        
        return self.get_obs(), {}

    def step(self, action):
        # Action: 0: Stand, 1: Hit, 2: Double
        reward = 0
        terminated = False
        truncated = False
        
        if action == 1: # Hit
            self.player_hand.append(self.deal_card())
            player_val = self.get_hand_value(self.player_hand)
            
            if player_val > 21:
                terminated = True
                reward = -1.0
                # Overshoot penalty
                overshoot = player_val - 21
                reward -= self.overshoot_weight * overshoot
                
        elif action == 2: # Double
            # Double: Hit once, then force stand. Double bet (2x reward).
            self.player_hand.append(self.deal_card())
            player_val = self.get_hand_value(self.player_hand)
            
            if player_val > 21:
                terminated = True
                reward = -2.0 # Doubled loss
                overshoot = player_val - 21
                reward -= self.overshoot_weight * overshoot
            else:
                # Force stand logic (same as below)
                terminated = True
                final_reward = self.resolve_dealer()
                reward = final_reward * 2 # Doubled win/loss
                
                # Undershoot penalty check (if lost)
                if final_reward < 0: # Lost
                     undershoot = max(0, 21 - player_val)
                     reward -= self.undershoot_weight * undershoot

        else: # Stand (0)
            terminated = True
            player_val = self.get_hand_value(self.player_hand)
            reward = self.resolve_dealer()
            
            # Undershoot penalty check (if lost)
            if reward < 0: # Lost
                 undershoot = max(0, 21 - player_val)
                 reward -= self.undershoot_weight * undershoot

        return self.get_obs(), reward, terminated, truncated, {}

    def is_natural_blackjack(self, hand):
        if len(hand) != 2:
            return False
        val = self.get_hand_value(hand)
        return val == 21

    def resolve_dealer(self):
        player_val = self.get_hand_value(self.player_hand)
        player_bj = self.is_natural_blackjack(self.player_hand)
        
        # Dealer plays
        while self.get_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deal_card())
            
        dealer_val = self.get_hand_value(self.dealer_hand)
        dealer_bj = self.is_natural_blackjack(self.dealer_hand)
        
        # Compare
        if player_bj:
            if dealer_bj:
                return 0.0 # Push (BJ vs BJ)
            else:
                return 1.0 # Player BJ wins
        elif dealer_bj:
            return -1.0 # Dealer BJ beats Player Non-BJ
            
        if dealer_val > 21:
            return 1.0 # Dealer bust, Player win
        elif player_val > dealer_val:
            return 1.0 # Player win
        elif player_val < dealer_val:
            return -1.0 # Player loss
        else:
            return 0.0 # Push
