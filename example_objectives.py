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
    
    # Vehicle 1: Compact EV (40 kWh), takes upper route, charges at S1
    v1 = VehicleSolution(
        vehicle_id=0,
        route=['A', 'J', 'S1', 'S2', 'M', 'B'],
        charging_stations=['S1'],
        charging_amounts={'S1': 12.0},  # Charges 12 kWh at S1
        arrival_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 45, 'M': 55, 'B': 68},
        departure_times={'A': 0, 'J': 15, 'S1': 42, 'S2': 45, 'M': 55, 'B': 68},
        soc_at_nodes={'A': 0.7000, 'J': 0.5875, 'S1': 0.4975, 'S2': 0.7375, 'M': 0.6500, 'B': 0.5450}
    )
    
    # Vehicle 2: Sedan (55 kWh), takes upper route, charges at S2
    v2 = VehicleSolution(
        vehicle_id=1,
        route=['A', 'J', 'S1', 'S2', 'M', 'B'],
        charging_stations=['S2'],
        charging_amounts={'S2': 18.0},  # Charges 18 kWh at S2
        arrival_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 35, 'M': 58, 'B': 71},
        departure_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 48, 'M': 58, 'B': 71},
        soc_at_nodes={'A': 0.5500, 'J': 0.4682, 'S1': 0.4027, 'S2': 0.3591, 'M': 0.6227, 'B': 0.5464}
    )
    
    # Vehicle 3: Sedan+ (62 kWh), takes upper route, charges at S1 and S2
    # Arrives at S2 same time as v2 but waits in queue
    v3 = VehicleSolution(
        vehicle_id=2,
        route=['A', 'J', 'S1', 'S2', 'M', 'B'],
        charging_stations=['S1', 'S2'],
        charging_amounts={'S1': 10.0, 'S2': 8.0},
        arrival_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 41, 'M': 69, 'B': 82},  # Arrives at S2 at 41
        departure_times={'A': 0, 'J': 15, 'S1': 41, 'S2': 59, 'M': 69, 'B': 82},  # Total time at S2: 41→59
        soc_at_nodes={'A': 0.4500, 'J': 0.3774, 'S1': 0.3194, 'S2': 0.4419, 'M': 0.5145, 'B': 0.4468},
        charging_start_times={'S1': 27, 'S2': 48}  # Waits at S2 from 41→48, charges 48→59
    )
    
    # Vehicle 4: SUV (75 kWh), takes lower route, charges at S3
    v4 = VehicleSolution(
        vehicle_id=3,
        route=['A', 'J', 'S3', 'M', 'B'],
        charging_stations=['S3'],
        charging_amounts={'S3': 20.0},
        arrival_times={'A': 0, 'J': 15, 'S3': 24, 'M': 52, 'B': 65},
        departure_times={'A': 0, 'J': 15, 'S3': 38, 'M': 52, 'B': 65},
        soc_at_nodes={'A': 0.6000, 'J': 0.5400, 'S3': 0.5040, 'M': 0.6960, 'B': 0.6400}
    )
    
    # Vehicle 5: Large SUV (80 kWh), takes lower route, charges at S3
    # Arrives at S3 same time as v4 but waits in queue at the station
    v5 = VehicleSolution(
        vehicle_id=4,
        route=['A', 'J', 'S3', 'M', 'B'],
        charging_stations=['S3'],
        charging_amounts={'S3': 25.0},
        arrival_times={'A': 0, 'J': 15, 'S3': 24, 'M': 70, 'B': 83},  # Arrives at S3 at 24 (same as v4)
        departure_times={'A': 0, 'J': 15, 'S3': 56, 'M': 70, 'B': 83},  # Total time at S3: 24→56
        soc_at_nodes={'A': 0.5000, 'J': 0.4437, 'S3': 0.4100, 'M': 0.6525, 'B': 0.6000},
        charging_start_times={'S3': 38}  # Waits at S3 from 24→38, charges 38→56
    )
    
    solution = FleetSolution(
        vehicle_solutions=[v1, v2, v3, v4, v5],
        params=params
    )
    
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
