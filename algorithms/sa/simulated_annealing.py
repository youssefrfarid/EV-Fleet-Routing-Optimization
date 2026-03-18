"""
simulated_annealing.py

Simulated annealing optimiser for the EV fleet routing problem.

The optimiser operates directly on the decision variables encoded in
`VehiclePlan` objects (routes, charging amounts, speed levels) and builds
`FleetSolution` objects for evaluation.  It reuses the feasibility checks
and objective functions provided in `objectives.py`.
"""

from __future__ import annotations

import sys
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib.pyplot as plt

# Allow running directly via `python algorithms/sa/simulated_annealing.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.objectives import (
    FleetSolution,
    VehicleSolution,
    objective_weighted,
    process_station_queues,
)
from common.params import SingleForkParams, DoubleForkParams, make_toy_params, make_double_fork_params


Edge = Tuple[str, str]


# Default Single Fork Routes
SINGLE_FORK_UPPER: Sequence[str] = ("A", "J", "S1", "S2", "M", "B")
SINGLE_FORK_LOWER: Sequence[str] = ("A", "J", "S3", "M", "B")

# Double Fork Routes (4 options)
# U-U: Upper 1 -> Upper 2
DOUBLE_FORK_UU: Sequence[str] = ("A", "J1", "S1", "S2", "M1", "J2", "S4", "S5", "M2", "B")
# U-L: Upper 1 -> Lower 2
DOUBLE_FORK_UL: Sequence[str] = ("A", "J1", "S1", "S2", "M1", "J2", "S6", "M2", "B")
# L-U: Lower 1 -> Upper 2
DOUBLE_FORK_LU: Sequence[str] = ("A", "J1", "S3", "M1", "J2", "S4", "S5", "M2", "B")
# L-L: Lower 1 -> Lower 2
DOUBLE_FORK_LL: Sequence[str] = ("A", "J1", "S3", "M1", "J2", "S6", "M2", "B")

# Legacy constants for backward compatibility (mapped to single fork)
UPPER_ROUTE = SINGLE_FORK_UPPER
LOWER_ROUTE = SINGLE_FORK_LOWER


@dataclass
class VehiclePlan:
    """Lightweight representation of a vehicle's decisions."""

    vehicle_id: int
    route: List[str]
    charging_amounts: Dict[str, float]
    speed_levels: Dict[Edge, float]  # Continuous speed in km/h

    def copy(self) -> "VehiclePlan":
        return VehiclePlan(
            vehicle_id=self.vehicle_id,
            route=list(self.route),
            charging_amounts=dict(self.charging_amounts),
            speed_levels=dict(self.speed_levels),
        )


@dataclass
class SAResult:
    best_solution: FleetSolution
    best_cost: float
    history: List[Tuple[int, float, float]] = field(default_factory=list)
    temperature_trace: List[float] = field(default_factory=list)


def plans_from_solution(solution: FleetSolution) -> List[VehiclePlan]:
    """Extract vehicle plans from an existing FleetSolution."""
    plans: List[VehiclePlan] = []
    for vs in solution.vehicle_solutions:
        plans.append(
            VehiclePlan(
                vehicle_id=vs.vehicle_id,
                route=list(vs.route),
                charging_amounts=dict(vs.charging_amounts),
                speed_levels=dict(vs.speed_levels or {}),
            )
        )
    return plans


def build_solution_from_plans(
    plans: Sequence[VehiclePlan], params: SingleForkParams
) -> FleetSolution:
    """Create a FleetSolution from high-level plans."""
    vehicle_solutions: List[VehicleSolution] = []

    for plan in plans:
        vs = _build_vehicle_solution(plan, params)
        vehicle_solutions.append(vs)

    solution = FleetSolution(
        vehicle_solutions=vehicle_solutions, params=params)
    solution = process_station_queues(solution, params)

    # Propagate travel times after queue adjustments so arrival/departure timelines remain consistent.
    for vs in solution.vehicle_solutions:
        _propagate_timeline(vs, params)

    return solution


