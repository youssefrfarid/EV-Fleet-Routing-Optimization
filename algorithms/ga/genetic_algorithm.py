"""
genetic_algorithm.py

Genetic Algorithm optimizer for the EV fleet routing problem.

This module implements a population-based optimization approach using:
- Tournament and roulette wheel selection
- Multi-level crossover (fleet and vehicle-specific)
- Mutation operators adapted from simulated annealing
- Elitism to preserve best solutions
- Feasibility repair mechanisms

The GA operates on VehiclePlan objects and reuses infrastructure from
the simulated annealing implementation for consistency.
"""

from __future__ import annotations

import sys
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Tuple, Callable, Optional

import matplotlib.pyplot as plt
import numpy as np

# Allow running directly via `python algorithms/ga/genetic_algorithm.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.objectives import (
    FleetSolution,
    objective_weighted,
    process_station_queues,
)
from common.params import SingleForkParams, DoubleForkParams, make_toy_params, make_double_fork_params

# Import reusable components from simulated annealing
from algorithms.sa.simulated_annealing import (
    VehiclePlan,
    build_solution_from_plans,
    plans_from_solution,
    _generate_random_initial_plans,
    _mutate_speed_step,
    _mutate_speed_random,
    _mutate_charge_step,
    _mutate_charge_random,
    _mutate_route_toggle,
    _mutate_route_shuffle,
    _mutate_station_add,
    _mutate_station_remove,
    _ensure_speed_defaults,
    _repair_plans_for_reason,
    _ensure_station_exists,
)


# ========================================
# Data Structures
# ========================================

@dataclass
class GAResult:
    """Result object returned by genetic algorithm."""
    best_solution: FleetSolution
    best_fitness: float
    history: List[Tuple[int, float, float, float]] = field(default_factory=list)  # (gen, best, avg, worst)
    diversity_trace: List[float] = field(default_factory=list)


# ========================================
# Population Initialization
# ========================================

def create_initial_population(
    params: SingleForkParams,
    pop_size: int,
    rng: random.Random | None = None
) -> List[List[VehiclePlan]]:
    """
    Generate diverse initial population.
    
    Creates population by generating random feasible plans with different seeds
    to ensure diversity in routes, charging strategies, and speeds.
    
    Args:
        params: Problem parameters
        pop_size: Population size
        rng: Random number generator
        
    Returns:
        List of fleet configurations (each is a list of VehiclePlan)
    """
    if rng is None:
        rng = random.Random()
    
    population: List[List[VehiclePlan]] = []
    
    for i in range(pop_size):
        # Generate random but feasible plans
        plans = _generate_random_initial_plans(params, rng)
        
        # Verify feasibility
        solution = build_solution_from_plans(plans, params)
        feasible, code, message = solution.is_feasible(return_reason=True)
        
        if feasible:
            population.append(plans)
        else:
            # Attempt repair
            repaired = repair_individual(plans, params, rng)
            if repaired is not None:
                population.append(repaired)
            else:
                # Fallback: retry generation
                retry_plans = _generate_random_initial_plans(params, rng)
                population.append(retry_plans)
    
    return population


# ========================================
# Fitness Evaluation
# ========================================

def evaluate_population(
    population: List[List[VehiclePlan]],
    params: SingleForkParams,
    objective_fn: Callable = objective_weighted
) -> List[float]:
    """
    Evaluate fitness for all individuals in population.
    
    Args:
        population: List of fleet configurations
        params: Problem parameters
        objective_fn: Objective function to minimize
        
    Returns:
        List of fitness scores (lower is better)
    """
    fitness_scores: List[float] = []
    
    for plans in population:
        solution = build_solution_from_plans(plans, params)
        
        # Check feasibility
        if not solution.is_feasible():
            # Penalty for infeasible solutions
            fitness = 1e9
        else:
            fitness = objective_fn(solution)
        
        fitness_scores.append(fitness)
    
    return fitness_scores


# ========================================
# Selection Operators
# ========================================

def tournament_selection(
    population: List[List[VehiclePlan]],
    fitness_scores: List[float],
    tournament_size: int,
    rng: random.Random
) -> List[VehiclePlan]:
    """
    Tournament selection: randomly select tournament_size individuals
    and return the one with best (lowest) fitness.
    
    Args:
        population: Current population
        fitness_scores: Fitness values for population
        tournament_size: Number of individuals in tournament
        rng: Random number generator
        
    Returns:
        Selected parent (copy of VehiclePlan list)
    """
    # Randomly select tournament_size individuals
    tournament_indices = rng.sample(range(len(population)), tournament_size)
    
    # Find the best among them (lowest fitness)
    best_idx = min(tournament_indices, key=lambda i: fitness_scores[i])
    
    # Return a copy of the selected individual
    return [plan.copy() for plan in population[best_idx]]


