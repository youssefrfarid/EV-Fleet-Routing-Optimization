"""
example_speed_levels.py
Demonstrates the new discrete speed level feature.

Shows:
1. How to view all 5 speed options for each edge
2. How to create a solution with different speed levels
3. How speed affects time and energy consumption
4. Trade-offs between speed choices
"""
from params import make_toy_params, SPEED_LEVELS, SPEED_TIME_MULTIPLIERS, SPEED_ENERGY_MULTIPLIERS
from objectives import VehicleSolution, FleetSolution, print_solution_summary
from visualize_params import visualize_network


def demonstrate_speed_options():
    """Show all speed options for edges in the network."""
    params = make_toy_params()

    print("=" * 80)
    print("DISCRETE SPEED LEVELS - ALL OPTIONS")
    print("=" * 80)

    print("\nSpeed Level Reference:")
    for level, name in SPEED_LEVELS.items():
        time_mult = SPEED_TIME_MULTIPLIERS[level]
        energy_mult = SPEED_ENERGY_MULTIPLIERS[level]
        print(
            f"  Level {level} ({name:12}): Time ×{time_mult:.2f}, Energy ×{energy_mult:.2f}")

    print("\n" + "=" * 80)
    print("EDGE-BY-EDGE SPEED OPTIONS")
    print("=" * 80)

    # Get all edges
    edges = list(params.edges_time_min.keys())

    for edge in edges:
        print(f"\n📍 Edge {edge[0]} → {edge[1]}")
        print(f"{'Level':<8} {'Name':<15} {'Time (min)':<15} {'Energy (kWh)':<15}")
        print("-" * 60)

        options = params.get_all_speed_options(edge)
        for level, name, time, energy in options:
            print(f"{level:<8} {name:<15} {time:<15.2f} {energy:<15.3f}")


def create_speed_optimized_solution():
    """Create a solution using different speed strategies."""
    params = make_toy_params()

    print("\n\n" + "=" * 80)
    print("EXAMPLE SOLUTION WITH SPEED OPTIMIZATION")
    print("=" * 80)

    # Vehicle 1: Conservative strategy (slow speeds, low energy)
    # Takes upper route, uses slow speeds to minimize energy consumption
    v1 = VehicleSolution(
        vehicle_id=0,
        route=['A', 'J', 'S1', 'S2', 'M', 'B'],
        charging_stations=['S1'],
        charging_amounts={'S1': 10.0},
        speed_levels={
            ('A', 'J'): 2,    # Slow
            ('J', 'S1'): 2,   # Slow
            ('S1', 'S2'): 2,  # Slow
            ('S2', 'M'): 2,   # Slow
            ('M', 'B'): 2,    # Slow
        },
        arrival_times={
            'A': 0.0,
            'J': 18.0,      # Slower (15 * 1.2 = 18)
            'S1': 32.4,     # Slower (18 + 12*1.2 = 32.4)
            'S2': 42.0,     # After charging
            'M': 54.0,
            'B': 69.6
        },
        departure_times={
            'A': 0.0,
            'J': 18.0,
            'S1': 42.0,     # Charges for 9.6 minutes (less energy needed)
            'S2': 42.0,
            'M': 54.0,
            'B': 69.6
        },
        soc_at_nodes={
            'A': 0.70,
            'J': 0.616,     # Uses less energy (4.5 * 0.9 = 4.05 kWh)
            'S1': 0.548,
            'S2': 0.798,    # After charging 10 kWh
            'M': 0.719,
            'B': 0.625
        }
    )

    # Vehicle 2: Aggressive strategy (fast speeds, high energy)
    # Takes lower route, uses fast speeds to minimize time
    v2 = VehicleSolution(
        vehicle_id=3,  # SUV with 75 kWh battery
        route=['A', 'J', 'S3', 'M', 'B'],
        charging_stations=['S3'],
        charging_amounts={'S3': 22.0},
        speed_levels={
            ('A', 'J'): 5,    # Very Fast
            ('J', 'S3'): 5,   # Very Fast
            ('S3', 'M'): 4,   # Fast (terrain is hilly, need some caution)
            ('M', 'B'): 5,    # Very Fast
        },
        arrival_times={
            'A': 0.0,
            'J': 10.5,      # Very fast (15 * 0.7 = 10.5)
            'S3': 16.8,     # Very fast (10.5 + 9*0.7 = 16.8)
            'M': 44.7,      # After charging (16.8 + charging_time + 14*0.85)
            'B': 53.8
        },
        departure_times={
            'A': 0.0,
            'J': 10.5,
            'S3': 32.8,     # Charges longer (more energy consumed)
            'M': 44.7,
            'B': 53.8
        },
        soc_at_nodes={
            'A': 0.60,
            'J': 0.51,      # Uses more energy (4.5 * 1.5 = 6.75 kWh)
            'S3': 0.456,    # Uses more energy on hilly section
            'M': 0.749,     # After charging 22 kWh
            'B': 0.666
        }
    )

    solution = FleetSolution(
        vehicle_solutions=[v1, v2],
        params=params
    )

    return solution


