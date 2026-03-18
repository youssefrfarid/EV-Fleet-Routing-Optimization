"""
ev_routing_env.py

Gym-like environment for EV Fleet Routing with:
- Event-driven simulation (advances to next decision point)
- Queue tracking per station
- SOC-dependent charging curves
- Makespan-based terminal reward
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

# Allow running directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.params import DoubleForkParams, make_double_fork_params


# ============================================================================
# Constants
# ============================================================================

# Node encoding
NODES = ['A', 'J1', 'S1', 'S2', 'S3', 'M1', 'J2', 'S4', 'S5', 'S6', 'M2', 'B']
NODE_TO_IDX = {n: i for i, n in enumerate(NODES)}
IDX_TO_NODE = {i: n for i, n in enumerate(NODES)}

# Station nodes
STATIONS = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']
STATION_TO_IDX = {s: i for i, s in enumerate(STATIONS)}

# Fork decision points
FORKS = {'J1': ('S1', 'S3'), 'J2': ('S4', 'S6')}  # upper, lower

# Route graph (next possible nodes from each)
GRAPH = {
    'A': ['J1'],
    'J1': ['S1', 'S3'],  # Fork 1: upper or lower
    'S1': ['S2'],
    'S2': ['M1'],
    'S3': ['M1'],
    'M1': ['J2'],
    'J2': ['S4', 'S6'],  # Fork 2: upper or lower
    'S4': ['S5'],
    'S5': ['M2'],
    'S6': ['M2'],
    'M2': ['B'],
    'B': []  # Terminal
}

# SOC bins for target charging (always charge enough)
SOC_TARGETS = [0.5, 0.6, 0.7, 0.8, 0.9]  # No skip option - always charge

# Speed options (km/h) - ordered slow to fast for action indexing
# Using 60-90 range to respect edge minimum speeds (some edges require 60+)
SPEED_OPTIONS = [60.0, 70.0, 80.0, 90.0]


# ============================================================================
# Vehicle State
# ============================================================================

@dataclass
class VehicleState:
    """State of a single EV."""
    vehicle_id: int
    node: str = 'A'
    soc: float = 1.0  # 0-1 fraction
    time: float = 0.0  # minutes since start
    finished: bool = False
    failed: bool = False  # SOC went below threshold
    route: List[str] = field(default_factory=lambda: ['A'])
    charging_amounts: Dict[str, float] = field(default_factory=dict)
    speed_levels: Dict[Tuple[str, str], float] = field(default_factory=dict)
    
    def copy(self) -> 'VehicleState':
        return VehicleState(
            vehicle_id=self.vehicle_id,
            node=self.node,
            soc=self.soc,
            time=self.time,
            finished=self.finished,
            failed=self.failed,
            route=list(self.route),
            charging_amounts=dict(self.charging_amounts),
            speed_levels=dict(self.speed_levels)
        )


# ============================================================================
# Station Queue State
# ============================================================================

@dataclass  
class StationQueue:
    """Queue state for a charging station."""
    station_id: str
    max_plugs: int = 1
    busy_until: List[float] = field(default_factory=list)  # Time when each plug becomes free
    
    def get_busy_plugs(self, current_time: float) -> int:
        """Count plugs that are still busy."""
        return sum(1 for t in self.busy_until if t > current_time)
    
    def get_wait_time(self, current_time: float) -> float:
        """Get wait time if arriving now."""
        if self.get_busy_plugs(current_time) < self.max_plugs:
            return 0.0
        # Wait for earliest plug to free
        future_times = [t for t in self.busy_until if t > current_time]
        if not future_times:
            return 0.0
        return min(future_times) - current_time
    
    def occupy_plug(self, start_time: float, duration: float):
        """Occupy a plug starting at start_time for duration minutes."""
        end_time = start_time + duration
        
        # Find first available plug
        for i, t in enumerate(self.busy_until):
            if t <= start_time:
                self.busy_until[i] = end_time
                return
        
        # All plugs busy, this shouldn't happen if wait_time was respected
        if len(self.busy_until) < self.max_plugs:
            self.busy_until.append(end_time)
        else:
            # Wait was not properly accounted, extend earliest
            idx = self.busy_until.index(min(self.busy_until))
            actual_start = max(start_time, self.busy_until[idx])
            self.busy_until[idx] = actual_start + duration


# ============================================================================
# EV Routing Environment
# ============================================================================

class EVRoutingEnv:
    """
    Event-driven EV Fleet Routing environment.
    
    The environment advances time to the next "decision event":
    - Vehicle arrives at a fork (route choice)
    - Vehicle arrives at a station (charging choice)
    
    State includes:
    - Per-vehicle: node, SOC, time
    - Per-station: queue length, busy ratio
    - Global: active vehicle, current makespan, total cost
    """
    
    def __init__(
        self,
        params: DoubleForkParams = None,
        alpha: float = 1.0,  # Makespan weight
        beta: float = 0.1,   # Cost weight
        soc_min: float = 0.02,  # Failure threshold (lowered for more leeway)
        step_penalty: float = 0.01,  # Per-step shaping (reduced from 0.05)
    ):
        self.params = params or make_double_fork_params()
        self.alpha = alpha
        self.beta = beta
        self.soc_min = soc_min
        self.step_penalty = step_penalty
        
        self.n_vehicles = self.params.m
        self.n_stations = len(STATIONS)
        
        # State dimensions
        self.state_dim = self._compute_state_dim()
        
        # Action dimensions (max actions at any decision point)
        self.n_route_actions = 2  # At forks
        self.n_soc_targets = len(SOC_TARGETS)
        self.n_speeds = len(SPEED_OPTIONS)
        self.n_station_actions = self.n_soc_targets * self.n_speeds
        self.n_actions = max(self.n_route_actions, self.n_station_actions)
        
        self.reset()
    
    def _compute_state_dim(self) -> int:
        """Compute state vector dimension."""
        # Per vehicle: node_id (1) + soc (1) + time (1) = 3
        vehicle_dim = self.n_vehicles * 3
        # Per station: queue (1) + busy_ratio (1) = 2
        station_dim = self.n_stations * 2
        # Global: active_vehicle (1) + makespan (1) + total_cost (1) = 3
        global_dim = 3
        return vehicle_dim + station_dim + global_dim
    
    def reset(self, seed: Optional[int] = None) -> np.ndarray:
        """Reset environment to initial state."""
        if seed is not None:
            np.random.seed(seed)
        
        # Initialize vehicles
        self.vehicles: List[VehicleState] = []
        for i in range(self.n_vehicles):
            v = VehicleState(
                vehicle_id=i,
                node='A',
                soc=self.params.soc0[i],
                time=0.0
            )
            self.vehicles.append(v)
        
        # Initialize station queues
        self.queues: Dict[str, StationQueue] = {}
        for station in STATIONS:
            plugs = self.params.station_plugs.get(station, 1)
            self.queues[station] = StationQueue(
                station_id=station,
                max_plugs=plugs,
                busy_until=[0.0] * plugs
            )
        
        # Global tracking
        self.total_cost = 0.0
        self.active_vehicle = 0
        self.done = False
        self.decision_type = 'start'  # 'fork' or 'station' or 'start'
        
        # Find first decision
        self._advance_to_next_decision()
        
        return self._get_state()
    
    def _get_state(self) -> np.ndarray:
        """Convert current state to numpy array."""
        state = []
        
        # Per-vehicle features
        for v in self.vehicles:
            state.append(NODE_TO_IDX[v.node] / len(NODES))  # Normalized node
            state.append(v.soc)  # SOC as fraction
            state.append(v.time / 300.0)  # Normalized time (assume max 300 min)
        
        # Per-station features
        current_time = max(v.time for v in self.vehicles)
        for station in STATIONS:
            q = self.queues[station]
            busy = q.get_busy_plugs(current_time)
            state.append(busy / q.max_plugs)  # Busy ratio
            state.append(q.get_wait_time(current_time) / 60.0)  # Normalized wait
        
        # Global features
        state.append(self.active_vehicle / self.n_vehicles)
        state.append(self._get_current_makespan() / 300.0)
        state.append(self.total_cost / 1000.0)  # Normalized cost
        
        return np.array(state, dtype=np.float32)
    
    def _get_current_makespan(self) -> float:
        """Get current makespan (max time among finished vehicles)."""
        times = [v.time for v in self.vehicles if v.finished]
        return max(times) if times else 0.0
    
    def _advance_to_next_decision(self):
        """
        Advance simulation to the next decision point.
        Sets self.active_vehicle and self.decision_type.
        """
        # Find unfinished vehicles
        pending = [(i, v) for i, v in enumerate(self.vehicles) 
                   if not v.finished and not v.failed]
        
        if not pending:
            self.done = True
            return
        
        # Find vehicle at earliest time that needs a decision
        for vid, v in sorted(pending, key=lambda x: x[1].time):
            node = v.node
            
            # Is this a decision point?
            if node in FORKS:
                self.active_vehicle = vid
                self.decision_type = 'fork'
                return
            elif node in STATIONS:
                self.active_vehicle = vid
                self.decision_type = 'station'
                return
            else:
                # Auto-advance (no decision needed)
                next_nodes = GRAPH.get(node, [])
                if len(next_nodes) == 1:
                    next_node = next_nodes[0]
                    edge = (node, next_node)
                    # Use valid speed within edge bounds
                    min_spd, max_spd = self.params.get_edge_speed_bounds(edge)
                    valid_speed = min(max_spd, max(min_spd, 60.0))  # Use 60 km/h or edge limits
                    self._move_vehicle(vid, next_node, speed=valid_speed, charge_target=None)
                elif len(next_nodes) == 0:
                    # At B - mark finished
                    v.finished = True
        
        # Recurse to find next decision
        pending = [(i, v) for i, v in enumerate(self.vehicles) 
                   if not v.finished and not v.failed]
        if pending:
            self._advance_to_next_decision()
        else:
            self.done = True
    
    def _move_vehicle(
        self, 
        vid: int, 
        next_node: str, 
        speed: float,
        charge_target: Optional[float]
    ) -> float:
        """
        Move vehicle to next node, optionally charging first.
        Returns cost incurred.
        """
        v = self.vehicles[vid]
        current_node = v.node
        edge = (current_node, next_node)
        
        battery_kwh = self.params.battery_kwh[vid]
        cost = 0.0
        
        # Charging (if at station and target set)
        if current_node in STATIONS and charge_target is not None and charge_target > v.soc:
            # Calculate charging time
            energy_needed = (charge_target - v.soc) * battery_kwh
            
            # Wait for plug
            wait_time = self.queues[current_node].get_wait_time(v.time)
            v.time += wait_time
            
            # Charge (simplified: assume average power)
            max_power = self.params.station_max_kw.get(current_node, 50.0)
            avg_power = min(max_power, 80.0)  # Simplified
            charge_time = (energy_needed / avg_power) * 60.0  # minutes
            
            # Occupy plug
            self.queues[current_node].occupy_plug(v.time, charge_time)
            v.time += charge_time
            
            # Update SOC
            v.soc = charge_target
            v.charging_amounts[current_node] = energy_needed
            
            # Cost
            price = self.params.station_price.get(current_node, 15.0)
            cost = energy_needed * price
            self.total_cost += cost
        
        # Travel to next node
        if edge in self.params.edges_distance_km:
            travel_time = self.params.get_edge_time(edge, speed)
            energy = self.params.get_edge_energy(edge, speed)
            energy_frac = energy / battery_kwh
            
            v.time += travel_time
            v.soc -= energy_frac
            v.route.append(next_node)
            v.speed_levels[edge] = speed
            
            # Check for failure
            if v.soc < self.soc_min:
                v.failed = True
        
        v.node = next_node
        
        if next_node == 'B':
            v.finished = True
        
        return cost
    
    def get_valid_actions(self) -> List[int]:
        """Get list of valid action indices for current decision."""
        v = self.vehicles[self.active_vehicle]
        valid = []
        
        if self.decision_type == 'fork':
            # Check which route options lead to viable charging opportunities
            # For simplicity, both are valid (agent will learn which is better)
            valid = [0, 1]
        
        elif self.decision_type == 'station':
            # Check which SOC targets are valid
            next_nodes = GRAPH.get(v.node, [])
            if not next_nodes:
                return [0]  # No next edge
            
            next_node = next_nodes[0]
            edge = (v.node, next_node)
            battery_kwh = self.params.battery_kwh[v.vehicle_id]
            
            for soc_idx, target_soc in enumerate(SOC_TARGETS):
                for speed_idx, speed in enumerate(SPEED_OPTIONS):
                    action_id = soc_idx * len(SPEED_OPTIONS) + speed_idx
                    
                    # Calculate actual target (can only increase SOC)
                    actual_target = max(v.soc, target_soc)
                    
                    # Check if can reach next node with buffer
                    if edge in self.params.edges_distance_km:
                        energy = self.params.get_edge_energy(edge, speed)
                        energy_frac = energy / battery_kwh
                        final_soc = actual_target - energy_frac
                        
                        # Need at least 10% SOC after travel for safety
                        if final_soc >= 0.10:
                            valid.append(action_id)
            
            if not valid:
                # No valid actions - force max charging with slowest speed
                # This gives the best chance of survival
                valid = [len(SOC_TARGETS) * len(SPEED_OPTIONS) - len(SPEED_OPTIONS)]  # 90% SOC, slowest speed
        
        return valid
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Execute action and return (next_state, reward, done, info).
        """
        v = self.vehicles[self.active_vehicle]
        reward = -self.step_penalty  # Base step penalty
        
        if self.decision_type == 'fork':
            # Route choice: 0 = upper, 1 = lower
            node = v.node
            upper, lower = FORKS[node]
            next_node = upper if action == 0 else lower
            
            # Move to first station on chosen branch (use valid speed for edge)
            edge = (node, next_node)
            min_spd, max_spd = self.params.get_edge_speed_bounds(edge)
            valid_speed = min(max_spd, max(min_spd, 60.0))  # Use 60 km/h or edge limits
            self._move_vehicle(self.active_vehicle, next_node, speed=valid_speed, charge_target=None)
        
        elif self.decision_type == 'station':
            # Decode action: soc_idx * n_speeds + speed_idx
            soc_idx = action // len(SPEED_OPTIONS)
            speed_idx = action % len(SPEED_OPTIONS)
            
            target_soc = SOC_TARGETS[soc_idx]
            speed = SPEED_OPTIONS[speed_idx]
            
            # Get next node
            next_nodes = GRAPH.get(v.node, [])
            if next_nodes:
                next_node = next_nodes[0]
                charge_target = max(v.soc, target_soc) if target_soc > 0 else None
                self._move_vehicle(self.active_vehicle, next_node, speed, charge_target)
        
        # Check for failure
        if v.failed:
            reward = -1000.0
            self.done = True
            return self._get_state(), reward, True, {'success': False}
        
        # Advance to next decision
        self._advance_to_next_decision()
        
        # Terminal reward
        if self.done:
            all_finished = all(v.finished for v in self.vehicles)
            if all_finished:
                makespan = max(v.time for v in self.vehicles)
                # IMPROVED REWARD SHAPING: Normalize by typical values
                # Typical makespan: ~200-300 min, typical cost: ~500-1000 EGP
                normalized_makespan = makespan / 300.0  # Normalize to ~1.0 scale
                normalized_cost = self.total_cost / 1000.0  # Normalize to ~1.0 scale
                
                # Weighted reward with normalization
                reward = -self.alpha * normalized_makespan - self.beta * normalized_cost
                
                # Add small bonus for success to encourage completion
                reward += 10.0
                
                return self._get_state(), reward, True, {
                    'success': True,
                    'makespan': makespan,
                    'total_cost': self.total_cost
                }
            else:
                reward = -1000.0
                return self._get_state(), reward, True, {'success': False}
        
        return self._get_state(), reward, False, {}
    
    def get_solution(self) -> Dict:
        """Extract solution in format compatible with FleetSolution."""
        return {
            'vehicles': [
                {
                    'vehicle_id': v.vehicle_id,
                    'route': v.route,
                    'charging_amounts': v.charging_amounts,
                    'speed_levels': v.speed_levels,
                    'completion_time': v.time
                }
                for v in self.vehicles
            ],
            'makespan': max(v.time for v in self.vehicles),
            'total_cost': self.total_cost
        }


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    env = EVRoutingEnv()
    state = env.reset(seed=42)
    print(f"State dim: {env.state_dim}")
    print(f"Initial state shape: {state.shape}")
    print(f"N actions: {env.n_actions}")
    
    # Random rollout
    done = False
    total_reward = 0
    steps = 0
    while not done:
        valid = env.get_valid_actions()
        action = np.random.choice(valid)
        state, reward, done, info = env.step(action)
        total_reward += reward
        steps += 1
        if steps > 100:
            break
    
    print(f"Steps: {steps}, Total reward: {total_reward:.2f}")
    print(f"Info: {info}")
