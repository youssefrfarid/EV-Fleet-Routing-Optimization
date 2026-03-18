"""
particle_swarm.py

Particle Swarm Optimization (PSO) implementation for the EV fleet routing
problem. The PSO formulation reuses the VehiclePlan representation defined in
simulated_annealing.py to keep compatibility with existing feasibility checks
and visualization helpers.

Highlights:
- Continuous PSO updates for speed selections and charging amounts
- Discrete handling of route choices with occasional adoption from personal /
  global bests plus simulated annealing mutations for exploration
- Compatibility with existing evaluation + repair utilities
"""

from __future__ import annotations

import sys
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

# Allow running directly via `python algorithms/pso/particle_swarm.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.objectives import (
    FleetSolution,
    objective_makespan,
    objective_total_cost,
    objective_weighted,
    process_station_queues,
)
from common.params import SingleForkParams, make_double_fork_params, make_toy_params
from algorithms.sa.simulated_annealing import (
    VehiclePlan,
    _ensure_speed_defaults,
    _ensure_station_exists,
    _generate_random_initial_plans,
    _mutate_charge_random,
    _mutate_charge_step,
    _mutate_route_toggle,
    _mutate_speed_random,
    _mutate_speed_step,
    _mutate_station_add,
    _mutate_station_remove,
    _repair_plans_for_reason,
    build_solution_from_plans,
)

# Large penalty applied to infeasible particles
INFEASIBLE_PENALTY = 1e9


@dataclass
class Particle:
    """Represents a PSO particle (fleet configuration + velocity state)."""

    plans: List[VehiclePlan]
    # Velocity can hold numeric deltas (speed/charge) or swap sequences for routes.
    velocity: Dict[Tuple, object] = field(default_factory=dict)
    best_plans: List[VehiclePlan] = field(default_factory=list)
    best_cost: float = math.inf

    def copy(self) -> "Particle":
        """Deep copy particle state."""
        return Particle(
            plans=[plan.copy() for plan in self.plans],
            velocity={
                key: (list(val) if isinstance(val, list) else val)
                for key, val in self.velocity.items()
            },
            best_plans=[plan.copy() for plan in self.best_plans],
            best_cost=self.best_cost,
        )

    def clone_plans(self) -> List[VehiclePlan]:
        """Return deep copies of the particle's plans."""
        return [plan.copy() for plan in self.plans]


@dataclass
class PSOResult:
    """Container for PSO optimisation results."""

    best_solution: FleetSolution
    best_cost: float
    history: List[Tuple[int, float, float, float]] = field(default_factory=list)
    runtime_seconds: float = 0.0


# ============================================================================
# Helper Functions
# ============================================================================

def evaluate_plans(
    plans: Sequence[VehiclePlan],
    params: SingleForkParams,
    objective_fn: Callable = objective_weighted,
) -> float:
    """
    Evaluate a list of VehiclePlan objects.

    Returns a large penalty if infeasible, otherwise the chosen objective value.
    """
    solution = build_solution_from_plans(plans, params)
    if not solution.is_feasible():
        return INFEASIBLE_PENALTY
    return float(objective_fn(solution))


def _routes_compatible(a: Sequence[str], b: Sequence[str]) -> bool:
    """Return True when two routes are permutations of the same nodes."""
    return len(a) == len(b) and sorted(a) == sorted(b)


def _subtract_permutations(target: Sequence[str], source: Sequence[str]) -> List[Tuple[int, int]]:
    """Return the swap sequence that transforms source into target."""
    if not _routes_compatible(target, source):
        return []

    working = list(source)
    swaps: List[Tuple[int, int]] = []
    for i, desired in enumerate(target):
        if working[i] == desired:
            continue
        try:
            j = working.index(desired)
        except ValueError:
            return []
        swaps.append((i, j))
        working[i], working[j] = working[j], working[i]
    return swaps


def _scale_velocity_swaps(velocity: Sequence[Tuple[int, int]], scalar: float) -> List[Tuple[int, int]]:
    """Reduce a swap sequence length according to the scalar (as in Tut 7)."""
    if scalar <= 0 or not velocity:
        return []
    k = max(0, min(len(velocity), math.ceil(abs(scalar) * len(velocity))))
    return list(velocity[:k])


def _apply_velocity_swaps(route: Sequence[str], velocity: Sequence[Tuple[int, int]]) -> List[str]:
    """Apply swap operations sequentially to a route."""
    perm = list(route)
    for i, j in velocity:
        if i < 0 or j < 0 or i >= len(perm) or j >= len(perm):
            continue
        perm[i], perm[j] = perm[j], perm[i]
    return perm


def _route_edges_valid(route: Sequence[str], params: SingleForkParams) -> bool:
    """Check that every consecutive edge on the route exists in the network."""
    edges = list(zip(route[:-1], route[1:]))
    return all(edge in params.edges_time_min for edge in edges)


