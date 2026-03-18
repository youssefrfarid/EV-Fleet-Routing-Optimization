"""
Simple double-fork compatible repair for RL solutions.
This ensures RL produces feasible solutions by adding sufficient charging.
"""

from common.params import DoubleForkParams
from common.objectives import FleetSolution, VehicleSolution, process_station_queues


def repair_rl_solution(solution: FleetSolution, params: DoubleForkParams) -> FleetSolution:
    """
    Repair RL solution for double-fork topology.
    Strategy: Ensure sufficient charging at all stations to complete journey.
    """
    repaired_vehicles = []
    
    for vs in solution.vehicle_solutions:
        battery_kwh = params.battery_kwh[vs.vehicle_id]
        route = vs.route
        
        # Identify stations in route
        stations = [node for node in route if node in params.station_plugs]
        
        # Simulate journey and add charging as needed
        current_soc = params.soc0[vs.vehicle_id]
        current_time = 0.0
        
        arrival_times = {route[0]: 0.0}
        departure_times = {route[0]: 0.0}
        soc_at_nodes = {route[0]: current_soc}
        charging_amounts = {}
        speed_levels = dict(vs.speed_levels)  # Keep original speeds
        
        for i in range(len(route) - 1):
            current_node = route[i]
            next_node = route[i + 1]
            edge = (current_node, next_node)
            
            # Charge at station if needed
            if current_node in stations and i > 0:
                # Calculate energy needed for rest of journey
                remaining_energy = 0.0
                for j in range(i, len(route) - 1):
                    e = (route[j], route[j + 1])
                    speed = speed_levels.get(e, 80.0)
                    if e in params.edges_distance_km:
                        remaining_energy += params.get_edge_energy(e, speed)
                
                # Add 25% safety margin
                remaining_energy *= 1.25
                
                # Target SOC to have enough energy + end with 15%
                target_soc = min(0.85, (remaining_energy + 0.15 * battery_kwh) / battery_kwh)
                
                if target_soc > current_soc:
                    charge_kwh = (target_soc - current_soc) * battery_kwh
                    charging_amounts[current_node] = charge_kwh
                    
                    # Calculate charging time (simplified)
                    max_power = params.station_max_kw.get(current_node, 50.0)
                    charge_time = (charge_kwh / min(max_power, 80.0)) * 60.0
                    current_time += charge_time
                    current_soc = target_soc
                    
                departure_times[current_node] = current_time
            
            # Travel to next node
            if edge in params.edges_distance_km:
                speed = speed_levels.get(edge, 80.0)
                travel_time = params.get_edge_time(edge, speed)
                energy = params.get_edge_energy(edge, speed)
                
                current_time += travel_time
                current_soc -= energy / battery_kwh
                current_soc = max(0.05, current_soc)  # Ensure minimum 5% SOC
                
                arrival_times[next_node] = current_time
                departure_times[next_node] = current_time
                soc_at_nodes[next_node] = current_soc
        
        # Create repaired vehicle solution
        repaired_vs = VehicleSolution(
            vehicle_id=vs.vehicle_id,
            route=route,
            charging_amounts=charging_amounts,
            speed_levels=speed_levels,
            arrival_times=arrival_times,
            departure_times=departure_times,
            soc_at_nodes=soc_at_nodes,
            charging_stations=list(charging_amounts.keys())
        )
        repaired_vehicles.append(repaired_vs)
    
    # Create fleet solution
    repaired_solution = FleetSolution(vehicle_solutions=repaired_vehicles, params=params)
    
    # CRITICAL: Process queues to handle station capacity constraints
    repaired_solution = process_station_queues(repaired_solution, params)
    
    return repaired_solution
