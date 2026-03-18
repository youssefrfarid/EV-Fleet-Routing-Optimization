"""
rl_optimizer.py

RL Optimization wrapper that integrates with the existing FleetSolution format.
Provides a consistent interface matching SA, GA, PSO, TLBO.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.params import DoubleForkParams, make_double_fork_params
from common.objectives import FleetSolution, VehicleSolution, objective_weighted

from algorithms.rl.ev_routing_env import EVRoutingEnv

# Import custom RL repair (works with double-fork topology)
from algorithms.rl.rl_repair import repair_rl_solution

# Check PyTorch availability
try:
    import torch
    from algorithms.rl.dqn_agent import DQNAgent, train_dqn  # noqa: F401
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# ============================================================================
# Result Dataclass
# ============================================================================

@dataclass
class RLResult:
    """Result object returned by RL optimization."""
    best_solution: FleetSolution
    best_fitness: float
    training_history: Dict[str, List[float]] = field(default_factory=dict)
    training_time: float = 0.0
    inference_time: float = 0.0
    success_rate: float = 0.0


# ============================================================================
# RL Optimization Function
# ============================================================================

def rl_optimization(
    params: DoubleForkParams,
    *,
    n_episodes: int = 500,  # Increased from 100 for better learning
    hidden_dim: int = 128,
    lr: float = 1e-3,
    gamma: float = 0.99,
    epsilon_decay: float = 0.997,  # Slower decay = more exploration
    alpha: float = 1.0,  # Makespan weight
    beta: float = 0.5,   # Cost weight (increased from 0.1 for better balance)
    seed: Optional[int] = None,
    verbose: bool = True,
    show_plots: bool = True,
) -> RLResult:
    """
    Run Reinforcement Learning optimization using Double DQN.
    
    Args:
        params: Problem parameters
        n_episodes: Number of training episodes
        hidden_dim: Neural network hidden layer size
        lr: Learning rate
        gamma: Discount factor
        epsilon_decay: Epsilon decay rate for exploration
        alpha: Makespan weight in reward
        beta: Cost weight in reward
        seed: Random seed for reproducibility
        verbose: Print progress
        show_plots: Show training plots (not implemented yet)
        
    Returns:
        RLResult with best solution and training history
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch required for RL optimization. Install with: pip install torch")
    
    if seed is not None:
        np.random.seed(seed)
        torch.manual_seed(seed)
    
    if verbose:
        print("🤖 Starting Reinforcement Learning (DQN) Optimization")
        print(f"Episodes: {n_episodes}, Hidden dim: {hidden_dim}, LR: {lr}")
    
    # Create environment
    env = EVRoutingEnv(params, alpha=alpha, beta=beta)
    
    # Create agent
    agent = DQNAgent(
        state_dim=env.state_dim,
        action_dim=env.n_actions,
        hidden_dim=hidden_dim,
        lr=lr,
        gamma=gamma,
        epsilon_decay=epsilon_decay,
        buffer_size=20000,  # Increased from 10000 for more experience diversity
        batch_size=128,     # Increased from 64 for more stable learning
        target_update=10
    )
    
    if verbose:
        print(f"Device: {agent.device}")
        print(f"State dim: {env.state_dim}, Action dim: {env.n_actions}")
        print()
    
    # Training
    training_start = time.time()
    history = train_dqn(
        env, agent, 
        n_episodes=n_episodes, 
        max_steps=100,
        verbose=verbose,
        eval_interval=max(50, n_episodes // 10)
    )
    training_time = time.time() - training_start
    
    if verbose:
        print(f"\nTraining completed in {training_time:.1f}s")
    
    # Evaluate and get best solution
    inference_start = time.time()
    
    # Run multiple evaluations and pick best
    best_solution = None
    best_fitness = float('inf')
    
    # Try DQN policy first (more rollouts for better solution)
    for eval_seed in range(20):  # Increased from 5 to 20
        state = env.reset(seed=1000 + eval_seed)
        done = False
        steps = 0
        
        while not done and steps < 100:
            valid = env.get_valid_actions()
            action = agent.select_action(state, valid, training=False)
            state, _, done, info = env.step(action)
            steps += 1
        
        if info.get('success', False):
            solution = _convert_to_fleet_solution(env, params)
            
            # REPAIR: Apply double-fork compatible repair
            feasible = solution.is_feasible()
            if not feasible:
                if verbose:
                    print("  Repairing infeasible DQN solution...")
                solution = repair_rl_solution(solution, params)
                feasible = solution.is_feasible()
            
            # Only consider if feasible after repair
            if feasible:
                fitness = objective_weighted(solution)
                if fitness < best_fitness:
                    best_fitness = fitness
                    best_solution = solution
    
    # If DQN failed, try expert policy
    if best_solution is None:
        if verbose:
            print("DQN policy failed, trying expert policy...")
        
        for eval_seed in range(20):  # Increased from 5 to 20
            state = env.reset(seed=2000 + eval_seed)
            done = False
            steps = 0
            
            while not done and steps < 100:
                valid = env.get_valid_actions()
                vid = env.active_vehicle
                action = _expert_action(valid, env.decision_type, vid)
                state, _, done, info = env.step(action)
                steps += 1
            
            if info.get('success', False):
                solution = _convert_to_fleet_solution(env, params)
                
                # REPAIR: Apply double-fork compatible repair
                feasible = solution.is_feasible()
                if not feasible:
                    if verbose:
                        print("  Repairing infeasible expert solution...")
                    solution = repair_rl_solution(solution, params)
                    feasible = solution.is_feasible()
                
                # Only consider if feasible
                if feasible:
                    fitness = objective_weighted(solution)
                    if fitness < best_fitness:
                        best_fitness = fitness
                        best_solution = solution
    
    inference_time = time.time() - inference_start
    
    if best_solution is None:
        if verbose:
            print("❌ No feasible solution found. Using fallback.")
        best_solution = _create_fallback_solution(params)
        best_fitness = objective_weighted(best_solution)
    
    # Calculate success rate from training
    success_rate = np.mean(history.get('success_rate', [0])[-100:]) if history.get('success_rate') else 0.0
    
    if verbose:
        print("\n✅ RL Optimization completed")
        print(f"Best fitness: {best_fitness:.3f}")
        print(f"Training time: {training_time:.1f}s")
        print(f"Inference time: {inference_time:.3f}s")
        print(f"Success rate (last 100 eps): {success_rate*100:.0f}%")
    
    return RLResult(
        best_solution=best_solution,
        best_fitness=best_fitness,
        training_history=history,
        training_time=training_time,
        inference_time=inference_time,
        success_rate=success_rate
    )


def _expert_action(valid_actions: List[int], decision_type: str, vehicle_id: int = 0) -> int:
    """
    Expert policy: prefer high SOC with slow speed.
    Diversifies routes by vehicle ID to avoid station capacity violations.
    """
    if decision_type == 'fork':
        # Alternate routes by vehicle ID: even vehicles upper (0), odd vehicles lower (1)
        preferred = 0 if vehicle_id % 2 == 0 else 1
        return preferred if preferred in valid_actions else valid_actions[0]
    else:
        n_speeds = 4
        best = None
        best_score = -1
        for a in valid_actions:
            soc_idx = a // n_speeds
            speed_idx = a % n_speeds
            score = soc_idx * 10 - speed_idx
            if score > best_score:
                best_score = score
                best = a
        return best if best is not None else valid_actions[0]


def _convert_to_fleet_solution(env: EVRoutingEnv, params: DoubleForkParams) -> FleetSolution:
    """Convert environment state to FleetSolution format."""
    vehicle_solutions = []
    
    for v in env.vehicles:
        # Reconstruct the solution
        route = v.route
        charging_amounts = v.charging_amounts
        speed_levels = v.speed_levels
        
        # Calculate timing and SOC
        arrival_times = {}
        departure_times = {}
        soc_at_nodes = {}
        
        current_time = 0.0
        current_soc = params.soc0[v.vehicle_id]
        battery_kwh = params.battery_kwh[v.vehicle_id]
        
        for i, node in enumerate(route):
            arrival_times[node] = current_time
            soc_at_nodes[node] = current_soc
            
            # Charging
            if node in charging_amounts:
                energy = charging_amounts[node]
                max_power = params.station_max_kw.get(node, 50.0)
                charge_time = (energy / min(max_power, 80.0)) * 60.0
                current_time += charge_time
                current_soc += energy / battery_kwh
                current_soc = min(1.0, current_soc)
            
            departure_times[node] = current_time
            
            # Travel to next node
            if i < len(route) - 1:
                next_node = route[i + 1]
                edge = (node, next_node)
                speed = speed_levels.get(edge, 80.0)
                
                if edge in params.edges_distance_km:
                    travel_time = params.get_edge_time(edge, speed)
                    energy = params.get_edge_energy(edge, speed)
                    current_time += travel_time
                    current_soc -= energy / battery_kwh
        
        vs = VehicleSolution(
            vehicle_id=v.vehicle_id,
            route=route,
            charging_amounts={k: v for k, v in charging_amounts.items()},
            speed_levels={k: v for k, v in speed_levels.items()},
            arrival_times=arrival_times,
            departure_times=departure_times,
            soc_at_nodes=soc_at_nodes,
            charging_stations=list(charging_amounts.keys())
        )
        vehicle_solutions.append(vs)
    
    return FleetSolution(
        vehicle_solutions=vehicle_solutions,
        params=params
    )


def _create_fallback_solution(params: DoubleForkParams) -> FleetSolution:
    """Create a simple fallback solution (may be infeasible)."""
    vehicle_solutions = []
    
    for vid in range(params.m):
        # Simple route: lower path for both forks
        route = ['A', 'J1', 'S3', 'M1', 'J2', 'S6', 'M2', 'B']
        
        vs = VehicleSolution(
            vehicle_id=vid,
            route=route,
            charging_amounts={'S3': 20.0, 'S6': 20.0},
            speed_levels={},
            arrival_times={n: i * 30.0 for i, n in enumerate(route)},
            departure_times={n: i * 30.0 + 10.0 for i, n in enumerate(route)},
            soc_at_nodes={n: 0.5 for n in route},
            charging_stations=['S3', 'S6']
        )
        vehicle_solutions.append(vs)
    
    return FleetSolution(vehicle_solutions=vehicle_solutions, params=params)


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing RL Optimization...")
    
    params = make_double_fork_params()
    
    result = rl_optimization(
        params,
        n_episodes=500,  # Increased for better performance
        seed=42,
        verbose=True
    )
    
    print(f"\nFinal fitness: {result.best_fitness:.2f}")
    print(f"Feasible: {result.best_solution.is_feasible()}")