def create_initial_swarm(
    params: SingleForkParams,
    swarm_size: int,
    rng: Optional[random.Random] = None,
    objective_fn: Callable = objective_weighted,
) -> List[Particle]:
    """
    Build the initial swarm by sampling feasible VehiclePlan configurations.
    """
    if rng is None:
        rng = random.Random()

    swarm: List[Particle] = []
    for _ in range(swarm_size):
        base_plans = [plan.copy() for plan in _generate_random_initial_plans(params, rng)]
        cost = evaluate_plans(base_plans, params, objective_fn)
        particle = Particle(plans=base_plans)
        particle.best_plans = [plan.copy() for plan in base_plans]
        particle.best_cost = cost
        swarm.append(particle)
    return swarm


def _attempt_repair(
    plans: List[VehiclePlan],
    params: SingleForkParams,
    rng: random.Random,
    max_attempts: int = 3,
) -> None:
    """
    Attempt lightweight repairs using the shared feasibility repair helper.
    """
    for _ in range(max_attempts):
        solution = build_solution_from_plans(plans, params)
        feasible, code, _ = solution.is_feasible(return_reason=True)
        if feasible:
            return
        modified = _repair_plans_for_reason(plans, code, params, rng)
        if not modified:
            return


def update_particle(
    particle: Particle,
    global_best_plans: Sequence[VehiclePlan],
    params: SingleForkParams,
    rng: random.Random,
    w: float,
    c1: float,
    c2: float,
    mutation_prob: float = 0.1,
) -> None:
    """
    Hybrid PSO update handling continuous (speed/charge) and discrete (route) vars.
    """
    personal_lookup = {plan.vehicle_id: plan for plan in particle.best_plans}
    global_lookup = {plan.vehicle_id: plan for plan in global_best_plans}

    for plan in particle.plans:
        vehicle_id = plan.vehicle_id
        battery_kwh = params.battery_kwh[vehicle_id]
        _ensure_speed_defaults(plan, params)

        # --- Discrete PSO route update (permutation + swap velocity) ---
        current_route = list(plan.route)
        personal_route = personal_lookup.get(vehicle_id, plan).route
        global_route = global_lookup.get(vehicle_id, plan).route
        route_key = ("route", vehicle_id)
        route_updated = False

        if _routes_compatible(current_route, personal_route) and _routes_compatible(current_route, global_route):
            v_old_route = particle.velocity.get(route_key, [])
            if not isinstance(v_old_route, list):
                v_old_route = []

            # Compute swap sequences toward personal/global bests, then scale.
            v_personal = _subtract_permutations(personal_route, current_route)
            v_global = _subtract_permutations(global_route, current_route)
            r1, r2 = rng.random(), rng.random()
            v_new_route: List[Tuple[int, int]] = (
                _scale_velocity_swaps(v_old_route, w)
                + _scale_velocity_swaps(v_personal, c1 * r1)
                + _scale_velocity_swaps(v_global, c2 * r2)
            )

            candidate_route = _apply_velocity_swaps(current_route, v_new_route)
            if _route_edges_valid(candidate_route, params):
                plan.route = candidate_route
                particle.velocity[route_key] = v_new_route
                route_updated = True

        if route_updated:
            _ensure_speed_defaults(plan, params)

        edges = list(zip(plan.route[:-1], plan.route[1:]))
        for edge in edges:
            min_speed, max_speed = params.get_edge_speed_bounds(edge)
            current_speed = plan.speed_levels.get(edge, params.speed_reference)

            personal_speed = personal_lookup.get(vehicle_id, plan).speed_levels.get(
                edge, current_speed
            )
            global_speed = global_lookup.get(vehicle_id, plan).speed_levels.get(
                edge, current_speed
            )

            key = ("speed", edge)
            v_old = particle.velocity.get(key, 0.0)
            r1, r2 = rng.random(), rng.random()
            v_new = (
                w * v_old
                + c1 * r1 * (personal_speed - current_speed)
                + c2 * r2 * (global_speed - current_speed)
            )
            particle.velocity[key] = v_new

            new_speed = current_speed + v_new
            new_speed = max(min_speed, min(max_speed, new_speed))
            plan.speed_levels[edge] = round(new_speed, 1)

        stations_on_route = [node for node in plan.route if node in params.station_plugs]
        for station in stations_on_route:
            key = ("charge", vehicle_id, station)
            current_charge = plan.charging_amounts.get(station, 0.0)
            personal_charge = personal_lookup.get(vehicle_id, plan).charging_amounts.get(
                station, current_charge
            )
            global_charge = global_lookup.get(vehicle_id, plan).charging_amounts.get(
                station, current_charge
            )

            v_old = particle.velocity.get(key, 0.0)
            r1, r2 = rng.random(), rng.random()
            v_new = (
                w * v_old
                + c1 * r1 * (personal_charge - current_charge)
                + c2 * r2 * (global_charge - current_charge)
            )
            particle.velocity[key] = v_new

            new_charge = max(0.0, current_charge + v_new)
            max_charge = battery_kwh * 0.95
            plan.charging_amounts[station] = round(min(new_charge, max_charge), 3)

        # Fallback route adoption/mutation when swap-based update was not applied.
        if not route_updated and rng.random() < 0.15:
            personal_route = personal_lookup.get(vehicle_id, plan).route
            global_route = global_lookup.get(vehicle_id, plan).route
            adopt_candidates = []
            if personal_route and personal_route != plan.route:
                adopt_candidates.append(("personal", personal_route))
            if global_route and global_route != plan.route:
                adopt_candidates.append(("global", global_route))

            if adopt_candidates:
                personal_weight = c1 / (c1 + c2) if (c1 + c2) > 0 else 0.5
                if len(adopt_candidates) == 2:
                    choose_personal = rng.random() < personal_weight
                    source = adopt_candidates[0] if choose_personal else adopt_candidates[1]
                else:
                    source = adopt_candidates[0]

                plan.route = list(source[1])
                plan.charging_amounts = {}
                plan.speed_levels = {}
                _ensure_station_exists(plan, params, rng)
                _ensure_speed_defaults(plan, params)

        if rng.random() < 0.05:
            _mutate_route_toggle(plan, params, rng)

        if rng.random() < mutation_prob:
            move = rng.choice(
                [
                    "speed_step",
                    "speed_random",
                    "charge_step",
                    "charge_random",
                    "station_add",
                    "station_remove",
                ]
            )
            if move == "speed_step":
                _mutate_speed_step(plan, params, rng)
            elif move == "speed_random":
                _mutate_speed_random(plan, params, rng)
            elif move == "charge_step":
                _mutate_charge_step(plan, params, rng)
            elif move == "charge_random":
                _mutate_charge_random(plan, params, rng)
            elif move == "station_add":
                _mutate_station_add(plan, params, rng)
            elif move == "station_remove":
                _mutate_station_remove(plan, rng)

        _ensure_speed_defaults(plan, params)
        _ensure_station_exists(plan, params, rng)

    _attempt_repair(particle.plans, params, rng)


