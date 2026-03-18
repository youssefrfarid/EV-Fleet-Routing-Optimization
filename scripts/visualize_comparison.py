"""
visualize_comparison.py

Generate comprehensive side-by-side comparison visualization for GA vs SA.
"""
from __future__ import annotations

import sys
import matplotlib.pyplot as plt
import numpy as np
import webbrowser
from pathlib import Path
from typing import Tuple

# Allow running as `python scripts/visualize_comparison.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.objectives import (
    FleetSolution,
    objective_makespan,
    objective_total_cost,
    objective_weighted,
)
from common.params import SingleForkParams

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLOTS_DIR = PROJECT_ROOT / "outputs" / "plots"

def create_comparison_visualization(
    sa_result,
    ga_result,
    params: SingleForkParams,
    sa_execution_time: float = 0.0,
    ga_execution_time: float = 0.0,
    output_file: str | Path = PLOTS_DIR / "ga_vs_sa_comparison.html",
):
    """
    Create comprehensive HTML comparison visualization.
    
    Args:
        sa_result: SAResult from simulated annealing
        ga_result: GAResult from genetic algorithm
        params: Problem parameters
        output_file: Output HTML filename
    """
    
    sa_solution = sa_result.best_solution
    ga_solution = ga_result.best_solution
    
    # Calculate all metrics
    sa_metrics = calculate_all_metrics(sa_solution, params)
    ga_metrics = calculate_all_metrics(ga_solution, params)
    
    # Generate individual solution dashboards
    from common.visualization import generate_dashboard
    
    sa_dashboard = PLOTS_DIR / "sa_solution_detail.html"
    ga_dashboard = PLOTS_DIR / "ga_solution_detail.html"
    
    print("Generating individual solution dashboards...")
    generate_dashboard(sa_solution, params, sa_dashboard, "Simulated Annealing")
    generate_dashboard(ga_solution, params, ga_dashboard, "Genetic Algorithm")
    
    # Generate HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GA vs SA Comparison - Double Fork EV Fleet</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
{_get_comparison_css()}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 GA vs 🔥 SA: Algorithm Comparison</h1>
        <p class="subtitle">Double Fork EV Fleet Routing Problem</p>
    </div>
    
    <div class="container">
        <!-- Solution Dashboard Links -->
        <div class="dashboard-links">
            <a href="{sa_dashboard}" target="_blank" class="dashboard-btn sa-btn">
                🔥 View SA Solution Details →
            </a>
            <a href="{ga_dashboard}" target="_blank" class="dashboard-btn ga-btn">
                🧬 View GA Solution Details →
            </a>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary-section">
            <h2>📊 Overall Performance</h2>
            <div class="cards-grid">
                <div class="card sa-card">
                    <div class="card-header">🔥 Simulated Annealing</div>
                    <div class="metric-large">{sa_metrics['total_weighted']:.2f}</div>
                    <div class="metric-label">Total Weighted Objective</div>
                    <div class="metric-subtext">Lower is better</div>
                </div>
                
                <div class="card ga-card">
                    <div class="card-header">🧬 Genetic Algorithm</div>
                    <div class="metric-large">{ga_metrics['total_weighted']:.2f}</div>
                    <div class="metric-label">Total Weighted Objective</div>
                    <div class="metric-subtext">Lower is better</div>
                </div>
                
                <div class="card improvement-card">
                    <div class="card-header">✨ Improvement</div>
                    <div class="metric-large">{((sa_metrics['total_weighted'] - ga_metrics['total_weighted']) / sa_metrics['total_weighted'] * 100):.1f}%</div>
                    <div class="metric-label">GA Better Than SA</div>
                    <div class="metric-subtext">Significant improvement!</div>
                </div>
            </div>
        </div>
        
        <!-- Detailed Metrics Comparison -->
        <div class="metrics-section">
            <h2>📈 Detailed Metrics Comparison</h2>
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th class="sa-col">🔥 SA</th>
                        <th class="ga-col">🧬 GA</th>
                        <th>Difference</th>
                        <th>Winner</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Total Weighted Objective</strong></td>
                        <td class="sa-col">{sa_metrics['total_weighted']:.2f}</td>
                        <td class="ga-col">{ga_metrics['total_weighted']:.2f}</td>
                        <td class="{"pos-diff" if ga_metrics['total_weighted'] < sa_metrics['total_weighted'] else "neg-diff"}">{sa_metrics['total_weighted'] - ga_metrics['total_weighted']:.2f}</td>
                        <td>{"🧬 GA" if ga_metrics['total_weighted'] < sa_metrics['total_weighted'] else "🔥 SA"}</td>
                    </tr>
                    <tr>
                        <td>Makespan (minutes)</td>
                        <td class="sa-col">{sa_metrics['makespan']:.2f}</td>
                        <td class="ga-col">{ga_metrics['makespan']:.2f}</td>
                        <td class="{"pos-diff" if ga_metrics['makespan'] < sa_metrics['makespan'] else "neg-diff"}">{sa_metrics['makespan'] - ga_metrics['makespan']:.2f}</td>
                        <td>{"🧬 GA" if ga_metrics['makespan'] < sa_metrics['makespan'] else "🔥 SA"}</td>
                    </tr>
                    <tr>
                        <td>Total Cost (EGP)</td>
                        <td class="sa-col">{sa_metrics['total_cost']:.2f}</td>
                        <td class="ga-col">{ga_metrics['total_cost']:.2f}</td>
                        <td class="{"pos-diff" if ga_metrics['total_cost'] < sa_metrics['total_cost'] else "neg-diff"}">{sa_metrics['total_cost'] - ga_metrics['total_cost']:.2f}</td>
                        <td>{"🧬 GA" if ga_metrics['total_cost'] < sa_metrics['total_cost'] else "🔥 SA"}</td>
                    </tr>
                    <tr>
                        <td>Total Charging Time (min)</td>
                        <td class="sa-col">{sa_metrics['total_charging_time']:.2f}</td>
                        <td class="ga-col">{ga_metrics['total_charging_time']:.2f}</td>
                        <td class="{"pos-diff" if ga_metrics['total_charging_time'] < sa_metrics['total_charging_time'] else "neg-diff"}">{sa_metrics['total_charging_time'] - ga_metrics['total_charging_time']:.2f}</td>
                        <td>{"🧬 GA" if ga_metrics['total_charging_time'] < sa_metrics['total_charging_time'] else "🔥 SA"}</td>
                    </tr>
                    <tr>
                        <td>Total Energy Charged (kWh)</td>
                        <td class="sa-col">{sa_metrics['total_energy']:.2f}</td>
                        <td class="ga-col">{ga_metrics['total_energy']:.2f}</td>
                        <td class="{"pos-diff" if ga_metrics['total_energy'] < sa_metrics['total_energy'] else "neg-diff"}">{sa_metrics['total_energy'] - ga_metrics['total_energy']:.2f}</td>
                        <td>{"🧬 GA" if ga_metrics['total_energy'] < sa_metrics['total_energy'] else "🔥 SA"}</td>
                    </tr>
                    <tr>
                        <td>Average Speed (km/h)</td>
                        <td class="sa-col">{sa_metrics['avg_speed']:.2f}</td>
                        <td class="ga-col">{ga_metrics['avg_speed']:.2f}</td>
                        <td>{abs(sa_metrics['avg_speed'] - ga_metrics['avg_speed']):.2f}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td><strong>⏱️ Execution Time (seconds)</strong></td>
                        <td class="sa-col"><strong>{sa_execution_time:.2f}</strong></td>
                        <td class="ga-col"><strong>{ga_execution_time:.2f}</strong></td>
                        <td class="{"pos-diff" if sa_execution_time < ga_execution_time else "neg-diff"}">{abs(sa_execution_time - ga_execution_time):.2f}</td>
                        <td>{"🔥 SA" if sa_execution_time < ga_execution_time else "🧬 GA"}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- Convergence Comparison -->
        <div class="chart-section">
            <h2>📉 Convergence Comparison</h2>
            <canvas id="convergenceChart"></canvas>
        </div>
        
        <!-- Per-Vehicle Comparison -->
        <div class="vehicle-section">
            <h2>🚗 Per-Vehicle Comparison</h2>
            {_generate_vehicle_comparison_html(sa_solution, ga_solution, params)}
        </div>
        
        <!-- Route Comparison -->
        <div class="route-section">
            <h2>🗺️ Route Strategy Comparison</h2>
            {_generate_route_comparison_html(sa_solution, ga_solution, params)}
        </div>
        
        <!-- Key Differences -->
        <div class="insights-section">
            <h2>🔍 Key Differences</h2>
            {_generate_key_differences_html(sa_metrics, ga_metrics, sa_solution, ga_solution, sa_execution_time, ga_execution_time)}
        </div>
        
        <!-- Algorithm Characteristics -->
        <div class="algo-section">
            <h2>⚙️ Algorithm Characteristics</h2>
            <div class="algo-grid">
                <div class="algo-card">
                    <h3>🔥 Simulated Annealing</h3>
                    <ul>
                        <li><strong>Iterations:</strong> {len(sa_result.history)}</li>
                        <li><strong>Search Type:</strong> Single-solution trajectory</li>
                        <li><strong>Acceptance:</strong> Temperature-based probabilistic</li>
                        <li><strong>Exploration:</strong> Sequential neighborhood search</li>
                        <li><strong>Best for:</strong> Quick convergence, simple landscapes</li>
                    </ul>
                </div>
                <div class="algo-card">
                    <h3>🧬 Genetic Algorithm</h3>
                    <ul>
                        <li><strong>Generations:</strong> {len(ga_result.history)}</li>
                        <li><strong>Search Type:</strong> Population-based (60 individuals)</li>
                        <li><strong>Acceptance:</strong> Fitness selection + elitism</li>
                        <li><strong>Exploration:</strong> Crossover + mutation operators</li>
                        <li><strong>Best for:</strong> Complex landscapes, diverse solutions</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    
    <script>
{_get_convergence_chart_js(sa_result, ga_result)}
    </script>
