"""
compare_all_algorithms.py

Utility script that compares all five optimization algorithms on the Double Fork:
- Simulated Annealing (SA)
- Genetic Algorithm (GA)
- Particle Swarm Optimization (PSO)
- Teaching-Learning Based Optimization (TLBO)
- Reinforcement Learning (RL)

Generates comparison tables and figures.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Tuple, Dict

import matplotlib.pyplot as plt

# Allow running via `python scripts/compare_all_algorithms.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from algorithms.ga.genetic_algorithm import genetic_algorithm
from algorithms.sa.simulated_annealing import simulated_annealing
from algorithms.pso.particle_swarm import particle_swarm_optimization
from algorithms.tlbo.teaching_learning_optimization import tlbo
from algorithms.rl.rl_optimizer import rl_optimization
from common.objectives import (
    objective_makespan,
    objective_total_cost,
    objective_weighted,
)
from common.params import make_double_fork_params


def _compute_metrics(solution) -> Tuple[float, float, float]:
    """Return weighted objective, makespan, and total cost for a solution."""
    weighted = float(objective_weighted(solution))
    makespan = float(objective_makespan(solution))
    total_cost = float(objective_total_cost(solution))
    return weighted, makespan, total_cost


def _plot_4_algorithm_comparison(
    metrics: Dict[str, Tuple[float, float, float]],
    runtimes: Dict[str, float],
    output_file: str | Path | None = None,
) -> None:
    """Create and optionally save comparison bar charts for all 4 algorithms."""
    labels = list(metrics.keys())
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12"]  # SA, GA, PSO, TLBO, RL

    weighted = [metrics[label][0] for label in labels]
    makespan = [metrics[label][1] for label in labels]
    cost = [metrics[label][2] for label in labels]
    runtime = [runtimes[label] for label in labels]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    plots = [
        ("Weighted Objective ↓", weighted, axes[0, 0], "Score"),
        ("Makespan (min)", makespan, axes[0, 1], "Minutes"),
        ("Total Cost (EGP)", cost, axes[1, 0], "EGP"),
        ("Runtime (s)", runtime, axes[1, 1], "Seconds"),
    ]

    for (title, values, ax, ylabel), color_list in zip(plots, [colors] * 4):
        bars = ax.bar(labels, values, color=colors)
        ax.set_title(title, fontsize=12, weight="bold")
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.3)
        
        # Add value labels on bars
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:.1f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

    fig.suptitle("Algorithm Comparison: SA vs GA vs PSO vs TLBO vs RL (Double Fork)", 
                 fontsize=14, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"📊 Saved comparison figure to {output_path}")

    plt.close(fig)


def _generate_html_dashboard(
    metrics: Dict[str, Tuple[float, float, float]],
    runtimes: Dict[str, float],
    output_file: str | Path,
) -> None:
    """Generate an interactive HTML dashboard comparing all 4 algorithms."""
    labels = list(metrics.keys())
    
    # Find best values for highlighting
    best_weighted_algo = min(metrics.keys(), key=lambda k: metrics[k][0])
    best_makespan_algo = min(metrics.keys(), key=lambda k: metrics[k][1])
    best_cost_algo = min(metrics.keys(), key=lambda k: metrics[k][2])
    fastest_algo = min(runtimes.keys(), key=lambda k: runtimes[k])
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Algorithm Comparison Dashboard</title>
    <style>
        :root {
            --sa-color: #e74c3c;
            --ga-color: #3498db;
            --pso-color: #2ecc71;
            --tlbo-color: #9b59b6;
            --rl-color: #f39c12;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5em;
            background: linear-gradient(90deg, #e74c3c, #3498db, #2ecc71, #9b59b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            text-align: center;
            color: #8892b0;
            margin-bottom: 40px;
            font-size: 1.1em;
        }
        
        .algorithms-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .algo-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .algo-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        
        .algo-card.sa { border-top: 4px solid var(--sa-color); }
        .algo-card.ga { border-top: 4px solid var(--ga-color); }
        .algo-card.pso { border-top: 4px solid var(--pso-color); }
        .algo-card.tlbo { border-top: 4px solid var(--tlbo-color); }
        .algo-card.rl { border-top: 4px solid var(--rl-color); }
        
        .algo-name {
            font-size: 1.4em;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .algo-card.sa .algo-name { color: var(--sa-color); }
        .algo-card.ga .algo-name { color: var(--ga-color); }
        .algo-card.pso .algo-name { color: var(--pso-color); }
        .algo-card.tlbo .algo-name { color: var(--tlbo-color); }
        .algo-card.rl .algo-name { color: var(--rl-color); }
        
        .algo-full-name {
            color: #8892b0;
            font-size: 0.85em;
            margin-bottom: 20px;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .metric:last-child {
            border-bottom: none;
        }
        
        .metric-label {
            color: #8892b0;
        }
        
        .metric-value {
            font-weight: 600;
            font-size: 1.1em;
        }
        
        .metric-value.best {
            color: #2ecc71;
        }
        
        .comparison-table {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 40px;
        }
        
        .comparison-table h2 {
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 16px;
            text-align: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        th {
            color: #8892b0;
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 1px;
        }
        
        td {
            font-size: 1.1em;
        }
        
        tr:hover td {
            background: rgba(255, 255, 255, 0.05);
        }
        
        .winner-badge {
            display: inline-block;
            background: linear-gradient(135deg, #2ecc71, #27ae60);
            color: #fff;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 600;
            margin-left: 8px;
        }
        
        .chart-container {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 30px;
        }
        
        .chart-container h2 {
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        
        .bar-chart {
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            height: 300px;
            padding: 20px;
        }
        
        .bar-group {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 20%;
        }
        
        .bar {
            width: 60px;
            border-radius: 8px 8px 0 0;
            transition: height 0.5s ease;
            position: relative;
        }
        
        .bar.sa { background: linear-gradient(180deg, var(--sa-color), #c0392b); }
        .bar.ga { background: linear-gradient(180deg, var(--ga-color), #2980b9); }
        .bar.pso { background: linear-gradient(180deg, var(--pso-color), #27ae60); }
        .bar.tlbo { background: linear-gradient(180deg, var(--tlbo-color), #8e44ad); }
        .bar.rl { background: linear-gradient(180deg, var(--rl-color), #e67e22); }
        
        .bar-label {
            margin-top: 10px;
            font-weight: 600;
        }
        
        .bar-value {
            position: absolute;
            top: -25px;
            width: 100%;
            text-align: center;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        @media (max-width: 1000px) {
            .algorithms-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        @media (max-width: 600px) {
            .algorithms-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Algorithm Comparison Dashboard</h1>
        <p class="subtitle">Double Fork EV Fleet Routing Optimization</p>
        
        <div class="algorithms-grid">
"""
    
    algo_full_names = {
        "SA": "Simulated Annealing",
        "GA": "Genetic Algorithm",
        "PSO": "Particle Swarm Optimization",
        "TLBO": "Teaching-Learning Based Optimization",
        "RL": "Reinforcement Learning (DQN)"
    }
    
    for algo in labels:
        weighted, makespan, cost = metrics[algo]
        runtime = runtimes[algo]
        
        is_best_weighted = algo == best_weighted_algo
        is_best_makespan = algo == best_makespan_algo
        is_best_cost = algo == best_cost_algo
        is_fastest = algo == fastest_algo
        
        html_content += f"""
            <div class="algo-card {algo.lower()}">
                <div class="algo-name">{algo}</div>
                <div class="algo-full-name">{algo_full_names[algo]}</div>
                <div class="metric">
                    <span class="metric-label">Weighted Objective</span>
                    <span class="metric-value {'best' if is_best_weighted else ''}">{weighted:.2f}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Makespan</span>
                    <span class="metric-value {'best' if is_best_makespan else ''}">{makespan:.1f} min</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Cost</span>
                    <span class="metric-value {'best' if is_best_cost else ''}">{cost:.2f} EGP</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Runtime</span>
                    <span class="metric-value {'best' if is_fastest else ''}">{runtime:.2f}s</span>
                </div>
            </div>
"""
    
    html_content += """
        </div>
        
        <div class="comparison-table">
            <h2>📊 Detailed Comparison</h2>
            <table>
                <thead>
                    <tr>
                        <th>Algorithm</th>
                        <th>Weighted Objective ↓</th>
                        <th>Makespan (min)</th>
                        <th>Total Cost (EGP)</th>
                        <th>Runtime (s)</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for algo in labels:
        weighted, makespan, cost = metrics[algo]
        runtime = runtimes[algo]
        
        winner_badges = ""
        if algo == best_weighted_algo:
            winner_badges += '<span class="winner-badge">Best Score</span>'
        if algo == fastest_algo and algo != best_weighted_algo:
            winner_badges += '<span class="winner-badge">Fastest</span>'
        
        html_content += f"""
                    <tr>
                        <td><strong>{algo}</strong>{winner_badges}</td>
                        <td>{weighted:.3f}</td>
                        <td>{makespan:.2f}</td>
                        <td>{cost:.2f}</td>
                        <td>{runtime:.2f}</td>
                    </tr>
