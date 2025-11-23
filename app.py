from flask import Flask, render_template, jsonify, request
from game_logic import BlackjackGame

app = Flask(__name__)
game = BlackjackGame()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    data = request.json
    num_players = data.get('num_players', 1)
    game.start_game(num_players)
    return jsonify(game.get_state())

@app.route('/next_round', methods=['POST'])
def next_round():
    game.next_round()
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
        
    return jsonify({'success': success, 'state': game.get_state()})

@app.route('/state', methods=['GET'])
def get_state():
    return jsonify(game.get_state())

if __name__ == '__main__':
    app.run(debug=True, port=5000)
