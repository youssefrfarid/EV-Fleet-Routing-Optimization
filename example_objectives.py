"""
example_objectives.py
Demonstrates how to use the objective functions with a sample solution.

Shows:
1. Manual solution creation with queue modeling
2. Queue analysis and waiting times
3. Constraint verification
4. Objective evaluation
5. Queue processing helper function usage
"""
from params import make_toy_params
from objectives import (
    VehicleSolution, FleetSolution,
    objective_makespan, objective_total_cost, objective_weighted,
    evaluate_solution, print_solution_summary,
    process_station_queues  # NEW: Queue processing helper
)


def create_sample_solution():
    """
    Create a sample solution for demonstration purposes.
    This represents a feasible routing where:
    - Vehicles 1-3 take upper route (S1 -> S2)
    - Vehicles 4-5 take lower route (S3)
    """
    params = make_toy_params()

    vehicle_plans = [
        {
            "vehicle_id": 0,
            "route": ['A', 'J', 'S1', 'S2', 'M', 'B'],
            "charging_amounts": {'S1': 18.0, 'S2': 12.0},
            "speed_levels": {
                ('A', 'J'): 2,
                ('J', 'S1'): 2,
                ('S1', 'S2'): 3,
                ('S2', 'M'): 4,
                ('M', 'B'): 3,
            },
        },
        {
            "vehicle_id": 1,
            "route": ['A', 'J', 'S1', 'S2', 'M', 'B'],
            "charging_amounts": {'S1': 12.0, 'S2': 20.0},
            "speed_levels": {
                ('A', 'J'): 3,
                ('J', 'S1'): 2,
                ('S1', 'S2'): 5,
                ('S2', 'M'): 2,
                ('M', 'B'): 2,
            },
        },
        {
            "vehicle_id": 2,
            "route": ['A', 'J', 'S1', 'S2', 'M', 'B'],
            "charging_amounts": {'S1': 14.0, 'S2': 18.0},
            "speed_levels": {
                ('A', 'J'): 4,
                ('J', 'S1'): 3,
                ('S1', 'S2'): 2,
                ('S2', 'M'): 5,
                ('M', 'B'): 2,
            },
        },
        {
            "vehicle_id": 3,
            "route": ['A', 'J', 'S3', 'M', 'B'],
            "charging_amounts": {'S3': 20.0},
            "speed_levels": {
                ('A', 'J'): 4,
                ('J', 'S3'): 5,
                ('S3', 'M'): 2,
                ('M', 'B'): 2,
            },
        },
        {
            "vehicle_id": 4,
            "route": ['A', 'J', 'S3', 'M', 'B'],
            "charging_amounts": {'S3': 26.0},
            "speed_levels": {
                ('A', 'J'): 2,
                ('J', 'S3'): 3,
                ('S3', 'M'): 5,
                ('M', 'B'): 1,
            },
        },
    ]

    def build_vehicle(plan: dict) -> VehicleSolution:
        vid = plan["vehicle_id"]
        route = plan["route"]
        speed_levels = plan["speed_levels"]
        charging_amounts = plan["charging_amounts"]
        charging_stations = [node for node in route if node in charging_amounts]

        battery_kwh = params.battery_kwh[vid]
        soc0 = params.soc0[vid]
        energy = battery_kwh * soc0

        arrival_times = {route[0]: 0.0}
        departure_times = {route[0]: 0.0}
        soc_at_nodes = {route[0]: soc0}
        charging_start_times = {} if charging_stations else None

        for idx in range(len(route) - 1):
            u = route[idx]
            v = route[idx + 1]
            edge = (u, v)

            travel_time = params.get_edge_time(edge, speed_levels[edge])
            energy_use = params.get_edge_energy(edge, speed_levels[edge])

            arrival = departure_times[u] + travel_time
            arrival_times[v] = arrival

            energy -= energy_use
            soc_at_nodes[v] = energy / battery_kwh

            departure = arrival
            if v in charging_amounts:
                charge_kwh = charging_amounts[v]
                if charging_start_times is not None:
                    charging_start_times[v] = arrival
                soc_after = soc_at_nodes[v] + charge_kwh / battery_kwh
                charge_minutes = params.charge_time_seconds(
                    soc_at_nodes[v], soc_after, battery_kwh, v
                ) / 60.0
                departure = arrival + charge_minutes
                energy += charge_kwh

            departure_times[v] = departure

        return VehicleSolution(
            vehicle_id=vid,
            route=route,
            charging_stations=charging_stations,
            charging_amounts=charging_amounts,
            arrival_times=arrival_times,
            departure_times=departure_times,
            soc_at_nodes=soc_at_nodes,
            charging_start_times=charging_start_times,
            speed_levels=speed_levels,
        )

    vehicle_solutions = [build_vehicle(plan) for plan in vehicle_plans]

    solution = FleetSolution(vehicle_solutions=vehicle_solutions, params=params)

    solution = process_station_queues(solution, params)

    for vs in solution.vehicle_solutions:
        route = vs.route
        vs.arrival_times[route[0]] = vs.arrival_times.get(route[0], 0.0)
        vs.departure_times[route[0]] = vs.departure_times.get(route[0], vs.arrival_times[route[0]])

        for i in range(len(route) - 1):
            current = route[i]
            nxt = route[i + 1]
            edge = (current, nxt)

            travel_time = params.get_edge_time(edge, vs.get_speed_level(edge))
            depart_current = vs.departure_times[current]
            arrival_next = depart_current + travel_time
            vs.arrival_times[nxt] = arrival_next

            if nxt in vs.charging_stations:
                if vs.charging_start_times is not None:
                    start = vs.charging_start_times.get(nxt, arrival_next)
                    if start < arrival_next:
                        vs.charging_start_times[nxt] = arrival_next
                        start = arrival_next
                    departure = max(vs.departure_times.get(nxt, start), start)
                    vs.departure_times[nxt] = departure
                else:
                    vs.departure_times[nxt] = max(vs.departure_times.get(nxt, arrival_next), arrival_next)
            else:
                vs.departure_times[nxt] = arrival_next

        final_node = route[-1]
        vs.departure_times[final_node] = vs.arrival_times[final_node]

    return solution


