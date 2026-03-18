#!/usr/bin/env python3
"""
visualization.py - Shared visualization module for EV fleet optimization

Provides dashboard generation that can be used by any optimization algorithm:
- Simulated Annealing
- Genetic Algorithm
- MILP solver
- Any future algorithms

Features:
- Static information (speeds, costs, routes)
- Animated network playback (JavaScript-based)
- Timeline visualization
- Speed analysis
"""

import json
from pathlib import Path

from common.objectives import FleetSolution
from common.params import SingleForkParams


def generate_dashboard(
    solution: FleetSolution, 
    params: SingleForkParams, 
    output_file: str = "solution_dashboard.html",
    algorithm_name: str = "Optimization"
) -> Path:
    """
    Generate interactive HTML dashboard for any optimization solution.
    
    Args:
        solution: Fleet solution from any algorithm
        params: Problem parameters
        output_file: Output HTML filename
        algorithm_name: Name of algorithm used (e.g., "Simulated Annealing")
    
    Returns:
        Path to generated HTML file
    """
    
    # Extract vehicle data
    vehicles_data = []
    for vs in solution.vehicle_solutions:
        vehicle = {
            'id': vs.vehicle_id,
            'route': vs.route,
            'route_text': ' → '.join(vs.route),
            'completion_time': vs.get_completion_time(),
            'total_cost': vs.get_total_charging_cost(params),
            'charging_time': vs.get_total_charging_time(),
            'queue_time': vs.get_total_queue_time(),
            'charging_stations': vs.charging_stations,
            'charging_amounts': vs.charging_amounts,
            'speeds': {f"{u}→{v}": vs.get_speed_level((u, v)) for u, v in zip(vs.route[:-1], vs.route[1:])},
            'arrival_times': vs.arrival_times,
            'departure_times': vs.departure_times,
        }
        vehicles_data.append(vehicle)
    
    # Extract edge data
    edges_data = []
    for edge in params.edges_time_min.keys():
        min_speed, max_speed = params.get_edge_speed_bounds(edge)
        distance = params.edges_distance_km[edge]
        base_energy = params.edges_energy_kwh[edge]
        
        edges_data.append({
            'from': edge[0],
            'to': edge[1],
            'label': f"{edge[0]}→{edge[1]}",
            'distance_km': round(distance, 1),
            'speed_min': round(min_speed, 0),
            'speed_max': round(max_speed, 0),
            'base_time': round(params.edges_time_min[edge], 1),
            'base_energy': round(base_energy, 1),
        })
    
    # Network positions (for visualization)
    if isinstance(params, SingleForkParams) and not hasattr(params, 'nodes'): # Heuristic for SingleFork
         network_pos = {
            'A': {'x': 50, 'y': 200},
            'J': {'x': 200, 'y': 200},
            'S1': {'x': 350, 'y': 100},
            'S2': {'x': 500, 'y': 100},
            'S3': {'x': 350, 'y': 300},
            'M': {'x': 650, 'y': 200},
            'B': {'x': 800, 'y': 200}
        }
    else:
        # Double Fork positions or generic fallback
        # A -> J1 -> (S1-S2 / S3) -> M1 -> J2 -> (S4-S5 / S6) -> M2 -> B
        network_pos = {
            'A': {'x': 40, 'y': 200},
            'J1': {'x': 120, 'y': 200},
            
            # Fork 1 Upper
            'S1': {'x': 220, 'y': 80},
            'S2': {'x': 320, 'y': 80},
            
            # Fork 1 Lower
            'S3': {'x': 270, 'y': 320},
            
            'M1': {'x': 400, 'y': 200},
            
            'J2': {'x': 480, 'y': 200},
            
            # Fork 2 Upper
            'S4': {'x': 580, 'y': 80},
            'S5': {'x': 680, 'y': 80},
            
            # Fork 2 Lower
            'S6': {'x': 630, 'y': 320},
            
            'M2': {'x': 780, 'y': 200},
            'B': {'x': 860, 'y': 200}
        }

    # Station data
    stations = list(params.station_plugs.keys())
    stations_data = [{
        'name': s,
        'plugs': params.station_plugs.get(s, 0),
        'price': params.station_price.get(s, 0),
        'max_power': params.station_max_kw.get(s, 0),
    } for s in stations]
    
    # Calculate max time for timeline scaling
    max_time = max(v['completion_time'] for v in vehicles_data)
    
    # Extract SOC data for visualization
    soc_data = _generate_soc_data(solution, params)
    soc_json = json.dumps(soc_data, indent=2)
    
    # Generate HTML
    html = _generate_html(
        vehicles_data=vehicles_data,
        edges_data=edges_data,
        stations_data=stations_data,
        network_pos=network_pos,
        params=params,
        max_time=max_time,
        algorithm_name=algorithm_name,
        solution=solution,
        soc_json=soc_json,
        stations_list=stations
    )
    
    # Write file (default to outputs/plots when a relative name is provided)
    output_path = Path(output_file)
    if not output_path.is_absolute():
        project_root = Path(__file__).resolve().parents[1]
        output_path = project_root / "outputs" / "plots" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')
    
    print(f"\n✅ Dashboard generated: {output_path.absolute()}")
    print(f"📂 Open: file://{output_path.absolute()}")
    
    # Try to open in browser
    import webbrowser
    try:
        webbrowser.open(f"file://{output_path.absolute()}")
        print("🌐 Opening in browser...")
    except Exception:
        pass
    
    return output_path


