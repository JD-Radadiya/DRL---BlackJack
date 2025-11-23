from flask import Flask, render_template, jsonify, request
from game_logic import BlackjackGame
import torch
import torch.nn as nn
from torch.distributions import Categorical
import os

app = Flask(__name__)
game = BlackjackGame()

# --- RL Agent Classes (Copied for simplicity) ---
class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(ActorCritic, self).__init__()
        self.backbone = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU()
        )
        self.actor = nn.Sequential(
            nn.Linear(64, action_dim),
            nn.Softmax(dim=-1)
        )
        self.critic = nn.Linear(64, 1)

    def act(self, state):
        features = self.backbone(state)
        action_probs = self.actor(features)
        dist = Categorical(action_probs)
        action = dist.sample()
        return action.item()

# Load Model
device = torch.device('cpu')
ppo_agent = None

def load_model():
    global ppo_agent
    try:
        # State dim 14, Action dim 3
        ppo_agent = ActorCritic(14, 3).to(device)
        # Look for model at project root first, then fall back to RL Agent Algorithms folder
        model_path = os.path.join(os.path.dirname(__file__), '..', 'ppo_blackjack.pth')
        if not os.path.exists(model_path):
            model_path = os.path.join(os.path.dirname(__file__), '..', 'RL Agent Algorithms', 'ppo_blackjack.pth')
        ppo_agent.load_state_dict(torch.load(model_path, map_location=device))
        ppo_agent.eval()
        print(f"RL Model loaded successfully from {model_path}")
    except Exception as e:
        print(f"Failed to load RL model: {e}")

load_model()

def run_ai_turns():
    global game
    while not game.game_over:
        current_player = game.players[game.current_player_index]
        
        # If human, stop and wait for input
        if not current_player.is_ai:
            return
            
        # If AI, play turn
        hand = current_player.current_hand()
        if not hand: # Should not happen if active
             game._update_turn()
             continue
             
        # Get observation
        obs = game.get_ai_observation(current_player.id)
        if obs is None:
             game._update_turn()
             continue
             
        # Query model
        state_tensor = torch.FloatTensor(obs).to(device)
        with torch.no_grad():
            action = ppo_agent.act(state_tensor)
            
        # Execute action
        # 0: Stand, 1: Hit, 2: Double (Treat Double as Hit for now if logic not supported, or implement double)
        # Simulation supports Hit/Stand/Split. Double not explicitly in API yet but logic exists? 
        # Actually game_logic doesn't have double. Let's map 2 -> Hit.
        
        if action == 0: # Stand
            game.stand(current_player.id)
        else: # Hit (or Double mapped to Hit)
            game.hit(current_player.id)
            
        # Loop continues to check if AI is still active (e.g. hit and didn't bust)
        # game._update_turn() is called inside hit/stand, so current_player_index might change.

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    data = request.json
    num_players = data.get('num_players', 1)
    ai_players = data.get('ai_players', 0)
    game.start_game(num_players, ai_players)
    run_ai_turns() # Check if first player is AI
    return jsonify(game.get_state())

@app.route('/next_round', methods=['POST'])
def next_round():
    game.next_round()
    run_ai_turns() # Check if first player is AI
    return jsonify(game.get_state())

@app.route('/action', methods=['POST'])
def action():
    data = request.json
    action_type = data.get('action')
    player_id = data.get('player_id')
    
    success = False
    if action_type == 'hit':
        success = game.hit(player_id)
    elif action_type == 'stand':
        success = game.stand(player_id)
    elif action_type == 'split':
        success = game.split(player_id)
        
    run_ai_turns() # After human acts, check if AI needs to play
    
    return jsonify({'success': success, 'state': game.get_state()})

@app.route('/state', methods=['GET'])
def get_state():
    return jsonify(game.get_state())

if __name__ == '__main__':
    app.run(debug=True, port=5000)