if __name__ == "__main__":
    print("Creating sample solution...")
    solution = create_sample_solution()
    
    # Demonstrate queue information
    print("\n" + "=" * 70)
    print("QUEUE ANALYSIS")
    print("=" * 70)
    for vs in solution.vehicle_solutions:
        print(f"\nVehicle {vs.vehicle_id + 1}:")
        for station in vs.charging_stations:
            arrival = vs.arrival_times.get(station, 0)
            if vs.charging_start_times and station in vs.charging_start_times:
                start = vs.charging_start_times[station]
                departure = vs.departure_times.get(station, 0)
                queue_wait = start - arrival
                charging_time = departure - start
                print(f"  {station}: Arrive {arrival:.1f} → Queue {queue_wait:.1f} min → Charge {charging_time:.1f} min → Depart {departure:.1f}")
            else:
                departure = vs.departure_times.get(station, 0)
                print(f"  {station}: Arrive {arrival:.1f} → Charge {departure - arrival:.1f} min → Depart {departure:.1f} (no queue)")
        queue_time = vs.get_total_queue_time()
        charging_time = vs.get_total_charging_time()
        print(f"  Total: {queue_time:.1f} min queue + {charging_time:.1f} min charging = {queue_time + charging_time:.1f} min at stations")
    
    # Check feasibility with verbose output
    print("\n" + "=" * 70)
    print("CONSTRAINT VERIFICATION")
    print("=" * 70)
    print("\nChecking feasibility with detailed constraint verification...")
    is_feas = solution.is_feasible(verbose=True)
    print(f"\n{'✓ Solution is FEASIBLE' if is_feas else '✗ Solution has constraint violations'}")
    
    # Calculate individual objectives
    print("\n" + "=" * 70)
    print("INDIVIDUAL OBJECTIVE VALUES")
    print("=" * 70)
    
    makespan = objective_makespan(solution)
    total_cost = objective_total_cost(solution)
    weighted = objective_weighted(solution)
    
    print(f"\nObjective 1 - Makespan: {makespan:.2f} minutes")
    print(f"  (Time when last vehicle reaches destination)")
    
    print(f"\nObjective 2 - Total Cost: {total_cost:.2f} EGP")
    print(f"  (Sum of all charging costs)")
    
    print(f"\nWeighted Objective: {weighted:.2f}")
    print(f"  (Combination: w_time × makespan + w_cost × total_cost)")
    
    # Full evaluation
    print("\n" + "=" * 70)
    print("FLEET SOLUTION EVALUATION")
    print("=" * 70)
    print("\n")
    print_solution_summary(solution)
    
    print("\n" + "=" * 70)
    print("SCENARIO ANALYSIS: Different Weight Settings")
    print("=" * 70)
    
    scenarios = [
        ("Balanced", 1.0, 1.0),
        ("Time-Critical", 2.0, 1.0),
        ("Cost-Conscious", 1.0, 3.0),
        ("Time-Only", 1.0, 0.0),
        ("Cost-Only", 0.0, 1.0),
    ]
    
    print(f"\n{'Scenario':<20} {'w_time':>8} {'w_cost':>8} {'Objective':>12}")
    print("-" * 70)
    for name, w_t, w_c in scenarios:
        obj_val = objective_weighted(solution, w_time=w_t, w_cost=w_c)
        print(f"{name:<20} {w_t:>8.1f} {w_c:>8.1f} {obj_val:>12.2f}")
    
    # Demonstrate automatic queue processing
    print("\n" + "=" * 70)
    print("AUTOMATIC QUEUE PROCESSING DEMONSTRATION")
    print("=" * 70)
    print("\nThe process_station_queues() function can automatically compute")
    print("charging_start_times based on FIFO queue discipline.")
    print("\nExample: Create solution with only arrival times, let function")
    print("compute queue waiting and charging start times automatically.")
    print("\nUsage:")
    print("  solution_with_queues = process_station_queues(solution, params)")
    print("\nThis is useful when building optimization algorithms - just specify")
    print("arrival times and charging amounts, and queue processing is automatic!")
    
    print("\n✓ Example completed successfully!")
