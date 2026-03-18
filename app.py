"""
Streamlit App - EV Fleet Routing Algorithm Comparison

An interactive dashboard for running and comparing optimization algorithms:
- Simulated Annealing (SA)
- Genetic Algorithm (GA)
- Particle Swarm Optimization (PSO)
- Teaching-Learning Based Optimization (TLBO)

Run with: streamlit run app.py
"""

import sys
import time
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.params import make_double_fork_params
from common.objectives import objective_weighted, objective_makespan, objective_total_cost


# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="EV Fleet Optimizer",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme enhancements
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #e74c3c, #3498db, #2ecc71, #9b59b6, #f39c12);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        margin: 0.5rem 0;
    }
    
    .algo-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .badge-sa { background: #e74c3c; color: white; }
    .badge-ga { background: #3498db; color: white; }
    .badge-pso { background: #2ecc71; color: white; }
    .badge-tlbo { background: #9b59b6; color: white; }
    .badge-rl { background: #f39c12; color: white; }
    
    .stProgress .st-bo {
        background: linear-gradient(90deg, #3498db, #2ecc71);
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Algorithm Runners
# ============================================================================

@st.cache_resource
def get_algorithms():
    """Lazy load algorithm modules."""
    from algorithms.sa.simulated_annealing import simulated_annealing
    from algorithms.ga.genetic_algorithm import genetic_algorithm
    from algorithms.pso.particle_swarm import particle_swarm_optimization
    from algorithms.tlbo.teaching_learning_optimization import tlbo
    from algorithms.rl.rl_optimizer import rl_optimization
    
    return {
        "SA": simulated_annealing,
        "GA": genetic_algorithm,
        "PSO": particle_swarm_optimization,
        "TLBO": tlbo,
        "RL": rl_optimization
    }


def run_algorithm(algo_name: str, params, settings: dict, progress_callback=None):
    """Run a single algorithm with given settings."""
    algorithms = get_algorithms()
    algo_fn = algorithms[algo_name]
    
    start_time = time.time()
    
    if algo_name == "SA":
        result = algo_fn(
            params,
            seed=settings["seed"],
            max_iterations=settings["sa_iterations"],
            temperature_start=settings.get("sa_temp_start", 60.0),
            temperature_end=settings.get("sa_temp_end", 0.5),
            cooling_rate=settings.get("sa_cooling_rate", 0.92),
            iterations_per_temp=settings.get("sa_iter_per_temp", 30),
            verbose=False,
            show_plots=False
        )
        best_solution = result.best_solution
        
    elif algo_name == "GA":
        result = algo_fn(
            params,
            seed=settings["seed"],
            pop_size=settings["ga_population"],
            num_generations=settings["ga_generations"],
            elite_size=settings.get("ga_elite_size", 2),
            tournament_size=settings.get("ga_tournament_size", 3),
            mutation_rate=settings.get("ga_mutation_rate", 0.15),
            crossover_rate=settings.get("ga_crossover_rate", 0.8),
            verbose=False,
            show_plots=False
        )
        best_solution = result.best_solution
        
    elif algo_name == "PSO":
        result = algo_fn(
            params,
            seed=settings["seed"],
            swarm_size=settings["pso_swarm_size"],
            max_iterations=settings["pso_iterations"],
            w=settings.get("pso_w", 0.5),
            c1=settings.get("pso_c1", 1.7),
            c2=settings.get("pso_c2", 1.7),
            verbose=False,
            show_plots=False
        )
        best_solution = result.best_solution
        
    elif algo_name == "TLBO":
        result = algo_fn(
            params,
            seed=settings["seed"],
            pop_size=settings["tlbo_population"],
            num_iterations=settings["tlbo_iterations"],
            verbose=False,
            show_plots=False
        )
        best_solution = result.best_solution
    
    elif algo_name == "RL":
        result = algo_fn(
            params,
            seed=settings["seed"],
            n_episodes=settings.get("rl_episodes", 500),  # Increased from 200
            hidden_dim=settings.get("rl_hidden_dim", 128),
            lr=settings.get("rl_lr", 0.001),
            verbose=False
        )
        best_solution = result.best_solution
    
    runtime = time.time() - start_time
    
    # Compute metrics
    weighted = float(objective_weighted(best_solution))
    makespan = float(objective_makespan(best_solution))
    total_cost = float(objective_total_cost(best_solution))
    feasible = best_solution.is_feasible()
    
    return {
        "algorithm": algo_name,
        "weighted": weighted,
        "makespan": makespan,
        "cost": total_cost,
        "runtime": runtime,
        "feasible": feasible,
        "solution": best_solution
    }


# ============================================================================
# Visualization Functions
# ============================================================================

def create_comparison_chart(results_df):
    """Create interactive comparison bar chart."""
    colors = {"SA": "#e74c3c", "GA": "#3498db", "PSO": "#2ecc71", "TLBO": "#9b59b6", "RL": "#f39c12"}
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Weighted Objective ↓", "Makespan (min)", "Total Cost (EGP)", "Runtime (s)"),
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )
    
    for i, (metric, title) in enumerate([
        ("weighted", "Weighted"),
        ("makespan", "Makespan"),
        ("cost", "Cost"),
        ("runtime", "Runtime")
    ]):
        row = i // 2 + 1
        col = i % 2 + 1
        
        fig.add_trace(
            go.Bar(
                x=results_df["algorithm"],
                y=results_df[metric],
                marker_color=[colors[algo] for algo in results_df["algorithm"]],
                text=results_df[metric].round(2),
                textposition="outside",
                showlegend=False
            ),
            row=row, col=col
        )
    
    fig.update_layout(
        height=600,
        title_text="Algorithm Comparison",
        title_x=0.5,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )
    
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")
    
    return fig


def create_convergence_chart(history_data):
    """Create convergence line chart."""
    fig = go.Figure()
    
    colors = {"SA": "#e74c3c", "GA": "#3498db", "PSO": "#2ecc71", "TLBO": "#9b59b6", "RL": "#f39c12"}
    
    for algo, history in history_data.items():
        if history:
            iterations = [h[0] for h in history]
            best_values = [h[1] for h in history]
            
            fig.add_trace(go.Scatter(
                x=iterations,
                y=best_values,
                mode="lines",
                name=algo,
                line=dict(color=colors.get(algo, "#ffffff"), width=2)
            ))
    
    fig.update_layout(
        title="Convergence Comparison",
        xaxis_title="Iteration",
        yaxis_title="Best Fitness",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400
    )
    
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")
    
    return fig


def create_timeline_chart(results):
    """Create Gantt-style timeline chart showing vehicle activities."""
    fig = go.Figure()
    
    colors = {"SA": "#e74c3c", "GA": "#3498db", "PSO": "#2ecc71", "TLBO": "#9b59b6", "RL": "#f39c12"}
    
    for result in results:
        algo = result["algorithm"]
        solution = result["solution"]
        color = colors.get(algo, "#ffffff")
        
        for vs in solution.vehicle_solutions:
            # Create timeline bars for each vehicle
            route = vs.route
            
            for i, node in enumerate(route[:-1]):
                next_node = route[i + 1]
                
                # Travel segment
                start = vs.departure_times.get(node, 0)
                end = vs.arrival_times.get(next_node, start)
                
                if end > start:
                    fig.add_trace(go.Bar(
                        x=[end - start],
                        y=[f"{algo} - V{vs.vehicle_id}"],
                        orientation="h",
                        base=start,
                        marker_color=color,
                        marker_line_color="white",
                        marker_line_width=1,
                        name=f"{node}→{next_node}",
                        showlegend=False,
                        hovertemplate=f"🚗 {node}→{next_node}<br>Travel: {start:.1f}-{end:.1f} min<extra></extra>"
                    ))
                
                # Charging segment (if charging at next node)
                if next_node in vs.charging_amounts:
                    charge_start = vs.arrival_times.get(next_node, 0)
                    charge_end = vs.departure_times.get(next_node, charge_start)
                    charge_amt = vs.charging_amounts.get(next_node, 0)
                    
                    if charge_end > charge_start:
                        fig.add_trace(go.Bar(
                            x=[charge_end - charge_start],
                            y=[f"{algo} - V{vs.vehicle_id}"],
                            orientation="h",
                            base=charge_start,
                            marker_color="#f39c12",  # Orange for charging
                            marker_pattern_shape="/",
                            name=f"Charging at {next_node}",
                            showlegend=False,
                            hovertemplate=f"⚡ Charging at {next_node}<br>{charge_amt:.1f} kWh<br>{charge_start:.1f}-{charge_end:.1f} min<extra></extra>"
                        ))
    
    fig.update_layout(
        title="📅 Vehicle Timeline (Travel & Charging)",
        barmode="overlay",
        xaxis_title="Time (minutes)",
        yaxis_title="",
        height=max(300, len(results) * 150),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        showlegend=False
    )
    
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")
    fig.update_yaxes(showgrid=False)
    
    # Add legend annotations
    fig.add_annotation(
        x=0.02, y=1.08, xref="paper", yref="paper",
        text="🚗 Travel | ⚡ Charging",
        showarrow=False,
        font=dict(size=12, color="#8892b0")
    )
    
    return fig


def create_soc_chart(solution, algo_name, params):
    """Create SOC over time chart for a solution."""
    fig = go.Figure()
    
    vehicle_colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
    
    for i, vs in enumerate(solution.vehicle_solutions):
        times = []
        soc_values = []
        labels = []
        
        battery_kwh = params.battery_kwh[vs.vehicle_id]
        
        for node in vs.route:
            arrival_soc = vs.soc_at_nodes.get(node, 0) * 100
            arrival_time = vs.arrival_times.get(node, 0)
            
            times.append(arrival_time)
            soc_values.append(arrival_soc)
            labels.append(f"Arrive {node}")
            
            # If charging at this node
            if node in vs.charging_amounts:
                charge_amt = vs.charging_amounts.get(node, 0)
                soc_after = arrival_soc + (charge_amt / battery_kwh) * 100
                depart_time = vs.departure_times.get(node, arrival_time)
                
                times.append(depart_time)
                soc_values.append(soc_after)
                labels.append(f"Depart {node} (charged)")
        
        fig.add_trace(go.Scatter(
            x=times,
            y=soc_values,
            mode="lines+markers",
            name=f"Vehicle {vs.vehicle_id}",
            line=dict(color=vehicle_colors[i % len(vehicle_colors)], width=2),
            marker=dict(size=8),
            hovertemplate="%{text}<br>SOC: %{y:.1f}%<br>Time: %{x:.1f} min<extra></extra>",
            text=labels
        ))
    
    # Add 10% minimum SOC line
    fig.add_hline(y=10, line_dash="dash", line_color="red", 
                  annotation_text="Min SOC (10%)", annotation_position="right")
    
    fig.update_layout(
        title=f"🔋 State of Charge - {algo_name}",
        xaxis_title="Time (minutes)",
        yaxis_title="SOC (%)",
        yaxis=dict(range=[0, 105]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")
    
    return fig


def create_network_diagram(solution, params):
    """Create an interactive network diagram with vehicle routes."""
    
    # Network positions for double fork
    positions = {
        'A': (0, 2), 'J1': (1, 2),
        'S1': (2, 3), 'S2': (3, 3), 'S3': (2.5, 1),
        'M1': (4, 2), 'J2': (5, 2),
        'S4': (6, 3), 'S5': (7, 3), 'S6': (6.5, 1),
        'M2': (8, 2), 'B': (9, 2)
    }
    
    stations = list(params.station_plugs.keys())
    
    fig = go.Figure()
    
    # Draw edges first (as lines)
    edges = list(params.edges_time_min.keys())
    for edge in edges:
        if edge[0] in positions and edge[1] in positions:
            x0, y0 = positions[edge[0]]
            x1, y1 = positions[edge[1]]
            
            fig.add_trace(go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color="rgba(150,150,150,0.5)", width=3),
                showlegend=False,
                hoverinfo="skip"
            ))
    
    # Draw nodes
    for node, (x, y) in positions.items():
        is_station = node in stations
        
        # Node style
        if is_station:
            color = "#f39c12"
            symbol = "square"
            size = 25
            text = f"⚡ {node}"
        elif node in ["A", "B"]:
            color = "#2ecc71"
            symbol = "circle"
            size = 30
            text = f"🏁 {node}"
        else:
            color = "#3498db"
            symbol = "circle"
            size = 20
            text = node
        
        fig.add_trace(go.Scatter(
            x=[x],
            y=[y],
            mode="markers+text",
            marker=dict(size=size, color=color, symbol=symbol, line=dict(width=2, color="white")),
            text=[text],
            textposition="top center",
            showlegend=False,
            hovertemplate=f"<b>{node}</b><br>" + 
                         (f"Station: {params.station_plugs.get(node, 0)} plugs<br>"
                          f"Price: {params.station_price.get(node, 0)} EGP/kWh<extra></extra>" if is_station else "<extra></extra>")
        ))
    
    # Draw vehicle routes
    vehicle_colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
    
    for i, vs in enumerate(solution.vehicle_solutions):
        route = vs.route
        color = vehicle_colors[i % len(vehicle_colors)]
        
        # Create route line slightly offset
        offset = (i - 2) * 0.08
        route_x = [positions[node][0] for node in route if node in positions]
        route_y = [positions[node][1] + offset for node in route if node in positions]
        
        fig.add_trace(go.Scatter(
            x=route_x,
            y=route_y,
            mode="lines",
            line=dict(color=color, width=3, dash="dot"),
            name=f"🚗 Vehicle {vs.vehicle_id}",
            hovertemplate=f"Vehicle {vs.vehicle_id}<br>Route: {' → '.join(route)}<extra></extra>"
        ))
    
    fig.update_layout(
        title="🗺️ Network Map & Vehicle Routes",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15),
        height=450,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x")
    )
    
    return fig


def display_solution_details(solution, algo_name, params):
    """Display detailed solution information."""
    st.markdown(f"### 🚗 {algo_name} Solution Details")
    
    for i, vs in enumerate(solution.vehicle_solutions):
        with st.expander(f"🚙 Vehicle {i+1} (ID: {vs.vehicle_id})", expanded=i==0):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📍 Route:**")
                st.code(" → ".join(vs.route))
            
            with col2:
                st.markdown("**⚡ Charging:**")
                if vs.charging_amounts:
                    for station, amount in vs.charging_amounts.items():
                        price = params.station_price.get(station, 0)
                        cost = amount * price
                        st.write(f"  • {station}: {amount:.1f} kWh ({cost:.1f} EGP)")
                else:
                    st.write("  • No charging")
            
            with col3:
                st.markdown("**⏱️ Timing:**")
                completion = vs.get_completion_time()
                charging_time = vs.get_total_charging_time()
                st.write(f"  • Completion: **{completion:.1f}** min")
                st.write(f"  • Charging: {charging_time:.1f} min")
            
            # SOC progression
            st.markdown("**🔋 SOC at Key Nodes:**")
            soc_df = pd.DataFrame([
                {"Node": node, "SOC (%)": f"{soc*100:.0f}%", "Time (min)": f"{vs.arrival_times.get(node, 0):.1f}"}
                for node, soc in vs.soc_at_nodes.items()
            ])
            st.dataframe(soc_df, hide_index=True, use_container_width=True)


def create_simulation_html(solution, params, algo_name):
    """Generate premium HTML simulation with realistic cars, roads, and charging stations."""
    
    # Extract vehicle data
    vehicles_data = []
    for vs in solution.vehicle_solutions:
        vehicle = {
            'id': vs.vehicle_id,
            'route': vs.route,
            'route_text': ' → '.join(vs.route),
            'completion_time': vs.get_completion_time(),
            'charging_stations': vs.charging_stations,
            'charging_amounts': vs.charging_amounts,
            'arrival_times': vs.arrival_times,
            'departure_times': vs.departure_times,
        }
        vehicles_data.append(vehicle)
    
    # Network positions for double fork - spread out more
    network_pos = {
        'A': {'x': 60, 'y': 220},
        'J1': {'x': 160, 'y': 220},
        'S1': {'x': 280, 'y': 90},
        'S2': {'x': 400, 'y': 90},
        'S3': {'x': 340, 'y': 350},
        'M1': {'x': 520, 'y': 220},
        'J2': {'x': 620, 'y': 220},
        'S4': {'x': 740, 'y': 90},
        'S5': {'x': 860, 'y': 90},
        'S6': {'x': 800, 'y': 350},
        'M2': {'x': 980, 'y': 220},
        'B': {'x': 1100, 'y': 220}
    }
    
    stations_list = list(params.station_plugs.keys())
    edges_data = list(params.edges_time_min.keys())
    max_time = max(v['completion_time'] for v in vehicles_data)
    
    vehicles_json = json.dumps(vehicles_data)
    network_json = json.dumps(network_pos)
    stations_json = json.dumps(stations_list)
    edges_json = json.dumps([{"from": e[0], "to": e[1]} for e in edges_data])
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif; 
                background: linear-gradient(180deg, #0a0a1a 0%, #1a1a3a 100%); 
                color: white; 
                padding: 15px; 
            }}
            .controls {{ 
                display: flex; 
                gap: 12px; 
                align-items: center; 
                margin-bottom: 15px; 
                flex-wrap: wrap;
                padding: 12px 20px;
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                backdrop-filter: blur(10px);
            }}
            .btn {{ 
                background: linear-gradient(135deg, #00d2ff, #3a7bd5); 
                color: white; 
                border: none; 
                padding: 10px 20px; 
                border-radius: 8px; 
                cursor: pointer; 
                font-weight: 600;
                font-size: 13px;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0, 210, 255, 0.3);
            }}
            .btn:hover {{ 
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0, 210, 255, 0.4);
            }}
            .btn:active {{ transform: translateY(0); }}
            #networkCanvas {{ 
                border-radius: 16px; 
                display: block; 
                margin: 0 auto;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            }}
            #timelineCanvas {{ 
                border-radius: 12px; 
                background: rgba(10,10,30,0.8); 
                display: block; 
                margin: 15px auto 0; 
                cursor: pointer;
                box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            }}
            .time-display {{ 
                font-size: 16px; 
                font-weight: 700; 
                background: linear-gradient(90deg, #00d2ff, #3a7bd5);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-left: auto; 
            }}
            .speed-label {{ color: #8892b0; font-size: 13px; }}
            input[type="range"] {{
                -webkit-appearance: none;
                width: 100px;
                height: 6px;
                background: linear-gradient(90deg, #3a7bd5, #00d2ff);
                border-radius: 3px;
                margin-left: 8px;
            }}
            input[type="range"]::-webkit-slider-thumb {{
                -webkit-appearance: none;
                width: 18px;
                height: 18px;
                background: white;
                border-radius: 50%;
                cursor: pointer;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            }}
            .legend {{ 
                display: flex; 
                gap: 12px; 
                margin-top: 15px; 
                flex-wrap: wrap; 
                justify-content: center; 
            }}
            .legend-item {{ 
                display: flex; 
                align-items: center; 
                gap: 8px; 
                font-size: 11px; 
                background: rgba(255,255,255,0.08); 
                padding: 8px 14px; 
                border-radius: 20px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .legend-color {{ 
                width: 14px; 
                height: 14px; 
                border-radius: 4px;
                box-shadow: 0 2px 8px currentColor;
            }}
        </style>
    </head>
    <body>
        <div class="controls">
            <button id="playBtn" class="btn">▶ Play</button>
            <button id="pauseBtn" class="btn">⏸ Pause</button>
            <button id="resetBtn" class="btn">↺ Reset</button>
            <span class="speed-label">Speed: <input type="range" id="speedSlider" min="0.5" max="5" step="0.5" value="2"></span>
            <span class="time-display" id="timeDisplay">⏱ 0.0 / {max_time:.0f} min</span>
        </div>
        <canvas id="networkCanvas" width="1160" height="450"></canvas>
        <canvas id="timelineCanvas" width="1160" height="200"></canvas>
        <div class="legend" id="legend"></div>
        
        <script>
            const vehicles = {vehicles_json};
            const networkPos = {network_json};
            const stations = {stations_json};
            const edges = {edges_json};
            const maxTime = {max_time};
            
            const canvas = document.getElementById('networkCanvas');
            const ctx = canvas.getContext('2d');
            const timelineCanvas = document.getElementById('timelineCanvas');
            const timelineCtx = timelineCanvas.getContext('2d');
            
            let currentTime = 0;
            let isPlaying = false;
            let speed = 2;
            let particles = [];
            
            const carColors = [
                {{ body: '#FF4757', roof: '#ff6b7a', accent: '#c0392b', dark: '#a52833' }},
                {{ body: '#2ED573', roof: '#7bed9f', accent: '#27ae60', dark: '#1e8449' }},
                {{ body: '#3742FA', roof: '#5f6cfa', accent: '#2c3e50', dark: '#252eb0' }},
                {{ body: '#FFA502', roof: '#ffbe33', accent: '#e67e22', dark: '#b37400' }},
                {{ body: '#A55EEA', roof: '#cd84f1', accent: '#8e44ad', dark: '#7b3db0' }}
            ];
            
            // Isometric transformation constants
            const ISO_ANGLE = 0.5;  // 30 degree tilt
            const ISO_SCALE_Y = 0.6; // Y compression for isometric
            
            // Convert 2D position to isometric
            function toIso(x, y) {{
                return {{
                    x: x,
                    y: y * ISO_SCALE_Y + 80  // Compress Y and offset
                }};
            }}
            
            // Create gradient background with 3D ground plane
            function drawBackground() {{
                // Sky gradient
                const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
                grad.addColorStop(0, '#0a0a1f');
                grad.addColorStop(0.4, '#1a1a3a');
                grad.addColorStop(1, '#0f1020');
                ctx.fillStyle = grad;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                // Ground plane grid
                ctx.strokeStyle = 'rgba(100,100,150,0.15)';
                ctx.lineWidth = 1;
                for (let i = 0; i < 20; i++) {{
                    const y = 100 + i * 25;
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(canvas.width, y);
                    ctx.stroke();
                }}
                for (let i = 0; i < 30; i++) {{
                    const x = i * 50;
                    ctx.beginPath();
                    ctx.moveTo(x, 100);
                    ctx.lineTo(x, canvas.height);
                    ctx.stroke();
                }}
                
                // Stars in sky
                ctx.fillStyle = 'rgba(255,255,255,0.4)';
                for (let i = 0; i < 30; i++) {{
                    const x = (i * 73) % canvas.width;
                    const y = (i * 29) % 90;
                    ctx.beginPath();
                    ctx.arc(x, y, 1, 0, Math.PI * 2);
                    ctx.fill();
                }}
            }}
            
            // Draw 3D road segment
            function drawRoad(from, to) {{
                const f = toIso(from.x, from.y);
                const t = toIso(to.x, to.y);
                const dx = t.x - f.x;
                const dy = t.y - f.y;
                const len = Math.sqrt(dx * dx + dy * dy);
                const angle = Math.atan2(dy, dx);
                
                ctx.save();
                ctx.translate(f.x, f.y);
                ctx.rotate(angle);
                
                // Road shadow
                ctx.fillStyle = 'rgba(0,0,0,0.3)';
                ctx.beginPath();
                ctx.roundRect(0, -12, len, 28, 4);
                ctx.fill();
                
                // Road surface (elevated)
                const roadGrad = ctx.createLinearGradient(0, -14, 0, 14);
                roadGrad.addColorStop(0, '#4a4a5a');
                roadGrad.addColorStop(0.5, '#3a3a4a');
                roadGrad.addColorStop(1, '#2a2a3a');
                ctx.fillStyle = roadGrad;
                ctx.beginPath();
                ctx.roundRect(-3, -14, len + 6, 28, 4);
                ctx.fill();
                
                // Road edge lines
                ctx.strokeStyle = 'rgba(255,255,255,0.5)';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(0, -12);
                ctx.lineTo(len, -12);
                ctx.moveTo(0, 12);
                ctx.lineTo(len, 12);
                ctx.stroke();
                
                // Center dashed line
                ctx.strokeStyle = '#f1c40f';
                ctx.lineWidth = 2;
                ctx.setLineDash([12, 8]);
                ctx.beginPath();
                ctx.moveTo(0, 0);
                ctx.lineTo(len, 0);
                ctx.stroke();
                ctx.setLineDash([]);
                
                ctx.restore();
            }}
            
            // Draw 3D node (junction/terminal/station)
            function drawNode(node, pos) {{
                const p = toIso(pos.x, pos.y);
                const isStation = stations.includes(node);
                const isTerminal = ['A', 'B'].includes(node);
                
                if (isStation) {{
                    // 3D Charging station building
                    const bw = 50, bh = 40, bd = 20;
                    
                    // Shadow
                    ctx.fillStyle = 'rgba(0,0,0,0.4)';
                    ctx.beginPath();
                    ctx.ellipse(p.x, p.y + 8, 35, 15, 0, 0, Math.PI * 2);
                    ctx.fill();
                    
                    // Building front
                    ctx.fillStyle = '#1a2a3e';
                    ctx.fillRect(p.x - bw/2, p.y - bh, bw, bh);
                    
                    // Building top
                    ctx.fillStyle = '#2ed573';
                    ctx.beginPath();
                    ctx.moveTo(p.x - bw/2, p.y - bh);
                    ctx.lineTo(p.x - bw/2 + 10, p.y - bh - bd/2);
                    ctx.lineTo(p.x + bw/2 + 10, p.y - bh - bd/2);
                    ctx.lineTo(p.x + bw/2, p.y - bh);
                    ctx.closePath();
                    ctx.fill();
                    
                    // Building side
                    ctx.fillStyle = '#0f1a2a';
                    ctx.beginPath();
                    ctx.moveTo(p.x + bw/2, p.y - bh);
                    ctx.lineTo(p.x + bw/2 + 10, p.y - bh - bd/2);
                    ctx.lineTo(p.x + bw/2 + 10, p.y - bd/2);
                    ctx.lineTo(p.x + bw/2, p.y);
                    ctx.closePath();
                    ctx.fill();
                    
                    // Charging icon
                    ctx.fillStyle = '#2ed573';
                    ctx.font = 'bold 22px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText('⚡', p.x, p.y - bh/2);
                    
                    // Label
                    ctx.fillStyle = '#fff';
                    ctx.font = 'bold 11px Arial';
                    ctx.fillText(node, p.x, p.y + 20);
                    
                }} else if (isTerminal) {{
                    // 3D Terminal cylinder
                    const r = 24;
                    
                    // Shadow
                    ctx.fillStyle = 'rgba(0,0,0,0.4)';
                    ctx.beginPath();
                    ctx.ellipse(p.x + 5, p.y + 5, r + 5, 12, 0, 0, Math.PI * 2);
                    ctx.fill();
                    
                    // Base ellipse
                    const color = node === 'A' ? '#2ed573' : '#ff4757';
                    const darkColor = node === 'A' ? '#1e8449' : '#c0392b';
                    ctx.fillStyle = darkColor;
                    ctx.beginPath();
                    ctx.ellipse(p.x, p.y, r, 10, 0, 0, Math.PI * 2);
                    ctx.fill();
                    
                    // Cylinder body
                    ctx.fillStyle = color;
                    ctx.fillRect(p.x - r, p.y - 25, r * 2, 25);
                    
                    // Top ellipse
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.ellipse(p.x, p.y - 25, r, 10, 0, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = '#fff';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                    
                    // Icon
                    ctx.fillStyle = '#fff';
                    ctx.font = 'bold 16px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(node === 'A' ? '🏁' : '🎯', p.x, p.y - 15);
                    ctx.font = 'bold 10px Arial';
                    ctx.fillText(node === 'A' ? 'START' : 'END', p.x, p.y + 18);
                    
                }} else {{
                    // 3D Junction node (small platform)
                    ctx.fillStyle = 'rgba(0,0,0,0.3)';
                    ctx.beginPath();
                    ctx.ellipse(p.x + 3, p.y + 3, 18, 8, 0, 0, Math.PI * 2);
                    ctx.fill();
                    
                    ctx.fillStyle = '#3a3a5a';
                    ctx.beginPath();
                    ctx.ellipse(p.x, p.y, 16, 7, 0, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = '#5a5a8a';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                    
                    ctx.fillStyle = '#fff';
                    ctx.font = 'bold 11px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(node, p.x, p.y);
                }}
            }}
            
            // Draw 3D isometric car
            function drawCar(x, y, angle, colorScheme, vehicleNum, isCharging) {{
                ctx.save();
                ctx.translate(x, y);
                ctx.rotate(angle);
                
                // Shadow on ground
                ctx.fillStyle = 'rgba(0,0,0,0.35)';
                ctx.beginPath();
                ctx.ellipse(4, 8, 20, 8, 0, 0, Math.PI * 2);
                ctx.fill();
                
                // Car body - bottom
                ctx.fillStyle = colorScheme.dark;
                ctx.beginPath();
                ctx.roundRect(-18, -6, 36, 14, 4);
                ctx.fill();
                
                // Car body - main
                ctx.fillStyle = colorScheme.body;
                ctx.beginPath();
                ctx.roundRect(-18, -12, 36, 12, 4);
                ctx.fill();
                
                // Cabin/roof (elevated)
                ctx.fillStyle = colorScheme.roof;
                ctx.beginPath();
                ctx.roundRect(-10, -18, 16, 10, 3);
                ctx.fill();
                
                // Windshield
                ctx.fillStyle = '#87CEEB';
                ctx.globalAlpha = 0.8;
                ctx.beginPath();
                ctx.roundRect(6, -16, 6, 8, 2);
                ctx.fill();
                ctx.globalAlpha = 1;
                
                // Headlights (glowing)
                ctx.fillStyle = '#ffffaa';
                ctx.shadowColor = '#ffffaa';
                ctx.shadowBlur = 10;
                ctx.beginPath();
                ctx.arc(17, -4, 2.5, 0, Math.PI * 2);
                ctx.arc(17, 3, 2.5, 0, Math.PI * 2);
                ctx.fill();
                ctx.shadowBlur = 0;
                
                // Tail lights
                ctx.fillStyle = '#ff3333';
                ctx.shadowColor = '#ff3333';
                ctx.shadowBlur = 6;
                ctx.beginPath();
                ctx.arc(-17, -4, 2, 0, Math.PI * 2);
                ctx.arc(-17, 3, 2, 0, Math.PI * 2);
                ctx.fill();
                ctx.shadowBlur = 0;
                
                // Vehicle number
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 8px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('V' + vehicleNum, -2, -12);
                
                ctx.restore();
                
                // Charging effect
                if (isCharging) {{
                    for (let i = 0; i < 2; i++) {{
                        particles.push({{
                            x: x + (Math.random() - 0.5) * 25,
                            y: y - 20 + (Math.random() - 0.5) * 10,
                            vx: (Math.random() - 0.5) * 2,
                            vy: -Math.random() * 2 - 1,
                            life: 25,
                            color: '#2ed573'
                        }});
                    }}
                    ctx.font = '18px Arial';
                    ctx.textAlign = 'center';
                    ctx.fillText('⚡', x, y - 35);
                }}
            }}
            
            // Update and draw particles
            function updateParticles() {{
                particles = particles.filter(p => p.life > 0);
                particles.forEach(p => {{
                    p.x += p.vx;
                    p.y += p.vy;
                    p.life--;
                    
                    ctx.fillStyle = p.color;
                    ctx.globalAlpha = p.life / 30;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.globalAlpha = 1;
                }});
            }}
            
            // Get vehicle position and angle (in isometric space)
            function getVehicleState(vehicle) {{
                const route = vehicle.route;
                for (let i = 0; i < route.length - 1; i++) {{
                    const curr = route[i];
                    const next = route[i + 1];
                    const depart = vehicle.departure_times[curr] || 0;
                    const arrive = vehicle.arrival_times[next] || Infinity;
                    
                    if (currentTime >= (vehicle.arrival_times[curr] || 0) && currentTime < depart) {{
                        const pos = networkPos[curr];
                        const iso = toIso(pos.x, pos.y);
                        return {{ 
                            x: iso.x, 
                            y: iso.y, 
                            angle: 0,
                            charging: vehicle.charging_stations.includes(curr) 
                        }};
                    }}
                    
                    if (currentTime >= depart && currentTime < arrive) {{
                        const progress = (currentTime - depart) / (arrive - depart);
                        const from = networkPos[curr];
                        const to = networkPos[next];
                        const fromIso = toIso(from.x, from.y);
                        const toIso2 = toIso(to.x, to.y);
                        const angle = Math.atan2(toIso2.y - fromIso.y, toIso2.x - fromIso.x);
                        return {{
                            x: fromIso.x + progress * (toIso2.x - fromIso.x),
                            y: fromIso.y + progress * (toIso2.y - fromIso.y),
                            angle: angle,
                            charging: false
                        }};
                    }}
                }}
                const finalIso = toIso(networkPos['B'].x, networkPos['B'].y);
                return {{ x: finalIso.x, y: finalIso.y, angle: 0, charging: false }};
            }}
            
            // Draw everything
            function draw() {{
                drawBackground();
                
                // Draw roads first
                edges.forEach(e => {{
                    if (networkPos[e.from] && networkPos[e.to]) {{
                        drawRoad(networkPos[e.from], networkPos[e.to]);
                    }}
                }});
                
                // Draw nodes
                Object.entries(networkPos).forEach(([node, pos]) => {{
                    drawNode(node, pos);
                }});
                
                // Draw vehicles
                vehicles.forEach((v, idx) => {{
                    if (currentTime <= v.completion_time + 10) {{
                        const state = getVehicleState(v);
                        drawCar(state.x, state.y, state.angle, carColors[idx % carColors.length], idx + 1, state.charging);
                    }}
                }});
                
                // Update particles
                updateParticles();
                
                // Draw timeline
                drawTimeline();
                
                document.getElementById('timeDisplay').textContent = '⏱ ' + currentTime.toFixed(1) + ' / ' + maxTime.toFixed(0) + ' min';
            }}
            
            // Draw timeline
            function drawTimeline() {{
                timelineCtx.clearRect(0, 0, timelineCanvas.width, timelineCanvas.height);
                
                // Background
                const grad = timelineCtx.createLinearGradient(0, 0, 0, timelineCanvas.height);
                grad.addColorStop(0, 'rgba(20,20,40,0.9)');
                grad.addColorStop(1, 'rgba(10,10,30,0.9)');
                timelineCtx.fillStyle = grad;
                timelineCtx.fillRect(0, 0, timelineCanvas.width, timelineCanvas.height);
                
                const margin = 60;
                const width = timelineCanvas.width - 2 * margin;
                const rowH = 32;
                
                vehicles.forEach((v, idx) => {{
                    const y = 20 + idx * rowH;
                    const color = carColors[idx % carColors.length].body;
                    
                    // Label
                    timelineCtx.fillStyle = '#8892b0';
                    timelineCtx.font = '12px Arial';
                    timelineCtx.textAlign = 'right';
                    timelineCtx.fillText('V' + (idx + 1), margin - 12, y + 14);
                    
                    // Track background
                    timelineCtx.fillStyle = 'rgba(255,255,255,0.05)';
                    timelineCtx.beginPath();
                    timelineCtx.roundRect(margin, y, width, 24, 4);
                    timelineCtx.fill();
                    
                    // Segments
                    let prev = 0;
                    v.route.forEach(node => {{
                        const arr = v.arrival_times[node] || 0;
                        const dep = v.departure_times[node] || arr;
                        
                        // Travel
                        if (arr > prev) {{
                            const x = margin + (prev / maxTime) * width;
                            const w = Math.max(2, ((arr - prev) / maxTime) * width);
                            timelineCtx.fillStyle = color;
                            timelineCtx.beginPath();
                            timelineCtx.roundRect(x, y + 2, w, 20, 3);
                            timelineCtx.fill();
                        }}
                        
                        // Charging - with diagonal stripes pattern
                        if (v.charging_stations.includes(node)) {{
                            const x = margin + (arr / maxTime) * width;
                            const w = Math.max(2, ((dep - arr) / maxTime) * width);
                            
                            // Base green
                            timelineCtx.fillStyle = '#2ed573';
                            timelineCtx.beginPath();
                            timelineCtx.roundRect(x, y + 2, w, 20, 3);
                            timelineCtx.fill();
                            
                            // Add diagonal stripes
                            timelineCtx.save();
                            timelineCtx.beginPath();
                            timelineCtx.roundRect(x, y + 2, w, 20, 3);
                            timelineCtx.clip();
                            
                            timelineCtx.strokeStyle = 'rgba(255,255,255,0.4)';
                            timelineCtx.lineWidth = 2;
                            for (let sx = x - 20; sx < x + w + 20; sx += 8) {{
                                timelineCtx.beginPath();
                                timelineCtx.moveTo(sx, y + 2);
                                timelineCtx.lineTo(sx + 20, y + 22);
                                timelineCtx.stroke();
                            }}
                            timelineCtx.restore();
                            
                            // Add ⚡ icon if wide enough
                            if (w > 15) {{
                                timelineCtx.fillStyle = '#fff';
                                timelineCtx.font = '10px Arial';
                                timelineCtx.textAlign = 'center';
                                timelineCtx.fillText('⚡', x + w/2, y + 15);
                            }}
                        }}
                        prev = dep;
                    }});
                }});
                
                // Current time indicator
                const timeX = margin + (currentTime / maxTime) * width;
                timelineCtx.strokeStyle = '#fff';
                timelineCtx.lineWidth = 2;
                timelineCtx.shadowColor = '#fff';
                timelineCtx.shadowBlur = 10;
                timelineCtx.beginPath();
                timelineCtx.moveTo(timeX, 10);
                timelineCtx.lineTo(timeX, timelineCanvas.height - 20);
                timelineCtx.stroke();
                timelineCtx.shadowBlur = 0;
                
                // Time markers
                timelineCtx.fillStyle = '#666';
                timelineCtx.font = '11px Arial';
                timelineCtx.textAlign = 'center';
                for (let i = 0; i <= 5; i++) {{
                    const t = (i / 5) * maxTime;
                    const x = margin + (i / 5) * width;
                    timelineCtx.fillText(t.toFixed(0) + 'm', x, timelineCanvas.height - 5);
                }}
            }}
            
            // Animation loop
            function animate() {{
                if (!isPlaying) return;
                currentTime += 0.12 * speed;
                if (currentTime > maxTime) currentTime = 0;
                draw();
                requestAnimationFrame(animate);
            }}
            
            // Controls
            document.getElementById('playBtn').onclick = () => {{ isPlaying = true; animate(); }};
            document.getElementById('pauseBtn').onclick = () => {{ isPlaying = false; }};
            document.getElementById('resetBtn').onclick = () => {{ currentTime = 0; isPlaying = false; draw(); }};
            document.getElementById('speedSlider').oninput = (e) => {{ speed = parseFloat(e.target.value); }};
            
            // Timeline scrubbing
            timelineCanvas.onclick = (e) => {{
                const rect = timelineCanvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const margin = 60;
                const width = timelineCanvas.width - 2 * margin;
                if (x >= margin && x <= margin + width) {{
                    currentTime = ((x - margin) / width) * maxTime;
                    draw();
                }}
            }};
            
            // Build legend
            const legend = document.getElementById('legend');
            vehicles.forEach((v, idx) => {{
                const div = document.createElement('div');
                div.className = 'legend-item';
                div.innerHTML = '<div class="legend-color" style="background:' + carColors[idx % carColors.length].body + '"></div><span>V' + (idx+1) + ': ' + v.route_text + '</span>';
                legend.appendChild(div);
            }});
            
            // Initial draw
            draw();
        </script>
    </body>
    </html>
    '''
    
    return html


# ============================================================================
# Case Studies - Pre-defined Parameter Configurations
# ============================================================================

CASE_STUDIES = {
    "Quick Test": {
        "description": "Fast run with minimal iterations for testing",
        "sa": {"max_iterations": 500, "temperature_start": 60.0, "temperature_end": 0.5, "cooling_rate": 0.92, "iterations_per_temp": 30},
        "ga": {"pop_size": 30, "num_generations": 50, "elite_size": 2, "tournament_size": 3, "mutation_rate": 0.15, "crossover_rate": 0.8},
        "pso": {"swarm_size": 20, "max_iterations": 50, "w": 0.5, "c1": 1.7, "c2": 1.7},
        "tlbo": {"pop_size": 30, "num_iterations": 50},
        "rl": {"n_episodes": 100, "hidden_dim": 128, "lr": 0.001},
    },
    "Balanced": {
        "description": "Balanced settings for quality and speed",
        "sa": {"max_iterations": 2000, "temperature_start": 60.0, "temperature_end": 0.5, "cooling_rate": 0.92, "iterations_per_temp": 30},
        "ga": {"pop_size": 60, "num_generations": 150, "elite_size": 2, "tournament_size": 3, "mutation_rate": 0.15, "crossover_rate": 0.8},
        "pso": {"swarm_size": 40, "max_iterations": 150, "w": 0.5, "c1": 1.7, "c2": 1.7},
        "tlbo": {"pop_size": 50, "num_iterations": 100},
        "rl": {"n_episodes": 500, "hidden_dim": 128, "lr": 0.001},
    },
    "High Quality": {
        "description": "Extended run for best quality solutions",
        "sa": {"max_iterations": 5000, "temperature_start": 100.0, "temperature_end": 0.1, "cooling_rate": 0.95, "iterations_per_temp": 50},
        "ga": {"pop_size": 100, "num_generations": 300, "elite_size": 5, "tournament_size": 5, "mutation_rate": 0.1, "crossover_rate": 0.85},
        "pso": {"swarm_size": 60, "max_iterations": 300, "w": 0.6, "c1": 2.0, "c2": 2.0},
        "tlbo": {"pop_size": 80, "num_iterations": 200},
        "rl": {"n_episodes": 1000, "hidden_dim": 256, "lr": 0.0005},
    },
    "Exploration Focus": {
        "description": "Parameters tuned for more exploration",
        "sa": {"max_iterations": 3000, "temperature_start": 150.0, "temperature_end": 1.0, "cooling_rate": 0.88, "iterations_per_temp": 40},
        "ga": {"pop_size": 80, "num_generations": 200, "elite_size": 1, "tournament_size": 2, "mutation_rate": 0.25, "crossover_rate": 0.7},
        "pso": {"swarm_size": 50, "max_iterations": 200, "w": 0.8, "c1": 1.5, "c2": 1.5},
        "tlbo": {"pop_size": 60, "num_iterations": 150},
        "rl": {"n_episodes": 300, "hidden_dim": 128, "lr": 0.001},
    },
    "Exploitation Focus": {
        "description": "Parameters tuned for intensive local search",
        "sa": {"max_iterations": 3000, "temperature_start": 30.0, "temperature_end": 0.01, "cooling_rate": 0.97, "iterations_per_temp": 60},
        "ga": {"pop_size": 50, "num_generations": 200, "elite_size": 5, "tournament_size": 5, "mutation_rate": 0.05, "crossover_rate": 0.9},
        "pso": {"swarm_size": 30, "max_iterations": 200, "w": 0.3, "c1": 2.0, "c2": 2.5},
        "tlbo": {"pop_size": 40, "num_iterations": 150},
        "rl": {"n_episodes": 300, "hidden_dim": 128, "lr": 0.001},
    },
}


# ============================================================================
# Main App
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">🚗⚡ EV Fleet Optimizer</h1>', unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8892b0;'>Compare optimization algorithms for the Double Fork routing problem</p>", unsafe_allow_html=True)
    
    # Sidebar - Settings
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Mode selection
        mode = st.radio("Mode", ["Custom Parameters", "Case Studies"], horizontal=True)
        
        st.divider()
        
        if mode == "Case Studies":
            st.subheader("📚 Case Studies")
            case_study = st.selectbox("Select Case Study", list(CASE_STUDIES.keys()))
            st.caption(CASE_STUDIES[case_study]["description"])
            
            # Show case study parameters
            with st.expander("View Parameters", expanded=False):
                cs = CASE_STUDIES[case_study]
                st.json({
                    "SA": cs["sa"],
                    "GA": cs["ga"],
                    "PSO": cs["pso"],
                    "TLBO": cs["tlbo"],
                    "RL": cs["rl"]
                })
            
            st.divider()
            
            st.subheader("🎯 Algorithms")
            col1, col2 = st.columns(2)
            with col1:
                run_sa = st.checkbox("SA", value=True, help="Simulated Annealing")
                run_ga = st.checkbox("GA", value=True, help="Genetic Algorithm")
                run_rl = st.checkbox("RL (DQN)", value=False, help="Reinforcement Learning - Deep Q-Network")
            with col2:
                run_pso = st.checkbox("PSO", value=True, help="Particle Swarm Optimization")
                run_tlbo = st.checkbox("TLBO", value=True, help="Teaching-Learning Based Optimization")
            
            seed = st.number_input("Random Seed", min_value=0, max_value=9999, value=42)
            
            # Build settings from case study
            cs = CASE_STUDIES[case_study]
            settings = {
                "seed": seed,
                # SA
                "sa_iterations": cs["sa"]["max_iterations"],
                "sa_temp_start": cs["sa"]["temperature_start"],
                "sa_temp_end": cs["sa"]["temperature_end"],
                "sa_cooling_rate": cs["sa"]["cooling_rate"],
                "sa_iter_per_temp": cs["sa"]["iterations_per_temp"],
                # GA
                "ga_population": cs["ga"]["pop_size"],
                "ga_generations": cs["ga"]["num_generations"],
                "ga_elite_size": cs["ga"]["elite_size"],
                "ga_tournament_size": cs["ga"]["tournament_size"],
                "ga_mutation_rate": cs["ga"]["mutation_rate"],
                "ga_crossover_rate": cs["ga"]["crossover_rate"],
                # PSO
                "pso_swarm_size": cs["pso"]["swarm_size"],
                "pso_iterations": cs["pso"]["max_iterations"],
                "pso_w": cs["pso"]["w"],
                "pso_c1": cs["pso"]["c1"],
                "pso_c2": cs["pso"]["c2"],
                # TLBO
                "tlbo_population": cs["tlbo"]["pop_size"],
                "tlbo_iterations": cs["tlbo"]["num_iterations"],
                # RL (from case study)
                "rl_episodes": cs["rl"]["n_episodes"],
                "rl_hidden_dim": cs["rl"]["hidden_dim"],
                "rl_lr": cs["rl"]["lr"],
            }
            
        else:
            # Custom Parameters Mode
            st.subheader("🎯 Algorithms")
            col1, col2 = st.columns(2)
            with col1:
                run_sa = st.checkbox("SA", value=True, help="Simulated Annealing")
                run_ga = st.checkbox("GA", value=True, help="Genetic Algorithm")
                run_rl = st.checkbox("RL (DQN)", value=False, help="Reinforcement Learning - Deep Q-Network")
            with col2:
                run_pso = st.checkbox("PSO", value=True, help="Particle Swarm Optimization")
                run_tlbo = st.checkbox("TLBO", value=True, help="Teaching-Learning Based Optimization")
            
            st.divider()
            
            st.subheader("🔢 Global Parameters")
            seed = st.number_input("Random Seed", min_value=0, max_value=9999, value=42)
            
            st.divider()
            
            # Full Algorithm-specific settings
            st.subheader("🔧 Algorithm Parameters")
            
            # SA Settings
            with st.expander("🔥 SA - Simulated Annealing", expanded=False):
                st.caption("Controls temperature schedule and iteration behavior")
                sa_iterations = st.slider("Max Iterations", 500, 10000, 2000, 100, key="sa_iter")
                sa_temp_start = st.slider("Start Temperature", 10.0, 200.0, 60.0, 5.0, key="sa_t_start")
                sa_temp_end = st.slider("End Temperature", 0.01, 5.0, 0.5, 0.1, key="sa_t_end")
                sa_cooling_rate = st.slider("Cooling Rate", 0.80, 0.99, 0.92, 0.01, key="sa_cool")
                sa_iter_per_temp = st.slider("Iterations per Temperature", 10, 100, 30, 5, key="sa_ipt")
            
            # GA Settings
            with st.expander("🧬 GA - Genetic Algorithm", expanded=False):
                st.caption("Population-based evolutionary optimization")
                ga_population = st.slider("Population Size", 20, 200, 60, 10, key="ga_pop")
                ga_generations = st.slider("Generations", 50, 500, 150, 10, key="ga_gen")
                ga_elite_size = st.slider("Elite Size", 1, 10, 2, 1, key="ga_elite")
                ga_tournament_size = st.slider("Tournament Size", 2, 10, 3, 1, key="ga_tour")
                ga_mutation_rate = st.slider("Mutation Rate", 0.01, 0.50, 0.15, 0.01, key="ga_mut")
                ga_crossover_rate = st.slider("Crossover Rate", 0.50, 1.0, 0.80, 0.05, key="ga_cross")
            
            # PSO Settings
            with st.expander("🐝 PSO - Particle Swarm Optimization", expanded=False):
                st.caption("Swarm intelligence optimization")
                pso_swarm_size = st.slider("Swarm Size", 20, 100, 40, 5, key="pso_swarm")
                pso_iterations = st.slider("Iterations", 50, 500, 150, 10, key="pso_iter")
                pso_w = st.slider("Inertia Weight (w)", 0.1, 1.0, 0.5, 0.1, key="pso_w")
                pso_c1 = st.slider("Cognitive Coef (c1)", 0.5, 3.0, 1.7, 0.1, key="pso_c1")
                pso_c2 = st.slider("Social Coef (c2)", 0.5, 3.0, 1.7, 0.1, key="pso_c2")
            
            # TLBO Settings
            with st.expander("📚 TLBO - Teaching-Learning Optimization", expanded=False):
                st.caption("No algorithm-specific parameters - only population and iterations!")
                tlbo_population = st.slider("Population Size", 20, 150, 50, 10, key="tlbo_pop")
                tlbo_iterations = st.slider("Iterations", 50, 300, 100, 10, key="tlbo_iter")
            
            # RL Settings
            with st.expander("🤖 RL - Reinforcement Learning (DQN)", expanded=False):
                st.caption("⚠️ Experimental: Deep Q-Network for route optimization")
                rl_episodes = st.slider("Training Episodes", 50, 500, 200, 50, key="rl_eps")
                rl_hidden_dim = st.slider("Hidden Dimensions", 64, 256, 128, 32, key="rl_hidden")
                rl_lr = st.number_input("Learning Rate", 0.0001, 0.01, 0.001, 0.0001, format="%.4f", key="rl_lr")
            
            # Build settings dict
            settings = {
                "seed": seed,
                # SA
                "sa_iterations": sa_iterations,
                "sa_temp_start": sa_temp_start,
                "sa_temp_end": sa_temp_end,
                "sa_cooling_rate": sa_cooling_rate,
                "sa_iter_per_temp": sa_iter_per_temp,
                # GA
                "ga_population": ga_population,
                "ga_generations": ga_generations,
                "ga_elite_size": ga_elite_size,
                "ga_tournament_size": ga_tournament_size,
                "ga_mutation_rate": ga_mutation_rate,
                "ga_crossover_rate": ga_crossover_rate,
                # PSO
                "pso_swarm_size": pso_swarm_size,
                "pso_iterations": pso_iterations,
                "pso_w": pso_w,
                "pso_c1": pso_c1,
                "pso_c2": pso_c2,
                # TLBO
                "tlbo_population": tlbo_population,
                "tlbo_iterations": tlbo_iterations,
                # RL
                "rl_episodes": rl_episodes,
                "rl_hidden_dim": rl_hidden_dim,
                "rl_lr": rl_lr,
            }
        
        st.divider()
        
        # Run button
        run_button = st.button("🚀 Run Optimization", type="primary", use_container_width=True)
    
    # Main content area
    selected_algorithms = []
    if run_sa: selected_algorithms.append("SA")
    if run_ga: selected_algorithms.append("GA")
    if run_pso: selected_algorithms.append("PSO")
    if run_tlbo: selected_algorithms.append("TLBO")
    if run_rl: selected_algorithms.append("RL")
    
    if not selected_algorithms:
        st.warning("Please select at least one algorithm to run.")
        return
    
    # Run optimization
    if run_button:
        params = make_double_fork_params()
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, algo_name in enumerate(selected_algorithms):
            status_text.markdown(f"**Running {algo_name}...**")
            
            result = run_algorithm(algo_name, params, settings)
            results.append(result)
            
            progress_bar.progress((i + 1) / len(selected_algorithms))
        
        progress_bar.empty()
        status_text.empty()
        
        # Store results in session state
        st.session_state["results"] = results
        st.session_state["params"] = params
    
    # Display results
    if "results" in st.session_state and st.session_state["results"]:
        results = st.session_state["results"]
        
        st.success(f"✅ Optimization complete! Ran {len(results)} algorithms.")
        
        # Metrics row
        st.subheader("📊 Results Summary")
        
        cols = st.columns(len(results))
        for i, result in enumerate(results):
            with cols[i]:
                algo = result["algorithm"]
                color_class = f"badge-{algo.lower()}"
                
                st.markdown(f"""
                <div class="metric-card">
                    <span class="algo-badge {color_class}">{algo}</span>
                    <h3 style="margin: 0.5rem 0;">{result['weighted']:.2f}</h3>
                    <p style="color: #8892b0; margin: 0;">Weighted Objective</p>
                    <hr style="border-color: rgba(255,255,255,0.1);">
                    <p>⏱️ Makespan: {result['makespan']:.1f} min</p>
                    <p>💰 Cost: {result['cost']:.2f} EGP</p>
                    <p>⚡ Runtime: {result['runtime']:.1f}s</p>
                    <p>{'✅ Feasible' if result['feasible'] else '❌ Infeasible'}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Comparison chart
        st.subheader("📈 Visual Comparison")
        
        results_df = pd.DataFrame([
            {
                "algorithm": r["algorithm"],
                "weighted": r["weighted"],
                "makespan": r["makespan"],
                "cost": r["cost"],
                "runtime": r["runtime"]
            }
            for r in results
        ])
        
        fig = create_comparison_chart(results_df)
        st.plotly_chart(fig, use_container_width=True)
        
        # Best algorithm highlight
        best_idx = results_df["weighted"].idxmin()
        best_algo = results_df.loc[best_idx, "algorithm"]
        st.info(f"🏆 **Best Algorithm:** {best_algo} with weighted objective {results_df.loc[best_idx, 'weighted']:.2f}")
        
        # ========================================
        # ANIMATED SIMULATION SECTION
        # ========================================
        st.subheader("🎬 Animated Simulation")
        st.markdown("*Click Play to see cars moving through the network. Click on the timeline to scrub. Green striped bars = charging.*")
        
        params = st.session_state["params"]
        
        # Simulation tabs for each algorithm
        sim_tabs = st.tabs([f"🚗 {r['algorithm']} Simulation" for r in results])
        for i, sim_tab in enumerate(sim_tabs):
            with sim_tab:
                result = results[i]
                algo_name = result["algorithm"]
                solution = result["solution"]
                
                # Generate and embed the HTML simulation
                sim_html = create_simulation_html(solution, params, algo_name)
                components.html(sim_html, height=780, scrolling=False)
                
                # Solution details below simulation
                display_solution_details(solution, algo_name, params)
        
        # Export option
        st.subheader("📥 Export Results")
        
        csv_data = results_df.to_csv(index=False)
        st.download_button(
            label="Download Results CSV",
            data=csv_data,
            file_name="algorithm_comparison_results.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()
