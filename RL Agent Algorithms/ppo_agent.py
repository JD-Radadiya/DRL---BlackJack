import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical
import numpy as np
from blackjack_env import BlackjackEnv

# Hyperparameters
GAMMA = 0.99
LR_ACTOR = 0.03
LR_CRITIC = 0.01
K_EPOCHS = 50
EPS_CLIP = 0.2
MAX_EPISODES = 150000
UPDATE_TIMESTEP = 2000

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(ActorCritic, self).__init__()
        
        # Shared backbone? Or separate? 
        # User requested shared backbone.
        self.backbone = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU()
        )
        
        # Actor head
        self.actor = nn.Sequential(
            nn.Linear(64, action_dim),
            nn.Softmax(dim=-1)
        )
        
        # Critic head
        self.critic = nn.Linear(64, 1)

    def forward(self):
        raise NotImplementedError
    
    def act(self, state):
        features = self.backbone(state)
        action_probs = self.actor(features)
        dist = Categorical(action_probs)
        action = dist.sample()
        action_logprob = dist.log_prob(action)
        
        return action.item(), action_logprob
    
    def evaluate(self, state, action):
        features = self.backbone(state)
        action_probs = self.actor(features)
        dist = Categorical(action_probs)
        
        action_logprobs = dist.log_prob(action)
        dist_entropy = dist.entropy()
        state_values = self.critic(features)
        
        return action_logprobs, state_values, dist_entropy

class PPO:
    def __init__(self, state_dim, action_dim):
        self.policy = ActorCritic(state_dim, action_dim).to(device)
        self.optimizer = optim.Adam([
            {'params': self.policy.actor.parameters(), 'lr': LR_ACTOR},
            {'params': self.policy.backbone.parameters(), 'lr': LR_ACTOR}, # Shared params
            {'params': self.policy.critic.parameters(), 'lr': LR_CRITIC}
        ])
        self.policy_old = ActorCritic(state_dim, action_dim).to(device)
        self.policy_old.load_state_dict(self.policy.state_dict())
        
        self.MseLoss = nn.MSELoss()

    def select_action(self, state):
        with torch.no_grad():
            state = torch.FloatTensor(state).to(device)
            action, action_logprob = self.policy_old.act(state)
        return action, action_logprob

    def update(self, memory):
        # Monte Carlo estimate of returns
        rewards = []
        discounted_reward = 0
        for reward, is_terminal in zip(reversed(memory.rewards), reversed(memory.is_terminals)):
            if is_terminal:
                discounted_reward = 0
            discounted_reward = reward + (GAMMA * discounted_reward)
            rewards.insert(0, discounted_reward)
            
        # Normalizing the rewards
        rewards = torch.tensor(rewards, dtype=torch.float32).to(device)
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)
        
        # Convert list to tensor
        old_states = torch.squeeze(torch.stack(memory.states, dim=0)).detach().to(device)
        old_actions = torch.squeeze(torch.stack(memory.actions, dim=0)).detach().to(device)
        old_logprobs = torch.squeeze(torch.stack(memory.logprobs, dim=0)).detach().to(device)
        
        # Optimize policy for K epochs
        for _ in range(K_EPOCHS):
            # Evaluating old actions and values
            logprobs, state_values, dist_entropy = self.policy.evaluate(old_states, old_actions)
            
            # match state_values tensor dimensions with rewards tensor
            state_values = torch.squeeze(state_values)
            
            # Finding the ratio (pi_theta / pi_theta__old)
            ratios = torch.exp(logprobs - old_logprobs.detach())

            # Finding Surrogate Loss
            advantages = rewards - state_values.detach()   
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1-EPS_CLIP, 1+EPS_CLIP) * advantages

            # final loss of clipped objective PPO
            loss = -torch.min(surr1, surr2) + 0.5 * self.MseLoss(state_values, rewards) - 0.01 * dist_entropy
            
            # take gradient step
            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()
            
        # Copy new weights into old policy
        self.policy_old.load_state_dict(self.policy.state_dict())

class Memory:
    def __init__(self):
        self.actions = []
        self.states = []
        self.logprobs = []
        self.rewards = []
        self.is_terminals = []
    
    def clear_memory(self):
        del self.actions[:]
        del self.states[:]
        del self.logprobs[:]
        del self.rewards[:]
        del self.is_terminals[:]

def train():
    env = BlackjackEnv()
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n
    
    ppo_agent = PPO(state_dim, action_dim)
    memory = Memory()
    
    time_step = 0
    running_reward = 0
    
    print(f"Starting training for {MAX_EPISODES} episodes...")
    
    for i_episode in range(1, MAX_EPISODES+1):
        state, _ = env.reset()
        current_ep_reward = 0
        
        for t in range(100): # Max steps per episode
            time_step += 1
            
            # Select action with policy
            action, log_prob = ppo_agent.select_action(state)
            
            # Interact with env
            next_state, reward, done, truncated, _ = env.step(action)
            
            # Save data in memory
            memory.states.append(torch.FloatTensor(state))
            memory.actions.append(torch.tensor(action))
            memory.logprobs.append(log_prob)
            memory.rewards.append(reward)
            memory.is_terminals.append(done)
            
            state = next_state
            current_ep_reward += reward
            
            # Update PPO agent
            if time_step % UPDATE_TIMESTEP == 0:
                ppo_agent.update(memory)
                memory.clear_memory()
                time_step = 0
            
            if done or truncated:
                break
        
        running_reward += current_ep_reward
        
        # Logging
        if i_episode % 1000 == 0:
            avg_reward = running_reward / 1000
            print(f'Episode {i_episode} \t Avg Reward: {avg_reward:.2f}')
            running_reward = 0
            
    # Save the model
    torch.save(ppo_agent.policy.state_dict(), 'ppo_blackjack.pth')
    print("Model saved to ppo_blackjack.pth")

if __name__ == '__main__':
    train()
