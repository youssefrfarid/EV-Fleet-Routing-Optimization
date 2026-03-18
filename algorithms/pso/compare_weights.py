"""
compare_weights.py

Compare Discrete PSO runs using a static inertia weight versus the adaptive
inertia update (route update component unchanged). The script reuses the
existing particle_swarm.py implementation and only toggles the
`use_adaptive_weight` flag to isolate the effect on convergence.
"""

from __future__ import annotations

import sys
import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt

# Allow running directly via `python algorithms/pso/compare_weights.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.params import SingleForkParams, make_double_fork_params
from algorithms.pso.particle_swarm import PSOResult, particle_swarm_optimization


@dataclass
class RunOutcome:
    """Container capturing metrics for one PSO run."""

    label: str
    result: PSOResult
    runtime: float
    best_history: List[float]
    iterations_to_converge: int

    @property
    def final_best(self) -> float:
        """Final (lowest) best fitness from the convergence history."""
        return self.best_history[-1] if self.best_history else float("inf")

    @property
    def best_routes(self) -> List[Tuple[int, List[str]]]:
        """Route per vehicle from the best solution."""
        routes: List[Tuple[int, List[str]]] = []
        for vehicle_solution in self.result.best_solution.vehicle_solutions:
            routes.append((vehicle_solution.vehicle_id, list(vehicle_solution.route)))
        return routes


def _iterations_to_converge(best_history: List[float], tol: float = 1e-3) -> int:
    """
    Return iterations needed until the last improvement.

    Counts iterations up to and including the last drop in best fitness
    greater than `tol`. Returns len(history) if improvements occur until the end.
    """
    if not best_history:
        return 0

    best_so_far = best_history[0]
    last_improvement = 0
    for idx, val in enumerate(best_history[1:], start=1):
        if best_so_far - val > tol:
            best_so_far = val
            last_improvement = idx
    return last_improvement + 1


def _run_pso(
    params: SingleForkParams,
    *,
    use_adaptive_weight: bool,
    seed: int,
    swarm_size: int,
    max_iterations: int,
) -> RunOutcome:
    """Execute one PSO run with the given inertia-weight strategy."""
    label = "Adaptive inertia" if use_adaptive_weight else "Static inertia"
    print(f"--> Starting {label} run (seed={seed}, iterations={max_iterations})")
    start = time.time()
    result = particle_swarm_optimization(
        params,
        swarm_size=swarm_size,
        max_iterations=max_iterations,
        use_adaptive_weight=use_adaptive_weight,
        seed=seed,
        verbose=False,
        show_plots=False,
    )
    runtime = time.time() - start
    print(f"<-- Finished {label} run in {runtime:.2f} seconds")
    best_history = [row[1] for row in result.history]
    converge_iter = _iterations_to_converge(best_history)

    return RunOutcome(
        label=label,
        result=result,
        runtime=runtime,
        best_history=best_history,
        iterations_to_converge=converge_iter,
    )