def _build_vehicle_solution(
    plan: VehiclePlan, params: SingleForkParams
) -> VehicleSolution:
    """Construct a VehicleSolution from a VehiclePlan."""
    route = list(plan.route)
    speed_levels = dict(plan.speed_levels)
    charging_amounts = dict(plan.charging_amounts)
    charging_stations: List[str] = list(charging_amounts.keys())

    battery_kwh = params.battery_kwh[plan.vehicle_id]
    soc0 = params.soc0[plan.vehicle_id]
    energy = battery_kwh * soc0

    arrival_times: Dict[str, float] = {route[0]: 0.0}
    departure_times: Dict[str, float] = {route[0]: 0.0}
    soc_at_nodes: Dict[str, float] = {route[0]: soc0}
    charging_start_times: Dict[str, float] = {}

    for idx in range(len(route) - 1):
        u = route[idx]
        v = route[idx + 1]
        edge = (u, v)
        level = speed_levels.get(edge, 3)

        travel_time = params.get_edge_time(edge, level)
        energy_use = params.get_edge_energy(edge, level)

        arrival = departure_times[u] + travel_time
        arrival_times[v] = arrival

        energy -= energy_use
        soc = energy / battery_kwh
        soc_at_nodes[v] = soc

        departure = arrival
        if v in charging_amounts:
            charge = charging_amounts[v]
            soc_after = soc + charge / battery_kwh
            charge_minutes = (
                params.charge_time_seconds(
                    soc, soc_after, battery_kwh, v) / 60.0
            )
            departure = arrival + charge_minutes
            energy += charge
            charging_start_times[v] = arrival

        departure_times[v] = departure

    return VehicleSolution(
        vehicle_id=plan.vehicle_id,
        route=route,
        charging_stations=charging_stations,
        charging_amounts=charging_amounts,
        arrival_times=arrival_times,
        departure_times=departure_times,
        soc_at_nodes=soc_at_nodes,
        charging_start_times=charging_start_times or None,
        speed_levels=speed_levels or None,
    )


def _propagate_timeline(vs: VehicleSolution, params: SingleForkParams) -> None:
    """After queue adjustments, recompute downstream arrival/departure times."""
    route = vs.route
    vs.arrival_times[route[0]] = vs.arrival_times.get(route[0], 0.0)
    vs.departure_times[route[0]] = vs.departure_times.get(route[0], 0.0)

    for i in range(len(route) - 1):
        current = route[i]
        nxt = route[i + 1]
        edge = (current, nxt)
        level = vs.get_speed_level(edge)

        travel_time = params.get_edge_time(edge, level)
        depart_current = vs.departure_times[current]
        arrival_next = depart_current + travel_time
        vs.arrival_times[nxt] = arrival_next

        if nxt in vs.charging_stations:
            start = (
                vs.charging_start_times.get(nxt)
                if vs.charging_start_times
                else None
            )
            if start is None or start < arrival_next:
                if vs.charging_start_times is not None:
                    vs.charging_start_times[nxt] = arrival_next
                start = arrival_next
            departure = max(vs.departure_times.get(nxt, start), start)
            vs.departure_times[nxt] = departure
        else:
            vs.departure_times[nxt] = arrival_next

    final_node = route[-1]
    vs.departure_times[final_node] = vs.arrival_times[final_node]


def create_initial_plans(
    params: SingleForkParams,
    rng: random.Random | None = None,
    *,
    randomize: bool = False,
    random_steps: int = 40,
) -> List[VehiclePlan]:
    """Seed plans derived from example objectives configuration or randomise them."""
    base_solution = build_solution_from_plans(
        _generate_random_initial_plans(params, rng), params)
    feasible, _, _ = base_solution.is_feasible(return_reason=True)
    if not feasible:
        raise RuntimeError("Baseline configuration is infeasible.")

    base_plans = plans_from_solution(base_solution)

    if not randomize or random_steps <= 0:
        return base_plans

    if rng is None:
        rng = random.Random()

    plans = [plan.copy() for plan in base_plans]
    for _ in range(random_steps):
        candidate_pair = _generate_feasible_candidate(plans, params, rng)
        if candidate_pair is None:
            continue
        candidate_plans, _ = candidate_pair
        plans = [plan.copy() for plan in candidate_plans]

    return plans