def roulette_wheel_selection(
    population: List[List[VehiclePlan]],
    fitness_scores: List[float],
    rng: random.Random
) -> List[VehiclePlan]:
    """
    Roulette wheel (fitness-proportionate) selection.
    
    Individuals with better (lower) fitness have higher selection probability.
    Handles negative fitness by shifting to positive range.
    
    Args:
        population: Current population
        fitness_scores: Fitness values for population
        rng: Random number generator
        
    Returns:
        Selected parent (copy of VehiclePlan list)
    """
    # Convert fitness to selection probabilities
    # Lower fitness = better, so invert
    max_fitness = max(fitness_scores)
    min_fitness = min(fitness_scores)
    
    # Shift to positive range and invert (so lower fitness = higher probability)
    if max_fitness == min_fitness:
        # All equal, uniform selection
        probabilities = [1.0 / len(population)] * len(population)
    else:
        # Invert: higher fitness gets lower probability
        inverted = [max_fitness - f + 1.0 for f in fitness_scores]
        total = sum(inverted)
        probabilities = [inv / total for inv in inverted]
    
    # Roulette wheel selection
    cumulative = 0.0
    spin = rng.random()
    
    for i, prob in enumerate(probabilities):
        cumulative += prob
        if spin <= cumulative:
            return [plan.copy() for plan in population[i]]
    
    # Fallback (shouldn't reach here)
    return [plan.copy() for plan in population[-1]]


# ========================================
# Crossover Operators
# ========================================

def crossover_fleet(
    parent1: List[VehiclePlan],
    parent2: List[VehiclePlan],
    params: SingleForkParams,
    rng: random.Random
) -> Tuple[List[VehiclePlan], List[VehiclePlan]]:
    """
    Perform crossover at fleet level.
    
    For each vehicle, randomly select from parent1 or parent2, then
    potentially apply vehicle-level crossover.
    
    Args:
        parent1: First parent fleet configuration
        parent2: Second parent fleet configuration
        params: Problem parameters
        rng: Random number generator
        
    Returns:
        Tuple of two offspring fleet configurations
    """
    offspring1: List[VehiclePlan] = []
    offspring2: List[VehiclePlan] = []
    
    for i in range(len(parent1)):
        # Uniform crossover: 50% chance to swap vehicles between parents
        if rng.random() < 0.5:
            # Vehicle i from parent1 -> offspring1, parent2 -> offspring2
            child1_plan = parent1[i].copy()
            child2_plan = parent2[i].copy()
        else:
            # Vehicle i from parent2 -> offspring1, parent1 -> offspring2
            child1_plan = parent2[i].copy()
            child2_plan = parent1[i].copy()
        
        # Additionally, with 30% chance, apply vehicle-level crossover
        if rng.random() < 0.3:
            child1_plan = crossover_vehicle(parent1[i], parent2[i], params, rng)
            child2_plan = crossover_vehicle(parent2[i], parent1[i], params, rng)
        
        offspring1.append(child1_plan)
        offspring2.append(child2_plan)
    
    return offspring1, offspring2