</body>
</html>
"""
    
    # Write to file
    output_path = Path(output_file).absolute()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content)
    print(f"✅ Comparison visualization saved to: {output_file}")
    print(f"✅ SA dashboard saved to: {sa_dashboard}")
    print(f"✅ GA dashboard saved to: {ga_dashboard}")
    
    return output_path


def calculate_all_metrics(solution: FleetSolution, params: SingleForkParams) -> dict:
    """Calculate comprehensive metrics for a solution."""
    
    makespan = objective_makespan(solution)
    total_cost = objective_total_cost(solution)
    total_weighted = objective_weighted(solution)
    
    # Charging metrics
    total_charging_time = sum(
        vs.get_total_charging_time() for vs in solution.vehicle_solutions
    )
    
    total_energy = sum(
        sum(vs.charging_amounts.values()) for vs in solution.vehicle_solutions
    )
    
    # Speed metrics
    all_speeds = []
    for vs in solution.vehicle_solutions:
        if vs.speed_levels:
            all_speeds.extend(vs.speed_levels.values())
    avg_speed = np.mean(all_speeds) if all_speeds else 0.0
    
    return {
        'total_weighted': total_weighted,
        'makespan': makespan,
        'total_cost': total_cost,
        'total_charging_time': total_charging_time,
        'total_energy': total_energy,
        'avg_speed': avg_speed,
    }


def _generate_vehicle_comparison_html(sa_sol, ga_sol, params):
    """Generate per-vehicle comparison table."""
    
    html = '<table class="vehicle-table"><thead><tr>'
    html += '<th>Vehicle</th>'
    html += '<th>Metric</th>'
    html += '<th class="sa-col">🔥 SA</th>'
    html += '<th class="ga-col">🧬 GA</th>'
    html += '<th>Difference</th>'
    html += '</tr></thead><tbody>'
    
    for i, (sa_vs, ga_vs) in enumerate(zip(sa_sol.vehicle_solutions, ga_sol.vehicle_solutions)):
        # Completion time
        html += f'<tr><td rowspan="4"><strong>Vehicle {i+1}</strong><br>({params.battery_kwh[i]:.0f} kWh)</td>'
        html += f'<td>Completion Time</td>'
        html += f'<td class="sa-col">{sa_vs.get_completion_time():.2f} min</td>'
        html += f'<td class="ga-col">{ga_vs.get_completion_time():.2f} min</td>'
        html += f'<td>{sa_vs.get_completion_time() - ga_vs.get_completion_time():.2f}</td></tr>'
        
        # Charging cost
        html += f'<tr><td>Charging Cost</td>'
        html += f'<td class="sa-col">{sa_vs.get_total_charging_cost(params):.2f} EGP</td>'
        html += f'<td class="ga-col">{ga_vs.get_total_charging_cost(params):.2f} EGP</td>'
        html += f'<td>{sa_vs.get_total_charging_cost(params) - ga_vs.get_total_charging_cost(params):.2f}</td></tr>'
        
        # Charging time
        html += f'<tr><td>Charging Time</td>'
        html += f'<td class="sa-col">{sa_vs.get_total_charging_time():.2f} min</td>'
        html += f'<td class="ga-col">{ga_vs.get_total_charging_time():.2f} min</td>'
        html += f'<td>{sa_vs.get_total_charging_time() - ga_vs.get_total_charging_time():.2f}</td></tr>'
        
        # Route
        sa_route_str = ' → '.join(sa_vs.route)
        ga_route_str = ' → '.join(ga_vs.route)
        html += f'<tr><td>Route</td>'
        html += f'<td class="sa-col route-cell">{sa_route_str}</td>'
        html += f'<td class="ga-col route-cell">{ga_route_str}</td>'
        html += f'<td>{"✓ Same" if sa_vs.route == ga_vs.route else "✗ Different"}</td></tr>'
    
    html += '</tbody></table>'
    return html


def _generate_route_comparison_html(sa_sol, ga_sol, params):
    """Generate route strategy comparison."""
    
    # Count route types
    sa_routes = {}
    ga_routes = {}
    
    for vs in sa_sol.vehicle_solutions:
        route_sig = tuple(vs.route)
        sa_routes[route_sig] = sa_routes.get(route_sig, 0) + 1
    
    for vs in ga_sol.vehicle_solutions:
        route_sig = tuple(vs.route)
        ga_routes[route_sig] = ga_routes.get(route_sig, 0) + 1
    
    html = '<div class="route-grid">'
    html += '<div class="route-card"><h3>🔥 SA Routes</h3><ul>'
    for route, count in sa_routes.items():
        html += f'<li><strong>{" → ".join(route[:4])}...{route[-1]}</strong>: {count} vehicle(s)</li>'
    html += '</ul></div>'
    
    html += '<div class="route-card"><h3>🧬 GA Routes</h3><ul>'
    for route, count in ga_routes.items():
        html += f'<li><strong>{" → ".join(route[:4])}...{route[-1]}</strong>: {count} vehicle(s)</li>'
    html += '</ul></div>'
    html += '</div>'
    
    return html


def _generate_key_differences_html(sa_metrics, ga_metrics, sa_sol, ga_sol, sa_execution_time=0.0, ga_execution_time=0.0):
    """Generate key differences insights."""
    
    html = '<div class="insights-grid">'
    
    # Time efficiency
    time_diff_pct = ((sa_metrics['makespan'] - ga_metrics['makespan']) / sa_metrics['makespan'] * 100)
    html += '<div class="insight-card">'
    html += '<h3>⏱️ Time Efficiency</h3>'
    html += f'<p>GA completes <strong>{abs(time_diff_pct):.1f}%</strong> '
    html += f'{"faster" if time_diff_pct > 0 else "slower"} than SA</p>'
    html += f'<p class="detail">Makespan: {ga_metrics["makespan"]:.1f} min vs {sa_metrics["makespan"]:.1f} min</p>'
    html += '</div>'
    
    # Cost efficiency
    cost_diff_pct = ((sa_metrics['total_cost'] - ga_metrics['total_cost']) / sa_metrics['total_cost'] * 100)
    html += '<div class="insight-card">'
    html += '<h3>💰 Cost Efficiency</h3>'
    html += f'<p>GA saves <strong>{abs(cost_diff_pct):.1f}%</strong> on charging costs</p>'
    html += f'<p class="detail">Cost: {ga_metrics["total_cost"]:.2f} EGP vs {sa_metrics["total_cost"]:.2f} EGP</p>'
    html += '</div>'
    
    # Energy usage
    energy_diff = sa_metrics['total_energy'] - ga_metrics['total_energy']
    html += '<div class="insight-card">'
    html += '<h3>⚡ Energy Usage</h3>'
    html += f'<p>GA uses <strong>{abs(energy_diff):.1f} kWh</strong> '
    html += f'{"less" if energy_diff > 0 else "more"} energy</p>'
    html += f'<p class="detail">Total: {ga_metrics["total_energy"]:.1f} kWh vs {sa_metrics["total_energy"]:.1f} kWh</p>'
    html += '</div>'
    
    # Speed strategy
    html += '<div class="insight-card">'
    html += '<h3>🏎️ Speed Strategy</h3>'
    html += f'<p>GA average speed: <strong>{ga_metrics["avg_speed"]:.1f} km/h</strong></p>'
    html += f'<p>SA average speed: <strong>{sa_metrics["avg_speed"]:.1f} km/h</strong></p>'
    html += f'<p class="detail">{"GA drives faster" if ga_metrics["avg_speed"] > sa_metrics["avg_speed"] else "SA drives faster"}</p>'
    html += '</div>'
    
    # Execution time
    html += '<div class="insight-card">'
    html += '<h3>⏱️ Execution Time</h3>'
    if sa_execution_time > 0 and ga_execution_time > 0:
        if sa_execution_time < ga_execution_time:
            speedup = ga_execution_time / sa_execution_time
            html += f'<p>SA completed <strong>{speedup:.2f}x faster</strong></p>'
            html += f'<p class="detail">{sa_execution_time:.2f}s vs {ga_execution_time:.2f}s</p>'
        else:
            speedup = sa_execution_time / ga_execution_time
            html += f'<p>GA completed <strong>{speedup:.2f}x faster</strong></p>'
            html += f'<p class="detail">{ga_execution_time:.2f}s vs {sa_execution_time:.2f}s</p>'
    else:
        html += '<p>Run comparison to see execution times</p>'
    html += '</div>'
    
    html += '</div>'
    return html


def _get_convergence_chart_js(sa_result, ga_result):
    """Generate JavaScript for convergence comparison chart."""
    
    # SA data - sample for performance if too many points
    sa_iterations = [h[0] for h in sa_result.history]
    sa_costs = [h[2] for h in sa_result.history]
    
    # Sample SA data if too many points
    if len(sa_iterations) > 500:
        step = len(sa_iterations) // 500
        sa_iterations = sa_iterations[::step]
        sa_costs = sa_costs[::step]
    
    # GA data
    ga_generations = [h[0] for h in ga_result.history]
    ga_fitness = [h[1] for h in ga_result.history]  # best fitness
    
    # Format data for Chart.js
    sa_data_points = [{"x": x, "y": y} for x, y in zip(sa_iterations, sa_costs)]
    ga_data_points = [{"x": g * 60, "y": f} for g, f in zip(ga_generations, ga_fitness)]  # Scale to match SA
    
    import json
    
    return f"""
