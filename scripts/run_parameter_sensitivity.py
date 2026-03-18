#!/usr/bin/env python3
"""
run_parameter_sensitivity.py

Test different parameter configurations for each algorithm on the same problem
to analyze parameter sensitivity and optimal tuning.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
from multiprocessing import Pool, cpu_count

# Make repository root importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.params import make_double_fork_params
from common.objectives import (
    FleetSolution,
    objective_makespan,
    objective_total_cost,
    objective_weighted,
)
from algorithms.pso.particle_swarm import particle_swarm_optimization
from algorithms.sa.simulated_annealing import simulated_annealing
from algorithms.ga.genetic_algorithm import genetic_algorithm
from algorithms.tlbo.teaching_learning_optimization import tlbo
from algorithms.rl.rl_optimizer import rl_optimization

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "parameter_sensitivity"


def _summarize_solution(solution: FleetSolution, runtime: float) -> Dict[str, float]:
    """Aggregate performance metrics."""
    total_queue = sum(v.get_total_queue_time() for v in solution.vehicle_solutions)
    total_charging = sum(v.get_total_charging_time() for v in solution.vehicle_solutions)
    total_energy = sum(
        sum(v.charging_amounts.values()) for v in solution.vehicle_solutions
    )
    return {
        "weighted": float(objective_weighted(solution)),
        "makespan": float(objective_makespan(solution)),
        "cost": float(objective_total_cost(solution)),
        "queue_time": float(total_queue),
        "charging_time": float(total_charging),
        "energy_kwh": float(total_energy),
        "runtime": runtime,
    }


# Parameter configurations for each algorithm
SA_CONFIGS = {
    "conservative": {"max_iterations": 1000, "temperature_start": 30.0, "temperature_end": 1.0, "cooling_rate": 0.95},
    "balanced": {"max_iterations": 1500, "temperature_start": 60.0, "temperature_end": 0.5, "cooling_rate": 0.92},
    "aggressive": {"max_iterations": 2000, "temperature_start": 100.0, "temperature_end": 0.1, "cooling_rate": 0.88},
}

GA_CONFIGS = {
    "small_pop": {"num_generations": 150, "pop_size": 30, "mutation_rate": 0.15, "crossover_rate": 0.8},
    "balanced": {"num_generations": 120, "pop_size": 50, "mutation_rate": 0.15, "crossover_rate": 0.8},
    "large_pop": {"num_generations": 100, "pop_size": 80, "mutation_rate": 0.12, "crossover_rate": 0.85},
}

PSO_CONFIGS = {
    "exploration": {"max_iterations": 150, "swarm_size": 40, "w": 0.8, "c1": 1.5, "c2": 1.5},
    "balanced": {"max_iterations": 150, "swarm_size": 40, "w": 0.5, "c1": 1.7, "c2": 1.7},
    "exploitation": {"max_iterations": 150, "swarm_size": 40, "w": 0.3, "c1": 2.0, "c2": 2.5},
}

TLBO_CONFIGS = {
    "small": {"num_iterations": 80, "pop_size": 30},
    "balanced": {"num_iterations": 100, "pop_size": 50},
    "large": {"num_iterations": 120, "pop_size": 70},
}

RL_CONFIGS = {
    "quick": {"n_episodes": 200, "hidden_dim": 128, "lr": 0.001},
    "balanced": {"n_episodes": 500, "hidden_dim": 128, "lr": 0.001},
    "deep": {"n_episodes": 500, "hidden_dim": 256, "lr": 0.0005},
}


def run_parameter_sensitivity(seed: int = 42):
    """Run all algorithms with different parameter configurations on the same problem."""
    
    # Use a standard double-fork problem
    print("\n" + "="*80)
    print("🔬 Parameter Sensitivity Analysis")
    print("="*80)
    print("\nProblem: Double Fork with 5 vehicles (balanced configuration)")
    print(f"Seed: {seed}\n")
    
    params = make_double_fork_params()
    params.m = 5
    params.battery_kwh = [40.0, 52.0, 63.0, 72.0, 80.0]
    params.soc0 = [0.62, 0.58, 0.54, 0.50, 0.47]
    params.validate()
    
    results = {}
    total_start = time.time()
    
    # SA Parameter Variations
    print("\n" + "-"*80)
    print("🔥 SIMULATED ANNEALING - Parameter Variations")
    print("-"*80)
    results["SA"] = {}
    for config_name, config in SA_CONFIGS.items():
        print(f"\n  Testing {config_name}: {config}")
        start = time.time()
        result = simulated_annealing(params, seed=seed, verbose=False, show_plots=False, **config)
        runtime = time.time() - start
        results["SA"][config_name] = _summarize_solution(result.best_solution, runtime)
        print(f"  ✓ Fitness: {results['SA'][config_name]['weighted']:.2f}, Runtime: {runtime:.2f}s")
    
    # GA Parameter Variations
    print("\n" + "-"*80)
    print("🧬 GENETIC ALGORITHM - Parameter Variations")
    print("-"*80)
    results["GA"] = {}
    for config_name, config in GA_CONFIGS.items():
        print(f"\n  Testing {config_name}: {config}")
        start = time.time()
        result = genetic_algorithm(params, seed=seed, verbose=False, show_plots=False, **config)
        runtime = time.time() - start
        results["GA"][config_name] = _summarize_solution(result.best_solution, runtime)
        print(f"  ✓ Fitness: {results['GA'][config_name]['weighted']:.2f}, Runtime: {runtime:.2f}s")
    
    # PSO Parameter Variations
    print("\n" + "-"*80)
    print("🐝 PARTICLE SWARM OPTIMIZATION - Parameter Variations")
    print("-"*80)
    results["PSO"] = {}
    for config_name, config in PSO_CONFIGS.items():
        print(f"\n  Testing {config_name}: {config}")
        start = time.time()
        result = particle_swarm_optimization(params, seed=seed, verbose=False, show_plots=False, **config)
        runtime = time.time() - start
        results["PSO"][config_name] = _summarize_solution(result.best_solution, runtime)
        print(f"  ✓ Fitness: {results['PSO'][config_name]['weighted']:.2f}, Runtime: {runtime:.2f}s")
    
    # TLBO Parameter Variations
    print("\n" + "-"*80)
    print("📚 TEACHING-LEARNING BASED OPTIMIZATION - Parameter Variations")
    print("-"*80)
    results["TLBO"] = {}
    for config_name, config in TLBO_CONFIGS.items():
        print(f"\n  Testing {config_name}: {config}")
        start = time.time()
        result = tlbo(params, seed=seed, verbose=False, show_plots=False, **config)
        runtime = time.time() - start
        results["TLBO"][config_name] = _summarize_solution(result.best_solution, runtime)
        print(f"  ✓ Fitness: {results['TLBO'][config_name]['weighted']:.2f}, Runtime: {runtime:.2f}s")
    
    # RL Parameter Variations
    print("\n" + "-"*80)
    print("🤖 REINFORCEMENT LEARNING - Parameter Variations")
    print("-"*80)
    results["RL"] = {}
    for config_name, config in RL_CONFIGS.items():
        print(f"\n  Testing {config_name}: {config}")
        start = time.time()
        result = rl_optimization(params, seed=seed, verbose=False, show_plots=False, **config)
        runtime = time.time() - start
        results["RL"][config_name] = _summarize_solution(result.best_solution, runtime)
        print(f"  ✓ Fitness: {results['RL'][config_name]['weighted']:.2f}, Runtime: {runtime:.2f}s")
    
    total_time = time.time() - total_start
    
    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "parameter_sensitivity_results.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    
    # Print summary
    print("\n" + "="*80)
    print(f"📊 PARAMETER SENSITIVITY SUMMARY (Completed in {total_time:.2f}s)")
    print("="*80)
    print(f"\n{'Algorithm':<10} | {'Config':<15} | {'Weighted':>10} | {'Makespan':>10} | {'Cost':>10} | {'Runtime':>10}")
    print("-" * 80)
    
    for algo, configs in results.items():
        for config_name, metrics in configs.items():
            print(f"{algo:<10} | {config_name:<15} | {metrics['weighted']:>10.2f} | {metrics['makespan']:>10.2f} | {metrics['cost']:>10.2f} | {metrics['runtime']:>10.2f}")
    
    print(f"\n✅ Results saved to {output_path}")
    print("="*80 + "\n")
    
    # Find best configuration for each algorithm
    print("\n🏆 BEST CONFIGURATIONS PER ALGORITHM")
    print("-" * 80)
    for algo, configs in results.items():
        best_config = min(configs.items(), key=lambda x: x[1]['weighted'])
        print(f"{algo:<10}: {best_config[0]:<15} (Fitness: {best_config[1]['weighted']:.2f})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parameter sensitivity analysis")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    
    run_parameter_sensitivity(seed=args.seed)