def _save_history_csv(
    static_run: RunOutcome, adaptive_run: RunOutcome, output_file: Path
) -> None:
    """Persist best-so-far fitness per iteration for both runs."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    max_len = max(len(static_run.best_history), len(adaptive_run.best_history))
    with output_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "static_best", "adaptive_best"])
        for idx in range(max_len):
            static_val = static_run.best_history[idx] if idx < len(static_run.best_history) else ""
            adaptive_val = adaptive_run.best_history[idx] if idx < len(adaptive_run.best_history) else ""
            writer.writerow([idx, static_val, adaptive_val])
    print(f"Saved convergence histories to {output_file}")


def _plot_convergence(
    static_run: RunOutcome,
    adaptive_run: RunOutcome,
    *,
    output_file: Path | None,
    show_plot: bool,
) -> None:
    """Plot fitness vs iteration for static vs adaptive inertia weights."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(
        range(len(static_run.best_history)),
        static_run.best_history,
        label=static_run.label,
        color="#1f77b4",
    )
    ax.plot(
        range(len(adaptive_run.best_history)),
        adaptive_run.best_history,
        label=adaptive_run.label,
        color="#ff7f0e",
    )
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Best weighted objective")
    ax.set_title("PSO Inertia Weight Comparison (best fitness per iteration)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_file, dpi=200, bbox_inches="tight")
        print(f"Saved comparison plot to {output_file}")

    if show_plot:
        plt.show(block=False)
    else:
        plt.close(fig)


def _print_summary(static_run: RunOutcome, adaptive_run: RunOutcome) -> None:
    """Print side-by-side comparison of key metrics."""
    print("\n=== PSO Inertia Weight Comparison (route update focus) ===")
    print(
        f"{'Mode':<18} | {'Final best':>12} | {'Iter to converge':>17} | {'Runtime (s)':>11}"
    )
    print("-" * 68)
    print(
        f"{'Static inertia':<18} | {static_run.final_best:>12.3f} | {static_run.iterations_to_converge:>17} | {static_run.runtime:>11.2f}"
    )
    print(
        f"{'Adaptive inertia':<18} | {adaptive_run.final_best:>12.3f} | {adaptive_run.iterations_to_converge:>17} | {adaptive_run.runtime:>11.2f}"
    )
    print("-" * 68)

    print("\nStatic inertia best routes:")
    for vehicle_id, route in static_run.best_routes:
        print(f"  Vehicle {vehicle_id}: {' -> '.join(route)}")

    print("\nAdaptive inertia best routes:")
    for vehicle_id, route in adaptive_run.best_routes:
        print(f"  Vehicle {vehicle_id}: {' -> '.join(route)}")
    print()


def compare_inertia_weights(
    *,
    seed: int = 42,
    swarm_size: int = 40,
    max_iterations: int = 150,
    plot: bool = True,
    plot_file: Path | None = Path(__file__).resolve().parents[2] / "outputs" / "plots" / "pso_inertia_weight_history_plot.png",
    history_csv: Path | None = None,
    params: SingleForkParams | None = None,
) -> tuple[RunOutcome, RunOutcome]:
    """
    Run PSO twice to contrast static vs adaptive inertia weights.

    Args:
        seed: Shared RNG seed so both runs start from identical swarms.
        swarm_size: Number of particles in the swarm.
        max_iterations: Maximum PSO iterations.
        plot: Whether to display the convergence plot.
        plot_file: Optional path to save the convergence plot.
        history_csv: Optional path to save per-iteration best fitness.
        params: Pre-built params; defaults to the Double Fork instance.
    """
    params = params or make_double_fork_params()
    print("Running PSO comparison: static inertia vs adaptive inertia\n")
    static_run = _run_pso(
        params,
        use_adaptive_weight=False,
        seed=seed,
        swarm_size=swarm_size,
        max_iterations=max_iterations,
    )
    adaptive_run = _run_pso(
        params,
        use_adaptive_weight=True,
        seed=seed,
        swarm_size=swarm_size,
        max_iterations=max_iterations,
    )
    print("Both runs completed.\n")

    _print_summary(static_run, adaptive_run)

    if history_csv:
        _save_history_csv(static_run, adaptive_run, history_csv)

    if plot or plot_file:
        _plot_convergence(
            static_run,
            adaptive_run,
            output_file=plot_file,
            show_plot=plot,
        )

    return static_run, adaptive_run


def _load_history_csv(csv_path: Path) -> tuple[List[int], List[float], List[float]]:
    """Load per-iteration best fitness curves from a saved CSV."""
    iterations: List[int] = []
    static_vals: List[float] = []
    adaptive_vals: List[float] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iterations.append(int(row["iteration"]))
            if row["static_best"] != "":
                static_vals.append(float(row["static_best"]))
            if row["adaptive_best"] != "":
                adaptive_vals.append(float(row["adaptive_best"]))
    return iterations, static_vals, adaptive_vals


def plot_history_from_csv(
    csv_path: Path,
    *,
    output_file: Path | None = None,
    show_plot: bool = True,
) -> None:
    """Plot convergence curves from the CSV exported by compare_inertia_weights."""
    iterations, static_vals, adaptive_vals = _load_history_csv(csv_path)
    plt.figure(figsize=(8, 4))
    plt.plot(iterations[: len(static_vals)], static_vals, label="Static inertia", color="#1f77b4")
    plt.plot(iterations[: len(adaptive_vals)], adaptive_vals, label="Adaptive inertia", color="#ff7f0e")
    plt.xlabel("Iteration")
    plt.ylabel("Best weighted objective")
    plt.title("PSO Inertia Weight Comparison (from CSV)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_file, dpi=200, bbox_inches="tight")
        print(f"Saved plot to {output_file}")

    if show_plot:
        plt.show(block=False)
    else:
        plt.close()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare PSO runs using static vs adaptive inertia weights "
            "(route update component unchanged)."
        )
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed used for both runs.")
    parser.add_argument("--swarm-size", type=int, default=40, help="Number of particles.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=150,
        help="PSO iteration budget for each run.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        default=True,
        help="Display convergence plot comparing static vs adaptive inertia (default: on).",
    )
    parser.add_argument(
        "--plot-file",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "outputs" / "plots" / "pso_inertia_weight_history_plot.png",
        help="Path to save the convergence plot (default: outputs/plots/pso_inertia_weight_history_plot.png).",
    )
    parser.add_argument(
        "--history-csv",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "outputs" / "csv" / "pso_inertia_weight_history.csv",
        help="Path to write per-iteration best fitness for both runs.",
    )
    parser.add_argument(
        "--plot-from-csv",
        type=Path,
        default=None,
        help="If provided, skip running PSO and plot this CSV instead.",
    )
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    if args.plot_from_csv:
        plot_history_from_csv(
            args.plot_from_csv,
            output_file=args.plot_file,
            show_plot=args.plot,
        )
    else:
        compare_inertia_weights(
            seed=args.seed,
            swarm_size=args.swarm_size,
            max_iterations=args.max_iterations,
            plot=args.plot,
            plot_file=args.plot_file,
            history_csv=args.history_csv,
        )