const ctx = document.getElementById('convergenceChart').getContext('2d');
new Chart(ctx, {{
    type: 'line',
    data: {{
        datasets: [
            {{
                label: '🔥 SA (Current Cost)',
                data: {json.dumps(sa_data_points)},
                borderColor: '#ff6b6b',
                backgroundColor: 'rgba(255, 107, 107, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.1
            }},
            {{
                label: '🧬 GA (Best Fitness)',
                data: {json.dumps(ga_data_points)},
                borderColor: '#4ecdc4',
                backgroundColor: 'rgba(78, 205, 196, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.1
            }}
        ]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: true,
        scales: {{
            x: {{
                type: 'linear',
                title: {{
                    display: true,
                    text: 'Evaluations (SA iterations / GA scaled generations)'
                }}
            }},
            y: {{
                title: {{
                    display: true,
                    text: 'Objective Value (lower is better)'
                }}
            }}
        }},
        plugins: {{
            legend: {{
                display: true,
                position: 'top'
            }},
            tooltip: {{
                mode: 'index',
                intersect: false
            }}
        }},
        interaction: {{
            mode: 'nearest',
            axis: 'x',
            intersect: false
        }}
    }}
}});
"""


def _get_comparison_css():
    """Return CSS styling for comparison page."""
    return """
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #333;
    padding: 20px;
}

