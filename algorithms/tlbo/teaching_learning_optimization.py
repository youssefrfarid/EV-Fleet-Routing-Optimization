"""
teaching_learning_optimization.py

Teaching-Learning Based Optimization (TLBO) for the EV fleet routing problem.

TLBO (Rao et al., 2011) is a population-based metaheuristic inspired by the
teaching-learning process in a classroom. It requires NO algorithm-specific
parameters - only population size and number of iterations.

Two phases per iteration:
1. Teacher Phase: Learners improve toward the "teacher" (best solution)
2. Learner Phase: Learners improve by interacting with each other

Reference:
    Rao, R.V., Savsani, V.J., & Vakharia, D.P. (2011). Teaching-learning-based
    optimization: A novel method for constrained mechanical design optimization
    problems. Computer-Aided Design, 43(3), 303-315.
"""

from __future__ import annotations

import sys
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Callable, Optional

import matplotlib.pyplot as plt
import numpy as np

# Allow running directly via `python algorithms/tlbo/teaching_learning_optimization.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.objectives import (
    FleetSolution,
    objective_weighted,
)
from common.params import SingleForkParams, make_double_fork_params

# Import reusable components from simulated annealing
from algorithms.sa.simulated_annealing import (
    VehiclePlan,
    build_solution_from_plans,
    _ensure_speed_defaults,
    _ensure_station_exists,
)

# Import repair utilities from GA
from algorithms.ga.genetic_algorithm import (
    create_initial_population,
    evaluate_population,
    repair_individual,
    calculate_population_diversity,
)


# ========================================
# Data Structures
# ========================================

@dataclass
class TLBOResult:
    """Result object returned by TLBO algorithm."""
    best_solution: FleetSolution
    best_fitness: float
    history: List[Tuple[int, float, float, float]] = field(default_factory=list)  # (iter, best, avg, worst)
    diversity_trace: List[float] = field(default_factory=list)


# ========================================
# TLBO Operators
# ========================================

def _blend_plans(
    plan1: VehiclePlan,
    plan2: VehiclePlan,
    factor: float,
    params: SingleForkParams,
    rng: random.Random
) -> VehiclePlan:
    """
    Blend two vehicle plans: result = plan1 + factor * (plan2 - plan1).
    
    For continuous variables (charging, speeds): arithmetic blend
    For discrete variables (route): probabilistic selection based on factor
    
    Args:
        plan1: Base plan
        plan2: Target plan (to move toward if factor > 0)
        factor: Blend factor (0 = plan1, 1 = plan2, can be negative or > 1)
        params: Problem parameters
        rng: Random number generator
        
    Returns:
        New blended VehiclePlan
    """
    result = plan1.copy()
    
    # Route: probabilistic selection
    # If factor > 0.5, prefer plan2's route; otherwise keep plan1's route
    if abs(factor) > 0.5 and rng.random() < abs(factor):
        result.route = list(plan2.route)
    
    # Charging amounts: arithmetic blend
    all_stations = set(plan1.charging_amounts.keys()) | set(plan2.charging_amounts.keys())
    result.charging_amounts = {}
    
    for station in all_stations:
        amt1 = plan1.charging_amounts.get(station, 0.0)
        amt2 = plan2.charging_amounts.get(station, 0.0)
        
        # Blend: new = old + factor * (target - old) = old * (1-factor) + target * factor
        new_amt = amt1 + factor * (amt2 - amt1)
        
        # Clamp to valid range
        new_amt = max(0.0, min(100.0, new_amt))
        
        if new_amt > 0.5:  # Keep only non-trivial charges
            result.charging_amounts[station] = new_amt
    
    # Speed levels: arithmetic blend on edges common to both routes
    result.speed_levels = {}
    
    for i in range(len(result.route) - 1):
        edge = (result.route[i], result.route[i + 1])
        
        speed1 = plan1.speed_levels.get(edge, params.speed_reference)
        speed2 = plan2.speed_levels.get(edge, params.speed_reference)
        
        # Blend speeds
        new_speed = speed1 + factor * (speed2 - speed1)
        
        # Clamp to valid range for this edge
        min_speed, max_speed = params.get_edge_speed_bounds(edge)
        new_speed = max(min_speed, min(max_speed, new_speed))
        
        result.speed_levels[edge] = new_speed
    
    # Ensure defaults and at least one charging station
    _ensure_speed_defaults(result, params)
    if not result.charging_amounts:
        _ensure_station_exists(result, params, rng)
    
    return result