def _get_valid_routes(params: SingleForkParams) -> List[List[str]]:
    """Get valid routes based on params type."""
    if isinstance(params, DoubleForkParams):
        return [list(r) for r in [DOUBLE_FORK_UU, DOUBLE_FORK_UL, DOUBLE_FORK_LU, DOUBLE_FORK_LL]]
    else:
        return [list(r) for r in [SINGLE_FORK_UPPER, SINGLE_FORK_LOWER]]


def _generate_random_initial_plans(params: SingleForkParams, rng: random.Random | None = None) -> List[VehiclePlan]:
    """Generate random but FEASIBLE initial plans for all vehicles.
    
    Instead of a hardcoded baseline, this creates plans dynamically:
    1. Assigns random valid route (Upper/Lower)
    2. Assigns conservative speeds to save energy
    3. Calculates exact energy needs
    4. Assigns charging amounts to cover deficits + buffer
    """
    if rng is None:
        rng = random.Random()
        
    plans = []
    valid_routes = _get_valid_routes(params)
    
    for v_id in range(params.m):
        # 1. Choose random route
        route = rng.choice(valid_routes)
        
        # 2. Assign conservative speeds (min speed + small buffer)
        # Slower speeds = less energy = easier to be feasible
        speed_levels = {}
        for i in range(len(route) - 1):
            u, v = route[i], route[i+1]
            edge = (u, v)
            min_s, max_s = params.get_edge_speed_bounds(edge)
            # Pick speed in lower 30% of range to be energy efficient
            speed = min_s + rng.random() * 0.3 * (max_s - min_s)
            speed_levels[edge] = speed
            
        # 3. Calculate energy needs and assign charging
        # We simulate the journey to find deficits
        battery_cap = params.battery_kwh[v_id]
        current_soc = params.soc0[v_id]
        current_kwh = battery_cap * current_soc
        min_kwh = battery_cap * 0.10  # 10% reserve
        
        charging_amounts = {}
        
        # Identify charging stations on route
        stations_on_route = [node for node in route if node in params.station_plugs]
        
        # Simple heuristic: check energy to reach next station/dest
        # If deficit, charge at current station
        
        # We need a more robust way: 
        # Calculate total energy needed for the whole trip at chosen speeds
        total_energy_needed = 0.0
        segment_energies = []
        
        for i in range(len(route) - 1):
            u, v = route[i], route[i+1]
            edge = (u, v)
            energy = params.get_edge_energy(edge, speed_levels[edge])
            segment_energies.append(energy)
            total_energy_needed += energy
            
        # Initial deficit?
        # We have current_kwh. We need total_energy_needed + min_kwh (at end)
        # But we also need to maintain min_kwh throughout.
        
        # Let's simulate step by step
        sim_kwh = current_kwh
        
        for i in range(len(route) - 1):
            u, v = route[i], route[i+1]
            
            # If we are at a station, check if we need to charge for the REST of the trip
            if u in params.station_plugs:
                # Energy needed for rest of trip
                rest_energy = sum(segment_energies[i:])
                
                # Target: arrive at dest with >10%
                # Also need to reach next station with >10% (simplified: just cover rest)
                
                # If we don't charge, we have sim_kwh.
                # We need sim_kwh - rest_energy >= min_kwh
                
                # If deficit, charge!
                if sim_kwh - rest_energy < min_kwh + 2.0: # 2.0 kWh extra buffer
                    # How much to charge?
                    # Aim to fill up to cover rest + buffer, but max 95% SOC
                    target_kwh = rest_energy + min_kwh + 5.0 # Healthy buffer
                    needed = target_kwh - sim_kwh
                    
                    # Cap at battery capacity (leave room for regen/errors? no regen here)
                    max_charge = (battery_cap * 0.95) - sim_kwh
                    
                    amount = min(needed, max_charge)
                    amount = max(0.0, amount)
                    
                    if amount > 0.1:
                        charging_amounts[u] = amount
                        sim_kwh += amount
            
            # Consume energy for this edge
            energy = segment_energies[i]
            sim_kwh -= energy
            
            # If we drop below min_kwh, this random plan failed (speeds too high or battery too small)
            # But with conservative speeds and charging, it should work.
            # If it fails here, we might need to retry or pick even slower speeds.
            
        plans.append(VehiclePlan(
            vehicle_id=v_id,
            route=route,
            charging_amounts=charging_amounts,
            speed_levels=speed_levels
        ))
        
    return plans


