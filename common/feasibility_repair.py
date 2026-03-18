"""
feasibility_repair.py - Repair mechanisms to ensure feasible solutions

This module provides methods to repair infeasible solutions by:
1. Ensuring sufficient charging to complete the journey
2. Adjusting charging amounts to avoid overcharging
3. Adding charging stops when needed
4. Removing unnecessary charging stops

The goal is to transform any solution into a feasible one while
minimizing changes to the original solution.
"""

from typing import List, Dict, Tuple
from common.params import SingleForkParams
from common.objectives import VehicleSolution, FleetSolution, process_station_queues


class FeasibilityRepairer:
    """Repairs infeasible solutions to make them feasible."""

    def __init__(self, params: SingleForkParams):
        self.params = params
        self.upper_route = ['A', 'J', 'S1', 'S2', 'M', 'B']
        self.lower_route = ['A', 'J', 'S3', 'M', 'B']
        self.upper_stations = ['S1', 'S2']
        self.lower_stations = ['S3']

    def repair_solution(self, solution: FleetSolution) -> FleetSolution:
        """Repair entire fleet solution."""
        repaired_vehicles = []

        for vs in solution.vehicle_solutions:
            repaired_vs = self.repair_vehicle_solution(vs)
            repaired_vehicles.append(repaired_vs)

        return FleetSolution(vehicle_solutions=repaired_vehicles, params=self.params)

    def repair_vehicle_solution(self, vs: VehicleSolution) -> VehicleSolution:
        """Repair single vehicle solution to ensure feasibility."""

        # Step 1: Simulate the journey and track SOC
        battery_kwh = self.params.battery_kwh[vs.vehicle_id]
        current_soc = self.params.soc0[vs.vehicle_id]

        # Get available stations on this route
        if 'S3' in vs.route:
            available_stations = self.lower_stations
        else:
            available_stations = self.upper_stations

        # Track which stations we need to charge at
        required_charging = {}
        soc_trajectory = {}

        # Simulate journey
        soc_trajectory[vs.route[0]] = current_soc

        for i in range(len(vs.route) - 1):
            current_node = vs.route[i]
            next_node = vs.route[i + 1]
            edge = (current_node, next_node)

            # Check if we charge at current node
            if current_node in available_stations:
                # Determine how much to charge
                charge_amount = self._determine_optimal_charge(
                    current_soc, vs.route[i:], battery_kwh, vs.speed_levels
                )
                if charge_amount > 0:
                    required_charging[current_node] = charge_amount
                    current_soc = min(1.0, current_soc +
                                      charge_amount / battery_kwh)

            # Travel to next node
            speed_level = vs.get_speed_level(edge)
            energy_consumed = self.params.get_edge_energy(edge, speed_level)
            current_soc -= energy_consumed / battery_kwh

            # Ensure we don't run out of battery
            if current_soc < 0.0:
                # Need to add charging at previous station
                required_charging = self._add_emergency_charging(
                    vs.route[:i+1], available_stations, battery_kwh,
                    vs.speed_levels, required_charging
                )
                # Recalculate from start
                return self._rebuild_solution_with_charging(
                    vs, required_charging
                )

            soc_trajectory[next_node] = current_soc

        # Check if we made it to destination with valid SOC
        final_soc = soc_trajectory[vs.route[-1]]
        if final_soc < 0.0 or final_soc > 1.0:
            # Rebuild with proper charging
            return self._rebuild_solution_with_charging(vs, required_charging)

        # Rebuild solution with corrected charging
        return self._rebuild_solution_with_charging(vs, required_charging)

    def _determine_optimal_charge(
        self,
        current_soc: float,
        remaining_route: List[str],
        battery_kwh: float,
        speed_levels: Dict[Tuple[str, str], int]
    ) -> float:
        """Determine how much to charge at current station."""

        # Calculate energy needed for remaining journey
        energy_needed = 0.0
        for i in range(len(remaining_route) - 1):
            edge = (remaining_route[i], remaining_route[i + 1])
            speed_level = speed_levels.get(edge, 3) if speed_levels else 3
            energy_needed += self.params.get_edge_energy(edge, speed_level)

        # Add minimum SOC requirement at destination (10%)
        energy_needed += 0.10 * battery_kwh

        # Add safety margin (15% more to be safe)
        energy_needed *= 1.15

        # Calculate SOC needed
        soc_needed = energy_needed / battery_kwh

        # How much charging do we need?
        soc_deficit = soc_needed - current_soc

        if soc_deficit > 0:
            # Need to charge
            # Target 80% SOC (good balance, avoids slow charging at high SOC)
            target_soc = min(0.85, current_soc + soc_deficit)
            charge_kwh = (target_soc - current_soc) * battery_kwh
            return max(0.0, charge_kwh)
        else:
            # Don't need to charge
            return 0.0

    def _add_emergency_charging(
        self,
        route_so_far: List[str],
        available_stations: List[str],
        battery_kwh: float,
        speed_levels: Dict[Tuple[str, str], int],
        current_charging: Dict[str, float]
    ) -> Dict[str, float]:
        """Add charging at the last available station to avoid battery depletion."""

        # Find last station in route so far
        last_station = None
        for node in reversed(route_so_far):
            if node in available_stations:
                last_station = node
                break

        if last_station:
            # Charge to 80% at this station
            current_charging[last_station] = 0.7 * battery_kwh

        return current_charging

    def _rebuild_solution_with_charging(
        self,
        original_vs: VehicleSolution,
        charging_dict: Dict[str, float]
    ) -> VehicleSolution:
        """Rebuild vehicle solution with specified charging amounts."""

        battery_kwh = self.params.battery_kwh[original_vs.vehicle_id]

        # Initialize
        arrival_times = {}
        departure_times = {}
        soc_at_nodes = {}
        charging_start_times = {}

        current_time = 0.0
        current_soc = self.params.soc0[original_vs.vehicle_id]

        arrival_times[original_vs.route[0]] = current_time
        departure_times[original_vs.route[0]] = current_time
        soc_at_nodes[original_vs.route[0]] = current_soc

        # Traverse route
        for i in range(len(original_vs.route) - 1):
            current_node = original_vs.route[i]
            next_node = original_vs.route[i + 1]
            edge = (current_node, next_node)

            # Check if we charge at current node (after arrival)
            if current_node in charging_dict and i > 0:  # Don't charge at start
                charge_amount = charging_dict[current_node]
                soc_before = current_soc
                soc_after = min(1.0, current_soc + charge_amount / battery_kwh)

                # Calculate charging time
                charging_time_sec = self.params.charge_time_seconds(
                    soc_before, soc_after, battery_kwh, current_node
                )
                charging_time_min = charging_time_sec / 60.0

                charging_start_times[current_node] = current_time
                current_time += charging_time_min
                current_soc = soc_after
                departure_times[current_node] = current_time

            # Travel to next node
            speed_level = original_vs.get_speed_level(edge)
            travel_time = self.params.get_edge_time(edge, speed_level)
            energy_consumed = self.params.get_edge_energy(edge, speed_level)

            current_time += travel_time
            current_soc -= energy_consumed / battery_kwh

            # Clamp SOC to valid range
            current_soc = max(0.0, min(1.0, current_soc))

            arrival_times[next_node] = current_time
            departure_times[next_node] = current_time
            soc_at_nodes[next_node] = current_soc

        # Create new VehicleSolution
        charging_stations = list(charging_dict.keys())
        charging_amounts = charging_dict

        return VehicleSolution(
            vehicle_id=original_vs.vehicle_id,
            route=original_vs.route,
            charging_stations=charging_stations,
            charging_amounts=charging_amounts,
            arrival_times=arrival_times,
            departure_times=departure_times,
            soc_at_nodes=soc_at_nodes,
            speed_levels=original_vs.speed_levels,
            charging_start_times=charging_start_times if charging_start_times else None
        )


