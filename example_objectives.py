"""
example_objectives.py
Demonstrates how to use the objective functions with a sample solution.
"""
from params import make_toy_params
from objectives import (
    VehicleSolution, FleetSolution,
    objective_makespan, objective_total_cost, objective_weighted,
    evaluate_solution, print_solution_summary
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
        soc_at_nodes={'A': 0.70, 'J': 0.59, 'S1': 0.50, 'S2': 0.74, 'M': 0.65, 'B': 0.54}
    )
    
    # Vehicle 2: Sedan (55 kWh), takes upper route, charges at S2
    v2 = VehicleSolution(
        vehicle_id=1,
        route=['A', 'J', 'S1', 'S2', 'M', 'B'],
        charging_stations=['S2'],
        charging_amounts={'S2': 18.0},  # Charges 18 kWh at S2
        arrival_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 35, 'M': 58, 'B': 71},
        departure_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 48, 'M': 58, 'B': 71},
        soc_at_nodes={'A': 0.55, 'J': 0.47, 'S1': 0.40, 'S2': 0.36, 'M': 0.59, 'B': 0.51}
    )
    
    # Vehicle 3: Sedan+ (62 kWh), takes upper route, charges at S1 and S2
    v3 = VehicleSolution(
        vehicle_id=2,
        route=['A', 'J', 'S1', 'S2', 'M', 'B'],
        charging_stations=['S1', 'S2'],
        charging_amounts={'S1': 10.0, 'S2': 8.0},
        arrival_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 48, 'M': 68, 'B': 81},
        departure_times={'A': 0, 'J': 15, 'S1': 40, 'S2': 58, 'M': 68, 'B': 81},
        soc_at_nodes={'A': 0.45, 'J': 0.38, 'S1': 0.32, 'S2': 0.45, 'M': 0.57, 'B': 0.50}
    )
    
    # Vehicle 4: SUV (75 kWh), takes lower route, charges at S3
    v4 = VehicleSolution(
        vehicle_id=3,
        route=['A', 'J', 'S3', 'M', 'B'],
        charging_stations=['S3'],
        charging_amounts={'S3': 20.0},
        arrival_times={'A': 0, 'J': 15, 'S3': 24, 'M': 52, 'B': 65},
        departure_times={'A': 0, 'J': 15, 'S3': 38, 'M': 52, 'B': 65},
        soc_at_nodes={'A': 0.60, 'J': 0.54, 'S3': 0.50, 'M': 0.60, 'B': 0.54}
    )
    
    # Vehicle 5: Large SUV (80 kWh), takes lower route, charges at S3
    v5 = VehicleSolution(
        vehicle_id=4,
        route=['A', 'J', 'S3', 'M', 'B'],
        charging_stations=['S3'],
        charging_amounts={'S3': 25.0},
        arrival_times={'A': 0, 'J': 15, 'S3': 24, 'M': 55, 'B': 68},
        departure_times={'A': 0, 'J': 15, 'S3': 41, 'M': 55, 'B': 68},
        soc_at_nodes={'A': 0.50, 'J': 0.44, 'S3': 0.41, 'M': 0.63, 'B': 0.57}
    )
    
    solution = FleetSolution(
        vehicle_solutions=[v1, v2, v3, v4, v5],
        params=params
    )
    
    return solution


if __name__ == "__main__":
    print("Creating sample solution...")
    solution = create_sample_solution()
    
    print("\n" + "=" * 70)
    print("INDIVIDUAL OBJECTIVE VALUES")
    print("=" * 70)
    
    # Calculate individual objectives
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
    
    print("\n✓ Example completed successfully!")