def random_neighbor(
    plans: Sequence[VehiclePlan], params: SingleForkParams, rng: random.Random
) -> List[VehiclePlan]:
    """Produce a neighbour solution by mutating a random vehicle plan."""
    new_plans = [plan.copy() for plan in plans]
    plan = rng.choice(new_plans)

    move = rng.choice(
        [
            "speed_step",
            "speed_random",
            "charge_tweak",
            "charge_random",
            "route_toggle",
            "route_shuffle",
            "station_add",
            "station_remove",
        ]
    )

    if move == "speed_step":
        _mutate_speed_step(plan, params, rng)
    elif move == "speed_random":
        _mutate_speed_random(plan, params, rng)
    elif move == "charge_tweak":
        _mutate_charge_step(plan, params, rng)
    elif move == "charge_random":
        _mutate_charge_random(plan, params, rng)
    elif move == "route_toggle":
        _mutate_route_toggle(plan, params, rng)
    elif move == "route_shuffle":
        _mutate_route_shuffle(plan, params, rng)
    elif move == "station_add":
        _mutate_station_add(plan, params, rng)
    elif move == "station_remove":
        _mutate_station_remove(plan, rng)

    _ensure_speed_defaults(plan, params)
    return new_plans


def _mutate_speed_step(plan: VehiclePlan, params: SingleForkParams, rng: random.Random) -> None:
    """Perturb speed by a small random amount."""
    if not plan.speed_levels:
        return
    
    edge = rng.choice(list(plan.speed_levels.keys()))
    current_speed = plan.speed_levels[edge]
    
    # Small perturbation ±10 km/h
    delta = rng.uniform(-10.0, 10.0)
    new_speed = current_speed + delta
    
    # Clamp to edge-specific valid range
    min_speed, max_speed = params.get_edge_speed_bounds(edge)
    new_speed = max(min_speed, min(max_speed, new_speed))
    plan.speed_levels[edge] = round(new_speed, 1)


def _mutate_speed_random(plan: VehiclePlan, params: SingleForkParams, rng: random.Random) -> None:
    """Set speed to a random value within valid range for that edge."""
    edges = list(plan.speed_levels.keys())
    if not edges:
        return
    
    edge = rng.choice(edges)
    # Random speed in edge-specific [min, max]
    min_speed, max_speed = params.get_edge_speed_bounds(edge)
    new_speed = rng.uniform(min_speed, max_speed)
    plan.speed_levels[edge] = round(new_speed, 1)


def _mutate_charge_step(
    plan: VehiclePlan, params: SingleForkParams, rng: random.Random
) -> None:
    if not plan.charging_amounts:
        return
    station = rng.choice(list(plan.charging_amounts.keys()))
    battery = params.battery_kwh[plan.vehicle_id]
    current = plan.charging_amounts[station]
    delta = rng.uniform(-4.0, 4.0)
    updated = max(1.0, min(current + delta, battery * 0.9))
    plan.charging_amounts[station] = round(updated, 2)


def _mutate_charge_random(
    plan: VehiclePlan, params: SingleForkParams, rng: random.Random
) -> None:
    station = _ensure_station_exists(plan, params, rng)
    battery = params.battery_kwh[plan.vehicle_id]
    plan.charging_amounts[station] = round(rng.uniform(1.0, battery * 0.9), 2)