.header {
    text-align: center;
    color: white;
    margin-bottom: 30px;
}

.header h1 {
    font-size: 2.5em;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.subtitle {
    font-size: 1.2em;
    opacity: 0.9;
}

.dashboard-links {
    display: flex;
    gap: 20px;
    justify-content: center;
    margin-bottom: 25px;
}

.dashboard-btn {
    padding: 15px 30px;
    border-radius: 10px;
    text-decoration: none;
    font-size: 1.1em;
    font-weight: bold;
    color: white;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}

.dashboard-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

.sa-btn {
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
}

.ga-btn {
    background: linear-gradient(135deg, #4ecdc4 0%, #44a08d 100%);
}

.container {
    max-width: 1400px;
    margin: 0 auto;
}

.summary-section, .metrics-section, .chart-section, 
.vehicle-section, .route-section, .insights-section, .algo-section {
    background: white;
    border-radius: 15px;
    padding: 30px;
    margin-bottom: 25px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

h2 {
    color: #667eea;
    margin-bottom: 20px;
    font-size: 1.8em;
    border-bottom: 3px solid #667eea;
    padding-bottom: 10px;
}

.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin-top: 20px;
}

.card {
    padding: 25px;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    transition: transform 0.3s ease;
}

.card:hover {
    transform: translateY(-5px);
}

.sa-card {
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
    color: white;
}

.ga-card {
    background: linear-gradient(135deg, #4ecdc4 0%, #44a08d 100%);
    color: white;
}

.improvement-card {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
}

.card-header {
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 15px;
    opacity: 0.9;
}

.metric-large {
    font-size: 3em;
    font-weight: bold;
    margin: 15px 0;
}

.metric-label {
    font-size: 1.1em;
    margin-top: 10px;
}

.metric-subtext {
    font-size: 0.9em;
    opacity: 0.8;
    margin-top: 5px;
}

.comparison-table, .vehicle-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}

.comparison-table th, .vehicle-table th {
    background: #667eea;
    color: white;
    padding: 15px;
    text-align: left;
    font-weight: bold;
}

.comparison-table td, .vehicle-table td {
    padding: 12px 15px;
    border-bottom: 1px solid #e0e0e0;
}

.comparison-table tr:hover, .vehicle-table tr:hover {
    background: #f5f5f5;
}

.sa-col {
    background: rgba(255, 107, 107, 0.1);
}

.ga-col {
    background: rgba(78, 205, 196, 0.1);
}

.pos-diff {
    color: #27ae60;
    font-weight: bold;
}

.neg-diff {
    color: #e74c3c;
    font-weight: bold;
}

.route-cell {
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
}

#convergenceChart {
    max-height: 400px;
    margin-top: 20px;
}

.route-grid, .insights-grid, .algo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin-top: 20px;
}