def _generate_soc_data(solution: FleetSolution, params: SingleForkParams):
    """Generate time-series SOC data for each vehicle."""
    soc_data = []
    for v_sol in solution.vehicle_solutions:
        # Get battery capacity for this vehicle
        capacity_kwh = params.battery_kwh[v_sol.vehicle_id]
        
        points = []
        
        # Add initial point
        points.append({
            't': v_sol.arrival_times['A'],
            'soc': v_sol.soc_at_nodes['A'] * 100,
            'energy': v_sol.soc_at_nodes['A'] * capacity_kwh
        })
        
        for i in range(len(v_sol.route) - 1):
            u, v = v_sol.route[i], v_sol.route[i+1]
            
            # If charging at u
            if u in v_sol.charging_stations:
                # Arrival (already added)
                
                # Queue end / Charge start
                start_charge_time = v_sol.charging_start_times.get(u, v_sol.arrival_times[u])
                if start_charge_time > v_sol.arrival_times[u]:
                    points.append({
                        't': start_charge_time,
                        'soc': v_sol.soc_at_nodes[u] * 100,
                        'energy': v_sol.soc_at_nodes[u] * capacity_kwh
                    })
                
                # Charge end / Departure
                departure_time = v_sol.departure_times[u]
                charged_amount = v_sol.charging_amounts.get(u, 0.0)
                # SOC after charging
                soc_after = v_sol.soc_at_nodes[u] + (charged_amount / capacity_kwh)
                
                points.append({
                    't': departure_time,
                    'soc': soc_after * 100,
                    'energy': soc_after * capacity_kwh
                })
                
                pass
            else:
                pass
            
            # Arrival at next node v
            arrival_time_v = v_sol.arrival_times[v]
            points.append({
                't': arrival_time_v,
                'soc': v_sol.soc_at_nodes[v] * 100,
                'energy': v_sol.soc_at_nodes[v] * capacity_kwh
            })
            
        soc_data.append({
            'label': f"Vehicle {v_sol.vehicle_id}",
            'data': points,
            'battery_kwh': capacity_kwh
        })
        
    return soc_data