def _blend_fleet(
    fleet1: List[VehiclePlan],
    fleet2: List[VehiclePlan],
    factor: float,
    params: SingleForkParams,
    rng: random.Random
) -> List[VehiclePlan]:
    """
    Blend two fleet configurations vehicle by vehicle.
    
    Args:
        fleet1: Base fleet (list of VehiclePlans)
        fleet2: Target fleet
        factor: Blend factor
        params: Problem parameters
        rng: Random number generator
        
    Returns:
        New blended fleet
    """
    return [
        _blend_plans(p1, p2, factor, params, rng)
        for p1, p2 in zip(fleet1, fleet2)
    ]


def _compute_mean_fleet(
    population: List[List[VehiclePlan]],
    params: SingleForkParams
) -> List[VehiclePlan]:
    """
    Compute the "mean" fleet configuration across the population.
    
    For continuous variables: arithmetic mean
    For discrete variables (routes): most common route
    
    Args:
        population: List of fleet configurations
        params: Problem parameters
        
    Returns:
        Mean fleet configuration
    """
    if not population:
        return []
    
    num_vehicles = len(population[0])
    mean_fleet: List[VehiclePlan] = []
    
    for v_idx in range(num_vehicles):
        # Collect all plans for this vehicle
        plans = [fleet[v_idx] for fleet in population]
        
        # Route: most common
        route_counts: Dict[tuple, int] = {}
        for plan in plans:
            route_key = tuple(plan.route)
            route_counts[route_key] = route_counts.get(route_key, 0) + 1
        
        most_common_route = list(max(route_counts.keys(), key=lambda r: route_counts[r]))
        
        # Charging: average amounts per station
        station_sums: Dict[str, float] = {}
        station_counts: Dict[str, int] = {}
        
        for plan in plans:
            for station, amt in plan.charging_amounts.items():
                station_sums[station] = station_sums.get(station, 0.0) + amt
                station_counts[station] = station_counts.get(station, 0) + 1
        
        mean_charging = {
            station: station_sums[station] / station_counts[station]
            for station in station_sums
            if station_sums[station] / station_counts[station] > 0.5
        }
        
        # Speed: average per edge
        edge_sums: Dict[tuple, float] = {}
        edge_counts: Dict[tuple, int] = {}
        
        for plan in plans:
            for edge, speed in plan.speed_levels.items():
                edge_sums[edge] = edge_sums.get(edge, 0.0) + speed
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        
        mean_speeds = {
            edge: edge_sums[edge] / edge_counts[edge]
            for edge in edge_sums
        }
        
        mean_plan = VehiclePlan(
            vehicle_id=v_idx,
            route=most_common_route,
            charging_amounts=mean_charging,
            speed_levels=mean_speeds
        )
        
        _ensure_speed_defaults(mean_plan, params)
        
        mean_fleet.append(mean_plan)
    
    return mean_fleet


def teacher_phase(
    population: List[List[VehiclePlan]],
    fitness_scores: List[float],
    params: SingleForkParams,
    rng: random.Random
) -> Tuple[List[List[VehiclePlan]], List[float]]:
    """
    TLBO Teacher Phase: Each learner improves toward the teacher.
    
    For each learner i:
        Teacher = best solution in population
        Mean = population mean
        Teaching_Factor (TF) = round(1 + random()) → 1 or 2
        Difference = r * (Teacher - TF * Mean)
        New_i = Learner_i + Difference
        Accept if New_i is better (greedy selection)
    
    Args:
        population: Current population
        fitness_scores: Current fitness values
        params: Problem parameters
        rng: Random number generator
        
    Returns:
        Updated (population, fitness_scores) tuple
    """
    pop_size = len(population)
    
    # Find teacher (best solution)
    teacher_idx = fitness_scores.index(min(fitness_scores))
    teacher = population[teacher_idx]
    
    # Compute mean
    mean_fleet = _compute_mean_fleet(population, params)
    
    new_population = []
    new_fitness = []
    
    for i in range(pop_size):
        learner = population[i]
        
        # Teaching factor: randomly 1 or 2
        tf = round(1 + rng.random())
        
        # Random factor
        r = rng.random()
        
        # Compute: new = learner + r * (teacher - tf * mean)
        # First: tf_mean = tf * mean (scale the mean)
        # Then: diff = teacher - tf_mean
        # Finally: new = learner + r * diff
        
        # Step 1: Scale mean by TF (blend mean toward zero by factor 1-TF)
        # Actually: tf*mean is implemented as interpolating mean toward itself scaled
        # Simpler: compute teacher - tf*mean directly via blending
        
        # Compute difference vector conceptually:
        # diff = teacher - tf * mean
        # We approximate by: blend(teacher, mean, factor= -tf) where blend gives teacher - tf*(mean - teacher)
        # Actually, let's be direct: new_learner = learner + r*(teacher - tf*mean)
        # = (1-r)*learner + r*teacher - r*tf*mean + r*learner - r*learner
        # = learner + r*(teacher - learner) + r*(learner - tf*mean)
        
        # Simpler approach: 
        # Step 1: Move toward teacher: temp = learner + r*(teacher - learner)
        # Step 2: Adjust away from mean: new = temp - r*tf*(mean - learner)
        
        # Even simpler: two-step blend
        # new = blend(learner, teacher, r) then adjust
        
        # Let's implement the formula directly:
        # First blend learner toward teacher
        temp_fleet = _blend_fleet(learner, teacher, r, params, rng)
        
        # Then adjust away from mean (subtract r*tf*(mean - learner))
        # This is equivalent to blending temp away from mean
        new_fleet = _blend_fleet(temp_fleet, mean_fleet, -r * (tf - 1), params, rng)
        
        # Repair if needed
        repaired = repair_individual(new_fleet, params, rng)
        
        if repaired is None:
            # Keep original
            new_population.append([p.copy() for p in learner])
            new_fitness.append(fitness_scores[i])
        else:
            # Evaluate new solution
            solution = build_solution_from_plans(repaired, params)
            if solution.is_feasible():
                new_fit = objective_weighted(solution)
                
                # Greedy selection: accept if better
                if new_fit < fitness_scores[i]:
                    new_population.append(repaired)
                    new_fitness.append(new_fit)
                else:
                    new_population.append([p.copy() for p in learner])
                    new_fitness.append(fitness_scores[i])
            else:
                new_population.append([p.copy() for p in learner])
                new_fitness.append(fitness_scores[i])
    
    return new_population, new_fitness


