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
        
    Note:
        At charging stations, departure_time > arrival_time (charging takes time)
        At non-charging nodes, departure_time ≈ arrival_time (no delay)
    """
    vehicle_id: int  # Unique identifier for this vehicle
    route: List[str]  # Sequence of nodes: e.g., ['A', 'J', 'S1', 'S2', 'M', 'B']
    charging_stations: List[str]  # Stations where charging occurs: e.g., ['S1', 'S2']
    charging_amounts: Dict[str, float]  # kWh charged at each station: {'S1': 15.0, 'S2': 10.0}
    arrival_times: Dict[str, float]  # Arrival time at each node (minutes from start)
    departure_times: Dict[str, float]  # Departure time from each node (minutes from start)
    soc_at_nodes: Dict[str, float]  # SOC at each node arrival (fraction [0,1])
    
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
        Calculate total time this vehicle spent charging.
        
        Sums (departure_time - arrival_time) for all charging stations.
        This is the time vehicle was plugged in, not traveling.
        
        Returns:
            Total charging time in minutes
            
        Example:
            At S1: arrives 27 min, departs 42 min → 15 min charging
            At S2: arrives 35 min, departs 48 min → 13 min charging
            Total charging time = 28 min
        """
        total_time = 0.0
        # Sum charging time at each station
        for node in self.charging_stations:
            if node in self.arrival_times and node in self.departure_times:
                # Charging time = departure - arrival
                total_time += self.departure_times[node] - self.arrival_times[node]
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
    
    def is_feasible(self) -> bool:
        """
        Check if solution is feasible.
        
        A solution is feasible if:
        1. All vehicles reach destination 'B'
        2. All SOC values are valid (between 0 and 1)
        
        Returns:
            True if solution is feasible, False otherwise
            
        Note:
            This does NOT check capacity constraints or timing conflicts.
            Those should be checked separately if needed.
        """
        for vs in self.vehicle_solutions:
            # Check if route ends at 'B'
            if vs.route[-1] != 'B':
                return False
            # Check if all SOC values are valid
            if not all(0.0 <= soc <= 1.0 for soc in vs.soc_at_nodes.values()):
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
    
    completion_times = [vs.get_completion_time() for vs in solution.vehicle_solutions]
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
    completion_times = [vs.get_completion_time() for vs in solution.vehicle_solutions]
    makespan = max(completion_times) if completion_times else 0.0
    bottleneck_idx = completion_times.index(makespan) if completion_times else -1
    
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
    print(f"\nFeasibility: {'✓ FEASIBLE' if results['feasible'] else '✗ INFEASIBLE'}")
    print(f"Number of vehicles: {results['num_vehicles']}")
    
    print("\n" + "-" * 70)
    print("PRIMARY OBJECTIVES")
    print("-" * 70)
    print(f"  Makespan (last vehicle completion):  {results['makespan']:.2f} minutes")
    print(f"  Total charging cost:                 {results['total_cost']:.2f} EGP")
    print(f"  Weighted objective:                  {results['weighted_objective']:.2f}")
    
    print("\n" + "-" * 70)
    print("ADDITIONAL METRICS")
    print("-" * 70)
    print(f"  Total travel time (sum):             {results['total_travel_time']:.2f} minutes")
    print(f"  Total charging time:                 {results['total_charging_time']:.2f} minutes")
    print(f"  Total energy charged:                {results['total_energy_charged']:.2f} kWh")
    
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
    print(f"  {'Average:':<12} {makespan_details['average_completion']:.2f} minutes")
    
    print("\n" + "=" * 70)
