"""
objectives.py - Objective Functions for EV Fleet Routing Optimization

OVERALL OBJECTIVE:
Define objective functions and evaluation tools for assessing the quality of
routing and charging solutions for an electric vehicle fleet.

MODULE CONTENTS:
1. Data Structures:
   - VehicleSolution: Represents one vehicle's complete journey
   - FleetSolution: Represents entire fleet's solution

2. Primary Objectives:
   - objective_makespan(): Minimize time for last vehicle to finish
   - objective_total_cost(): Minimize total charging costs

3. Combined Objectives:
   - objective_weighted(): Combine time and cost with weights
   - objective_normalized_weighted(): Normalized combination

4. Additional Metrics:
   - Total travel time, charging time, energy charged
   - Station utilization analysis

5. Evaluation Tools:
   - evaluate_solution(): Comprehensive solution analysis
   - print_solution_summary(): Human-readable reporting

USAGE EXAMPLE:
    from objectives import FleetSolution, objective_makespan, objective_total_cost
    
    # Evaluate a solution
    makespan = objective_makespan(solution)
    total_cost = objective_total_cost(solution)
    
    # Print comprehensive analysis
    print_solution_summary(solution)
"""
from __future__ import annotations
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from params import SingleForkParams


@dataclass
class VehicleSolution:
    """
    Complete solution for a single vehicle.

    Bundles all information about one vehicle's journey:
    - WHERE it goes (route)
    - HOW FAST it travels (speed_levels for each edge) ← NEW!
    - WHERE it charges (charging_stations)
    - HOW MUCH it charges (charging_amounts)
    - WHEN events happen (arrival/departure times)
    - Battery state (SOC at each node)

    Attributes:
        vehicle_id: Unique identifier (0-indexed)
        route: Ordered list of nodes visited ['A', 'J', 'S1', ..., 'B']
        charging_stations: Subset of route where charging occurs ['S1', 'S2']
        charging_amounts: Dict mapping station → kWh charged {'S1': 15.0}
        arrival_times: Dict mapping node → arrival time in minutes {'A': 0, 'B': 68}
        departure_times: Dict mapping node → departure time in minutes
        soc_at_nodes: Dict mapping node → SOC on arrival (0-1 fraction)
        charging_start_times: Dict mapping station → time when charging actually starts
                             (allows modeling queue waiting at stations)
        speed_levels: Dict mapping edge → speed level (1-5) ← NEW!
                     Example: {('A', 'J'): 3, ('J', 'S1'): 4}
                     If None or edge missing, defaults to level 3 (Normal)

    Speed Levels (NEW):
        1 = Very Slow (most efficient, slowest)
        2 = Slow (efficient, slow)
        3 = Normal (baseline - default if not specified)
        4 = Fast (less efficient, faster)
        5 = Very Fast (least efficient, fastest)

    Queue Behavior at Charging Stations:
        - arrival_time[station]: When vehicle arrives and joins queue
        - charging_start_time[station]: When vehicle gets a plug and starts charging
        - departure_time[station]: When charging completes and vehicle leaves

        Queue wait time = charging_start_time - arrival_time
        Actual charging time = departure_time - charging_start_time
        Total time at station = departure_time - arrival_time

    Note:
        If charging_start_times not provided, assumes charging starts immediately
        upon arrival (backward compatibility).
    """
    vehicle_id: int  # Unique identifier for this vehicle
    # Sequence of nodes: e.g., ['A', 'J', 'S1', 'S2', 'M', 'B']
    route: List[str]
    # Stations where charging occurs: e.g., ['S1', 'S2']
    charging_stations: List[str]
    # kWh charged at each station: {'S1': 15.0, 'S2': 10.0}
    charging_amounts: Dict[str, float]
    # Arrival time at each node (minutes from start)
    arrival_times: Dict[str, float]
    # Departure time from each node (minutes from start)
    departure_times: Dict[str, float]
    soc_at_nodes: Dict[str, float]  # SOC at each node arrival (fraction [0,1])
    # Optional: when charging actually starts (after queue wait)
    charging_start_times: Dict[str, float] = None
    # Optional: speed level for each edge (1-5, default 3)
    speed_levels: Dict[Tuple[str, str], int] = None

    def get_speed_level(self, edge: Tuple[str, str]) -> int:
        """
        Get the speed level chosen for a specific edge.

        Args:
            edge: Tuple of (source_node, destination_node)

        Returns:
            Speed level (1-5), defaults to 3 (Normal) if not specified
        """
        if self.speed_levels is None:
            return 3  # Default to Normal speed
        return self.speed_levels.get(edge, 3)

    def get_completion_time(self) -> float:
        """
        Get the time when this vehicle completes its journey.

        Returns:
            Arrival time at destination 'B' in minutes
            Returns infinity if 'B' not reached (infeasible solution)
        """
        return self.arrival_times.get('B', float('inf'))

    def get_total_charging_cost(self, params: SingleForkParams) -> float:
        """
        Calculate total charging cost for this vehicle.

        Sums cost across all charging events:
            Cost = Σ (energy_charged_at_station × price_at_station)

        Args:
            params: Problem parameters (needed for station prices)

        Returns:
            Total cost in EGP (Egyptian Pounds)

        Example:
            Charges 12 kWh at S1 (0.10 EGP/kWh) = 1.20 EGP
            Charges 8 kWh at S2 (0.25 EGP/kWh) = 2.00 EGP
            Total = 3.20 EGP
        """
        total_cost = 0.0
        # Sum cost for each charging event
        for station, kwh_charged in self.charging_amounts.items():
            price = params.price_at(station)  # Get price at this station
            total_cost += kwh_charged * price  # Cost = Energy × Price
        return total_cost

    def get_total_charging_time(self) -> float:
        """
        Calculate total time this vehicle spent ACTUALLY CHARGING (plugged in).

        If charging_start_times provided: uses (departure - charging_start) 
        Otherwise: uses (departure - arrival) for backward compatibility

        Returns:
            Total actual charging time in minutes (excludes queue waiting)

        Example with queue:
            At S1: arrives 27, starts charging 30, departs 42 
            → Queue wait: 3 min, Charging: 12 min
            This method returns: 12 min (actual charging only)
        """
        total_time = 0.0
        for node in self.charging_stations:
            if node in self.departure_times:
                if self.charging_start_times and node in self.charging_start_times:
                    # Use actual charging start time (excludes queue wait)
                    start_time = self.charging_start_times[node]
                else:
                    # Backward compatibility: assume charging starts at arrival
                    start_time = self.arrival_times.get(node, 0.0)

                charging_time = self.departure_times[node] - start_time
                total_time += charging_time
        return total_time

    def get_total_queue_time(self) -> float:
        """
        Calculate total time this vehicle spent waiting in queue at stations.

        Returns:
            Total queue waiting time in minutes
            Returns 0 if no charging_start_times provided (no queue modeled)

        Example:
            At S1: arrives 27, starts charging 30 → Queue wait: 3 min
            At S2: arrives 50, starts charging 50 → Queue wait: 0 min
            Total queue time = 3 min
        """
        if not self.charging_start_times:
            return 0.0

        total_wait = 0.0
        for node in self.charging_stations:
            if node in self.charging_start_times and node in self.arrival_times:
                wait_time = self.charging_start_times[node] - \
                    self.arrival_times[node]
                total_wait += max(0.0, wait_time)  # Ensure non-negative
        return total_wait

    def get_total_time_at_stations(self) -> float:
        """
        Calculate total time spent at charging stations (queue + charging).

        Returns:
            Total time at stations in minutes
        """
        total_time = 0.0
        for node in self.charging_stations:
            if node in self.arrival_times and node in self.departure_times:
                total_time += self.departure_times[node] - \
                    self.arrival_times[node]
        return total_time