# ============================================================================
# Main PSO Optimizer
# ============================================================================

def particle_swarm_optimization(
    params: SingleForkParams,
    *,
    swarm_size: int = 40,
    max_iterations: int = 150,
    w: float = 0.5,
    c1: float = 1.7,
    c2: float = 1.7,
    use_adaptive_weight: bool = True,
    objective_fn: Callable = objective_weighted,
    seed: Optional[int] = None,
    verbose: bool = True,
    show_plots: bool = True,
    plot_file: str | Path | None = None,
) -> PSOResult:
    """
    Run Particle Swarm Optimization on the EV fleet routing problem.

    Args:
        params: Problem parameters / network definition
        swarm_size: Number of PSO particles
        max_iterations: Number of iterations for the loop
        w, c1, c2: Velocity update coefficients
        objective_fn: Objective to minimize
        seed: Optional RNG seed
        verbose: Whether to print iteration logs
        show_plots: Display convergence figures interactively
        plot_file: Optional path to save convergence plot (for convergence figures)
    """
    rng = random.Random(seed)
    swarm = create_initial_swarm(params, swarm_size, rng, objective_fn)

    global_best_cost = math.inf
    global_best_plans: List[VehiclePlan] = []
    w0 = w  # Baseline inertia weight for adaptive updates
    w_current = w

    for particle in swarm:
        if particle.best_cost < global_best_cost:
            global_best_cost = particle.best_cost
            global_best_plans = particle.clone_plans()

    history: List[Tuple[int, float, float, float]] = []
    t0 = time.time()

    for iteration in range(max_iterations):
        costs = []
        for particle in swarm:
            update_particle(particle, global_best_plans, params, rng, w_current, c1, c2)
            cost = evaluate_plans(particle.plans, params, objective_fn)
            costs.append(cost)

            if cost < particle.best_cost:
                particle.best_cost = cost
                particle.best_plans = particle.clone_plans()

            if cost < global_best_cost:
                global_best_cost = cost
                global_best_plans = particle.clone_plans()

            if use_adaptive_weight:
                # Adaptive inertia: adjust w based on improvement relative to neighborhood best.
                denom = global_best_cost + cost
                if denom != 0:
                    m = (global_best_cost - cost) / denom
                    ratio = (math.exp(m) - 1) / (math.exp(m) + 1)
                    # Nudge inertia within [0.2, 0.9] based on relative improvement.
                    w_current = max(0.2, min(0.9, w_current + 0.1 * ratio))

        avg_cost = float(np.mean(costs)) if costs else math.inf
        worst_cost = float(np.max(costs)) if costs else math.inf
        history.append((iteration, global_best_cost, avg_cost, worst_cost))

        if verbose and (iteration % 10 == 0 or iteration == max_iterations - 1):
            print(
                f"[PSO] Iteration {iteration:04d} | Best: {global_best_cost:.3f} | "
                f"Avg: {avg_cost:.3f}"
            )

    runtime = time.time() - t0

    best_solution = build_solution_from_plans(global_best_plans, params)
    best_solution = process_station_queues(best_solution, params)
    feasible = best_solution.is_feasible()
    best_cost_value = float(objective_fn(best_solution))

    if history and (show_plots or plot_file is not None):
        _plot_convergence(history, output_file=plot_file, show_plot=show_plots)

    makespan = objective_makespan(best_solution)
    total_cost = objective_total_cost(best_solution)
    print("\n=== PSO SUMMARY ===")
    print(f"Weighted objective : {best_cost_value:.3f}")
    print(f"Makespan (minutes) : {makespan:.2f}")
    print(f"Total cost (EGP)   : {total_cost:.2f}")
    print(f"Feasible solution? : {feasible}")
    print(f"Runtime (seconds)  : {runtime:.2f}\n")

    return PSOResult(
        best_solution=best_solution,
        best_cost=best_cost_value,
        history=history,
        runtime_seconds=runtime,
    )