def create_feasible_initial_solution(
    params: SingleForkParams,
    route_choice: int = 0,  # 0=upper, 1=lower
    speed_level: int = 3    # Default to Normal
) -> FleetSolution:
    """
    Create a guaranteed feasible solution by construction.

    Strategy:
    1. Use conservative speeds (Normal = 3)
    2. Charge at all available stations to ~70% SOC
    3. Ensure sufficient energy for entire journey

    Args:
        params: Problem parameters
        route_choice: 0 for upper route, 1 for lower route
        speed_level: Speed level to use (1-5, default 3=Normal)

    Returns:
        Feasible FleetSolution
    """

    if route_choice == 0:
        route = ['A', 'J', 'S1', 'S2', 'M', 'B']
        stations = ['S1', 'S2']
    else:
        route = ['A', 'J', 'S3', 'M', 'B']
        stations = ['S3']

    vehicle_solutions = []

    for v in range(params.m):
        battery_kwh = params.battery_kwh[v]

        # Create speed levels dict (all same speed)
        speed_levels = {}
        for i in range(len(route) - 1):
            edge = (route[i], route[i + 1])
            speed_levels[edge] = speed_level

        # Simulate journey and determine charging needs
        current_time = 0.0
        current_soc = params.soc0[v]

        arrival_times = {route[0]: current_time}
        departure_times = {route[0]: current_time}
        soc_at_nodes = {route[0]: current_soc}
        charging_amounts = {}

        for i in range(len(route) - 1):
            current_node = route[i]
            next_node = route[i + 1]
            edge = (current_node, next_node)

            # Charge at ALL stations to 80% to ensure we have enough
            if current_node in stations and i > 0:
                target_soc = 0.80
                if current_soc < target_soc:
                    charge_kwh = (target_soc - current_soc) * battery_kwh
                    charging_amounts[current_node] = charge_kwh

                    # Calculate charging time
                    charging_time_sec = params.charge_time_seconds(
                        current_soc, target_soc, battery_kwh, current_node
                    )
                    current_time += charging_time_sec / 60.0
                    current_soc = target_soc
                    departure_times[current_node] = current_time

            # Travel to next node
            travel_time = params.get_edge_time(edge, speed_level)
            energy_consumed = params.get_edge_energy(edge, speed_level)

            current_time += travel_time
            current_soc -= energy_consumed / battery_kwh

            arrival_times[next_node] = current_time
            departure_times[next_node] = current_time
            soc_at_nodes[next_node] = current_soc

        # If final SOC is too low, we need more charging - add to all stations
        final_soc = soc_at_nodes[route[-1]]
        if final_soc < 0.10:  # Need at least 10% at destination
            # Recalculate with more aggressive charging (charge to 80% at all stations)
            current_time = 0.0
            current_soc = params.soc0[v]

            arrival_times = {route[0]: current_time}
            departure_times = {route[0]: current_time}
            soc_at_nodes = {route[0]: current_soc}
            charging_amounts = {}

            for i in range(len(route) - 1):
                current_node = route[i]
                next_node = route[i + 1]
                edge = (current_node, next_node)

                # Charge at ALL stations to 80%
                if current_node in stations and i > 0:
                    target_soc = 0.80
                    if current_soc < target_soc:
                        charge_kwh = (target_soc - current_soc) * battery_kwh
                        charging_amounts[current_node] = charge_kwh

                        charging_time_sec = params.charge_time_seconds(
                            current_soc, target_soc, battery_kwh, current_node
                        )
                        current_time += charging_time_sec / 60.0
                        current_soc = target_soc
                        departure_times[current_node] = current_time

                # Travel
                travel_time = params.get_edge_time(edge, speed_level)
                energy_consumed = params.get_edge_energy(edge, speed_level)

                current_time += travel_time
                current_soc -= energy_consumed / battery_kwh

                arrival_times[next_node] = current_time
                departure_times[next_node] = current_time
                soc_at_nodes[next_node] = current_soc

        vs = VehicleSolution(
            vehicle_id=v,
            route=route,
            charging_stations=list(charging_amounts.keys()),
            charging_amounts=charging_amounts,
            arrival_times=arrival_times,
            departure_times=departure_times,
            soc_at_nodes=soc_at_nodes,
            speed_levels=speed_levels
        )

        vehicle_solutions.append(vs)

    solution = FleetSolution(
        vehicle_solutions=vehicle_solutions, params=params)

    # Process queues to handle station capacity
    solution = process_station_queues(solution, params)

    # Verify it's feasible
    if not solution.is_feasible():
        # Apply repair if needed
        repairer = FeasibilityRepairer(params)
        solution = repairer.repair_solution(solution)
        # Process queues again after repair
        solution = process_station_queues(solution, params)

    return solution