def analyze_speed_tradeoffs():
    """Analyze trade-offs between different speed strategies."""
    params = make_toy_params()

    print("\n\n" + "=" * 80)
    print("SPEED STRATEGY TRADE-OFF ANALYSIS")
    print("=" * 80)

    # Example: Edge A→J (baseline: 15 min, 4.5 kWh)
    edge = ('A', 'J')
    base_time = params.edges_time_min[edge]
    base_energy = params.edges_energy_kwh[edge]

    print(f"\n📊 Analysis for edge {edge[0]} → {edge[1]}")
    print(
        f"Baseline (Level 3 - Normal): {base_time:.1f} min, {base_energy:.2f} kWh")
    print("\n" + "-" * 80)

    print(f"{'Level':<8} {'Name':<15} {'Time':<12} {'Energy':<12} {'Time Saved':<15} {'Extra Energy':<15}")
    print("-" * 80)

    options = params.get_all_speed_options(edge)
    for level, name, time, energy in options:
        time_saved = base_time - time
        extra_energy = energy - base_energy
        print(f"{level:<8} {name:<15} {time:<12.2f} {energy:<12.3f} "
              f"{time_saved:+12.2f} min {extra_energy:+12.3f} kWh")

    print("\n📝 Key Insights:")
    print("  • Very Slow (1): Save 25% energy but take 40% more time")
    print("  • Normal (3):    Baseline reference point")
    print("  • Very Fast (5): Save 30% time but use 50% more energy")
    print("  • Trade-off:     Speed vs. Energy consumption")
    print("  • Impact:        Affects both arrival times and charging needs")


def compare_speed_strategies():
    """Compare different speed strategies for the same route."""
    params = make_toy_params()

    print("\n\n" + "=" * 80)
    print("SPEED STRATEGY COMPARISON: SAME ROUTE, DIFFERENT SPEEDS")
    print("=" * 80)

    # Route: A → J → S1 → S2 → M → B (upper route)
    route = ['A', 'J', 'S1', 'S2', 'M', 'B']

    strategies = {
        "Eco (All Slow)": [1, 1, 1, 1, 1],
        "Balanced": [3, 3, 3, 3, 3],
        "Sport (All Fast)": [5, 5, 5, 5, 5],
        "Mixed (Fast Highway, Slow City)": [2, 4, 4, 4, 2],
    }

    print(f"\nRoute: {' → '.join(route)}")
    print("\n" + "-" * 80)
    print(f"{'Strategy':<30} {'Total Time':<15} {'Total Energy':<15} {'Time vs Base':<15} {'Energy vs Base'}")
    print("-" * 80)

    for strategy_name, speed_levels in strategies.items():
        total_time = 0.0
        total_energy = 0.0

        for i, speed in enumerate(speed_levels):
            edge = (route[i], route[i+1])
            total_time += params.get_edge_time(edge, speed)
            total_energy += params.get_edge_energy(edge, speed)

        # Calculate vs baseline (level 3)
        baseline_time = sum(params.get_edge_time((route[i], route[i+1]), 3)
                            for i in range(len(route)-1))
        baseline_energy = sum(params.get_edge_energy((route[i], route[i+1]), 3)
                              for i in range(len(route)-1))

        time_diff = total_time - baseline_time
        energy_diff = total_energy - baseline_energy

        print(f"{strategy_name:<30} {total_time:<15.2f} {total_energy:<15.2f} "
              f"{time_diff:+12.2f} min {energy_diff:+12.2f} kWh")

    print("\n📝 Strategic Implications:")
    print("  • Eco strategy:    More charging time needed (less energy saved)")
    print("  • Sport strategy:  Less travel time but much more charging needed")
    print("  • Mixed strategy:  Optimizes based on road conditions")
    print("  • Optimization:    Must balance travel time + charging time")


if __name__ == "__main__":
    print("\n" + "🚗" * 40)
    print("EV FLEET ROUTING - DISCRETE SPEED LEVELS DEMONSTRATION")
    print("🚗" * 40)

    # 1. Show all speed options
    demonstrate_speed_options()

    # 2. Analyze trade-offs
    analyze_speed_tradeoffs()

    # 3. Compare strategies
    compare_speed_strategies()

    # 4. Create and evaluate solution
    print("\n\n" + "=" * 80)
    print("CREATING SOLUTION WITH SPEED OPTIMIZATION")
    print("=" * 80)
    solution = create_speed_optimized_solution()

    print("\n✅ Checking feasibility...")
    is_feasible = solution.is_feasible(verbose=True)
    print(f"\nFeasibility: {'✓ FEASIBLE' if is_feasible else '✗ INFEASIBLE'}")

    if is_feasible:
        print("\n")
        print_solution_summary(solution)

    print("\n\n" + "=" * 80)
    print("SUMMARY: DISCRETE SPEED LEVELS FEATURE")
    print("=" * 80)
    print("""
✅ Feature Implemented Successfully!

Key Capabilities:
  1. Five discrete speed levels (1=Very Slow to 5=Very Fast)
  2. Speed-dependent travel time and energy consumption
  3. Physics-based multipliers (faster = more air resistance)
  4. Full integration with constraint checking
  5. Backward compatible (defaults to level 3 if not specified)

Usage in Optimization:
  • Add speed_levels to VehicleSolution
  • Choose speed level (1-5) for each edge
  • System automatically computes time and energy
  • Constraints validate speed choices

Decision Variables (Updated):
  • Route selection (which path)
  • Charging stations (where to charge)
  • Charging amounts (how much to charge)
  • Speed levels (how fast to drive) ← NEW!

Trade-offs to Optimize:
  • Faster speeds → Less travel time BUT more energy needed
  • Slower speeds → More travel time BUT less energy needed
  • Must balance: travel_time + charging_time + cost

Example Speed Levels Dict:
  speed_levels = {
      ('A', 'J'): 3,    # Normal speed
      ('J', 'S1'): 5,   # Very fast (highway)
      ('S1', 'S2'): 2,  # Slow (save energy)
  }

Next Steps for Your Optimizer:
  1. For each vehicle, choose route
  2. For each edge in route, choose speed level (1-5)
  3. For each station visited, choose charging amount
  4. Evaluate objectives (makespan, cost)
  5. Find optimal combination
    """)

    print("\n✓ Example completed successfully!")
    print("=" * 80)