@dataclass
class FleetSolution:
    """
    Complete solution for entire fleet.

    Bundles solutions for all vehicles plus reference to problem parameters.

    Attributes:
        vehicle_solutions: List of VehicleSolution objects (one per vehicle)
        params: Problem parameters (needed for evaluation)
    """
    vehicle_solutions: List[VehicleSolution]  # Solution for each vehicle
    params: SingleForkParams  # Problem parameters

    def is_feasible(self, verbose: bool = False) -> bool:
        """
        Comprehensive feasibility check with all constraints.

        Checks:
        1. Route feasibility (starts at A, ends at B, valid edges)
        2. SOC bounds (10% ≤ SOC ≤ 100%)
        3. Energy balance (consistent SOC trajectory)
        4. Time consistency (departure ≥ arrival)
        5. Charging limits (no overcharging)
        6. Station capacity constraints
        7. Non-negativity (charging amounts, times)

        Args:
            verbose: If True, print detailed error messages

        Returns:
            True if solution is feasible, False otherwise
        """
        # Check each vehicle individually
        for i, vs in enumerate(self.vehicle_solutions):
            # 1. Route feasibility
            if not self._check_route_feasibility(vs, verbose, i):
                return False

            # 2. SOC bounds
            if not self._check_soc_bounds(vs, verbose, i):
                return False

            # 3. Energy balance
            if not self._check_energy_balance(vs, verbose, i):
                return False

            # 4. Time consistency
            if not self._check_time_consistency(vs, verbose, i):
                return False

            # 5. Charging limits
            if not self._check_charging_limits(vs, verbose, i):
                return False

            # 6. Non-negativity
            if not self._check_non_negativity(vs, verbose, i):
                return False

            # 7. Speed level validity
            if not self._check_speed_levels(vs, verbose, i):
                return False

        # 8. Station capacity constraints (fleet-wide)
        if not self._check_station_capacity(verbose):
            return False

        return True

    def _check_route_feasibility(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
        """Check if route is valid (starts at A, ends at B, connected edges)."""
        # Must start at A
        if not vs.route or vs.route[0] != 'A':
            if verbose:
                print(
                    f"❌ Vehicle {vehicle_idx}: Route must start at 'A', got {vs.route[0] if vs.route else 'empty'}")
            return False

        # Must end at B
        if vs.route[-1] != 'B':
            if verbose:
                print(
                    f"❌ Vehicle {vehicle_idx}: Route must end at 'B', got {vs.route[-1]}")
            return False

        # Check consecutive nodes are connected
        for i in range(len(vs.route) - 1):
            edge = (vs.route[i], vs.route[i+1])
            if edge not in self.params.edges_time_min:
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: Invalid edge {edge} in route")
                return False

        return True

    def _check_soc_bounds(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
        """Check if all SOC values stay within [10%, 100%]."""
        min_soc = 0.10
        tolerance = 1e-6
        for node, soc in vs.soc_at_nodes.items():
            if soc < min_soc - tolerance or soc > 1.0 + tolerance:
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: SOC at node '{node}' = {soc:.3f} (must be in [0.10, 1.00])")
                return False
        return True

    def _check_energy_balance(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
        """Check if SOC changes are consistent with energy consumed and charged.

        Now accounts for speed level selection: different speeds consume different energy.
        """
        battery_kwh = self.params.battery_kwh[vs.vehicle_id]
        tolerance = 1e-4  # Allow small numerical errors

        for i in range(len(vs.route) - 1):
            current_node = vs.route[i]
            next_node = vs.route[i + 1]

            # Get current SOC
            soc_current = vs.soc_at_nodes.get(current_node, 0.0)

            # Add charging if current node is a charging station
            if current_node in vs.charging_stations:
                charged_kwh = vs.charging_amounts.get(current_node, 0.0)
                soc_after_charge = soc_current + (charged_kwh / battery_kwh)
            else:
                soc_after_charge = soc_current

            # Subtract energy consumed on edge (speed-dependent)
            edge = (current_node, next_node)
            speed_level = vs.get_speed_level(edge)
            energy_consumed = self.params.get_edge_energy(edge, speed_level)
            soc_expected = soc_after_charge - (energy_consumed / battery_kwh)

            # Check consistency
            soc_actual = vs.soc_at_nodes.get(next_node, 0.0)
            if abs(soc_expected - soc_actual) > tolerance:
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: Energy balance violated at edge {edge}")
                    print(
                        f"   Speed level: {speed_level}, Energy consumed: {energy_consumed:.3f} kWh")
                    print(
                        f"   Expected SOC at {next_node}: {soc_expected:.4f}, Actual: {soc_actual:.4f}")
                return False

        return True

    def _check_time_consistency(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
        """Check if departure time >= arrival time at all nodes."""
        for node in vs.route:
            arrival = vs.arrival_times.get(node, 0.0)
            departure = vs.departure_times.get(node, 0.0)

            if departure < arrival - 1e-6:  # Small tolerance for floating point
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: Time inconsistency at node '{node}'")
                    print(
                        f"   Arrival: {arrival:.2f}, Departure: {departure:.2f}")
                return False

        return True

    def _check_charging_limits(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
        """Check if charging doesn't exceed battery capacity."""
        battery_kwh = self.params.battery_kwh[vs.vehicle_id]
        tolerance = 1e-4

        for station in vs.charging_stations:
            soc_before = vs.soc_at_nodes.get(station, 0.0)
            energy_charged = vs.charging_amounts.get(station, 0.0)
            soc_after = soc_before + (energy_charged / battery_kwh)

            if soc_after > 1.0 + tolerance:
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: Overcharging at station '{station}'")
                    print(
                        f"   SOC before: {soc_before:.3f}, Charged: {energy_charged:.2f} kWh")
                    print(f"   SOC after: {soc_after:.3f} (exceeds 100%)")
                return False

        return True

    def _check_non_negativity(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
        """Check if charging amounts and times are non-negative."""
        # Check charging amounts
        for station, amount in vs.charging_amounts.items():
            if amount < 0:
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: Negative charging at '{station}': {amount} kWh")
                return False

        # Check times
        for node, time in vs.arrival_times.items():
            if time < 0:
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: Negative arrival time at '{node}': {time}")
                return False

        for node, time in vs.departure_times.items():
            if time < 0:
                if verbose:
                    print(
                        f"❌ Vehicle {vehicle_idx}: Negative departure time at '{node}': {time}")
                return False

        return True

    def _check_speed_levels(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
        """Check if all speed levels are valid (1-5) for all edges in route."""
        if vs.speed_levels is None:
            # No speed levels specified, defaults to 3 (Normal) - OK
            return True

        for i in range(len(vs.route) - 1):
            edge = (vs.route[i], vs.route[i+1])
            if edge in vs.speed_levels:
                speed = vs.speed_levels[edge]
                if speed not in [1, 2, 3, 4, 5]:
                    if verbose:
                        print(
                            f"❌ Vehicle {vehicle_idx}: Invalid speed level {speed} for edge {edge}")
                        print(f"   Speed level must be in [1, 2, 3, 4, 5]")
                    return False

        return True

    def _check_station_capacity(self, verbose: bool) -> bool:
        """
        Check if station capacity constraints are satisfied.

        Capacity is based on CONCURRENT CHARGING, not just presence at station.
        If charging_start_times provided, uses those to determine when vehicles
        actually occupy a plug. Otherwise, assumes charging starts at arrival.
        """
        all_stations = set(self.params.upper_stations +
                           self.params.lower_stations)

        for station in all_stations:
            # Collect all CHARGING events at this station (when plug is actually used)
            events = []
            for vs in self.vehicle_solutions:
                if station in vs.charging_stations:
                    # Determine when charging actually starts
                    if vs.charging_start_times and station in vs.charging_start_times:
                        # Use explicit charging start time (queue-aware)
                        charging_start = vs.charging_start_times[station]
                    else:
                        # Backward compatibility: assume charging starts at arrival
                        charging_start = vs.arrival_times.get(station, 0.0)

                    departure = vs.departure_times.get(station, 0.0)

                    # Track when plug is OCCUPIED (charging period only)
                    # +1 plug becomes occupied
                    events.append((charging_start, 1, vs.vehicle_id))
                    events.append((departure, -1, vs.vehicle_id)
                                  )        # -1 plug becomes free

            if not events:
                continue  # No vehicles use this station

            # Sort by time and check max concurrent usage
            # At same time, process departures (-1) before arrivals (+1) to free up plugs first
            # Sort by time, then by delta (departures first)
            events.sort(key=lambda x: (x[0], x[1]))
            current_usage = 0
            max_usage = 0
            max_usage_time = 0

            for time, delta, _ in events:
                current_usage += delta
                if current_usage > max_usage:
                    max_usage = current_usage
                    max_usage_time = time

            # Check against capacity
            capacity = self.params.station_plugs.get(station, 0)
            if max_usage > capacity:
                if verbose:
                    print(f"❌ Station capacity violated at '{station}'")
                    print(
                        f"   Max concurrent CHARGING vehicles: {max_usage}, Available plugs: {capacity}")
                    print(
                        f"   Violation occurred at time: {max_usage_time:.2f} minutes")
                return False

        return True

    def get_vehicle_count(self) -> int:
        """Return number of vehicles in the fleet."""
        return len(self.vehicle_solutions)


# ========================================
# OBJECTIVE 1: Minimize Total Charging Cost
# ========================================

def objective_total_cost(solution: FleetSolution) -> float:
    """
    Calculate the total charging cost across all vehicles.

    Objective: Minimize the sum of all charging costs.

    Args:
        solution: Complete fleet solution

    Returns:
        Total cost in EGP (Egyptian Pounds)
    """
    total_cost = 0.0
    for vehicle_sol in solution.vehicle_solutions:
        total_cost += vehicle_sol.get_total_charging_cost(solution.params)
    return total_cost


def objective_cost_detailed(solution: FleetSolution) -> Dict[str, float]:
    """
    Calculate detailed cost breakdown by vehicle and by station.

    Returns:
        Dictionary with cost breakdown:
        - 'total': total cost
        - 'by_vehicle': list of costs per vehicle
        - 'by_station': dictionary of total cost per station
    """
    by_vehicle = []
    by_station = {}

    for vehicle_sol in solution.vehicle_solutions:
        vehicle_cost = vehicle_sol.get_total_charging_cost(solution.params)
        by_vehicle.append(vehicle_cost)

        # Accumulate by station
        for station, kwh in vehicle_sol.charging_amounts.items():
            price = solution.params.price_at(station)
            cost = kwh * price
            by_station[station] = by_station.get(station, 0.0) + cost

    return {
        'total': sum(by_vehicle),
        'by_vehicle': by_vehicle,
        'by_station': by_station
    }


# ========================================
# OBJECTIVE 2: Minimize Makespan
# ========================================

def objective_makespan(solution: FleetSolution) -> float:
    """
    Calculate the makespan: time when the last vehicle completes its journey.

    Objective: Minimize the maximum completion time across all vehicles.

    Args:
        solution: Complete fleet solution

    Returns:
        Makespan in minutes (time when last vehicle reaches destination 'B')
    """
    if not solution.vehicle_solutions:
        return 0.0

    completion_times = [vs.get_completion_time()
                        for vs in solution.vehicle_solutions]
    return max(completion_times)


def objective_makespan_detailed(solution: FleetSolution) -> Dict[str, float]:
    """
    Calculate detailed makespan information.

    Returns:
        Dictionary with:
        - 'makespan': maximum completion time
        - 'completion_times': list of completion times per vehicle
        - 'bottleneck_vehicle': ID of vehicle that determines makespan
        - 'average_completion': average completion time
    """
    completion_times = [vs.get_completion_time()
                        for vs in solution.vehicle_solutions]
    makespan = max(completion_times) if completion_times else 0.0
    bottleneck_idx = completion_times.index(
        makespan) if completion_times else -1

    return {
        'makespan': makespan,
        'completion_times': completion_times,
        'bottleneck_vehicle': bottleneck_idx,
        'average_completion': np.mean(completion_times) if completion_times else 0.0
    }


# ========================================
# COMBINED OBJECTIVES
# ========================================

def objective_weighted(
    solution: FleetSolution,
    w_time: Optional[float] = None,
    w_cost: Optional[float] = None
) -> float:
    """
    Calculate weighted combination of makespan and cost objectives.

    Objective = w_time * makespan + w_cost * total_cost

    Args:
        solution: Complete fleet solution
        w_time: Weight for time objective (uses params.w_time if None)
        w_cost: Weight for cost objective (uses params.w_cost if None)

    Returns:
        Weighted objective value
    """
    w_t = w_time if w_time is not None else solution.params.w_time
    w_c = w_cost if w_cost is not None else solution.params.w_cost

    makespan = objective_makespan(solution)
    total_cost = objective_total_cost(solution)

    return w_t * makespan + w_c * total_cost


def objective_normalized_weighted(
    solution: FleetSolution,
    baseline_makespan: float,
    baseline_cost: float,
    w_time: Optional[float] = None,
    w_cost: Optional[float] = None
) -> float:
    """
    Calculate normalized weighted objective (useful when time and cost are on different scales).

    Objective = w_time * (makespan/baseline_makespan) + w_cost * (cost/baseline_cost)

    Args:
        solution: Complete fleet solution
        baseline_makespan: Reference makespan for normalization
        baseline_cost: Reference cost for normalization
        w_time: Weight for time objective
        w_cost: Weight for cost objective

    Returns:
        Normalized weighted objective value
    """
    w_t = w_time if w_time is not None else solution.params.w_time
    w_c = w_cost if w_cost is not None else solution.params.w_cost

    makespan = objective_makespan(solution)
    total_cost = objective_total_cost(solution)

    norm_time = makespan / max(1e-9, baseline_makespan)
    norm_cost = total_cost / max(1e-9, baseline_cost)

    return w_t * norm_time + w_c * norm_cost


# ========================================
# ADDITIONAL METRICS
# ========================================

def metric_total_travel_time(solution: FleetSolution) -> float:
    """
    Calculate sum of all vehicles' completion times (not makespan).
    """
    return sum(vs.get_completion_time() for vs in solution.vehicle_solutions)


def metric_total_charging_time(solution: FleetSolution) -> float:
    """
    Calculate total time spent charging across all vehicles.
    """
    return sum(vs.get_total_charging_time() for vs in solution.vehicle_solutions)


def metric_total_energy_charged(solution: FleetSolution) -> float:
    """
    Calculate total energy charged across all vehicles (kWh).
    """
    total_energy = 0.0
    for vs in solution.vehicle_solutions:
        for kwh in vs.charging_amounts.values():
            total_energy += kwh
    return total_energy


def metric_station_utilization(solution: FleetSolution) -> Dict[str, int]:
    """
    Count how many vehicles used each station.
    """
    utilization = {}
    for vs in solution.vehicle_solutions:
        for station in vs.charging_stations:
            utilization[station] = utilization.get(station, 0) + 1
    return utilization


# ========================================
# EVALUATION SUMMARY
# ========================================

def evaluate_solution(solution: FleetSolution, verbose: bool = False) -> Dict:
    """
    Comprehensive evaluation of a fleet solution.

    Args:
        solution: Complete fleet solution
        verbose: If True, include detailed breakdowns

    Returns:
        Dictionary with all metrics and objective values
    """
    results = {
        'feasible': solution.is_feasible(),
        'num_vehicles': solution.get_vehicle_count(),

        # Primary objectives
        'makespan': objective_makespan(solution),
        'total_cost': objective_total_cost(solution),
        'weighted_objective': objective_weighted(solution),

        # Additional metrics
        'total_travel_time': metric_total_travel_time(solution),
        'total_charging_time': metric_total_charging_time(solution),
        'total_energy_charged': metric_total_energy_charged(solution),
        'station_utilization': metric_station_utilization(solution),
    }

    if verbose:
        results['makespan_details'] = objective_makespan_detailed(solution)
        results['cost_details'] = objective_cost_detailed(solution)
        results['vehicle_summaries'] = [
            {
                'vehicle_id': vs.vehicle_id,
                'route': vs.route,
                'completion_time': vs.get_completion_time(),
                'charging_cost': vs.get_total_charging_cost(solution.params),
                'charging_time': vs.get_total_charging_time(),
                'stations_used': vs.charging_stations,
            }
            for vs in solution.vehicle_solutions
        ]

    return results


def print_solution_summary(solution: FleetSolution) -> None:
    """
    Print a human-readable summary of the solution evaluation.
    """
    results = evaluate_solution(solution, verbose=True)

    print("=" * 70)
    print("FLEET SOLUTION EVALUATION")
    print("=" * 70)
    print(
        f"\nFeasibility: {'✓ FEASIBLE' if results['feasible'] else '✗ INFEASIBLE'}")
    print(f"Number of vehicles: {results['num_vehicles']}")

    print("\n" + "-" * 70)
    print("PRIMARY OBJECTIVES")
    print("-" * 70)
    print(
        f"  Makespan (last vehicle completion):  {results['makespan']:.2f} minutes")
    print(
        f"  Total charging cost:                 {results['total_cost']:.2f} EGP")
    print(
        f"  Weighted objective:                  {results['weighted_objective']:.2f}")

    print("\n" + "-" * 70)
    print("ADDITIONAL METRICS")
    print("-" * 70)
    print(
        f"  Total travel time (sum):             {results['total_travel_time']:.2f} minutes")
    print(
        f"  Total charging time:                 {results['total_charging_time']:.2f} minutes")
    print(
        f"  Total energy charged:                {results['total_energy_charged']:.2f} kWh")

    print("\n" + "-" * 70)
    print("STATION UTILIZATION")
    print("-" * 70)
    for station, count in sorted(results['station_utilization'].items()):
        print(f"  {station}: {count} vehicle(s)")

    print("\n" + "-" * 70)
    print("COST BREAKDOWN")
    print("-" * 70)
    cost_details = results['cost_details']
    for i, cost in enumerate(cost_details['by_vehicle']):
        print(f"  Vehicle {i+1}: {cost:.2f} EGP")
    print(f"  {'Total:':<12} {cost_details['total']:.2f} EGP")

    print("\n" + "-" * 70)
    print("VEHICLE COMPLETION TIMES")
    print("-" * 70)
    makespan_details = results['makespan_details']
    for i, time in enumerate(makespan_details['completion_times']):
        marker = " ← BOTTLENECK" if i == makespan_details['bottleneck_vehicle'] else ""
        print(f"  Vehicle {i+1}: {time:.2f} minutes{marker}")
    print(
        f"  {'Average:':<12} {makespan_details['average_completion']:.2f} minutes")

    print("\n" + "=" * 70)


# ========================================
# QUEUE PROCESSING HELPER
# ========================================

def process_station_queues(solution: FleetSolution, params: SingleForkParams) -> FleetSolution:
    """
    Process queuing at charging stations and compute charging_start_times.

    Takes a solution where vehicles have arrival_times and charging_amounts,
    and computes when each vehicle actually starts charging based on:
    - FIFO (First-In-First-Out) queue discipline
    - Station capacity (number of available plugs)
    - Charging duration for each vehicle

    This function:
    1. Sorts vehicles by arrival time at each station
    2. Assigns charging start times based on plug availability
    3. Updates charging_start_times for each vehicle
    4. Recalculates departure_times to include queue waiting

    Args:
        solution: FleetSolution with arrival_times and charging_amounts
        params: Problem parameters (needed for charging time calculation)

    Returns:
        Updated FleetSolution with charging_start_times populated

    Example:
        Station S1 has 1 plug:
        - Vehicle 1 arrives at t=20, needs 10 min charging
          → Starts at t=20, finishes at t=30
        - Vehicle 2 arrives at t=25, needs 15 min charging
          → Waits until t=30, starts at t=30, finishes at t=45

    Note:
        Modifies the solution in place and returns it.
    """
    # Process each station
    all_stations = set(params.upper_stations + params.lower_stations)

    for station in all_stations:
        # Collect vehicles charging at this station
        vehicles_at_station = []
        for vs in solution.vehicle_solutions:
            if station in vs.charging_stations:
                arrival = vs.arrival_times.get(station, 0.0)
                vehicles_at_station.append((arrival, vs))

        if not vehicles_at_station:
            continue  # No vehicles at this station

        # Sort by arrival time (FIFO)
        vehicles_at_station.sort(key=lambda x: x[0])

        # Track when each plug becomes available
        station_capacity = params.station_plugs.get(station, 1)
        # When each plug becomes free
        plug_available_times = [0.0] * station_capacity

        # Assign charging start times
        for arrival_time, vs in vehicles_at_station:
            # Find earliest available plug
            earliest_plug_idx = min(
                range(station_capacity), key=lambda i: plug_available_times[i])
            earliest_available = plug_available_times[earliest_plug_idx]

            # Vehicle can start charging when: max(arrival_time, plug_available_time)
            charging_start = max(arrival_time, earliest_available)

            # Calculate charging duration
            battery_kwh = params.battery_kwh[vs.vehicle_id]
            soc_before = vs.soc_at_nodes.get(station, 0.5)
            energy_charged = vs.charging_amounts.get(station, 0.0)
            soc_after = soc_before + (energy_charged / battery_kwh)

            # Get charging time from params
            charging_duration_sec = params.charge_time_seconds(
                soc_before, soc_after, battery_kwh, station
            )
            charging_duration_min = charging_duration_sec / 60.0

            # Update vehicle's charging_start_times
            if vs.charging_start_times is None:
                vs.charging_start_times = {}
            vs.charging_start_times[station] = charging_start

            # Update departure time to include queue wait + charging
            vs.departure_times[station] = charging_start + \
                charging_duration_min

            # Mark plug as busy until this vehicle finishes
            plug_available_times[earliest_plug_idx] = charging_start + \
                charging_duration_min

    return solution
