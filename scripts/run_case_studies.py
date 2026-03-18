#!/usr/bin/env python3
"""
run_case_studies.py

Execute all Benchmark case studies across SA, GA, PSO, TLBO and RL, then export
structured results (JSON + Markdown tables) for the progress report.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt

# Make repository root importable when running directly from scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.case_studies import CaseStudy, get_case_study, list_case_studies
from common.objectives import (
    FleetSolution,
    objective_makespan,
    objective_total_cost,
    objective_weighted,
)
from algorithms.pso.particle_swarm import particle_swarm_optimization
from algorithms.sa.simulated_annealing import simulated_annealing
from algorithms.ga.genetic_algorithm import genetic_algorithm
from algorithms.rl.rl_optimizer import rl_optimization
from algorithms.tlbo.teaching_learning_optimization import tlbo

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "results"
TABLE_PATH = OUTPUT_DIR / "case_studies_table.md"
PLOT_DIR = PROJECT_ROOT / "outputs" / "plots"
PLOT_STEM = "case_studies_summary"


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


def _run_sa(params, seed: int, iterations: int, verbose: bool):
    start = time.time()
    result = simulated_annealing(
        params,
        seed=seed,
        max_iterations=iterations,
        verbose=verbose,
        show_plots=False,
    )
    runtime = time.time() - start
    return result.best_solution, runtime


def _run_ga(params, seed: int, generations: int, pop_size: int, verbose: bool):
    start = time.time()
    result = genetic_algorithm(
        params,
        seed=seed,
        num_generations=generations,
        pop_size=pop_size,
        verbose=verbose,
        show_plots=False,
    )
    runtime = time.time() - start
    return result.best_solution, runtime


def _run_pso(params, seed: int, iterations: int, swarm: int, verbose: bool):
    start = time.time()
    result = particle_swarm_optimization(
        params,
        seed=seed,
        max_iterations=iterations,
        swarm_size=swarm,
        verbose=verbose,
        show_plots=False,
    )
    runtime = time.time() - start
    return result.best_solution, runtime


def _run_tlbo(params, seed: int, iterations: int, pop_size: int, verbose: bool):
    start = time.time()
    result = tlbo(
        params,
        seed=seed,
        num_iterations=iterations,
        pop_size=pop_size,
        verbose=verbose,
        show_plots=False,
    )
    runtime = time.time() - start
    return result.best_solution, runtime


def _run_rl(params, seed: int, episodes: int, verbose: bool):
    start = time.time()
    result = rl_optimization(
        params,
        seed=seed,
        n_episodes=episodes,
        verbose=verbose,
        show_plots=False,
    )
    runtime = time.time() - start
    return result.best_solution, runtime


def _write_markdown_table(rows: List[Dict[str, str]]) -> None:
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "| Case | Algorithm | Weighted | Makespan (min) | Cost (EGP) | "
        "Queue (min) | Charging (min) | Energy (kWh) | Runtime (s) |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    body = ""
    for row in rows:
        body += (
            f"| {row['case']} | {row['algo']} | {row['weighted']:.2f} | "
            f"{row['makespan']:.2f} | {row['cost']:.2f} | {row['queue_time']:.2f} | "
            f"{row['charging_time']:.2f} | {row['energy_kwh']:.2f} | "
            f"{row['runtime']:.2f} |\n"
        )
    TABLE_PATH.write_text(header + body, encoding="utf-8")
    print(f"Wrote Markdown summary to {TABLE_PATH}")


def _chunk(items: List, size: int) -> List[List]:
    """Yield successive chunks from a list."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def _plot_case_study_results(results: Dict[str, Dict[str, Dict[str, float]]]) -> None:
    """Create one or more summary plots across all cases and algorithms."""
    if not results:
        print("No results to plot.")
        return

    preferred_order = ["SA", "GA", "PSO", "RL"]
    algos: List[str] = []
    for case_data in results.values():
        for algo in case_data["metrics"].keys():
            if algo not in algos:
                algos.append(algo)
    if not algos:
        print("No algorithm metrics available to plot.")
        return
    algos.sort(
        key=lambda a: preferred_order.index(a)
        if a in preferred_order
        else len(preferred_order)
    )

    metrics = [
        ("weighted", "Weighted Objective", "Score"),
        ("makespan", "Makespan", "Minutes"),
        ("cost", "Cost", "EGP"),
        ("queue_time", "Queue Time", "Minutes"),
        ("charging_time", "Charging Time", "Minutes"),
        ("energy_kwh", "Energy Delivered", "kWh"),
        ("runtime", "Runtime", "Seconds"),
    ]

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    cases = list(results.keys())
    width = 0.8 / max(len(algos), 1)
    saved_paths: List[Path] = []

    for part_idx, metric_chunk in enumerate(_chunk(metrics, 4), start=1):
        rows = 2
        cols = 2
        fig, axes = plt.subplots(rows, cols, figsize=(12, 8))
        axes = axes.flatten()

        for idx, (metric_key, title, ylabel) in enumerate(metric_chunk):
            ax = axes[idx]
            x = list(range(len(cases)))
            for i, algo in enumerate(algos):
                values = [
                    results[case]["metrics"].get(algo, {}).get(metric_key, float("nan"))
                    for case in cases
                ]
                offsets = [(xi + (i - (len(algos) - 1) / 2) * width) for xi in x]
                ax.bar(offsets, values, width=width, label=algo)
            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xticks(x)
            ax.set_xticklabels(cases, rotation=20, ha="right")
            ax.grid(True, axis="y", alpha=0.3)

        for j in range(len(metric_chunk), len(axes)):
            axes[j].axis("off")

        fig.suptitle(
            f"Benchmark Case Studies: SA vs GA vs PSO vs RL (Part {part_idx})",
            fontsize=14,
            weight="bold",
        )
        fig.legend(loc="upper center", ncol=len(algos), bbox_to_anchor=(0.5, 0.04))
        fig.tight_layout(rect=(0, 0.05, 1, 0.94))

        plot_path = PLOT_DIR / f"{PLOT_STEM}_part{part_idx}.png"
        fig.savefig(plot_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        saved_paths.append(plot_path)

    for path in saved_paths:
        print(f"Saved plot to {path}")




def run_case_studies(
    cases: List[CaseStudy],
    algorithms: List[str],
    seed: int,
    sa_iterations: int,
    ga_generations: int,
    ga_pop: int,
    pso_iterations: int,
    pso_swarm: int,
    tlbo_iterations: int,
    tlbo_pop: int,
    rl_episodes: int,
    verbose: bool,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Dict[str, Dict[str, float]]] = {}
    table_rows: List[Dict[str, str]] = []

    for case in cases:
        print(f"\n{'='*80}")
        print(f"📋 Running Case Study: {case.name}")
        print(f"{'='*80}\n")
        
        params = case.build_params()
        case_entry: Dict[str, Dict[str, float]] = {}
        if "sa" in algorithms:
            print(f"🔥 Running SA on {case.name}...")
            solution, runtime = _run_sa(params, seed, sa_iterations, verbose)
            metrics = _summarize_solution(solution, runtime)
            case_entry["SA"] = metrics
            table_rows.append({"case": case.name, "algo": "SA", **metrics})
        if "ga" in algorithms:
            print(f"🧬 Running GA on {case.name}...")
            solution, runtime = _run_ga(params, seed, ga_generations, ga_pop, verbose)
            metrics = _summarize_solution(solution, runtime)
            case_entry["GA"] = metrics
            table_rows.append({"case": case.name, "algo": "GA", **metrics})
        if "pso" in algorithms:
            print(f"🐝 Running PSO on {case.name}...")
            solution, runtime = _run_pso(params, seed, pso_iterations, pso_swarm, verbose)
            metrics = _summarize_solution(solution, runtime)
            case_entry["PSO"] = metrics
            table_rows.append({"case": case.name, "algo": "PSO", **metrics})
        if "tlbo" in algorithms:
            print(f"📚 Running TLBO on {case.name}...")
            solution, runtime = _run_tlbo(params, seed, tlbo_iterations, tlbo_pop, verbose)
            metrics = _summarize_solution(solution, runtime)
            case_entry["TLBO"] = metrics
            table_rows.append({"case": case.name, "algo": "TLBO", **metrics})
        if "rl" in algorithms:
            print(f"🤖 Running RL on {case.name}...")
            solution, runtime = _run_rl(params, seed, rl_episodes, verbose)
            metrics = _summarize_solution(solution, runtime)
            case_entry["RL"] = metrics
            table_rows.append({"case": case.name, "algo": "RL", **metrics})

        results[case.case_id] = {
            "metadata": {
                "name": case.name,
                "description": case.description,
                "topology": case.topology,
                "inputs": case.inputs,
            },
            "metrics": case_entry,
        }

    output_path = OUTPUT_DIR / "case_study_results.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved structured results to {output_path}")
    _write_markdown_table(table_rows)
    _plot_case_study_results(results)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Benchmark case studies.")
    parser.add_argument(
        "--cases",
        nargs="+",
        default=["all"],
        help="Case IDs to run (default: all).",
    )
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=["sa", "ga", "pso", "tlbo", "rl"],
        choices=["sa", "ga", "pso", "tlbo", "rl"],
        help="Algorithms to run per case.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sa-iterations", type=int, default=1500)
    parser.add_argument("--ga-generations", type=int, default=120)
    parser.add_argument("--ga-pop", type=int, default=50)
    parser.add_argument("--pso-iterations", type=int, default=150)
    parser.add_argument("--pso-swarm", type=int, default=40)
    parser.add_argument("--tlbo-iterations", type=int, default=100)
    parser.add_argument("--tlbo-pop", type=int, default=50)
    parser.add_argument("--rl-episodes", type=int, default=500)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.cases == ["all"]:
        cases = list_case_studies()
    else:
        cases = [get_case_study(case_id) for case_id in args.cases]
    run_case_studies(
        cases=cases,
        algorithms=args.algorithms,
        seed=args.seed,
        sa_iterations=args.sa_iterations,
        ga_generations=args.ga_generations,
        ga_pop=args.ga_pop,
        pso_iterations=args.pso_iterations,
        pso_swarm=args.pso_swarm,
        tlbo_iterations=args.tlbo_iterations,
        tlbo_pop=args.tlbo_pop,
        rl_episodes=args.rl_episodes,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
