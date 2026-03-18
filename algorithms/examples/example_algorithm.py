#!/usr/bin/env python3
"""
Example: How to use visualization.py with any optimization algorithm

This template shows how to integrate the dashboard with future algorithms:
- Genetic Algorithm
- MILP Solver
- Tabu Search
- etc.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.visualization import generate_dashboard
from common.params import make_toy_params
from common.objectives import FleetSolution

def run_my_algorithm():
    """
    Template for any optimization algorithm.
    
    Replace this with your GA, MILP, or other algorithm.
    """
    # 1. Load problem
    params = make_toy_params()
    
    # 2. Run your optimization
    # solution = genetic_algorithm(params)
    # solution = milp_solver(params)
    # solution = tabu_search(params)
    
    # For demonstration, use SA
    from algorithms.sa.simulated_annealing import simulated_annealing
    result = simulated_annealing(params, seed=42, verbose=False)
    solution = result.best_solution
    
    # 3. Generate dashboard (works for ANY algorithm!)
    generate_dashboard(
        solution=solution,
        params=params,
        algorithm_name="Genetic Algorithm"  # Change to your algorithm name
    )
    
    return solution


if __name__ == "__main__":
    print("Running optimization...")
    solution = run_my_algorithm()
    print(f"✅ Best cost: {solution.get_objective_weighted():.2f}")