def _plot_convergence(
    history: List[Tuple[int, float, float, float]],
    output_file: str | Path | None = None,
    show_plot: bool = True,
) -> None:
    """Plot (and optionally save) the PSO convergence curve."""
    iterations = [h[0] for h in history]
    best_values = [h[1] for h in history]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(iterations, best_values, label="Best", color="#1f77b4")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Weighted Objective")
    ax.set_title("PSO Convergence (Weighted Objective)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"📈 Saved PSO convergence plot to {output_path}")

    if show_plot:
        plt.show(block=False)
    else:
        plt.close(fig)


# ============================================================================
# Demo Helpers
# ============================================================================

def _resolve_plot_path(
    default_filename: str, override: str | Path | None, enabled: bool
) -> Path | None:
    """Return the plot path if saving is enabled."""
    if not enabled:
        return None
    if override:
        return Path(override)
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "outputs" / "plots" / default_filename


def run_pso_single_fork_demo(
    seed: int = 42,
    visualize: bool = True,
    save_plot: bool = True,
    plot_file: str | Path | None = None,
) -> PSOResult:
    """
    Run PSO on the original single-fork network.

    Args:
        seed: Random seed for reproducibility
        visualize: Whether to generate the HTML dashboard
    save_plot: Save the convergence plot (defaults to outputs/plots)
        plot_file: Optional override for the saved plot path
    """
    params = make_toy_params()
    plot_path = _resolve_plot_path(
        "pso_single_fork_convergence.png", plot_file, save_plot
    )
    result = particle_swarm_optimization(
        params,
        swarm_size=40,
        max_iterations=120,
        w=0.5,
        c1=1.7,
        c2=1.7,
        objective_fn=objective_weighted,
        seed=seed,
        verbose=True,
        show_plots=True,
        plot_file=plot_path,
    )

    if visualize:
        from common.visualization import generate_dashboard

        generate_dashboard(
            result.best_solution,
            params,
            "pso_single_fork_solution.html",
            algorithm_name="Particle Swarm Optimization",
        )

    return result


def run_pso_double_fork_demo(
    seed: int = 42,
    visualize: bool = True,
    save_plot: bool = True,
    plot_file: str | Path | None = None,
) -> PSOResult:
    """
    Run PSO on the double-fork instance (Benchmark benchmark).

    Args:
        seed: Random seed for reproducibility
        visualize: Whether to create the HTML dashboard
    save_plot: Persist convergence plot (defaults to outputs/plots)
        plot_file: Optional override for the figure path
    """
    params = make_double_fork_params()
    plot_path = _resolve_plot_path(
        "pso_double_fork_convergence.png", plot_file, save_plot
    )
    result = particle_swarm_optimization(
        params,
        swarm_size=40,
        max_iterations=150,
        w=0.5,
        c1=1.7,
        c2=1.7,
        objective_fn=objective_weighted,
        seed=seed,
        verbose=True,
        show_plots=True,
        plot_file=plot_path,
    )

    if visualize:
        from common.visualization import generate_dashboard

        generate_dashboard(
            result.best_solution,
            params,
            "pso_double_fork_solution.html",
            algorithm_name="Particle Swarm Optimization",
        )

    return result


if __name__ == "__main__":
    run_pso_double_fork_demo(seed=42, visualize=True)