def _generate_html(vehicles_data, edges_data, stations_data, network_pos, params, max_time, algorithm_name, solution, soc_json, stations_list):
    """Generate complete HTML content."""
    
    # Convert data to JSON for JavaScript
    vehicles_json = json.dumps(vehicles_data, indent=2)
    network_json = json.dumps(network_pos, indent=2)
    edges_json = json.dumps(edges_data, indent=2)
    stations_json = json.dumps(stations_list, indent=2)
    
    # Generate HTML sections
    edge_cards_html = _generate_edge_cards(edges_data)
    vehicle_cards_html = _generate_vehicle_cards(vehicles_data, params)
    stations_table_html = _generate_stations_table(stations_data)
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EV Fleet Dashboard - {algorithm_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        {_get_css()}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚗 EV Fleet Optimization Dashboard</h1>
        <div class="algorithm-badge">{algorithm_name}</div>
        
        <!-- Summary Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{solution.get_vehicle_count()}</div>
                <div class="stat-label">Vehicles</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{max(vs['completion_time'] for vs in vehicles_data):.1f} min</div>
                <div class="stat-label">Makespan</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(vs['total_cost'] for vs in vehicles_data):.2f} EGP</div>
                <div class="stat-label">Total Cost</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(vs['charging_time'] for vs in vehicles_data):.1f} min</div>
                <div class="stat-label">Charging Time</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{"✅ Feasible" if solution.is_feasible() else "❌ Infeasible"}</div>
                <div class="stat-label">Status</div>
            </div>
        </div>
        
        <!-- Animated Network Map with Integrated Timeline -->
        <div class="section">
            <div class="section-title">🗺️ Network Animation & Timeline</div>
            <div class="animation-controls">
                <button id="playBtn" class="control-btn">▶ Play</button>
                <button id="pauseBtn" class="control-btn">⏸ Pause</button>
                <button id="resetBtn" class="control-btn">↺ Reset</button>
                <label>Speed: <input type="range" id="speedSlider" min="0.1" max="5" step="0.1" value="1"></label>
                <span id="timeDisplay">Time: 0.0 min / {max(vs['completion_time'] for vs in vehicles_data):.1f} min</span>
            </div>
            <canvas id="networkCanvas" width="900" height="400"></canvas>
            <canvas id="timelineCanvas" width="900" height="200"></canvas>
            <div class="timeline-legend">
                <div class="legend-item"><div class="legend-color" style="background:#4CAF50"></div><span>Traveling</span></div>
                <div class="legend-item"><div class="legend-color" style="background:#EF5350"></div><span>Charging</span></div>
                <div class="legend-item"><div class="legend-color" style="background:#666; width:2px;"></div><span>Current Time</span></div>
            </div>
            <div class="vehicle-legend" id="vehicleLegend"></div>
        </div>

        <!-- SOC Chart -->
        <div class="section">
            <div class="section-title">🔋 State of Charge (SOC) vs Time</div>
            <div style="height: 400px;">
                <canvas id="socChart"></canvas>
            </div>
        </div>

        <!-- Energy Chart -->
        <div class="section">
            <div class="section-title">⚡ Energy Level (kWh) vs Time</div>
            <div style="height: 400px;">
                <canvas id="energyChart"></canvas>
            </div>
        </div>
        
        <!-- Network Edges -->
        <div class="section">
            <div class="section-title">📍 Network Edges & Speed Limits</div>
            <div class="network-info">{edge_cards_html}</div>
        </div>
        
        <!-- Vehicles -->
        <div class="section">
            <div class="section-title">🚙 Vehicle Details</div>
            <div class="vehicles-grid">{vehicle_cards_html}</div>
        </div>
        
        <!-- Stations -->
        <div class="section">
            <div class="section-title">⚡ Charging Stations</div>
            <table class="info-table">
                <thead><tr><th>Station</th><th>Plugs</th><th>Price (EGP/kWh)</th><th>Max Power (kW)</th></tr></thead>
                <tbody>{stations_table_html}</tbody>
            </table>
        </div>
    </div>
    
    <script>
        const socData = {soc_json};
        {_get_javascript(vehicles_json, network_json, edges_json, max_time, stations_json)}
        {_get_soc_chart_js()}
    </script>
