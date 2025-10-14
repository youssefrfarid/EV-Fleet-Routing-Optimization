"""
visualize_objectives.py
Visualize objective function results and solution analysis.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from typing import List, Tuple
from objectives import FleetSolution, evaluate_solution, objective_weighted


def visualize_solution(solution: FleetSolution, save_path=None):
    """
    Create comprehensive visualization of a fleet solution.
    """
    results = evaluate_solution(solution, verbose=True)
    
    fig = plt.figure(figsize=(16, 12))
    
    # ========== Main Objectives Summary ==========
    ax1 = plt.subplot(3, 3, 1)
    ax1.set_title("Primary Objectives", fontsize=14, fontweight='bold')
    ax1.axis('off')
    
    feasibility = "✓ FEASIBLE" if results['feasible'] else "✗ INFEASIBLE"
    feasibility_color = 'green' if results['feasible'] else 'red'
    
    summary_text = f"""
    Status: {feasibility}
    
    Makespan:          {results['makespan']:.1f} min
    Total Cost:        {results['total_cost']:.2f} EGP
    Weighted Obj:      {results['weighted_objective']:.2f}
    
    Fleet Size:        {results['num_vehicles']} vehicles
    Total Energy:      {results['total_energy_charged']:.1f} kWh
    Total Charge Time: {results['total_charging_time']:.1f} min
    """
    
    ax1.text(0.1, 0.5, summary_text, fontsize=11, verticalalignment='center',
            fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
    
    # ========== Vehicle Completion Times (with bottleneck) ==========
    ax2 = plt.subplot(3, 3, 2)
    ax2.set_title("Vehicle Completion Times", fontsize=14, fontweight='bold')
    
    makespan_details = results['makespan_details']
    completion_times = makespan_details['completion_times']
    bottleneck_idx = makespan_details['bottleneck_vehicle']
    
    vehicle_ids = [f"EV {i+1}" for i in range(len(completion_times))]
    colors = ['red' if i == bottleneck_idx else 'steelblue' for i in range(len(completion_times))]
    
    bars = ax2.barh(vehicle_ids, completion_times, color=colors, alpha=0.8)
    ax2.axvline(results['makespan'], color='red', linestyle='--', linewidth=2, 
                label=f"Makespan: {results['makespan']:.1f} min")
    ax2.axvline(makespan_details['average_completion'], color='green', linestyle=':', 
                linewidth=2, label=f"Avg: {makespan_details['average_completion']:.1f} min")
    
    # Add value labels
    for i, (bar, time) in enumerate(zip(bars, completion_times)):
        label_text = f"{time:.1f}"
        if i == bottleneck_idx:
            label_text += " ← BOTTLENECK"
        ax2.text(time + 1, bar.get_y() + bar.get_height()/2, label_text,
                va='center', fontsize=9, fontweight='bold' if i == bottleneck_idx else 'normal')
    
    ax2.set_xlabel('Time (minutes)', fontsize=10)
    ax2.legend(fontsize=9)
    ax2.grid(axis='x', alpha=0.3)
    
    # ========== Cost Breakdown by Vehicle ==========
    ax3 = plt.subplot(3, 3, 3)
    ax3.set_title("Charging Cost by Vehicle", fontsize=14, fontweight='bold')
    
    cost_details = results['cost_details']
    vehicle_costs = cost_details['by_vehicle']
    vehicle_ids_cost = [f"EV {i+1}" for i in range(len(vehicle_costs))]
    
    bars = ax3.bar(vehicle_ids_cost, vehicle_costs, color='gold', alpha=0.8, edgecolor='black')
    ax3.axhline(np.mean(vehicle_costs), color='red', linestyle='--', linewidth=2, 
                label=f"Avg: {np.mean(vehicle_costs):.2f} EGP")
    
    # Add value labels
    for bar, cost in zip(bars, vehicle_costs):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{cost:.2f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    ax3.set_ylabel('Cost (EGP)', fontsize=10)
    ax3.set_xlabel('Vehicle', fontsize=10)
    ax3.legend(fontsize=9)
    ax3.grid(axis='y', alpha=0.3)
    
    # ========== Cost Breakdown by Station ==========
    ax4 = plt.subplot(3, 3, 4)
    ax4.set_title("Total Cost by Station", fontsize=14, fontweight='bold')
    
    station_costs = cost_details['by_station']
    stations = list(station_costs.keys())
    costs = [station_costs[s] for s in stations]
    
    colors_station = ['lightgreen' if s in solution.params.upper_stations else 'lightcoral' 
                     for s in stations]
    bars = ax4.bar(stations, costs, color=colors_station, alpha=0.8, edgecolor='black')
    
    # Add value labels
    for bar, cost in zip(bars, costs):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                f'{cost:.2f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax4.set_ylabel('Total Cost (EGP)', fontsize=10)
    ax4.set_xlabel('Station', fontsize=10)
    ax4.grid(axis='y', alpha=0.3)
    
    # ========== Station Utilization ==========
    ax5 = plt.subplot(3, 3, 5)
    ax5.set_title("Station Utilization", fontsize=14, fontweight='bold')
    
    utilization = results['station_utilization']
    stations_util = list(utilization.keys())
    counts = [utilization[s] for s in stations_util]
    plugs = [solution.params.station_plugs[s] for s in stations_util]
    
    x_pos = np.arange(len(stations_util))
    width = 0.35
    
    bars1 = ax5.bar(x_pos - width/2, counts, width, label='Vehicles Using', 
                    color='steelblue', alpha=0.8)
    bars2 = ax5.bar(x_pos + width/2, plugs, width, label='Available Plugs', 
                    color='orange', alpha=0.8)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax5.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    ax5.set_ylabel('Count', fontsize=10)
    ax5.set_xlabel('Station', fontsize=10)
    ax5.set_xticks(x_pos)
    ax5.set_xticklabels(stations_util)
    ax5.legend(fontsize=9)
    ax5.grid(axis='y', alpha=0.3)
    
    # ========== Energy Charged per Vehicle ==========
    ax6 = plt.subplot(3, 3, 6)
    ax6.set_title("Energy Charged per Vehicle", fontsize=14, fontweight='bold')
    
    vehicle_ids_energy = [f"EV {i+1}" for i in range(len(solution.vehicle_solutions))]
    energy_charged = [sum(vs.charging_amounts.values()) for vs in solution.vehicle_solutions]
    battery_capacities = [solution.params.battery_kwh[i] for i in range(len(solution.vehicle_solutions))]
    
    x_pos = np.arange(len(vehicle_ids_energy))
    width = 0.35
    
    bars1 = ax6.bar(x_pos - width/2, energy_charged, width, label='Energy Charged', 
                    color='limegreen', alpha=0.8)
    bars2 = ax6.bar(x_pos + width/2, battery_capacities, width, label='Battery Capacity', 
                    color='gray', alpha=0.5)
    
    # Add value labels
    for bar, energy in zip(bars1, energy_charged):
        height = bar.get_height()
        ax6.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{energy:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    ax6.set_ylabel('Energy (kWh)', fontsize=10)
    ax6.set_xlabel('Vehicle', fontsize=10)
    ax6.set_xticks(x_pos)
    ax6.set_xticklabels(vehicle_ids_energy)
    ax6.legend(fontsize=9)
    ax6.grid(axis='y', alpha=0.3)
    
    # ========== Route Choices ==========
    ax7 = plt.subplot(3, 3, 7)
    ax7.set_title("Route Distribution", fontsize=14, fontweight='bold')
    
    upper_count = sum(1 for vs in solution.vehicle_solutions 
                     if any(s in vs.route for s in solution.params.upper_stations))
    lower_count = sum(1 for vs in solution.vehicle_solutions 
                     if any(s in vs.route for s in solution.params.lower_stations))
    
    route_labels = ['Upper Branch\n(S1→S2)', 'Lower Branch\n(S3)']
    route_counts = [upper_count, lower_count]
    colors_route = ['lightgreen', 'lightcoral']
    
    wedges, texts, autotexts = ax7.pie(route_counts, labels=route_labels, autopct='%1.0f%%',
                                        colors=colors_route, startangle=90, textprops={'fontsize': 10})
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontweight('bold')
    
    ax7.text(0, -1.4, f'{upper_count} vehicles took upper route\n{lower_count} vehicles took lower route',
            ha='center', fontsize=9, style='italic')
    
    # ========== Time Breakdown ==========
    ax8 = plt.subplot(3, 3, 8)
    ax8.set_title("Time Analysis", fontsize=14, fontweight='bold')
    
    charging_times = [vs.get_total_charging_time() for vs in solution.vehicle_solutions]
    travel_times = [vs.get_completion_time() - vs.get_total_charging_time() 
                   for vs in solution.vehicle_solutions]
    
    vehicle_ids_time = [f"EV {i+1}" for i in range(len(solution.vehicle_solutions))]
    
    bars1 = ax8.bar(vehicle_ids_time, travel_times, label='Travel Time', 
                    color='skyblue', alpha=0.8)
    bars2 = ax8.bar(vehicle_ids_time, charging_times, bottom=travel_times,
                    label='Charging Time', color='orange', alpha=0.8)
    
    # Add total time labels
    for i, (b1, b2) in enumerate(zip(bars1, bars2)):
        total = travel_times[i] + charging_times[i]
        ax8.text(b1.get_x() + b1.get_width()/2., total + 1,
                f'{total:.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    ax8.set_ylabel('Time (minutes)', fontsize=10)
    ax8.set_xlabel('Vehicle', fontsize=10)
    ax8.legend(fontsize=9)
    ax8.grid(axis='y', alpha=0.3)
    
    # ========== Vehicle Journey Details ==========
    ax9 = plt.subplot(3, 3, 9)
    ax9.set_title("Vehicle Summaries", fontsize=14, fontweight='bold')
    ax9.axis('off')
    
    summary_lines = []
    for vs_summary in results['vehicle_summaries']:
        vid = vs_summary['vehicle_id'] + 1
        route_str = ' → '.join(vs_summary['route'])
        stations_str = ', '.join(vs_summary['stations_used']) if vs_summary['stations_used'] else 'None'
        
        summary_lines.append(f"EV {vid}:")
        summary_lines.append(f"  Route: {route_str}")
        summary_lines.append(f"  Stations: {stations_str}")
        summary_lines.append(f"  Time: {vs_summary['completion_time']:.1f} min | Cost: {vs_summary['charging_cost']:.2f} EGP")
        summary_lines.append("")
    
    summary_text = '\n'.join(summary_lines)
    ax9.text(0.05, 0.95, summary_text, fontsize=8, verticalalignment='top',
            fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Solution visualization saved to: {save_path}")
    
    plt.show()


def visualize_scenario_comparison(solution: FleetSolution, 
                                  scenarios: List[Tuple[str, float, float]], 
                                  save_path=None):
    """
    Compare different weight scenarios for the same solution.
    
    Args:
        solution: Fleet solution to analyze
        scenarios: List of (name, w_time, w_cost) tuples
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    scenario_names = [s[0] for s in scenarios]
    w_times = [s[1] for s in scenarios]
    w_costs = [s[2] for s in scenarios]
    
    # Calculate objectives for each scenario
    makespan = evaluate_solution(solution)['makespan']
    total_cost = evaluate_solution(solution)['total_cost']
    objectives = [objective_weighted(solution, w_time=wt, w_cost=wc) 
                 for _, wt, wc in scenarios]
    
    # ========== Weighted Objectives Comparison ==========
    ax1 = axes[0, 0]
    ax1.set_title("Weighted Objective by Scenario", fontsize=14, fontweight='bold')
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(scenarios)))
    bars = ax1.bar(scenario_names, objectives, color=colors, alpha=0.8, edgecolor='black')
    
    for bar, obj in zip(bars, objectives):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + max(objectives)*0.01,
                f'{obj:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    ax1.set_ylabel('Objective Value', fontsize=11)
    ax1.set_xlabel('Scenario', fontsize=11)
    ax1.tick_params(axis='x', rotation=45)
    ax1.grid(axis='y', alpha=0.3)
    
    # ========== Weight Distribution ==========
    ax2 = axes[0, 1]
    ax2.set_title("Weight Settings", fontsize=14, fontweight='bold')
    
    x_pos = np.arange(len(scenarios))
    width = 0.35
    
    bars1 = ax2.bar(x_pos - width/2, w_times, width, label='w_time', 
                    color='steelblue', alpha=0.8)
    bars2 = ax2.bar(x_pos + width/2, w_costs, width, label='w_cost', 
                    color='coral', alpha=0.8)
    
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}', ha='center', va='bottom', fontsize=8)
    
    ax2.set_ylabel('Weight Value', fontsize=11)
    ax2.set_xlabel('Scenario', fontsize=11)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(scenario_names, rotation=45, ha='right')
    ax2.legend(fontsize=10)
    ax2.grid(axis='y', alpha=0.3)
    
    # ========== Contribution Breakdown ==========
    ax3 = axes[1, 0]
    ax3.set_title("Objective Contributions", fontsize=14, fontweight='bold')
    
    time_contributions = [wt * makespan for _, wt, _ in scenarios]
    cost_contributions = [wc * total_cost for _, _, wc in scenarios]
    
    bars1 = ax3.bar(scenario_names, time_contributions, label=f'Time Component (×{makespan:.1f} min)', 
                    color='skyblue', alpha=0.8)
    bars2 = ax3.bar(scenario_names, cost_contributions, bottom=time_contributions,
                    label=f'Cost Component (×{total_cost:.2f} EGP)', color='gold', alpha=0.8)
    
    ax3.set_ylabel('Contribution to Objective', fontsize=11)
    ax3.set_xlabel('Scenario', fontsize=11)
    ax3.tick_params(axis='x', rotation=45)
    ax3.legend(fontsize=9)
    ax3.grid(axis='y', alpha=0.3)
    
    # ========== Scenario Summary Table ==========
    ax4 = axes[1, 1]
    ax4.set_title("Scenario Comparison Table", fontsize=14, fontweight='bold')
    ax4.axis('off')
    
    table_data = []
    table_data.append(['Scenario', 'w_time', 'w_cost', 'Objective'])
    table_data.append(['─' * 15, '─' * 6, '─' * 6, '─' * 10])
    
    for (name, wt, wc), obj in zip(scenarios, objectives):
        table_data.append([name, f'{wt:.1f}', f'{wc:.1f}', f'{obj:.2f}'])
    
    table_data.append(['─' * 15, '─' * 6, '─' * 6, '─' * 10])
    table_data.append(['', '', '', ''])
    table_data.append(['Base Values:', '', '', ''])
    table_data.append([f'  Makespan:', '', '', f'{makespan:.2f} min'])
    table_data.append([f'  Total Cost:', '', '', f'{total_cost:.2f} EGP'])
    
    table_text = '\n'.join(['  '.join(row) for row in table_data])
    ax4.text(0.1, 0.9, table_text, fontsize=10, verticalalignment='top',
            fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.5))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Scenario comparison saved to: {save_path}")
    
    plt.show()


if __name__ == "__main__":
    # Import here to avoid circular dependency
    from example_objectives import create_sample_solution
    
    print("Creating sample solution...")
    solution = create_sample_solution()
    
    print("Generating solution visualization...")
    visualize_solution(solution, save_path='solution_analysis.png')
    
    print("\nGenerating scenario comparison...")
    scenarios = [
        ("Balanced", 1.0, 1.0),
        ("Time-Critical", 2.0, 1.0),
        ("Cost-Conscious", 1.0, 3.0),
        ("Time-Only", 1.0, 0.0),
        ("Cost-Only", 0.0, 1.0),
    ]
    visualize_scenario_comparison(solution, scenarios, save_path='scenario_comparison.png')
    
    print("\n✓ Visualizations complete!")