def crossover_vehicle(
    plan1: VehiclePlan,
    plan2: VehiclePlan,
    params: SingleForkParams,
    rng: random.Random
) -> VehiclePlan:
    """
    Perform crossover at vehicle level.
    
    Combines genetic material from two vehicle plans by selecting:
    - Route from one parent
    - Blend charging amounts
    - Blend or select speed levels
    
    Args:
        plan1: First parent vehicle plan
        plan2: Second parent vehicle plan
        params: Problem parameters
        rng: Random number generator
        
    Returns:
        New offspring vehicle plan
    """
    # Start with a copy of plan1
    child = plan1.copy()
    
    # Route crossover: inherit from one parent
    if rng.random() < 0.5:
        child.route = list(plan2.route)
    
    # Charging crossover: blend amounts if routes are compatible
    if plan1.route == plan2.route:
        # Same route: blend charging amounts
        all_stations = set(plan1.charging_amounts.keys()) | set(plan2.charging_amounts.keys())
        child.charging_amounts = {}
        
        for station in all_stations:
            amt1 = plan1.charging_amounts.get(station, 0.0)
            amt2 = plan2.charging_amounts.get(station, 0.0)
            
            # Weighted average
            blend_weight = rng.random()
            child.charging_amounts[station] = blend_weight * amt1 + (1 - blend_weight) * amt2
        
        # Remove zero charges
        child.charging_amounts = {s: amt for s, amt in child.charging_amounts.items() if amt > 0.5}
    
    # Speed crossover: blend if routes match
    if plan1.route == plan2.route:
        child.speed_levels = {}
        
        for i in range(len(child.route) - 1):
            edge = (child.route[i], child.route[i+1])
            
            speed1 = plan1.speed_levels.get(edge, params.speed_reference)
            speed2 = plan2.speed_levels.get(edge, params.speed_reference)
            
            # Weighted average
            blend_weight = rng.random()
            child.speed_levels[edge] = blend_weight * speed1 + (1 - blend_weight) * speed2
    
    # Ensure defaults
    _ensure_speed_defaults(child, params)
    
    # Ensure at least one charging station
    if not child.charging_amounts:
        _ensure_station_exists(child, params, rng)
    
    return child


# ========================================
# Mutation Operators
# ========================================

def mutate_fleet(
    plans: List[VehiclePlan],
    params: SingleForkParams,
    mutation_rate: float,
    rng: random.Random
) -> List[VehiclePlan]:
    """
    Apply mutations to fleet with given probability.
    
    For each vehicle, with probability mutation_rate, apply a random mutation.
    Reuses mutation operators from simulated annealing.
    
    Args:
        plans: Fleet configuration to mutate
        params: Problem parameters
        mutation_rate: Probability of mutation per vehicle
        rng: Random number generator
        
    Returns:
        Mutated fleet configuration
    """
    mutated_plans = [plan.copy() for plan in plans]
    
    for plan in mutated_plans:
        # Apply mutation with probability mutation_rate
        if rng.random() < mutation_rate:
            # Select random mutation operator
            mutation_type = rng.choice([
                "speed_step",
                "speed_random",
                "charge_step",
                "charge_random",
                "route_toggle",
                "station_add",
                "station_remove",
            ])
            
            # Apply mutation
            if mutation_type == "speed_step":
                _mutate_speed_step(plan, params, rng)
            elif mutation_type == "speed_random":
                _mutate_speed_random(plan, params, rng)
            elif mutation_type == "charge_step":
                _mutate_charge_step(plan, params, rng)
            elif mutation_type == "charge_random":
                _mutate_charge_random(plan, params, rng)
            elif mutation_type == "route_toggle":
                _mutate_route_toggle(plan, params, rng)
            elif mutation_type == "station_add":
                _mutate_station_add(plan, params, rng)
            elif mutation_type == "station_remove":
                _mutate_station_remove(plan, rng)
            
            # Ensure defaults after mutation
            _ensure_speed_defaults(plan, params)
    
    return mutated_plans


# ========================================
# Feasibility Repair
# ========================================

def repair_individual(
    plans: List[VehiclePlan],
    params: SingleForkParams,
    rng: random.Random,
    max_attempts: int = 10
) -> Optional[List[VehiclePlan]]:
    """
    Repair infeasible individual.
    
    Attempts to fix feasibility violations using repair mechanisms
    from simulated annealing.
    
    Args:
        plans: Fleet configuration to repair
        params: Problem parameters
        rng: Random number generator
        max_attempts: Maximum repair attempts
        
    Returns:
        Repaired plans or None if repair fails
    """
    current_plans = [plan.copy() for plan in plans]
    
    for attempt in range(max_attempts):
        solution = build_solution_from_plans(current_plans, params)
        feasible, code, message = solution.is_feasible(return_reason=True)
        
        if feasible:
            return current_plans
        
        # Apply repair based on code
        modified = _repair_plans_for_reason(current_plans, code, params, rng)
        
        if not modified:
            # No repair possible, return None
            break
    
    return None


# ========================================
# Helper Functions
# ========================================