</body>
</html>"""


def _get_soc_chart_js():
    """Return JavaScript for SOC chart."""
    return """
        // Render SOC Chart
        const ctx = document.getElementById('socChart').getContext('2d');
        const datasets = socData.map((v, i) => ({
            label: v.label,
            data: v.data.map(p => ({x: p.t, y: p.soc, energy: p.energy})),
            borderColor: colors[i % colors.length],
            backgroundColor: colors[i % colors.length],
            borderWidth: 2,
            pointRadius: 3,
            fill: false,
            tension: 0.1,
            showLine: true
        }));
        
        new Chart(ctx, {
            type: 'scatter',
            data: { datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: { display: true, text: 'Time (minutes)' }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        title: { display: true, text: 'State of Charge (%)' }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const point = context.raw;
                                return context.dataset.label + ': ' + 
                                       context.parsed.y.toFixed(1) + '% (' + 
                                       point.energy.toFixed(1) + ' kWh) at ' + 
                                       context.parsed.x.toFixed(1) + ' min';
                            }
                        }
                    }
                }
            }
        });

        // Render Energy Chart
        const ctxEnergy = document.getElementById('energyChart').getContext('2d');
        const datasetsEnergy = socData.map((v, i) => ({
            label: v.label,
            data: v.data.map(p => ({x: p.t, y: p.energy, soc: p.soc})),
            borderColor: colors[i % colors.length],
            backgroundColor: colors[i % colors.length],
            borderWidth: 2,
            pointRadius: 3,
            fill: false,
            tension: 0.1,
            showLine: true
        }));
        
        new Chart(ctxEnergy, {
            type: 'scatter',
            data: { datasets: datasetsEnergy },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: { display: true, text: 'Time (minutes)' }
                    },
                    y: {
                        min: 0,
                        // max: auto (depends on battery size)
                        title: { display: true, text: 'Energy Level (kWh)' }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const point = context.raw;
                                return context.dataset.label + ': ' + 
                                       context.parsed.y.toFixed(1) + ' kWh (' + 
                                       point.soc.toFixed(1) + '%) at ' + 
                                       context.parsed.x.toFixed(1) + ' min';
                            }
                        }
                    }
                }
            }
        });
    """


def _get_css():
    """Return CSS styling."""
    return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .algorithm-badge {
            text-align: center;
            color: white;
            font-size: 1.2em;
            margin-bottom: 30px;
            opacity: 0.9;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
        }
        .section {
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .section-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        #networkCanvas {
            border: 2px solid #ddd;
            border-radius: 8px 8px 0 0;
            background: #f9f9f9;
            display: block;
            margin: 0 auto;
        }
        #timelineCanvas {
            border: 2px solid #ddd;
            border-top: none;
            border-radius: 0 0 8px 8px;
            background: white;
            display: block;
            margin: 0 auto;
            cursor: pointer;
        }
        #timelineCanvas:hover {
            background: #f5f5f5;
        }
        .timeline-legend {
            display: flex;
            gap: 20px;
            margin: 15px 0;
            justify-content: center;
        }
        .animation-controls {
            display: flex;
            gap: 15px;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .control-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            font-weight: bold;
        }
        .control-btn:hover { background: #5568d3; }
        #timeDisplay {
            font-weight: bold;
            color: #667eea;
            margin-left: auto;
        }
        .vehicle-legend {
            display: flex;
            gap: 15px;
            margin-top: 15px;
            flex-wrap: wrap;
            justify-content: center;
        }
        .legend-vehicle {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 5px 10px;
            background: #f5f5f5;
            border-radius: 5px;
        }
        .legend-vehicle-color {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            border: 2px solid black;
        }
        .network-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        .edge-card {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .edge-name {
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 10px;
            color: #333;
        }
        .edge-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.9em;
        }
        .info-item {
            display: flex;
            justify-content: space-between;
        }
        .info-label { color: #666; }
        .info-value { font-weight: 600; color: #333; }
        .vehicles-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .vehicle-card {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        }
        .vehicle-header {
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
            display: flex;
            justify-content: space-between;
        }
        .vehicle-badge {
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
        }
        .vehicle-detail {
            margin: 8px 0;
            padding: 8px;
            background: white;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
        }
        .detail-label { font-weight: 500; color: #666; }
        .detail-value { font-weight: bold; color: #333; }
        .info-table {
            width: 100%;
            border-collapse: collapse;
        }
        .info-table th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
        }
        .info-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        .info-table tbody tr:hover { background: #f5f5f5; }
        .speed-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.9em;
        }
        .speed-table th {
            background: #667eea;
            color: white;
            padding: 8px;
            text-align: left;
        }
        .speed-table td {
            padding: 6px 8px;
            border-bottom: 1px solid #e0e0e0;
        }
        .speed-value { font-weight: bold; color: #667eea; }
        .speed-range { font-size: 0.85em; color: #999; }
        .vehicle-section {
            margin: 15px 0;
            padding: 12px;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }
        .vehicle-section strong {
            display: block;
            margin-bottom: 8px;
            color: #667eea;
            font-size: 0.95em;
        }
        .timeline { margin-top: 20px; }
        .timeline-row { margin-bottom: 15px; }
        .timeline-label {
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
        }
        .timeline-bar {
            display: flex;
            height: 40px;
            border-radius: 5px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .timeline-segment {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8em;
            color: white;
            font-weight: 500;
            border-right: 1px solid white;
        }
        .timeline-segment:hover {
            filter: brightness(1.2);
            cursor: pointer;
        }
        .legend {
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .legend-color {
            width: 30px;
            height: 20px;
            border-radius: 3px;
        }
    """