def _mutate_route_toggle(
    plan: VehiclePlan, params: SingleForkParams, rng: random.Random
) -> None:
    """Switch to a random different valid route."""
    valid_routes = _get_valid_routes(params)
    # Filter out current route if possible
    candidates = [r for r in valid_routes if r != plan.route]
    if not candidates:
        candidates = valid_routes
        
    new_route = rng.choice(candidates)
    plan.route = new_route
    
    # Reset charging and speeds for new route
    plan.charging_amounts = {}
    plan.speed_levels = {}
    
    # Add at least one station if available
    stations = [n for n in new_route if n in params.station_plugs]
    if stations:
        s = rng.choice(stations)
        plan.charging_amounts[s] = 15.0 # Default amount
        
    _ensure_speed_defaults(plan, params)


def _mutate_route_shuffle(
    plan: VehiclePlan, params: SingleForkParams, rng: random.Random
) -> None:
    """Randomise speeds and charge defaults for the current route."""
    # Randomize charging amounts
    for station in list(plan.charging_amounts.keys()):
         plan.charging_amounts[station] = round(
            rng.uniform(5.0, params.battery_kwh[plan.vehicle_id] * 0.8), 2
        )
         
    # Randomize speeds
    for edge in plan.speed_levels:
        min_s, max_s = params.get_edge_speed_bounds(edge)
        plan.speed_levels[edge] = round(rng.uniform(min_s, max_s), 1)


def _mutate_station_add(
    plan: VehiclePlan, params: SingleForkParams, rng: random.Random
) -> None:
    """Add a charging stop for the current route if possible."""
    battery = params.battery_kwh[plan.vehicle_id]
    
    # Find stations on route not currently used
    stations_on_route = [n for n in plan.route if n in params.station_plugs]
    candidates = [s for s in stations_on_route if s not in plan.charging_amounts]
    
    if not candidates:
        # Already using all stations, maybe increase amount?
        if plan.charging_amounts:
            s = rng.choice(list(plan.charging_amounts.keys()))
            plan.charging_amounts[s] = min(battery*0.9, plan.charging_amounts[s] + 5.0)
        return

    station = rng.choice(candidates)
    plan.charging_amounts[station] = round(
        rng.uniform(6.0, battery * 0.6), 2
    )


def _mutate_station_remove(plan: VehiclePlan, rng: random.Random) -> None:
    """Remove a charging station if more than one is present."""
    if len(plan.charging_amounts) <= 1:
        return
    station = rng.choice(list(plan.charging_amounts.keys()))
    del plan.charging_amounts[station]


def _ensure_speed_defaults(plan: VehiclePlan, params: SingleForkParams) -> None:
    """Ensure every edge in the route has a speed entry."""
    for u, v in zip(plan.route[:-1], plan.route[1:]):
        edge = (u, v)
        if edge not in plan.speed_levels:
            plan.speed_levels[edge] = params.speed_reference  # Default to 80.0 km/h


def _generate_feasible_candidate(
    current_plans: Sequence[VehiclePlan],
    params: SingleForkParams,
    rng: random.Random,
    max_attempts: int = 32,
) -> Tuple[List[VehiclePlan], FleetSolution] | None:
    """
    Produce a feasible neighbour by repeatedly mutating and repairing.
    Returns (plans, solution) pair or None if max_attempts exceeded.
    """
    for _ in range(max_attempts):
        candidate_plans = random_neighbor(current_plans, params, rng)

        for repair_round in range(6):
            candidate_solution = build_solution_from_plans(
                candidate_plans, params)
            feasible, code, _ = candidate_solution.is_feasible(
                return_reason=True)
            if feasible:
                return candidate_plans, candidate_solution

            if not _repair_plans_for_reason(candidate_plans, code, params, rng):
                break

        # retry with new random mutation if repairs failed
    return None