def calculate_population_diversity(population: List[List[VehiclePlan]]) -> float:
    """
    Calculate population diversity metric.
    
    Measures diversity based on:
    - Route distribution (entropy)
    - Charging amount variance
    
    Args:
        population: Current population
        
    Returns:
        Diversity score (higher = more diverse)
    """
    if not population:
        return 0.0
    
    # Route diversity: count unique routes
    route_signatures = []
    for plans in population:
        # Create signature from all vehicle routes
        signature = tuple(tuple(plan.route) for plan in plans)
        route_signatures.append(signature)
    
    unique_routes = len(set(route_signatures))
    route_diversity = unique_routes / len(population)
    
    # Charging diversity: variance in charging amounts
    all_charging_amounts = []
    for plans in population:
        for plan in plans:
            all_charging_amounts.extend(plan.charging_amounts.values())
    
    if all_charging_amounts:
        charging_variance = np.var(all_charging_amounts)
    else:
        charging_variance = 0.0
    
    # Combine metrics (weighted average)
    diversity = 0.7 * route_diversity + 0.3 * min(1.0, charging_variance / 100.0)
    
    return diversity


# ========================================
# Main Genetic Algorithm
# ========================================

def genetic_algorithm(
    params: SingleForkParams,
    *,
    pop_size: int = 50,
    num_generations: int = 100,
    elite_size: int = 2,
    tournament_size: int = 3,
    mutation_rate: float = 0.15,
    crossover_rate: float = 0.8,
    objective_fn: Callable = objective_weighted,
    seed: Optional[int] = None,
    verbose: bool = True,
    show_plots: bool = True,
) -> GAResult:
    """
    Run genetic algorithm optimization.
    
    Args:
        params: Problem parameters
        pop_size: Population size
        num_generations: Number of generations to run
        elite_size: Number of elite individuals to preserve
        tournament_size: Tournament size for selection
        mutation_rate: Probability of mutation per individual
        crossover_rate: Probability of crossover
        objective_fn: Objective function to minimize
        seed: Random seed for reproducibility
        verbose: Print progress information
        show_plots: Show convergence plots at end
        
    Returns:
        GAResult containing best solution and history
    """
    rng = random.Random(seed)
    random.seed(seed)
    np.random.seed(seed)
    
    if verbose:
        print("🧬 Starting Genetic Algorithm Optimization")
        print(f"Population size: {pop_size}")
        print(f"Generations: {num_generations}")
        print(f"Elite size: {elite_size}")
        print(f"Tournament size: {tournament_size}")
        print(f"Mutation rate: {mutation_rate}")
        print(f"Crossover rate: {crossover_rate}\n")
    
    # Initialize population
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
    
    # Main GA loop
    for generation in range(num_generations):
        # Record statistics
        avg_fitness = sum(fitness_scores) / len(fitness_scores)
        worst_fitness = max(fitness_scores)
        diversity = calculate_population_diversity(population)
        
        history.append((generation, best_fitness, avg_fitness, worst_fitness))
        diversity_trace.append(diversity)
        
        if verbose and generation % 10 == 0:
            print(f"Generation {generation:3d}: Best={best_fitness:.3f}, Avg={avg_fitness:.3f}, Diversity={diversity:.3f}")
        
        # Create new population
        new_population: List[List[VehiclePlan]] = []
        
        # Elitism: preserve best individuals
        sorted_indices = sorted(range(len(fitness_scores)), key=lambda i: fitness_scores[i])
        for i in range(elite_size):
            elite_plans = [plan.copy() for plan in population[sorted_indices[i]]]
            new_population.append(elite_plans)
        
        # Generate offspring
        while len(new_population) < pop_size:
            # Selection
            parent1 = tournament_selection(population, fitness_scores, tournament_size, rng)
            parent2 = tournament_selection(population, fitness_scores, tournament_size, rng)
            
            # Crossover
            if rng.random() < crossover_rate:
                offspring1, offspring2 = crossover_fleet(parent1, parent2, params, rng)
            else:
                offspring1 = [plan.copy() for plan in parent1]
                offspring2 = [plan.copy() for plan in parent2]
            
            # Mutation
            offspring1 = mutate_fleet(offspring1, params, mutation_rate, rng)
            offspring2 = mutate_fleet(offspring2, params, mutation_rate, rng)
            
            # Repair if needed
            repaired1 = repair_individual(offspring1, params, rng)
            if repaired1 is not None:
                new_population.append(repaired1)
            
            if len(new_population) < pop_size:
                repaired2 = repair_individual(offspring2, params, rng)
                if repaired2 is not None:
                    new_population.append(repaired2)
        
        # Trim to exact population size
        population = new_population[:pop_size]
        
        # Evaluate new population
        fitness_scores = evaluate_population(population, params, objective_fn)
        
        # Update best solution
        current_best_idx = fitness_scores.index(min(fitness_scores))
        current_best_fitness = fitness_scores[current_best_idx]
        
        if current_best_fitness < best_fitness:
            best_fitness = current_best_fitness
            best_solution = build_solution_from_plans(population[current_best_idx], params)
            
            if verbose:
                print(f"  🌟 New best solution found: {best_fitness:.3f}")
    
    if verbose:
        print(f"\n✅ Genetic Algorithm completed")
        print(f"Best fitness: {best_fitness:.3f}")
        print(f"Solution feasible: {best_solution.is_feasible()}")
    
    # Visualization
    if show_plots:
        _plot_ga_results(history, diversity_trace)
    
    return GAResult(
        best_solution=best_solution,
        best_fitness=best_fitness,
        history=history,
        diversity_trace=diversity_trace
    )


