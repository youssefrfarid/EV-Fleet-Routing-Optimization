#!/usr/bin/env python3
"""
visualize_params.py
Visualizes the EV routing network and charging parameters from params.py
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from params import make_toy_params


def visualize_network(params, save_path=None):
    """
    Create a comprehensive visualization of the network topology and charging parameters.
    """
    fig = plt.figure(figsize=(16, 10))
    
    # ========== Network Graph ==========
    ax1 = plt.subplot(2, 2, 1)
    ax1.set_title("Network Topology", fontsize=14, fontweight='bold')
    
    # Define node positions for visualization (fork layout)
    pos = {
        'A': (0, 2),
        'J': (2, 2),
        'S1': (4, 3),
        'S2': (6, 3),
        'S3': (4, 1),
        'M': (8, 2),
        'B': (10, 2)
    }
    
    # Draw edges with travel time and energy labels
    for (u, v), time_min in params.edges_time_min.items():
        energy_kwh = params.edges_energy_kwh[(u, v)]
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        
        # Draw arrow
        ax1.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', lw=2, color='gray'))
        
        # Add edge label
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax1.text(mid_x, mid_y + 0.15, f'{time_min:.0f}min\n{energy_kwh:.1f}kWh',
                fontsize=8, ha='center', bbox=dict(boxstyle='round,pad=0.3', 
                facecolor='white', edgecolor='gray', alpha=0.8))
    
    # Draw nodes
    stations = set(params.upper_stations + params.lower_stations)
    for node, (x, y) in pos.items():
        if node in stations:
            # Station nodes - different styling
            color = 'lightgreen' if node in params.upper_stations else 'lightcoral'
            ax1.scatter(x, y, s=800, c=color, edgecolors='black', linewidths=2, zorder=3)
            
            # Add station info
            plugs = params.station_plugs.get(node, 0)
            price = params.station_price.get(node, 0)
            max_kw = params.station_max_kw.get(node, 0)
            label = f'{node}\n{plugs} plugs\n{price:.2f} EGP/kWh\n{max_kw:.0f}kW'
            ax1.text(x, y, label, fontsize=9, ha='center', va='center', fontweight='bold')
        else:
            # Junction nodes
            ax1.scatter(x, y, s=500, c='lightblue', edgecolors='black', linewidths=2, zorder=3)
            ax1.text(x, y, node, fontsize=12, ha='center', va='center', fontweight='bold')
    
    ax1.set_xlim(-0.5, 10.5)
    ax1.set_ylim(0, 4)
    ax1.axis('off')
    
    # Legend
    upper_patch = mpatches.Patch(color='lightgreen', label='Upper Branch Stations')
    lower_patch = mpatches.Patch(color='lightcoral', label='Lower Branch Stations')
    junction_patch = mpatches.Patch(color='lightblue', label='Junction Nodes')
    ax1.legend(handles=[upper_patch, lower_patch, junction_patch], loc='upper left', fontsize=9)
    
    # ========== Charging Power Curve ==========
    ax2 = plt.subplot(2, 2, 2)
    ax2.set_title("Charging Power vs SOC", fontsize=14, fontweight='bold')
    
    soc_range = np.linspace(0, 1, 200)
    
    # Plot base curve
    base_power = [params.charge_power_kw_fn(soc, 'dummy') for soc in soc_range]
    ax2.plot(soc_range * 100, base_power, 'b-', linewidth=2.5, label='Base Curve (All EVs)')
    
    # Plot effective power at each station
    for station in list(params.upper_stations) + list(params.lower_stations):
        effective_power = [params.effective_power_kw(soc, station) for soc in soc_range]
        station_cap = params.station_max_kw.get(station, float('inf'))
        linestyle = '--' if station in params.upper_stations else ':'
        ax2.plot(soc_range * 100, effective_power, linestyle=linestyle, linewidth=2,
                label=f'{station} (cap: {station_cap:.0f}kW)')
    
    ax2.axvline(x=80, color='red', linestyle='--', alpha=0.5, label='80% SOC (taper start)')
    ax2.set_xlabel('State of Charge (%)', fontsize=11)
    ax2.set_ylabel('Charging Power (kW)', fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=9)
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, max(base_power) * 1.1)
    
    # ========== Fleet Information ==========
    ax3 = plt.subplot(2, 2, 3)
    ax3.set_title("Fleet Configuration", fontsize=14, fontweight='bold')
    ax3.axis('off')
    
    fleet_info = f"""
    Number of Vehicles: {params.m}
    
    Vehicle Details:
    """
    for i in range(params.m):
        fleet_info += f"\n    EV {i+1}:"
        fleet_info += f"\n        • Battery: {params.battery_kwh[i]:.1f} kWh"
        fleet_info += f"\n        • Initial SOC: {params.soc0[i]*100:.0f}%"
        fleet_info += f"\n        • Initial Energy: {params.battery_kwh[i] * params.soc0[i]:.1f} kWh"
    
    fleet_info += f"\n\n    Charging Efficiency: {params.eta_charge*100:.0f}%"
    fleet_info += f"\n    EV Max Power: {'No limit' if params.ev_max_kw is None else f'{params.ev_max_kw:.0f} kW'}"
    
    ax3.text(0.1, 0.9, fleet_info, fontsize=11, verticalalignment='top',
            fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # ========== Station Comparison ==========
    ax4 = plt.subplot(2, 2, 4)
    ax4.set_title("Station Comparison", fontsize=14, fontweight='bold')
    
    stations_list = list(params.upper_stations) + list(params.lower_stations)
    x_pos = np.arange(len(stations_list))
    
    prices = [params.station_price[s] for s in stations_list]
    plugs = [params.station_plugs[s] for s in stations_list]
    max_kws = [params.station_max_kw[s] for s in stations_list]
    
    # Create grouped bar chart
    width = 0.25
    ax4_twin1 = ax4.twinx()
    ax4_twin2 = ax4.twinx()
    ax4_twin2.spines['right'].set_position(('outward', 60))
    
    bar1 = ax4.bar(x_pos - width, prices, width, label='Price (EGP/kWh)', color='gold', alpha=0.8)
    bar2 = ax4_twin1.bar(x_pos, plugs, width, label='Plugs', color='steelblue', alpha=0.8)
    bar3 = ax4_twin2.bar(x_pos + width, max_kws, width, label='Max Power (kW)', color='coral', alpha=0.8)
    
    ax4.set_xlabel('Station', fontsize=11)
    ax4.set_ylabel('Price (EGP/kWh)', fontsize=10, color='darkgoldenrod')
    ax4_twin1.set_ylabel('Plugs', fontsize=10, color='steelblue')
    ax4_twin2.set_ylabel('Max Power (kW)', fontsize=10, color='coral')
    
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(stations_list)
    ax4.tick_params(axis='y', labelcolor='darkgoldenrod')
    ax4_twin1.tick_params(axis='y', labelcolor='steelblue')
    ax4_twin2.tick_params(axis='y', labelcolor='coral')
    
    # Add value labels on bars
    for bars in [bar1, bar2, bar3]:
        for bar in bars:
            height = bar.get_height()
            ax = bar.axes
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}' if height < 10 else f'{height:.0f}',
                   ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    # Combined legend
    lines1, labels1 = ax4.get_legend_handles_labels()
    lines2, labels2 = ax4_twin1.get_legend_handles_labels()
    lines3, labels3 = ax4_twin2.get_legend_handles_labels()
    ax4.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3, 
              loc='upper left', fontsize=9)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Visualization saved to: {save_path}")
    
    plt.show()


def visualize_charging_time_heatmap(params, save_path=None):
    """
    Create a heatmap showing charging time for different SOC ranges at each station.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    stations_list = list(params.upper_stations) + list(params.lower_stations)
    soc_start_range = np.linspace(0.1, 0.8, 15)
    soc_end_range = np.linspace(0.3, 1.0, 15)
    
    for vehicle_idx, battery_kwh in enumerate(params.battery_kwh):
        ax = axes[vehicle_idx]
        ax.set_title(f'EV {vehicle_idx+1} ({battery_kwh:.0f} kWh) - Charging Time (minutes)', 
                    fontsize=12, fontweight='bold')
        
        # Calculate charging times for first station (as example)
        station = stations_list[0]
        times_matrix = np.zeros((len(soc_start_range), len(soc_end_range)))
        
        for i, soc_start in enumerate(soc_start_range):
            for j, soc_end in enumerate(soc_end_range):
                if soc_end > soc_start:
                    time_sec = params.charge_time_seconds(soc_start, soc_end, battery_kwh, station)
                    times_matrix[i, j] = time_sec / 60.0  # Convert to minutes
                else:
                    times_matrix[i, j] = np.nan
        
        im = ax.imshow(times_matrix, aspect='auto', origin='lower', cmap='YlOrRd')
        ax.set_xlabel('Target SOC', fontsize=10)
        ax.set_ylabel('Starting SOC', fontsize=10)
        
        # Set tick labels
        ax.set_xticks(np.arange(0, len(soc_end_range), 3))
        ax.set_xticklabels([f'{soc*100:.0f}%' for soc in soc_end_range[::3]])
        ax.set_yticks(np.arange(0, len(soc_start_range), 3))
        ax.set_yticklabels([f'{soc*100:.0f}%' for soc in soc_start_range[::3]])
        
        plt.colorbar(im, ax=ax, label='Time (minutes)')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Charging time heatmap saved to: {save_path}")
    
    plt.show()


if __name__ == "__main__":
    # Load parameters
    params = make_toy_params()
    
    print("=" * 60)
    print("EV Fleet Routing Network Visualization")
    print("=" * 60)
    print(f"\nNetwork: {' -> '.join(params.nodes)}")
    print(f"Upper Branch: {' -> '.join(params.upper_stations)}")
    print(f"Lower Branch: {' -> '.join(params.lower_stations)}")
    print(f"Fleet Size: {params.m} vehicles")
    print("\nGenerating visualizations...\n")
    
    # Create main visualization
    visualize_network(params, save_path='network_visualization.png')
    
    # Create charging time heatmap
    visualize_charging_time_heatmap(params, save_path='charging_time_heatmap.png')
    
    print("\n✓ Visualizations complete!")