def _repair_plans_for_reason(
    plans: List[VehiclePlan],
    code: int,
    params: SingleForkParams,
    rng: random.Random,
) -> bool:
    """
    Apply a lightweight repair based on feasibility code.
    Returns True if a modification was made, False otherwise.
    """
    plan = rng.choice(plans)

    if code in {2, 3}:  # SOC / energy balance -> increase charge
        station = _ensure_station_exists(plan, params, rng)
        battery = params.battery_kwh[plan.vehicle_id]
        current = plan.charging_amounts.get(station, 0.0)
        plan.charging_amounts[station] = round(
            min(current + 6.0, battery * 0.9), 2)
        return True

    if code == 5:  # charging limits exceeded -> clamp charge
        for station in list(plan.charging_amounts.keys()):
            battery = params.battery_kwh[plan.vehicle_id]
            plan.charging_amounts[station] = round(
                min(plan.charging_amounts[station], battery * 0.85), 2
            )
        return True

    if code == 6:  # negative values
        for station, amount in plan.charging_amounts.items():
            if amount < 0:
                plan.charging_amounts[station] = max(1.0, abs(amount))
        return True

    if code == 7:  # invalid speed choice
        for edge, level in list(plan.speed_levels.items()):
            # Clamp to valid range
            min_s, max_s = params.get_edge_speed_bounds(edge)
            plan.speed_levels[edge] = max(min_s, min(max_s, level))
        _ensure_speed_defaults(plan, params)
        return True

    if code == 8:  # station capacity -> switch route or redistribute
        if rng.random() < 0.5:
            _mutate_route_toggle(plan, params, rng)
        else:
            _mutate_route_shuffle(plan, params, rng)
        return True

    if code == 4:  # time consistency -> slow down on a random edge
        if plan.speed_levels:
            edge = rng.choice(list(plan.speed_levels.keys()))
            plan.speed_levels[edge] = max(params.speed_min_default, plan.speed_levels[edge] - 10.0)
        return True

    if code == 1:  # invalid route -> reset to default
        valid_routes = _get_valid_routes(params)
        plan.route = rng.choice(valid_routes)
        plan.charging_amounts = {} # Reset charging
        _ensure_station_exists(plan, params, rng) # Add at least one
        _ensure_speed_defaults(plan, params)
        return True

    return False


def _ensure_station_exists(
    plan: VehiclePlan, params: SingleForkParams, rng: random.Random
) -> str:
    """Ensure plan has at least one charging station, returning the chosen station."""
    if plan.charging_amounts:
        return rng.choice(list(plan.charging_amounts.keys()))

    # Find stations on current route
    stations_on_route = [n for n in plan.route if n in params.station_plugs]
    
    if stations_on_route:
        station = rng.choice(stations_on_route)
        plan.charging_amounts = {station: 15.0}
        return station
        
    return "" # Should not happen in our networks


