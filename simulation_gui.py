#!/usr/bin/env python3
"""
simulation_gui.py
Interactive GUI for visualizing and simulating EV fleet routing solutions.

Features:
- Real-time animation of vehicles moving through network
- Queue visualization at charging stations
- Charging progress bars
- Live metrics dashboard
- Playback controls (play/pause/speed)
- Timeline scrubbing
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
import numpy as np
from typing import Dict, List, Tuple
from params import SingleForkParams
from objectives import FleetSolution, VehicleSolution


class EVFleetSimulation:
    """
    Interactive simulation GUI for EV fleet routing solutions.
    
    Shows:
    - Vehicle positions moving through network
    - Queue status at each station
    - Charging progress
    - Real-time metrics
    """
    
    def __init__(self, solution: FleetSolution, params: SingleForkParams):
        """
        Initialize the simulation.
        
        Args:
            solution: Complete fleet solution to simulate
            params: Problem parameters
        """
        self.solution = solution
        self.params = params
        self.current_time = 0.0
        self.is_playing = True  # Start playing automatically
        self.speed_multiplier = 1.0
        
        # Network layout (same as visualize_params)
        self.pos = {
            'A': (0, 2),
            'J': (2, 2),
            'S1': (4, 3),
            'S2': (6, 3),
            'S3': (4, 1),
            'M': (8, 2),
            'B': (10, 2)
        }
        
        # Calculate simulation duration
        self.max_time = max(vs.get_completion_time() for vs in solution.vehicle_solutions)
        
        # Track vehicle states
        self.vehicle_states = self._initialize_vehicle_states()
        
        # Setup GUI
        self._setup_figure()
        
    def _initialize_vehicle_states(self) -> List[Dict]:
        """Initialize state tracking for each vehicle."""
        states = []
        for vs in self.solution.vehicle_solutions:
            state = {
                'vehicle_id': vs.vehicle_id,
                'route': vs.route,
                'position': (0, 0),  # Current (x, y) position
                'current_segment': 0,  # Which edge they're on
                'status': 'traveling',  # 'traveling', 'queued', 'charging', 'completed'
                'current_station': None,
                'charging_progress': 0.0,  # 0-1
                'soc': self.params.soc0[vs.vehicle_id],
                'arrival_times': vs.arrival_times,
                'departure_times': vs.departure_times,
                'charging_start_times': vs.charging_start_times or {},
                'charging_stations': vs.charging_stations,
            }
            states.append(state)
        return states
    
    def _setup_figure(self):
        """Setup the matplotlib figure and axes."""
        self.fig = plt.figure(figsize=(16, 10))
        self.main_title = self.fig.suptitle('EV Fleet Routing Simulation - ▶ PLAYING', 
                                            fontsize=16, fontweight='bold', color='green')
        
        # Main network view (left, large)
        self.ax_network = plt.subplot2grid((3, 3), (0, 0), colspan=2, rowspan=2)
        self.ax_network.set_title('Network & Vehicle Positions')
        self.ax_network.set_xlim(-1, 11)
        self.ax_network.set_ylim(0, 4)
        self.ax_network.axis('off')
        
        # Metrics dashboard (top right)
        self.ax_metrics = plt.subplot2grid((3, 3), (0, 2))
        self.ax_metrics.set_title('Metrics')
        self.ax_metrics.axis('off')
        
        # Queue status (middle right)
        self.ax_queues = plt.subplot2grid((3, 3), (1, 2))
        self.ax_queues.set_title('Station Queues')
        self.ax_queues.axis('off')
        
        # Timeline and controls (bottom)
        self.ax_timeline = plt.subplot2grid((3, 3), (2, 0), colspan=3)
        self.ax_timeline.set_title('Timeline')
        
        # Draw static network elements
        self._draw_network()
        
        # Add playback controls
        self._add_controls()
        
    def _draw_network(self):
        """Draw the static network topology."""
        # Draw edges
        for (u, v) in self.params.edges_time_min.keys():
            x1, y1 = self.pos[u]
            x2, y2 = self.pos[v]
            self.ax_network.plot([x1, x2], [y1, y2], 'k-', alpha=0.3, linewidth=2, zorder=1)
            
            # Edge label
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            time_min = self.params.edges_time_min[(u, v)]
            self.ax_network.text(mid_x, mid_y, f'{time_min:.0f}m', 
                               fontsize=7, ha='center', alpha=0.5)
        
        # Draw nodes
        stations = set(self.params.upper_stations + self.params.lower_stations)
        for node, (x, y) in self.pos.items():
            if node in stations:
                color = 'lightgreen' if node in self.params.upper_stations else 'lightcoral'
                circle = plt.Circle((x, y), 0.3, color=color, ec='black', linewidth=2, zorder=2)
                self.ax_network.add_patch(circle)
                
                # Station info
                plugs = self.params.station_plugs.get(node, 0)
                price = self.params.station_price.get(node, 0)
                self.ax_network.text(x, y, f'{node}\n{plugs}⚡\n{price:.2f}', 
                                   fontsize=8, ha='center', va='center', fontweight='bold', zorder=3)
            else:
                circle = plt.Circle((x, y), 0.2, color='lightblue', ec='black', linewidth=2, zorder=2)
                self.ax_network.add_patch(circle)
                self.ax_network.text(x, y, node, fontsize=10, ha='center', va='center', 
                                   fontweight='bold', zorder=3)
    
    def _add_controls(self):
        """Add playback control buttons."""
        # Play/Pause button
        self.ax_play = plt.axes([0.15, 0.02, 0.1, 0.04])
        self.btn_play = Button(self.ax_play, 'Play/Pause')
        self.btn_play.on_clicked(self._toggle_play)
        
        # Reset button
        self.ax_reset = plt.axes([0.27, 0.02, 0.1, 0.04])
        self.btn_reset = Button(self.ax_reset, 'Reset')
        self.btn_reset.on_clicked(self._reset)
        
        # Speed slider
        self.ax_speed = plt.axes([0.5, 0.02, 0.3, 0.03])
        self.slider_speed = Slider(self.ax_speed, 'Speed', 0.1, 5.0, valinit=1.0, valstep=0.1)
        self.slider_speed.on_changed(self._update_speed)
    
    def _toggle_play(self, event):
        """Toggle play/pause state."""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.main_title.set_text('EV Fleet Routing Simulation - ▶ PLAYING')
            self.main_title.set_color('green')
        else:
            self.main_title.set_text('EV Fleet Routing Simulation - ⏸ PAUSED')
            self.main_title.set_color('orange')
    
    def _reset(self, event):
        """Reset simulation to beginning."""
        self.current_time = 0.0
        self.is_playing = True
        self.vehicle_states = self._initialize_vehicle_states()
        self.main_title.set_text('EV Fleet Routing Simulation - ▶ PLAYING')
        self.main_title.set_color('green')
    
    def _update_speed(self, val):
        """Update playback speed."""
        self.speed_multiplier = val
    
    def _get_vehicle_position(self, state: Dict) -> Tuple[float, float]:
        """
        Calculate current (x, y) position of vehicle based on time.
        
        Returns position by interpolating along edges based on travel times.
        """
        route = state['route']
        arrival_times = state['arrival_times']
        departure_times = state['departure_times']
        
        # Find which segment vehicle is on
        for i in range(len(route) - 1):
            current_node = route[i]
            next_node = route[i + 1]
            
            arrival_at_next = arrival_times.get(next_node, float('inf'))
            departure_from_current = departure_times.get(current_node, 0)
            
            # Check if vehicle is at current node (charging or waiting)
            if self.current_time >= arrival_times.get(current_node, 0) and \
               self.current_time < departure_from_current:
                return self.pos[current_node]
            
            # Check if vehicle is traveling between nodes
            if self.current_time >= departure_from_current and \
               self.current_time < arrival_at_next:
                # Interpolate position along edge
                travel_time = arrival_at_next - departure_from_current
                progress = (self.current_time - departure_from_current) / max(travel_time, 0.01)
                progress = np.clip(progress, 0, 1)
                
                x1, y1 = self.pos[current_node]
                x2, y2 = self.pos[next_node]
                x = x1 + progress * (x2 - x1)
                y = y1 + progress * (y2 - y1)
                return (x, y)
        
        # Vehicle has completed journey
        return self.pos['B']
    
    def _get_vehicle_status(self, state: Dict) -> str:
        """Determine current status of vehicle."""
        route = state['route']
        
        # Check if completed
        if self.current_time >= state['arrival_times'].get('B', float('inf')):
            return 'completed'
        
        # Check each node
        for node in route:
            arrival = state['arrival_times'].get(node, float('inf'))
            departure = state['departure_times'].get(node, float('inf'))
            
            if arrival <= self.current_time < departure:
                # At this node
                if node in state['charging_stations']:
                    charging_start = state['charging_start_times'].get(node, arrival)
                    if self.current_time < charging_start:
                        return f'queued@{node}'
                    else:
                        return f'charging@{node}'
                return f'at_{node}'
        
        return 'traveling'
    
    def _update_frame(self, frame):
        """Update animation frame."""
        if self.is_playing:
            self.current_time += 0.1 * self.speed_multiplier
            if self.current_time > self.max_time:
                self.current_time = 0  # Loop
                print(f"\n🔄 Simulation looped. Restarting from t=0")
            
            # Print progress every 5 time units
            if int(self.current_time) % 5 == 0 and int(self.current_time * 10) % 50 == 0:
                traveling = sum(1 for s in self.vehicle_states if 'traveling' in s['status'] or 'at_' in s['status'])
                charging = sum(1 for s in self.vehicle_states if 'charging' in s['status'])
                completed = sum(1 for s in self.vehicle_states if s['status'] == 'completed')
                print(f"⏱ Time: {self.current_time:5.1f} min | Traveling: {traveling} | Charging: {charging} | Completed: {completed}/{len(self.vehicle_states)}")
        
        # Clear dynamic elements (vehicles and their labels)
        # Remove all vehicle markers (small circles with radius < 0.2)
        for patch in list(self.ax_network.patches):
            if isinstance(patch, mpatches.Circle) and patch.get_radius() < 0.2:
                patch.remove()
        
        # Remove all dynamic text labels
        for text in list(self.ax_network.texts):
            if hasattr(text, 'is_dynamic'):
                text.remove()
        
        # Update each vehicle
        colors = plt.cm.tab10(range(len(self.vehicle_states)))
        
        for state, color in zip(self.vehicle_states, colors):
            # Get current position and status
            x, y = self._get_vehicle_position(state)
            status = self._get_vehicle_status(state)
            state['position'] = (x, y)
            state['status'] = status
            
            # Draw vehicle
            if status != 'completed':
                vehicle_circle = plt.Circle((x, y), 0.15, color=color, ec='black', 
                                          linewidth=2, zorder=10, alpha=0.8)
                self.ax_network.add_patch(vehicle_circle)
                
                # Vehicle label
                label = self.ax_network.text(x, y, f'V{state["vehicle_id"]+1}', 
                                           fontsize=8, ha='center', va='center',
                                           color='white', fontweight='bold', zorder=11)
                label.is_dynamic = True
        
        # Update metrics
        self._update_metrics()
        
        # Update queues
        self._update_queues()
        
        # Update timeline
        self._update_timeline()
        
        return []
    
    def _update_metrics(self):
        """Update metrics dashboard."""
        self.ax_metrics.clear()
        self.ax_metrics.axis('off')
        
        # Count vehicle statuses
        traveling = sum(1 for s in self.vehicle_states if 'traveling' in s['status'] or 'at_' in s['status'])
        queued = sum(1 for s in self.vehicle_states if 'queued' in s['status'])
        charging = sum(1 for s in self.vehicle_states if 'charging' in s['status'])
        completed = sum(1 for s in self.vehicle_states if s['status'] == 'completed')
        
        metrics_text = f"""