def _plot_ga_results(
    history: List[Tuple[int, float, float, float]],
    diversity_trace: List[float]
) -> None:
    """
    Plot GA convergence results.
    
    Args:
        history: List of (generation, best, avg, worst) tuples
        diversity_trace: Population diversity over generations
    """
    generations = [h[0] for h in history]
    best_fitness = [h[1] for h in history]
    avg_fitness = [h[2] for h in history]
    worst_fitness = [h[3] for h in history]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)
    
    # Fitness evolution
    ax1.plot(generations, best_fitness, label='Best', color='green', linewidth=2)
    ax1.plot(generations, avg_fitness, label='Average', color='blue', linewidth=1.5)
    ax1.plot(generations, worst_fitness, label='Worst', color='red', linewidth=1, alpha=0.5)
    ax1.set_xlabel('Generation')
    ax1.set_ylabel('Fitness (lower is better)')
    ax1.set_title('Genetic Algorithm - Fitness Evolution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Diversity evolution
    ax2.plot(generations, diversity_trace, color='purple', linewidth=2)
    ax2.set_xlabel('Generation')
    ax2.set_ylabel('Population Diversity')
    ax2.set_title('Genetic Algorithm - Population Diversity')
    ax2.grid(True, alpha=0.3)
    
    plt.show()


# ========================================
# Demo Functions
# ========================================

def run_ga_demo(seed: Optional[int] = None, visualize: bool = True) -> GAResult:
    """
    Run GA on single fork toy instance.
    
    Args:
        seed: Random seed
        visualize: Show plots
        
    Returns:
        GAResult object
    """
    print("=" * 60)
    print("GENETIC ALGORITHM DEMO - Single Fork Instance")
    print("=" * 60)
    
    params = make_toy_params()
    
    result = genetic_algorithm(
        params,
        pop_size=50,
        num_generations=100,
        elite_size=2,
        tournament_size=3,
        mutation_rate=0.15,
        crossover_rate=0.8,
        seed=seed,
        verbose=True,
        show_plots=visualize
    )
    
    if visualize:
        from common.visualization import generate_dashboard
        generate_dashboard(result.best_solution, params, "ga_single_fork_solution.html", "Genetic Algorithm")
        print("\n📊 Solution dashboard saved to: ga_single_fork_solution.html")
    
    return result


def run_ga_double_fork_demo(seed: Optional[int] = None, visualize: bool = True) -> GAResult:
    """
    Run GA on double fork instance.
    
    Args:
        seed: Random seed
        visualize: Show plots
        
    Returns:
        GAResult object
    """
    print("=" * 60)
    print("GENETIC ALGORITHM DEMO - Double Fork Instance")
    print("=" * 60)
    
    params = make_double_fork_params()
    
    result = genetic_algorithm(
        params,
        pop_size=60,
        num_generations=150,
        elite_size=3,
        tournament_size=4,
        mutation_rate=0.2,
        crossover_rate=0.8,
        seed=seed,
        verbose=True,
        show_plots=visualize
    )
    
    if visualize:
        from common.visualization import generate_dashboard
        generate_dashboard(result.best_solution, params, "ga_double_fork_solution.html", "Genetic Algorithm")
        print("\n📊 Solution dashboard saved to: ga_double_fork_solution.html")
    
    return result


if __name__ == "__main__":
    # Run demo on double fork instance by default
    run_ga_double_fork_demo(seed=42, visualize=True)
