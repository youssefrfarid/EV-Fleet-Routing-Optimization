#!/usr/bin/env python3
"""
run_metaheuristic_studies_parallel.py

Run metaheuristic algorithms (SA, GA, PSO, TLBO) on multiple case studies
in parallel for faster execution. Excludes RL to focus on traditional optimization.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict
from multiprocessing import Pool, cpu_count

# Make repository root importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.case_studies import get_case_study, list_case_studies
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

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "metaheuristic_results"


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


def run_single_case_study(args):
    """Run all metaheuristic algorithms on a single case study."""
    case_id, seed, sa_iter, ga_gen, ga_pop, pso_iter, pso_swarm, tlbo_iter, tlbo_pop = args
    
    # Get case study and build params inside worker
    case = get_case_study(case_id)
    
    print(f"\n{'='*80}")
    print(f"📋 Running Case Study: {case.name}")
    print(f"{'='*80}\n")
    
    params = case.build_params()
    results = {}
    
    # SA
    print(f"🔥 Running SA on {case.name}...")
    start = time.time()
    sa_result = simulated_annealing(params, seed=seed, max_iterations=sa_iter, verbose=False, show_plots=False)
    sa_time = time.time() - start
    results["SA"] = _summarize_solution(sa_result.best_solution, sa_time)
    
    # GA
    print(f"🧬 Running GA on {case.name}...")
    start = time.time()
    ga_result = genetic_algorithm(params, seed=seed, num_generations=ga_gen, pop_size=ga_pop, verbose=False, show_plots=False)
    ga_time = time.time() - start
    results["GA"] = _summarize_solution(ga_result.best_solution, ga_time)
    
    # PSO
    print(f"🐝 Running PSO on {case.name}...")
    start = time.time()
    pso_result = particle_swarm_optimization(params, seed=seed, max_iterations=pso_iter, swarm_size=pso_swarm, verbose=False, show_plots=False)
    pso_time = time.time() - start
    results["PSO"] = _summarize_solution(pso_result.best_solution, pso_time)
    
    # TLBO
    print(f"📚 Running TLBO on {case.name}...")
    start = time.time()
    tlbo_result = tlbo(params, seed=seed, num_iterations=tlbo_iter, pop_size=tlbo_pop, verbose=False, show_plots=False)
    tlbo_time = time.time() - start
    results["TLBO"] = _summarize_solution(tlbo_result.best_solution, tlbo_time)
    
    print(f"✅ Completed {case.name}\n")
    
    return {
        "case_id": case.case_id,
        "metadata": {
            "name": case.name,
            "description": case.description,
            "topology": case.topology,
            "inputs": case.inputs,
        },
        "metrics": results
    }


def main():
    parser = argparse.ArgumentParser(description="Run metaheuristic case studies in parallel")
    parser.add_argument("--cases", nargs="+", default=["single_small", "single_large", "double_sparse", "double_balanced", "double_premium"], 
                       help="Case IDs to run (default: unique non-RL cases)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sa-iterations", type=int, default=1500)
    parser.add_argument("--ga-generations", type=int, default=120)
    parser.add_argument("--ga-pop", type=int, default=50)
    parser.add_argument("--pso-iterations", type=int, default=150)
    parser.add_argument("--pso-swarm", type=int, default=40)
    parser.add_argument("--tlbo-iterations", type=int, default=100)
    parser.add_argument("--tlbo-pop", type=int, default=50)
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)")
    args = parser.parse_args()
    
    # Get case studies
    if "all" in args.cases:
        cases = list_case_studies()
    else:
        cases = [get_case_study(case_id) for case_id in args.cases]
    
    # Prepare arguments for each case (pass case_id instead of case object)
    case_args = [
        (case.case_id, args.seed, args.sa_iterations, args.ga_generations, args.ga_pop,
         args.pso_iterations, args.pso_swarm, args.tlbo_iterations, args.tlbo_pop)
        for case in cases
    ]
    
    # Determine number of workers
    n_workers = args.workers or min(cpu_count(), len(cases))
    
    print(f"\n🚀 Running {len(cases)} case studies in parallel with {n_workers} workers\n")
    
    # Run in parallel
    start_time = time.time()
    with Pool(processes=n_workers) as pool:
        case_results = pool.map(run_single_case_study, case_args)
    total_time = time.time() - start_time
    
    # Aggregate results
    results = {r["case_id"]: {"metadata": r["metadata"], "metrics": r["metrics"]} for r in case_results}
    
    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "metaheuristic_results.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    
    print(f"\n{'='*80}")
    print(f"✅ All case studies completed in {total_time:.2f}s")
    print(f"📁 Results saved to {output_path}")
    print(f"{'='*80}\n")
    
    # Print summary table
    print("\n📊 RESULTS SUMMARY\n")
    print(f"{'Case':<30} | {'Algo':<6} | {'Weighted':>10} | {'Makespan':>10} | {'Cost':>10} | {'Runtime':>10}")
    print("-" * 100)
    
    for case_id, data in results.items():
        case_name = data["metadata"]["name"]
        for algo, metrics in data["metrics"].items():
            print(f"{case_name:<30} | {algo:<6} | {metrics['weighted']:>10.2f} | {metrics['makespan']:>10.2f} | {metrics['cost']:>10.2f} | {metrics['runtime']:>10.2f}")


if __name__ == "__main__":
    main()