def _get_javascript(vehicles_json, network_json, edges_json, max_time, stations_json):
    """Return JavaScript for animation."""
    return f"""
        const vehicles = {vehicles_json};
        const networkPos = {network_json};
        const edges = {edges_json};
        const maxTime = {max_time};
        const stationNodes = {stations_json};
        
        const networkCanvas = document.getElementById('networkCanvas');
        const networkCtx = networkCanvas.getContext('2d');
        const timelineCanvas = document.getElementById('timelineCanvas');
        const timelineCtx = timelineCanvas.getContext('2d');
        
        let currentTime = 0;
        let isPlaying = false;
        let animationSpeed = 1.0;
        let animationFrame = null;
        
        const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE'];
        
        // Timeline constants
        const TIMELINE_MARGIN = 50;
        const TIMELINE_ROW_HEIGHT = 35;
        const TIMELINE_PADDING = 20;
        
        // Draw static network
        function drawNetwork() {{
            networkCtx.clearRect(0, 0, networkCanvas.width, networkCanvas.height);
            
            // Draw edges
            networkCtx.strokeStyle = '#ccc';
            networkCtx.lineWidth = 3;
            edges.forEach(edge => {{
                const from = networkPos[edge.from];
                const to = networkPos[edge.to];
                networkCtx.beginPath();
                networkCtx.moveTo(from.x, from.y);
                networkCtx.lineTo(to.x, to.y);
                networkCtx.stroke();
                
                // Edge label
                const midX = (from.x + to.x) / 2;
                const midY = (from.y + to.y) / 2;
                networkCtx.fillStyle = '#666';
                networkCtx.font = '10px Arial';
                networkCtx.fillText(`${{edge.speed_min}}-${{edge.speed_max}} km/h`, midX - 30, midY - 5);
            }});
            
            // Draw nodes
            Object.entries(networkPos).forEach(([node, pos]) => {{
                const isStation = stationNodes.includes(node);
                networkCtx.fillStyle = isStation ? '#b7e4c7' : '#cde4ff';
                networkCtx.beginPath();
                networkCtx.arc(pos.x, pos.y, 20, 0, Math.PI * 2);
                networkCtx.fill();
                networkCtx.strokeStyle = '#333';
                networkCtx.lineWidth = 2;
                networkCtx.stroke();
                
                networkCtx.fillStyle = '#000';
                networkCtx.font = 'bold 14px Arial';
                networkCtx.textAlign = 'center';
                networkCtx.textBaseline = 'middle';
                networkCtx.fillText(node, pos.x, pos.y);
            }});
        }}
        
        // Draw timeline
        function drawTimeline() {{
            timelineCtx.clearRect(0, 0, timelineCanvas.width, timelineCanvas.height);
            
            const chartWidth = timelineCanvas.width - 2 * TIMELINE_MARGIN;
            const chartStart = TIMELINE_MARGIN;
            
            // Draw each vehicle's timeline
            vehicles.forEach((vehicle, idx) => {{
                const y = TIMELINE_PADDING + idx * TIMELINE_ROW_HEIGHT;
                const color = colors[idx % colors.length];
                
                // Vehicle label
                timelineCtx.fillStyle = '#333';
                timelineCtx.font = 'bold 11px Arial';
                timelineCtx.textAlign = 'right';
                timelineCtx.textBaseline = 'middle';
                timelineCtx.fillText(`V${{idx + 1}}`, chartStart - 10, y + 15);
                
                // Draw timeline segments
                let prevTime = 0;
                vehicle.route.forEach((node, nodeIdx) => {{
                    if (node in vehicle.arrival_times) {{
                        const arrival = vehicle.arrival_times[node];
                        const departure = vehicle.departure_times[node];
                        
                        // Travel segment
                        if (prevTime < arrival) {{
                            const startX = chartStart + (prevTime / maxTime) * chartWidth;
                            const width = ((arrival - prevTime) / maxTime) * chartWidth;
                            timelineCtx.fillStyle = '#4CAF50';
                            timelineCtx.fillRect(startX, y, width, 30);
                            timelineCtx.strokeStyle = '#fff';
                            timelineCtx.lineWidth = 1;
                            timelineCtx.strokeRect(startX, y, width, 30);
                        }}
                        
                        // Charging segment
                        if (vehicle.charging_stations.includes(node)) {{
                            const startX = chartStart + (arrival / maxTime) * chartWidth;
                            const width = ((departure - arrival) / maxTime) * chartWidth;
                            timelineCtx.fillStyle = '#EF5350';
                            timelineCtx.fillRect(startX, y, width, 30);
                            timelineCtx.strokeStyle = '#fff';
                            timelineCtx.lineWidth = 1;
                            timelineCtx.strokeRect(startX, y, width, 30);
                            
                            // Station label on charging segment
                            if (width > 20) {{
                                timelineCtx.fillStyle = '#fff';
                                timelineCtx.font = 'bold 10px Arial';
                                timelineCtx.textAlign = 'center';
                                timelineCtx.fillText(node, startX + width/2, y + 15);
                            }}
                        }}
                        
                        prevTime = departure;
                    }}
                }});
            }});
            
            // Draw current time indicator
            const currentX = chartStart + (currentTime / maxTime) * chartWidth;
            timelineCtx.strokeStyle = '#666';
            timelineCtx.lineWidth = 2;
            timelineCtx.beginPath();
            timelineCtx.moveTo(currentX, 0);
            timelineCtx.lineTo(currentX, timelineCanvas.height);
            timelineCtx.stroke();
            
            // Time markers
            timelineCtx.fillStyle = '#999';
            timelineCtx.font = '10px Arial';
            timelineCtx.textAlign = 'center';
            for (let i = 0; i <= 5; i++) {{
                const time = (i / 5) * maxTime;
                const x = chartStart + (i / 5) * chartWidth;
                timelineCtx.fillText(`${{time.toFixed(0)}}m`, x, timelineCanvas.height - 5);
            }}
        }}
        
        // Get vehicle position at current time
        function getVehiclePosition(vehicle) {{
            const route = vehicle.route;
            
            for (let i = 0; i < route.length - 1; i++) {{
                const currentNode = route[i];
                const nextNode = route[i + 1];
                
                const arrivalNext = vehicle.arrival_times[nextNode] || Infinity;
                const departCurrent = vehicle.departure_times[currentNode] || 0;
                
                // At station
                if (currentTime >= vehicle.arrival_times[currentNode] && currentTime < departCurrent) {{
                    return networkPos[currentNode];
                }}
                
                // Traveling
                if (currentTime >= departCurrent && currentTime < arrivalNext) {{
                    const progress = (currentTime - departCurrent) / (arrivalNext - departCurrent);
                    const from = networkPos[currentNode];
                    const to = networkPos[nextNode];
                    return {{
                        x: from.x + progress * (to.x - from.x),
                        y: from.y + progress * (to.y - from.y)
                    }};
                }}
            }}
            
            return networkPos['B']; // Completed
        }}
        
        // Draw vehicles
        function drawVehicles() {{
            vehicles.forEach((vehicle, idx) => {{
                if (currentTime > vehicle.completion_time) return;
                
                const pos = getVehiclePosition(vehicle);
                const color = colors[idx % colors.length];
                
                networkCtx.fillStyle = color;
                networkCtx.beginPath();
                networkCtx.arc(pos.x, pos.y, 12, 0, Math.PI * 2);
                networkCtx.fill();
                networkCtx.strokeStyle = '#000';
                networkCtx.lineWidth = 2;
                networkCtx.stroke();
                
                networkCtx.fillStyle = '#fff';
                networkCtx.font = 'bold 10px Arial';
                networkCtx.textAlign = 'center';
                networkCtx.textBaseline = 'middle';
                networkCtx.fillText(`V${{idx + 1}}`, pos.x, pos.y);
            }});
        }}
        
        // Update everything
        function updateDisplay() {{
            drawNetwork();
            drawVehicles();
            drawTimeline();
            document.getElementById('timeDisplay').textContent = `Time: ${{currentTime.toFixed(1)}} min / ${{maxTime.toFixed(1)}} min`;
        }}
        
        // Animation loop
        function animate() {{
            if (!isPlaying) return;
            
            currentTime += 0.1 * animationSpeed;
            if (currentTime > maxTime) {{
                currentTime = 0;
            }}
            
            updateDisplay();
            animationFrame = requestAnimationFrame(animate);
        }}
        
        // Timeline click handler (scrubbing)
        timelineCanvas.addEventListener('click', (e) => {{
            const rect = timelineCanvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const chartWidth = timelineCanvas.width - 2 * TIMELINE_MARGIN;
            const chartStart = TIMELINE_MARGIN;
            
            if (x >= chartStart && x <= chartStart + chartWidth) {{
                const clickedTime = ((x - chartStart) / chartWidth) * maxTime;
                currentTime = Math.max(0, Math.min(maxTime, clickedTime));
                updateDisplay();
            }}
        }});
        
        // Controls
        document.getElementById('playBtn').onclick = () => {{
            isPlaying = true;
            animate();
        }};
        
        document.getElementById('pauseBtn').onclick = () => {{
            isPlaying = false;
            if (animationFrame) cancelAnimationFrame(animationFrame);
        }};
        
        document.getElementById('resetBtn').onclick = () => {{
            currentTime = 0;
            isPlaying = false;
            if (animationFrame) cancelAnimationFrame(animationFrame);
            updateDisplay();
        }};
        
        document.getElementById('speedSlider').oninput = (e) => {{
            animationSpeed = parseFloat(e.target.value);
        }};
        
        // Create vehicle legend
        const legend = document.getElementById('vehicleLegend');
        vehicles.forEach((v, idx) => {{
            const div = document.createElement('div');
            div.className = 'legend-vehicle';
            div.innerHTML = `
                <div class="legend-vehicle-color" style="background: ${{colors[idx % colors.length]}}"></div>
                <span>Vehicle ${{idx + 1}}: ${{v.route_text}}</span>
            `;
            legend.appendChild(div);
        }});
        
        // Initial draw
        updateDisplay();
    """