TIME: {self.current_time:.1f} / {self.max_time:.1f} min

VEHICLE STATUS:
  Traveling: {traveling}
  Queued: {queued}
  Charging: {charging}
  Completed: {completed}

OBJECTIVES:
  Makespan: {self.max_time:.1f} min
  Total Cost: {sum(vs.get_total_charging_cost(self.params) for vs in self.solution.vehicle_solutions):.2f} EGP
        """
        
        self.ax_metrics.text(0.1, 0.9, metrics_text.strip(), 
                           fontsize=9, verticalalignment='top',
                           fontfamily='monospace',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    def _update_queues(self):
        """Update queue status visualization."""
        self.ax_queues.clear()
        self.ax_queues.axis('off')
        
        stations = list(self.params.upper_stations) + list(self.params.lower_stations)
        queue_text = "STATION QUEUES:\n\n"
        
        for station in stations:
            # Find vehicles at this station
            queued = [s for s in self.vehicle_states if s['status'] == f'queued@{station}']
            charging = [s for s in self.vehicle_states if s['status'] == f'charging@{station}']
            capacity = self.params.station_plugs.get(station, 0)
            
            queue_text += f"{station} ({len(charging)}/{capacity} plugs):\n"
            
            if charging:
                for s in charging:
                    # Calculate charging progress
                    arrival = s['arrival_times'][station]
                    departure = s['departure_times'][station]
                    start = s['charging_start_times'].get(station, arrival)
                    
                    if self.current_time >= start:
                        progress = (self.current_time - start) / max(departure - start, 0.01)
                        progress = min(progress, 1.0)
                        bar = '█' * int(progress * 10) + '░' * (10 - int(progress * 10))
                        queue_text += f"  V{s['vehicle_id']+1}: {bar} {progress*100:.0f}%\n"
            
            if queued:
                queue_text += f"  Queue: {len(queued)} vehicle(s)\n"
                for s in queued:
                    queue_text += f"    V{s['vehicle_id']+1} waiting\n"
            
            if not charging and not queued:
                queue_text += f"  (empty)\n"
            
            queue_text += "\n"
        
        self.ax_queues.text(0.05, 0.95, queue_text, 
                          fontsize=8, verticalalignment='top',
                          fontfamily='monospace')
    
    def _update_timeline(self):
        """Update timeline visualization."""
        self.ax_timeline.clear()
        
        # Draw timeline for each vehicle
        colors = plt.cm.tab10(range(len(self.vehicle_states)))
        
        for i, (vs_original, color) in enumerate(zip(self.solution.vehicle_solutions, colors)):
            y_pos = len(self.vehicle_states) - i - 1
            
            # Draw route segments
            prev_time = 0
            for node in vs_original.route:
                if node in vs_original.arrival_times:
                    arrival = vs_original.arrival_times[node]
                    departure = vs_original.departure_times[node]
                    
                    # Travel segment
                    if prev_time < arrival:
                        self.ax_timeline.barh(y_pos, arrival - prev_time, left=prev_time, 
                                            height=0.8, color='lightblue', 
                                            edgecolor='black', linewidth=0.5)
                    
                    # Station segment
                    if node in vs_original.charging_stations:
                        charging_start = vs_original.charging_start_times.get(node, arrival) if vs_original.charging_start_times else arrival
                        
                        # Queue time
                        if charging_start > arrival:
                            self.ax_timeline.barh(y_pos, charging_start - arrival, left=arrival,
                                                height=0.8, color='yellow',
                                                edgecolor='black', linewidth=0.5,
                                                label='Queue' if i == 0 and node == vs_original.charging_stations[0] else '')
                        
                        # Charging time
                        self.ax_timeline.barh(y_pos, departure - charging_start, left=charging_start,
                                            height=0.8, color='orange',
                                            edgecolor='black', linewidth=0.5,
                                            label='Charging' if i == 0 and node == vs_original.charging_stations[0] else '')
                    
                    prev_time = departure
            
            # Vehicle label
            self.ax_timeline.text(-2, y_pos, f'V{i+1}', ha='right', va='center', fontweight='bold')
        
        # Current time indicator
        self.ax_timeline.axvline(self.current_time, color='red', linewidth=2, linestyle='--', 
                                label='Current Time', zorder=100)
        
        self.ax_timeline.set_xlim(0, self.max_time * 1.05)
        self.ax_timeline.set_ylim(-0.5, len(self.vehicle_states) - 0.5)
        self.ax_timeline.set_xlabel('Time (minutes)', fontsize=10)
        self.ax_timeline.set_yticks([])
        self.ax_timeline.grid(True, alpha=0.3, axis='x')
        self.ax_timeline.legend(loc='upper right', fontsize=8)
    
    def run(self):
        """Start the simulation."""
        self.anim = FuncAnimation(self.fig, self._update_frame, 
                                 interval=100,  # Update every 100ms
                                 blit=False,
                                 cache_frame_data=False)
        # Don't use tight_layout - conflicts with button axes
        plt.subplots_adjust(bottom=0.12, top=0.93)
        plt.show()


def simulate_solution(solution: FleetSolution, params: SingleForkParams):
    """
    Launch interactive simulation GUI for a solution.
    
    Args:
        solution: Complete fleet solution to simulate
        params: Problem parameters
        
    Usage:
        from simulation_gui import simulate_solution
        from example_objectives import create_sample_solution
        from params import make_toy_params
        
        solution = create_sample_solution()
        params = make_toy_params()
        simulate_solution(solution, params)
    """
    sim = EVFleetSimulation(solution, params)
    sim.run()


if __name__ == "__main__":
    print("Loading example solution...")
    from example_objectives import create_sample_solution
    from params import make_toy_params
    
    solution = create_sample_solution()
    params = make_toy_params()
    
    print("\n" + "=" * 70)
    print("LAUNCHING SIMULATION GUI")
    print("=" * 70)
    print("\n🚗 Animation will start AUTOMATICALLY")
    print("   You should see vehicles moving on the network!")
    print("\nControls:")
    print("  - Click 'Play/Pause' to start/stop animation")
    print("  - Adjust 'Speed' slider to change playback speed (0.1x to 5x)")
    print("  - Click 'Reset' to restart from beginning")
    print("\nWhat to watch:")
    print("  - Colored circles = vehicles moving through network")
    print("  - Queue status shows vehicles waiting at stations")
    print("  - Timeline shows charging progress with orange bars")
    print("  - Metrics show real-time statistics")
    print("\nClose the window to exit.")
    print("=" * 70 + "\n")
    print("Simulation starting...")
    
    simulate_solution(solution, params)