def simulated_annealing(
    params: SingleForkParams,
    *,
    initial_plans: Sequence[VehiclePlan] | None = None,
    random_initial: bool = False,
    initial_random_steps: int = 40,
    temperature_start: float = 60.0,
    temperature_end: float = 0.5,
    cooling_rate: float = 0.92,
    iterations_per_temp: int = 30,
    max_iterations: int = 2000,
    objective_fn=objective_weighted,
    seed: int | None = None,
    verbose: bool = True,
    iteration_callback=None,
    show_plots: bool = True,
) -> SAResult:
    """Run simulated annealing over the fleet solution space."""
    rng = random.Random(seed)
    random.seed(seed)

    if initial_plans is None:
        initial_plans = create_initial_plans(
            params,
            rng=rng,
            randomize=random_initial,
            random_steps=initial_random_steps,
        )

    current_plans = [plan.copy() for plan in initial_plans]
    current_solution = build_solution_from_plans(current_plans, params)
    feasible, code, message = current_solution.is_feasible(return_reason=True)
    if not feasible:
        # If initial is infeasible, try to repair it immediately
        print(f"⚠️ Initial solution infeasible ({message}). Attempting repair...")
        repaired = _generate_feasible_candidate(current_plans, params, rng, max_attempts=100)
        if repaired:
            current_plans, current_solution = repaired
            print("✅ Initial solution repaired.")
        else:
            print("❌ Could not repair initial solution. Proceeding with infeasible start (SA might fix it).")

    current_cost = objective_fn(current_solution)

    best_solution = current_solution
    best_cost = current_cost

    history: List[Tuple[int, float, float]] = []
    temperature_trace: List[float] = []

    iteration = 0
    temperature = temperature_start

    while temperature > temperature_end and iteration < max_iterations:
        if verbose:
            print(f"\n🔥 Temperature {temperature:.3f}")

        temperature_trace.append(temperature)

        inner_iterations = 0
        failed_neighbors = 0
        max_failed_neighbors = iterations_per_temp * 4

        while inner_iterations < iterations_per_temp:
            if iteration >= max_iterations:
                break

            candidate_pair = _generate_feasible_candidate(
                current_plans, params, rng
            )

            if candidate_pair is None:
                failed_neighbors += 1
                if failed_neighbors >= max_failed_neighbors:
                    if verbose:
                        print(
                            "  ⚠️  Aborting temperature step after repeated infeasible neighbours"
                        )
                    break
                continue

            failed_neighbors = 0
            iteration += 1
            inner_iterations += 1

            candidate_plans, candidate_solution = candidate_pair
            candidate_cost = objective_fn(candidate_solution)
            delta = candidate_cost - current_cost

            accept = False
            if delta <= 0:
                accept = True
            else:
                probability = math.exp(-delta / max(temperature, 1e-9))
                if rng.random() < probability:
                    accept = True

            if accept:
                current_plans = [plan.copy() for plan in candidate_plans]
                current_solution = candidate_solution
                current_cost = candidate_cost
                if verbose:
                    print(
                        f"  ✔ Accepted move (Δ={delta:.3f}), cost={current_cost:.3f}"
                    )

                if current_cost < best_cost:
                    best_cost = current_cost
                    best_solution = current_solution
                    if verbose:
                        print(
                            f"    🌟 New best solution with cost {best_cost:.3f}"
                        )

            history.append((iteration, temperature, current_cost))
            if iteration_callback is not None:
                iteration_callback(
                    iteration=iteration,
                    temperature=temperature,
                    cost=current_cost,
                    best_cost=best_cost,
                )

        temperature *= cooling_rate

    if verbose:
        print("\n✅ Simulated annealing completed.")
        print(f"Best cost: {best_cost:.3f}")

    if show_plots:
        iterations = [entry[0] for entry in history]
        temps = [entry[1] for entry in history]
        costs = [entry[2] for entry in history]

        fig, (ax_temp, ax_cost) = plt.subplots(
            2, 1, figsize=(10, 8), sharex=False, constrained_layout=True
        )

        ax_temp.plot(iterations, temps,
                     drawstyle="steps-post", color="#1f77b4")
        ax_temp.set_title("Temperature Schedule")
        ax_temp.set_xlabel("Iteration")
        ax_temp.set_ylabel("Temperature")

        ax_cost.plot(iterations, costs, color="orange")
        ax_cost.set_title("Objective Cost over Iterations")
        ax_cost.set_xlabel("Iteration")
        ax_cost.set_ylabel("Weighted Cost")

        plt.show()

    return SAResult(
        best_solution=best_solution,
        best_cost=best_cost,
        history=history,
        temperature_trace=temperature_trace,
    )


def run_demo(
    seed: int | None = None, visualize: bool = True, random_initial: bool = False
) -> SAResult:
    """Convenience helper to run SA on the toy instance (Single Fork)."""
    params = make_toy_params()
    print("🚀 Running Single Fork Demo...")
    result = simulated_annealing(
        params, 
        seed=seed, 
        random_initial=random_initial,
        show_plots=False # Disable plots for automated runs
    )
    
    if visualize:
        from common.visualization import generate_dashboard
        generate_dashboard(result.best_solution, params, "solution_dashboard.html")
        
    return result


def run_double_fork_demo(
    seed: int | None = None, visualize: bool = True, random_initial: bool = True
) -> SAResult:
    """Convenience helper to run SA on the DOUBLE FORK instance."""
    params = make_double_fork_params()
    print("🚀 Running Double Fork Demo...")
    result = simulated_annealing(
        params, 
        seed=seed, 
        random_initial=random_initial,
        show_plots=False
    )
    
    if visualize:
        from common.visualization import generate_dashboard
        generate_dashboard(result.best_solution, params, "double_fork_dashboard.html")
        
    return result


if __name__ == "__main__":
    # By default run the new double fork demo
    run_double_fork_demo(seed=42, visualize=True, random_initial=True)
