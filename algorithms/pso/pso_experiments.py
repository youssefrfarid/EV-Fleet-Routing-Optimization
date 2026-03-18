"""
pso_experiments.py

Experiment driver for benchmarking. Generates PSO performance data across
multiple case studies and parameter configurations, writing results to CSV for
use in the final report.
"""

from __future__ import annotations

import sys
import csv
import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Sequence

# Allow running directly via `python algorithms/pso/pso_experiments.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.objectives import objective_makespan, objective_total_cost, objective_weighted
from common.params import SingleForkParams, make_double_fork_params, make_toy_params
from algorithms.pso.particle_swarm import particle_swarm_optimization

# Parameter grids (can be adjusted to taste)
SWARM_SIZE_OPTIONS = [20, 40, 80]
INERTIA_OPTIONS = [0.3, 0.5, 0.8]
ACCELERATION_OPTIONS = [1.2, 1.7, 2.2]
ITERATION_OPTIONS = [80, 150, 250]


@dataclass
class CaseStudy:
    """Container describing a case study builder."""

    name: str
    builder: Callable[[], SingleForkParams]


def _single_fork_small() -> SingleForkParams:
    params = make_toy_params()
    params.m = 3
    params.battery_kwh = params.battery_kwh[:3]
    params.soc0 = params.soc0[:3]
    return params


def _single_fork_large() -> SingleForkParams:
    params = make_toy_params()
    params.m = 6
    params.battery_kwh = params.battery_kwh + [85.0]
    params.soc0 = params.soc0 + [0.5]
    return params


def _double_fork_default() -> SingleForkParams:
    return make_double_fork_params()


def _double_fork_heavy() -> SingleForkParams:
    params = make_double_fork_params()
    params.m = 6
    extra_battery = [70.0, 85.0]
    extra_soc = [0.55, 0.5]
    params.battery_kwh = params.battery_kwh + extra_battery
    params.soc0 = params.soc0 + extra_soc
    return params


CASE_STUDIES: Sequence[CaseStudy] = [
    CaseStudy("single_small", _single_fork_small),
    CaseStudy("single_large", _single_fork_large),
    CaseStudy("double_default", _double_fork_default),
    CaseStudy("double_heavy", _double_fork_heavy),
]


def _record_result(
    records: List[Dict[str, float]],
    case_name: str,
    config: Dict[str, float],
    seed: int,
    metrics: Dict[str, float],
):
    row = {
        "case_name": case_name,
        "swarm_size": config["swarm_size"],
        "w": config["w"],
        "c1": config["c1"],
        "c2": config["c2"],
        "max_iterations": config["max_iterations"],
        "seed": seed,
        "best_weighted": metrics["weighted"],
        "makespan": metrics["makespan"],
        "total_cost": metrics["cost"],
        "runtime": metrics["runtime"],
    }
    records.append(row)


def _extract_metrics(result) -> Dict[str, float]:
    solution = result.best_solution
    return {
        "weighted": float(objective_weighted(solution)),
        "makespan": float(objective_makespan(solution)),
        "cost": float(objective_total_cost(solution)),
        "runtime": float(result.runtime_seconds),
    }


DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[2] / "outputs" / "csv" / "pso_param_sweep_results.csv"
)


def run_param_sweep(
    output_file: str | Path = DEFAULT_OUTPUT_PATH,
    seeds_per_config: int = 3,
):
    """
    Execute PSO on all configured case studies + parameter grids.
    """
    configs = list(
        itertools.product(
            SWARM_SIZE_OPTIONS,
            INERTIA_OPTIONS,
            ACCELERATION_OPTIONS,
            ITERATION_OPTIONS,
        )
    )
    records: List[Dict[str, float]] = []

    total_runs = len(CASE_STUDIES) * len(configs) * seeds_per_config
    run_counter = 0

    for case in CASE_STUDIES:
        for swarm, w, accel, iters in configs:
            config = {
                "swarm_size": swarm,
                "w": w,
                "c1": accel,
                "c2": accel,
                "max_iterations": iters,
            }
            for _ in range(seeds_per_config):
                seed = 1000 + run_counter
                params = case.builder()
                result = particle_swarm_optimization(
                    params,
                    swarm_size=swarm,
                    max_iterations=iters,
                    w=w,
                    c1=accel,
                    c2=accel,
                    seed=seed,
                    verbose=False,
                    show_plots=False,
                )
                metrics = _extract_metrics(result)
                _record_result(records, case.name, config, seed, metrics)
                run_counter += 1
                print(
                    f"[PSO Experiments] Completed run {run_counter}/{total_runs} "
                    f"({case.name}, swarm={swarm}, w={w}, accel={accel}, iters={iters})"
                )

    output_path = Path(output_file)
    _write_csv(records, output_path)
    print(f"\nSaved {len(records)} experiment rows to {output_path}")


def _write_csv(records: List[Dict[str, float]], output_file: Path) -> None:
    if not records:
        return
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0].keys())
    with output_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    run_param_sweep()
