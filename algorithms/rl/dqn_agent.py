"""
dqn_agent.py

Double DQN Agent with:
- Dueling network architecture
- Prioritized experience replay
- Action masking for infeasible actions
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import random

# PyTorch imports
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorch not available. Install with: pip install torch")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from algorithms.rl.ev_routing_env import EVRoutingEnv


# ============================================================================
# Dueling DQN Network
# ============================================================================

if TORCH_AVAILABLE:
    class DuelingDQN(nn.Module):
        """
        Dueling DQN architecture.
        Separates value and advantage streams for better learning.
        """
        
        def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128):
            super().__init__()
            
            # Shared feature layer
            self.feature = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU()
            )
            
            # Value stream
            self.value_stream = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, 1)
            )
            
            # Advantage stream
            self.advantage_stream = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, action_dim)
            )
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            features = self.feature(x)
            value = self.value_stream(features)
            advantage = self.advantage_stream(features)
            
            # Combine: Q = V + (A - mean(A))
            q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
            return q_values


# ============================================================================
# Prioritized Replay Buffer
# ============================================================================

@dataclass
class Transition:
    """Single experience tuple."""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    valid_actions: List[int]


class PrioritizedReplayBuffer:
    """
    Prioritized experience replay buffer.
    Samples experiences with probability proportional to TD error.
    """
    
    def __init__(self, capacity: int = 10000, alpha: float = 0.6):
        self.capacity = capacity
        self.alpha = alpha  # Priority exponent
        self.buffer = []
        self.priorities = []
        self.position = 0
    
    def push(self, transition: Transition, priority: float = 1.0):
        """Add transition with priority."""
        if len(self.buffer) < self.capacity:
            self.buffer.append(transition)
            self.priorities.append(priority ** self.alpha)
        else:
            self.buffer[self.position] = transition
            self.priorities[self.position] = priority ** self.alpha
        
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size: int, beta: float = 0.4) -> Tuple[List[Transition], np.ndarray, np.ndarray]:
        """Sample batch with importance sampling weights."""
        if len(self.buffer) == 0:
            return [], np.array([]), np.array([])
        
        priorities = np.array(self.priorities[:len(self.buffer)])
        probs = priorities / priorities.sum()
        
        indices = np.random.choice(len(self.buffer), size=min(batch_size, len(self.buffer)), 
                                   p=probs, replace=False)
        
        samples = [self.buffer[i] for i in indices]
        
        # Importance sampling weights
        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights = weights / weights.max()
        
        return samples, indices, weights
    
    def update_priorities(self, indices: np.ndarray, priorities: np.ndarray):
        """Update priorities after learning."""
        for idx, priority in zip(indices, priorities):
            self.priorities[idx] = (priority + 1e-6) ** self.alpha
    
    def __len__(self):
        return len(self.buffer)


# ============================================================================
# DQN Agent
# ============================================================================

class DQNAgent:
    """
    Double DQN Agent with Dueling architecture and prioritized replay.
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        lr: float = 1e-3,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.05,
        epsilon_decay: float = 0.995,
        buffer_size: int = 10000,
        batch_size: int = 64,
        target_update: int = 10,
        device: str = None
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for DQN agent")
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update = target_update
        
        # Device - prefer MPS on M1 Mac
        if device is None:
            if torch.backends.mps.is_available():
                self.device = torch.device("mps")
            elif torch.cuda.is_available():
                self.device = torch.device("cuda")
            else:
                self.device = torch.device("cpu")
        else:
            self.device = torch.device(device)
        
        # Networks
        self.policy_net = DuelingDQN(state_dim, action_dim, hidden_dim).to(self.device)
        self.target_net = DuelingDQN(state_dim, action_dim, hidden_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        # Optimizer
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        
        # Replay buffer
        self.replay_buffer = PrioritizedReplayBuffer(buffer_size)
        
        # Training counter
        self.steps = 0
        self.updates = 0
    
    def select_action(self, state: np.ndarray, valid_actions: List[int], training: bool = True, 
                       decision_type: str = 'station') -> int:
        """
        Select action using epsilon-greedy with action masking.
        Uses guided exploration: bias towards expert policy early in training.
        """
        if training and random.random() < self.epsilon:
            # Guided exploration: mix random with expert-biased
            if random.random() < 0.7:  # 70% of exploration uses expert bias
                return self._expert_action(valid_actions, decision_type)
            else:
                return random.choice(valid_actions)
        
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor).cpu().numpy()[0]
            
            # Mask invalid actions
            masked_q = np.full(self.action_dim, -np.inf)
            for a in valid_actions:
                masked_q[a] = q_values[a]
            
            return int(np.argmax(masked_q))
    
    def _expert_action(self, valid_actions: List[int], decision_type: str) -> int:
        """
        Expert policy: prefer high SOC (90%) with slowest speed for stations,
        or lower path (action 1) for forks.
        """
        if decision_type == 'fork':
            # Prefer lower path (usually shorter)
            return 1 if 1 in valid_actions else valid_actions[0]
        else:
            # For stations: find action with highest SOC (index 4) and slowest speed (index 0)
            # Action encoding: soc_idx * n_speeds + speed_idx
            # With 5 SOC targets and 4 speeds, we want soc_idx=4, speed_idx=0 -> action=16
            n_speeds = 4  # SPEED_OPTIONS length
            
            # Find best available action (prefer high SOC, then slow speed)
            best = None
            best_score = -1
            for a in valid_actions:
                soc_idx = a // n_speeds
                speed_idx = a % n_speeds
                # Score: high SOC good, low speed good
                score = soc_idx * 10 - speed_idx
                if score > best_score:
                    best_score = score
                    best = a
            return best if best is not None else valid_actions[0]
    
    def store_transition(self, state, action, reward, next_state, done, valid_actions):
        """Store transition in replay buffer."""
        transition = Transition(state, action, reward, next_state, done, valid_actions)
        self.replay_buffer.push(transition)
    
    def update(self) -> Optional[float]:
        """Perform one update step. Returns loss if update happened."""
        if len(self.replay_buffer) < self.batch_size:
            return None
        
        # Sample batch
        batch, indices, weights = self.replay_buffer.sample(self.batch_size)
        
        if not batch:
            return None
        
        # Convert to tensors
        states = torch.FloatTensor(np.array([t.state for t in batch])).to(self.device)
        actions = torch.LongTensor([t.action for t in batch]).to(self.device)
        rewards = torch.FloatTensor([t.reward for t in batch]).to(self.device)
        next_states = torch.FloatTensor(np.array([t.next_state for t in batch])).to(self.device)
        dones = torch.FloatTensor([float(t.done) for t in batch]).to(self.device)
        weights_tensor = torch.FloatTensor(weights).to(self.device)
        
        # Current Q values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        # Double DQN: use policy net to select action, target net to evaluate
        with torch.no_grad():
            next_q_policy = self.policy_net(next_states)
            
            # Mask invalid actions for next state
            for i, t in enumerate(batch):
                if not t.done and t.valid_actions:
                    mask = torch.full((self.action_dim,), -np.inf, device=self.device)
                    for a in t.valid_actions:
                        mask[a] = 0
                    next_q_policy[i] += mask
            
            next_actions = next_q_policy.argmax(dim=1)
            next_q_target = self.target_net(next_states).gather(1, next_actions.unsqueeze(1)).squeeze(1)
            target_q = rewards + (1 - dones) * self.gamma * next_q_target
        
        # Compute TD error for priority update
        td_errors = torch.abs(current_q - target_q).detach().cpu().numpy()
        self.replay_buffer.update_priorities(indices, td_errors)
        
        # Weighted loss
        loss = (weights_tensor * F.smooth_l1_loss(current_q, target_q, reduction='none')).mean()
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        self.optimizer.step()
        
        self.updates += 1
        
        # Update target network
        if self.updates % self.target_update == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())
        
        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        
        return loss.item()
    
    def save(self, path: str):
        """Save model weights."""
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'target_net': self.target_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'updates': self.updates
        }, path)
    
    def load(self, path: str):
        """Load model weights."""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['target_net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.epsilon = checkpoint['epsilon']
        self.updates = checkpoint['updates']


# ============================================================================
# Training Function
# ============================================================================

def train_dqn(
    env: EVRoutingEnv,
    agent: DQNAgent,
    n_episodes: int = 500,
    max_steps: int = 100,
    verbose: bool = True,
    eval_interval: int = 50
) -> dict:
    """
    Train DQN agent on EV routing environment.
    """
    episode_rewards = []
    episode_makespans = []
    episode_costs = []
    losses = []
    success_rate = []
    
    for episode in range(n_episodes):
        state = env.reset(seed=episode)
        total_reward = 0
        step = 0
        
        while step < max_steps:
            valid_actions = env.get_valid_actions()
            action = agent.select_action(state, valid_actions, training=True, 
                                        decision_type=env.decision_type)
            
            next_state, reward, done, info = env.step(action)
            
            # Get valid actions for next state (for masking in update)
            next_valid = env.get_valid_actions() if not done else []
            
            agent.store_transition(state, action, reward, next_state, done, next_valid)
            
            loss = agent.update()
            if loss is not None:
                losses.append(loss)
            
            total_reward += reward
            state = next_state
            step += 1
            
            if done:
                break
        
        episode_rewards.append(total_reward)
        
        if info.get('success', False):
            episode_makespans.append(info.get('makespan', 0))
            episode_costs.append(info.get('total_cost', 0))
            success_rate.append(1)
        else:
            success_rate.append(0)
        
        if verbose and (episode + 1) % eval_interval == 0:
            avg_reward = np.mean(episode_rewards[-eval_interval:])
            avg_success = np.mean(success_rate[-eval_interval:])
            print(f"Episode {episode+1}/{n_episodes} | "
                  f"Avg Reward: {avg_reward:.1f} | "
                  f"Success: {avg_success*100:.0f}% | "
                  f"Epsilon: {agent.epsilon:.3f}")
    
    return {
        'rewards': episode_rewards,
        'makespans': episode_makespans,
        'costs': episode_costs,
        'losses': losses,
        'success_rate': success_rate
    }


def evaluate_dqn(
    env: EVRoutingEnv,
    agent: DQNAgent,
    n_episodes: int = 10,
    seed: int = 1000
) -> dict:
    """
    Evaluate trained agent (no exploration).
    """
    makespans = []
    costs = []
    successes = []
    
    for i in range(n_episodes):
        state = env.reset(seed=seed + i)
        done = False
        steps = 0
        
        while not done and steps < 100:
            valid_actions = env.get_valid_actions()
            action = agent.select_action(state, valid_actions, training=False)
            state, _, done, info = env.step(action)
            steps += 1
        
        if info.get('success', False):
            makespans.append(info['makespan'])
            costs.append(info['total_cost'])
            successes.append(1)
        else:
            successes.append(0)
    
    return {
        'mean_makespan': np.mean(makespans) if makespans else float('inf'),
        'std_makespan': np.std(makespans) if makespans else 0,
        'mean_cost': np.mean(costs) if costs else float('inf'),
        'std_cost': np.std(costs) if costs else 0,
        'success_rate': np.mean(successes)
    }


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    if not TORCH_AVAILABLE:
        print("Install PyTorch to run this test")
        exit(1)
    
    print("Creating environment...")
    env = EVRoutingEnv()
    
    print("Creating agent...")
    agent = DQNAgent(
        state_dim=env.state_dim,
        action_dim=env.n_actions,
        hidden_dim=128,
        lr=1e-3,
        epsilon_decay=0.99
    )
    
    print("Training for 100 episodes (quick test)...")
    history = train_dqn(env, agent, n_episodes=100, verbose=True, eval_interval=20)
    
    print("\nEvaluating...")
    results = evaluate_dqn(env, agent, n_episodes=5)
    print(f"Mean makespan: {results['mean_makespan']:.2f} ± {results['std_makespan']:.2f}")
    print(f"Mean cost: {results['mean_cost']:.2f} ± {results['std_cost']:.2f}")
    print(f"Success rate: {results['success_rate']*100:.0f}%")
