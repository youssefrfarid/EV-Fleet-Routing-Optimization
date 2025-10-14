# EV Fleet Routing Optimization - Documentation

## Project Overview

Multi-Vehicle Electric Vehicle Fleet Routing and Charging Optimization system.

**Problem**: Route multiple EVs through a fork-shaped network with charging stations, optimizing for time and cost.

**Network**: A → J → {Upper: S1→S2 | Lower: S3} → M → B

**Objectives**:
1. Minimize makespan (time for last vehicle to finish)
2. Minimize total charging cost

---

## File Descriptions

### params.py
**Purpose**: Defines problem parameters, network topology, charging physics, and fleet specifications.

**Key Classes**:
- `SingleForkParams`: Container for all problem parameters
  - Network (nodes, edges, travel times, energy)
  - Stations (capacity, pricing, power limits)
  - Fleet (battery sizes, initial SOC)
  - Charging model (SOC-dependent curves, efficiency)

**Key Methods**:
- `charge_time_seconds()`: Calculates charging time using numerical integration
- `energy_bought_kwh()`: Calculates grid energy accounting for efficiency
- `validate()`: Sanity checks on all parameters
- `make_toy_params()`: Factory function for test instance with 5 vehicles

### objectives.py
**Purpose**: Objective functions and solution evaluation.

**Key Classes**:
- `VehicleSolution`: Single vehicle's route, charging plan, and timing
- `FleetSolution`: Complete solution for entire fleet

**Key Functions**:
- `objective_makespan()`: Returns max completion time (MINIMIZE)
- `objective_total_cost()`: Returns sum of charging costs (MINIMIZE)
- `objective_weighted()`: Combines both with weights
- `evaluate_solution()`: Comprehensive analysis with all metrics
- `print_solution_summary()`: Human-readable output

### visualize_params.py
**Purpose**: Visualize problem structure before solving.

**Functions**:
- `visualize_network()`: 4-panel visualization
  - Network topology graph
  - Charging power vs SOC curves
  - Fleet configuration
  - Station comparison
- `visualize_charging_time_heatmap()`: Charging time for all SOC combinations

### visualize_objectives.py
**Purpose**: Visualize solutions and objective analysis.

**Functions**:
- `visualize_solution()`: 9-panel dashboard
  - Objectives summary
  - Vehicle completion times (bottleneck highlighted)
  - Cost breakdown
  - Station utilization
  - Energy analysis
  - Route distribution
  - Time breakdown
  - Journey details
- `visualize_scenario_comparison()`: Compare different weight settings

### example_objectives.py
**Purpose**: Tutorial and testing.

**Functions**:
- `create_sample_solution()`: Manually constructs realistic feasible solution
- Main execution: Demonstrates objective calculation and scenario analysis

---

## Quick Start

```python
# 1. Load parameters
from params import make_toy_params
params = make_toy_params()

# 2. Visualize problem
from visualize_params import visualize_network
visualize_network(params)

# 3. Create/load solution
from example_objectives import create_sample_solution
solution = create_sample_solution()

# 4. Evaluate
from objectives import print_solution_summary
print_solution_summary(solution)

# 5. Visualize solution
from visualize_objectives import visualize_solution
visualize_solution(solution)
```

---

## Mathematical Details

**Charging Time Formula**: t = ∫(B/η) dSOC / P(SOC) × 3600 seconds
- B = battery capacity
- η = charging efficiency  
- P(SOC) = effective power at given SOC

**Energy Cost**: (Battery × ΔSOC) / efficiency × price

**Objectives**:
- Makespan: max(completion_time_i) for all vehicles i
- Total Minimum Cost: Σ(energy_charged × price) across all charging events