def learner_phase(
    population: List[List[VehiclePlan]],
    fitness_scores: List[float],
    params: SingleForkParams,
    rng: random.Random
) -> Tuple[List[List[VehiclePlan]], List[float]]:
    """
    TLBO Learner Phase: Learners improve by interacting with each other.
    
    For each learner i:
        Select random learner j (j != i)
        r = random()
        If fitness_i < fitness_j (i is better):
            New_i = Learner_i + r * (Learner_i - Learner_j)  # move away from worse
        Else:
            New_i = Learner_i + r * (Learner_j - Learner_i)  # move toward better
        Accept if New_i is better (greedy selection)
    
    Args:
        population: Current population
        fitness_scores: Current fitness values  
        params: Problem parameters
        rng: Random number generator
        
    Returns:
        Updated (population, fitness_scores) tuple
    """
    pop_size = len(population)
    
    new_population = []
    new_fitness = []
    
    for i in range(pop_size):
        learner_i = population[i]
        fit_i = fitness_scores[i]
        
        # Select random partner j != i
        j = rng.randint(0, pop_size - 1)
        while j == i:
            j = rng.randint(0, pop_size - 1)
        
        learner_j = population[j]
        fit_j = fitness_scores[j]
        
        # Random factor
        r = rng.random()
        
        # Determine direction based on fitness comparison
        if fit_i < fit_j:
            # i is better: move away from j (positive factor means move away)
            new_fleet = _blend_fleet(learner_i, learner_j, -r, params, rng)
        else:
            # j is better: move toward j
            new_fleet = _blend_fleet(learner_i, learner_j, r, params, rng)
        
        # Repair if needed
        repaired = repair_individual(new_fleet, params, rng)
        
        if repaired is None:
            # Keep original
            new_population.append([p.copy() for p in learner_i])
            new_fitness.append(fit_i)
        else:
            # Evaluate new solution
            solution = build_solution_from_plans(repaired, params)
            if solution.is_feasible():
                new_fit = objective_weighted(solution)
                
                # Greedy selection: accept if better
                if new_fit < fit_i:
                    new_population.append(repaired)
                    new_fitness.append(new_fit)
                else:
                    new_population.append([p.copy() for p in learner_i])
                    new_fitness.append(fit_i)
            else:
                new_population.append([p.copy() for p in learner_i])
                new_fitness.append(fit_i)
    
    return new_population, new_fitness


# ========================================
# Main TLBO Algorithm
# ========================================