"""
    
    # Calculate bar heights (normalize to max 250px)
    weighted_values = [metrics[a][0] for a in labels]
    max_weighted = max(weighted_values)
    bar_heights = [int((v / max_weighted) * 250) for v in weighted_values]
    
    html_content += """
                </tbody>
            </table>
        </div>
        
        <div class="chart-container">
            <h2>📈 Weighted Objective Comparison</h2>
            <div class="bar-chart">
"""
    
    for algo, height, value in zip(labels, bar_heights, weighted_values):
        html_content += f"""
                <div class="bar-group">
                    <div class="bar {algo.lower()}" style="height: {height}px;">
                        <div class="bar-value">{value:.1f}</div>
                    </div>
                    <div class="bar-label">{algo}</div>
                </div>
"""
    
    html_content += """
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content)
    print(f"🌐 Saved HTML dashboard to {output_path}")


def compare_all_algorithms(
    seed: int = 42,
    verbose: bool = True,
    save_plot: str | Path | None = None,
    save_html: str | Path | None = None,
    generate_individual_dashboards: bool = True,
    extended_run: bool = True,
):
    """
    Compare all 4 algorithms on the Double Fork instance.

    Args:
        seed: Random seed shared across optimizers
        verbose: Print textual observations
        save_plot: Optional path to save the comparison figure (PNG)
        save_html: Optional path to save the HTML dashboard
        generate_individual_dashboards: Generate solution dashboards for each algorithm
        extended_run: Use higher iteration counts for better solutions
    """
    print("=" * 80)
    print("SA vs GA vs PSO vs TLBO – Double Fork Instance")
    if extended_run:
        print("(Extended run mode: higher iteration counts for better solutions)")
    print("=" * 80)
    params = make_double_fork_params()
    
    outputs_dir = PROJECT_ROOT / "outputs" / "plots"

    # Run SA (extended: more iterations)
    print("\n🔥 Running Simulated Annealing…")
    start = time.time()
    sa_kwargs = {"seed": seed, "verbose": False, "show_plots": False}
    if extended_run:
        sa_kwargs["max_iterations"] = 3000  # Up from default 2000
    sa_result = simulated_annealing(params, **sa_kwargs)
    sa_time = time.time() - start
    print(f"   Completed in {sa_time:.2f}s")

    # Run GA (extended: more generations, larger population)
    print("🧬 Running Genetic Algorithm…")
    start = time.time()
    ga_kwargs = {"seed": seed, "verbose": False, "show_plots": False}
    if extended_run:
        ga_kwargs["pop_size"] = 80  # Up from 60
        ga_kwargs["num_generations"] = 200  # Up from 150
    ga_result = genetic_algorithm(params, **ga_kwargs)
    ga_time = time.time() - start
    print(f"   Completed in {ga_time:.2f}s")

    # Run PSO (extended: more iterations)
    print("🐝 Running Particle Swarm Optimization…")
    start = time.time()
    pso_kwargs = {"seed": seed, "verbose": False, "show_plots": False}
    if extended_run:
        pso_kwargs["max_iterations"] = 200  # Up from 150
        pso_kwargs["swarm_size"] = 50  # Up from 40
    pso_result = particle_swarm_optimization(params, **pso_kwargs)
    pso_time = time.time() - start
    print(f"   Completed in {pso_time:.2f}s")

    # Run TLBO (extended: more iterations)
    print("📚 Running Teaching-Learning Based Optimization…")
    start = time.time()
    tlbo_kwargs = {"seed": seed, "verbose": False, "show_plots": False}
    if extended_run:
        tlbo_kwargs["pop_size"] = 80  # Up from 50
        tlbo_kwargs["num_iterations"] = 200  # Up from 100
    tlbo_result = tlbo(params, **tlbo_kwargs)
    tlbo_time = time.time() - start
    print(f"   Completed in {tlbo_time:.2f}s")

    # Run RL (extended: more episodes)
    print("🤖 Running Reinforcement Learning (DQN)…")
    start = time.time()
    rl_kwargs = {"seed": seed, "verbose": False, "show_plots": False}
    if extended_run:
        rl_kwargs["n_episodes"] = 500  # Standard for RL
    rl_result = rl_optimization(params, **rl_kwargs)
    rl_time = time.time() - start
    print(f"   Completed in {rl_time:.2f}s")

    # Generate individual dashboards
    if generate_individual_dashboards:
        from common.visualization import generate_dashboard
        print("\n📊 Generating individual solution dashboards…")
        
        sa_dashboard = str(outputs_dir / "sa_solution_dashboard.html")
        ga_dashboard = str(outputs_dir / "ga_solution_dashboard.html")
        pso_dashboard = str(outputs_dir / "pso_solution_dashboard.html")
        tlbo_dashboard = str(outputs_dir / "tlbo_solution_dashboard.html")
        
        generate_dashboard(sa_result.best_solution, params, sa_dashboard, "Simulated Annealing")
        print(f"   ✅ SA dashboard: {sa_dashboard}")
        
        generate_dashboard(ga_result.best_solution, params, ga_dashboard, "Genetic Algorithm")
        print(f"   ✅ GA dashboard: {ga_dashboard}")
        
        generate_dashboard(pso_result.best_solution, params, pso_dashboard, "Particle Swarm Optimization")
        print(f"   ✅ PSO dashboard: {pso_dashboard}")
        
        generate_dashboard(tlbo_result.best_solution, params, tlbo_dashboard, "TLBO")
        print(f"   ✅ TLBO dashboard: {tlbo_dashboard}")
        
        rl_dashboard = str(outputs_dir / "rl_solution_dashboard.html")
        generate_dashboard(rl_result.best_solution, params, rl_dashboard, "Reinforcement Learning")
        print(f"   ✅ RL dashboard: {rl_dashboard}")

    # Compute metrics
    sa_metrics = _compute_metrics(sa_result.best_solution)
    ga_metrics = _compute_metrics(ga_result.best_solution)
    pso_metrics = _compute_metrics(pso_result.best_solution)
    tlbo_metrics = _compute_metrics(tlbo_result.best_solution)
    rl_metrics = _compute_metrics(rl_result.best_solution)
    
    metric_map = {
        "SA": sa_metrics,
        "GA": ga_metrics,
        "PSO": pso_metrics,
        "TLBO": tlbo_metrics,
        "RL": rl_metrics,
    }
    runtimes = {"SA": sa_time, "GA": ga_time, "PSO": pso_time, "TLBO": tlbo_time, "RL": rl_time}

    # Print summary table
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    header = f"{'Algo':<6} | {'Weighted':>12} | {'Makespan (min)':>15} | {'Cost (EGP)':>12} | {'Runtime (s)':>12}"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    for algo in ["SA", "GA", "PSO", "TLBO", "RL"]:
        m = metric_map[algo]
        r = runtimes[algo]
        print(f"{algo:<6} | {m[0]:>12.3f} | {m[1]:>15.2f} | {m[2]:>12.2f} | {r:>12.2f}")
    
    print("-" * len(header))

    if verbose:
        print("\n📋 Observations:")
        best_algo = min(metric_map.keys(), key=lambda k: metric_map[k][0])
        fastest_algo = min(runtimes.keys(), key=lambda k: runtimes[k])
        print(f"   • Best weighted score: {best_algo} ({metric_map[best_algo][0]:.3f})")
        print(f"   • Fastest algorithm: {fastest_algo} ({runtimes[fastest_algo]:.2f}s)")
        
        # Check feasibility
        print("\n🔍 Feasibility Check:")
        print(f"   • SA feasible: {sa_result.best_solution.is_feasible()}")
        print(f"   • GA feasible: {ga_result.best_solution.is_feasible()}")
        print(f"   • PSO feasible: {pso_result.best_solution.is_feasible()}")
        print(f"   • TLBO feasible: {tlbo_result.best_solution.is_feasible()}")
        print(f"   • RL feasible: {rl_result.best_solution.is_feasible()}")

    # Save outputs
    if save_plot:
        _plot_4_algorithm_comparison(metric_map, runtimes, output_file=save_plot)
    
    if save_html:
        _generate_html_dashboard(metric_map, runtimes, output_file=save_html)

    return {
        "SA": (sa_result, sa_time),
        "GA": (ga_result, ga_time),
        "PSO": (pso_result, pso_time),
        "TLBO": (tlbo_result, tlbo_time),
        "RL": (rl_result, rl_time),
    }


if __name__ == "__main__":
    outputs_dir = PROJECT_ROOT / "outputs" / "plots"
    
    compare_all_algorithms(
        seed=42,
        save_plot=outputs_dir / "all_algorithms_comparison.png",
        save_html=outputs_dir / "all_algorithms_comparison.html",
        generate_individual_dashboards=True,
        extended_run=True,
    )