def _generate_edge_cards(edges_data):
    """Generate edge information cards."""
    return '\n'.join([
        f"""<div class="edge-card">
            <div class="edge-name">{e['label']}</div>
            <div class="edge-info">
                <div class="info-item"><span class="info-label">Distance:</span><span class="info-value">{e['distance_km']} km</span></div>
                <div class="info-item"><span class="info-label">Speed Range:</span><span class="info-value">{e['speed_min']}-{e['speed_max']} km/h</span></div>
                <div class="info-item"><span class="info-label">Base Time:</span><span class="info-value">{e['base_time']} min</span></div>
                <div class="info-item"><span class="info-label">Base Energy:</span><span class="info-value">{e['base_energy']} kWh</span></div>
            </div>
        </div>"""
        for e in edges_data
    ])


def _generate_vehicle_cards(vehicles_data, params):
    """Generate vehicle detail cards."""
    cards = []
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']
    
    for i, v in enumerate(vehicles_data):
        color = colors[i % len(colors)]
        
        # Starting data
        vehicle_id = v['id']
        battery_capacity = params.battery_kwh[vehicle_id]
        initial_soc = params.soc0[vehicle_id]
        initial_battery_kwh = battery_capacity * initial_soc
        departure_time = v['departure_times'].get('A', 0.0)
        
        # Speed table
        speed_rows = '\n'.join([
            f"""<tr>
                <td>{edge}</td>
                <td class="speed-value">{speed:.0f} km/h</td>
                <td class="speed-range">[{params.get_edge_speed_bounds(tuple(edge.split('→')))[0]:.0f}-{params.get_edge_speed_bounds(tuple(edge.split('→')))[1]:.0f}]</td>
            </tr>"""
            for edge, speed in v['speeds'].items()
        ])
        
        # Charging details
        charging_info = '\n'.join([
            f"""<div class="vehicle-detail">
                <span class="detail-label">{station}:</span>
                <span class="detail-value">{v['charging_amounts'][station]:.1f} kWh (×{params.station_price[station]:.1f} = {v['charging_amounts'][station] * params.station_price[station]:.2f} EGP)</span>
            </div>"""
            for station in v['charging_stations']
        ])
        
        cards.append(f"""
            <div class="vehicle-card">
                <div class="vehicle-header">
                    <span>Vehicle {v['id'] + 1}</span>
                    <span class="vehicle-badge" style="background: {color}">{v['completion_time']:.1f} min</span>
                </div>
                
                <!-- Starting Data -->
                <div class="vehicle-section">
                    <strong>📊 Starting Conditions:</strong>
                    <div class="vehicle-detail">
                        <span class="detail-label">Battery Capacity:</span>
                        <span class="detail-value">{battery_capacity:.1f} kWh</span>
                    </div>
                    <div class="vehicle-detail">
                        <span class="detail-label">Initial Charge:</span>
                        <span class="detail-value">{initial_soc*100:.0f}% ({initial_battery_kwh:.1f} kWh)</span>
                    </div>
                    <div class="vehicle-detail">
                        <span class="detail-label">Departure Time:</span>
                        <span class="detail-value">{departure_time:.1f} min</span>
                    </div>
                </div>
                
                <!-- Journey Summary -->
                <div class="vehicle-section">
                    <strong>🗺️ Journey:</strong>
                    <div class="vehicle-detail">
                        <span class="detail-label">Route:</span>
                        <span class="detail-value">{v['route_text']}</span>
                    </div>
                    <div class="vehicle-detail">
                        <span class="detail-label">Total Cost:</span>
                        <span class="detail-value">{v['total_cost']:.2f} EGP</span>
                    </div>
                </div>
                
                <!-- Charging Details -->
                <div class="vehicle-section">
                    <strong>⚡ Charging:</strong>
                    {charging_info}
                </div>
                
                <!-- Speed Choices -->
                <div class="vehicle-section">
                    <strong>🏎️ Speed Choices:</strong>
                    <table class="speed-table">
                        <thead><tr><th>Edge</th><th>Speed</th><th>Allowed</th></tr></thead>
                        <tbody>{speed_rows}</tbody>
                    </table>
                </div>
            </div>
        """)
    
    return '\n'.join(cards)


