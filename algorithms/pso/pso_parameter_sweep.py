#!/usr/bin/env python3
"""
pso_parameter_sweep.py

Run a grid search over key PSO hyperparameters and export numerical / graphical
results for parameter-sensitivity analysis.
"""

from __future__ import annotations

import sys
import csv
import itertools
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Allow running directly via `python algorithms/pso/pso_parameter_sweep.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.objectives import objective_makespan, objective_total_cost, objective_weighted
from common.params import make_double_fork_params
from algorithms.pso.particle_swarm import particle_swarm_optimization

RESULTS_PATH = PROJECT_ROOT / "outputs" / "csv" / "pso_parameter_sweep.csv"
FIGURE_PATH = PROJECT_ROOT / "outputs" / "plots" / "pso_parameter_sweep.png"


def _ensure_dirs():
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)


def run_sweep(
    swarm_sizes=(30, 45, 60),
    inertias=(0.4, 0.6, 0.8),
    accel_pairs=((1.5, 1.5), (1.7, 1.7)),
    iterations: int = 150,
) -> list[dict]:
    params = make_double_fork_params()
    rows: list[dict] = []
    for swarm, w, (c1, c2) in itertools.product(swarm_sizes, inertias, accel_pairs):
        start = time.time()
        result = particle_swarm_optimization(
            params,
            swarm_size=swarm,
            max_iterations=iterations,
            w=w,
            c1=c1,
            c2=c2,
            show_plots=False,
            verbose=False,
        )
        runtime = time.time() - start
        solution = result.best_solution
        rows.append(
            {
                "swarm": swarm,
                "w": w,
                "c1": c1,
                "c2": c2,
                "weighted": float(objective_weighted(solution)),
                "makespan": float(objective_makespan(solution)),
                "cost": float(objective_total_cost(solution)),
                "runtime": runtime,
            }
        )
        print(
            f"[SWEEP] swarm={swarm:02d} w={w:.2f} c1=c2={c1:.1f} -> "
            f"weighted={rows[-1]['weighted']:.2f}"
        )
    return rows


def export_csv(rows: list[dict]) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["swarm", "w", "c1", "c2", "weighted", "makespan", "cost", "runtime"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"💾 Saved parameter sweep CSV to {RESULTS_PATH}")


def export_heatmap(rows: list[dict]) -> None:
    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    swarms = sorted({row["swarm"] for row in rows})
    inertias = sorted({row["w"] for row in rows})
    matrix = np.zeros((len(inertias), len(swarms)))
    for i, w in enumerate(inertias):
        for j, swarm in enumerate(swarms):
            subset = [r for r in rows if r["swarm"] == swarm and r["w"] == w]
            if subset:
                best = min(subset, key=lambda r: r["weighted"])
                matrix[i, j] = best["weighted"]

    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(matrix, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(swarms)))
    ax.set_xticklabels(swarms)
    ax.set_ylabel("Inertia (w)")
    ax.set_yticks(range(len(inertias)))
    ax.set_yticklabels([f"{w:.1f}" for w in inertias])
    ax.set_xlabel("Swarm Size")
    ax.set_title("PSO Weighted Objective – Best c1=c2 per grid cell")
    fig.colorbar(im, ax=ax, label="Weighted objective (lower better)")
    fig.tight_layout()
    fig.savefig(FIGURE_PATH, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"📈 Saved sweep heatmap to {FIGURE_PATH}")


def main():
    _ensure_dirs()
    rows = run_sweep()
    export_csv(rows)
    export_heatmap(rows)


if __name__ == "__main__":
    main()