.route-card, .insight-card, .algo-card {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 10px;
    border-left: 4px solid #667eea;
}

.route-card h3, .insight-card h3, .algo-card h3 {
    color: #667eea;
    margin-bottom: 15px;
}

.route-card ul, .algo-card ul {
    list-style: none;
    padding-left: 0;
}

.route-card li, .algo-card li {
    padding: 8px 0;
    border-bottom: 1px solid #e0e0e0;
}

.route-card li:last-child, .algo-card li:last-child {
    border-bottom: none;
}

.insight-card p {
    margin: 10px 0;
}

.insight-card .detail {
    font-size: 0.9em;
    color: #666;
    font-style: italic;
}

@media (max-width: 768px) {
    .cards-grid, .route-grid, .insights-grid, .algo-grid {
        grid-template-columns: 1fr;
    }
    
    .header h1 {
        font-size: 1.8em;
    }
}
"""


# Standalone usage
if __name__ == "__main__":
    from scripts.compare_ga_sa import compare_algorithms_double_fork

    print("Running comparison and generating visualization...")
    sa_result, ga_result, sa_time, ga_time = compare_algorithms_double_fork(seed=42, verbose=False)

    from common.params import make_double_fork_params
    params = make_double_fork_params()

    output_file = create_comparison_visualization(sa_result, ga_result, params, sa_time, ga_time)

    # Auto-open in browser
    print("\nOpening comparison in your default browser...")
    webbrowser.open(f'file://{output_file.absolute()}')
    print("Done!")