def _generate_timeline(vehicles_data, max_time):
    """Generate timeline HTML."""
    rows = []
    for v in vehicles_data:
        segments = []
        prev_time = 0
        
        for node in v['route']:
            if node in v['arrival_times']:
                arrival = v['arrival_times'][node]
                departure = v['departure_times'][node]
                
                # Travel segment
                if prev_time < arrival:
                    width = ((arrival - prev_time) / max_time) * 100
                    segments.append(f'<div class="timeline-segment" style="width:{width}%;background:#4CAF50" title="Travel: {arrival - prev_time:.1f}min">{arrival - prev_time:.0f}m</div>')
                
                # Charging segment
                if node in v['charging_stations']:
                    width = ((departure - arrival) / max_time) * 100
                    segments.append(f'<div class="timeline-segment" style="width:{width}%;background:#EF5350" title="Charge at {node}: {departure - arrival:.1f}min">{node} {departure - arrival:.0f}m</div>')
                
                prev_time = departure
        
        rows.append(f'<div class="timeline-row"><div class="timeline-label">Vehicle {v["id"] + 1} ({v["completion_time"]:.1f} min)</div><div class="timeline-bar">{"".join(segments)}</div></div>')
    
    return '\n'.join(rows)


def _generate_stations_table(stations_data):
    """Generate stations table HTML."""
    return '\n'.join([
        f'<tr><td><strong>{s["name"]}</strong></td><td>{s["plugs"]}</td><td>{s["price"]:.2f}</td><td>{s["max_power"]:.0f}</td></tr>'
        for s in stations_data
    ])