def tlbo(
    params: SingleForkParams,
    *,
    pop_size: int = 50,
    num_iterations: int = 100,
    objective_fn: Callable = objective_weighted,
    seed: Optional[int] = None,
    verbose: bool = True,
    show_plots: bool = True,
) -> TLBOResult:
    """
    Run Teaching-Learning Based Optimization.
    
    TLBO has NO algorithm-specific parameters - only population size and iterations.
    
    Args:
        params: Problem parameters
        pop_size: Population size (number of learners)
        num_iterations: Number of iterations to run
        objective_fn: Objective function to minimize
        seed: Random seed for reproducibility
        verbose: Print progress information
        show_plots: Show convergence plots at end
        
    Returns:
        TLBOResult containing best solution and history
    """
    rng = random.Random(seed)
    random.seed(seed)
    np.random.seed(seed)
    
    if verbose:
        print("📚 Starting Teaching-Learning Based Optimization (TLBO)")
        print(f"Population size: {pop_size}")
        print(f"Iterations: {num_iterations}")
        print("No algorithm-specific parameters needed!\n")
    
    # Initialize population (reuse from GA)
    if verbose:
        print("Initializing population...")
    population = create_initial_population(params, pop_size, rng)
    
    # Evaluate initial population
    fitness_scores = evaluate_population(population, params, objective_fn)
    
    # Track best solution
    best_idx = fitness_scores.index(min(fitness_scores))
    best_fitness = fitness_scores[best_idx]
    best_solution = build_solution_from_plans(population[best_idx], params)
    
    # History tracking
    history: List[Tuple[int, float, float, float]] = []
    diversity_trace: List[float] = []
    
    if verbose:
        print(f"Initial best fitness: {best_fitness:.3f}\n")
    
    # Main TLBO loop
    for iteration in range(num_iterations):
        # Record statistics
        avg_fitness = sum(fitness_scores) / len(fitness_scores)
        worst_fitness = max(fitness_scores)
        diversity = calculate_population_diversity(population)
        
        history.append((iteration, best_fitness, avg_fitness, worst_fitness))
        diversity_trace.append(diversity)
        
        if verbose and iteration % 10 == 0:
            print(f"Iteration {iteration:3d}: Best={best_fitness:.3f}, Avg={avg_fitness:.3f}, Diversity={diversity:.3f}")
        
        # Teacher Phase
        population, fitness_scores = teacher_phase(population, fitness_scores, params, rng)
        
        # Learner Phase
        population, fitness_scores = learner_phase(population, fitness_scores, params, rng)
        
        # Update best solution
        current_best_idx = fitness_scores.index(min(fitness_scores))
        current_best_fitness = fitness_scores[current_best_idx]
        
        if current_best_fitness < best_fitness:
            best_fitness = current_best_fitness
            best_solution = build_solution_from_plans(population[current_best_idx], params)
            
            if verbose:
                print(f"  🌟 New best solution found: {best_fitness:.3f}")
    
    if verbose:
        print("\n✅ TLBO completed")
        print(f"Best fitness: {best_fitness:.3f}")
        print(f"Solution feasible: {best_solution.is_feasible()}")
    
    # Visualization
    if show_plots:
        _plot_tlbo_results(history, diversity_trace)
    
    return TLBOResult(
        best_solution=best_solution,
        best_fitness=best_fitness,
        history=history,
        diversity_trace=diversity_trace
    )


def _plot_tlbo_results(
    history: List[Tuple[int, float, float, float]],
    diversity_trace: List[float]
) -> None:
    """
    Plot TLBO convergence results.
    
    Args:
        history: List of (iteration, best, avg, worst) tuples
        diversity_trace: Population diversity over iterations
    """
    iterations = [h[0] for h in history]
    best_fitness = [h[1] for h in history]
    avg_fitness = [h[2] for h in history]
    worst_fitness = [h[3] for h in history]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)
    
    # Fitness evolution
    ax1.plot(iterations, best_fitness, label='Best', color='green', linewidth=2)
    ax1.plot(iterations, avg_fitness, label='Average', color='blue', linewidth=1.5)
    ax1.plot(iterations, worst_fitness, label='Worst', color='red', linewidth=1, alpha=0.5)
    ax1.set_xlabel('Iteration')
    ax1.set_ylabel('Fitness (lower is better)')
    ax1.set_title('TLBO - Fitness Evolution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Diversity evolution
    ax2.plot(iterations, diversity_trace, color='purple', linewidth=2)
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Population Diversity')
    ax2.set_title('TLBO - Population Diversity')
    ax2.grid(True, alpha=0.3)
    
    plt.show()


# ========================================
# Demo Functions
# ========================================

def run_tlbo_double_fork_demo(seed: Optional[int] = None, visualize: bool = True) -> TLBOResult:
    """
    Run TLBO on double fork instance.
    
    Args:
        seed: Random seed
        visualize: Show plots and generate dashboard
        
    Returns:
        TLBOResult object
    """
    print("=" * 60)
    print("TLBO DEMO - Double Fork Instance")
    print("=" * 60)
    
    params = make_double_fork_params()
    
    result = tlbo(
        params,
        pop_size=60,
        num_iterations=150,
        seed=seed,
        verbose=True,
        show_plots=visualize
    )
    
    if visualize:
        from common.visualization import generate_dashboard
        output_path = PROJECT_ROOT / "outputs" / "plots" / "tlbo_double_fork_solution.html"
        generate_dashboard(result.best_solution, params, str(output_path), "TLBO")
        print(f"\n📊 Solution dashboard saved to: {output_path}")
    
    return result


if __name__ == "__main__":
    # Run demo on double fork instance
    run_tlbo_double_fork_demo(seed=42, visualize=True)
