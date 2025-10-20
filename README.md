# EV Fleet Routing Optimization

Multi-vehicle electric vehicle fleet routing and charging optimization with realistic physics.

## 📋 Problem Description

Route multiple electric vehicles through a fork-shaped network with charging stations, optimizing for:

1. **Makespan**: Time for last vehicle to complete journey
2. **Total Cost**: Sum of all charging costs

**Network**: `A → J → {Upper: S1→S2 | Lower: S3} → M → B`

## 🚗 Features

- **Realistic Charging Physics**: SOC-dependent power curves with efficiency losses
- **Queue Modeling**: Vehicles wait at stations (FIFO discipline) when plugs are occupied
- **Discrete Speed Levels**: 5 speed options per edge (time vs. energy trade-offs) 🆕
- **Heterogeneous Fleet**: 5 vehicles with different battery capacities (40-80 kWh)
- **Varied Stations**: 3 stations with different speeds, prices, and capacities
- **Multi-Objective**: Time vs cost trade-offs with configurable weights
- **Interactive Simulation**: Real-time animated visualization of solutions
- **Comprehensive Visualization**: Network, parameters, solutions, and objectives
- **Well-Documented**: Detailed inline comments and documentation

## 📁 File Structure

```
├── params.py                           # Problem parameters and physics models
├── objectives.py                       # Objective functions and evaluation
├── visualize_params.py                 # Network and parameter visualization
├── visualize_objectives.py             # Solution visualization
├── simulation_gui.py                   # 🆕 Interactive simulation GUI
├── example_objectives.py               # Usage examples and demonstrations
├── example_speed_levels.py             # 🆕 Speed levels demonstration
├── DOCUMENTATION.md                    # Comprehensive documentation
├── LINE_BY_LINE_EXPLANATION.md         # Detailed code explanations
├── DECISION_VARIABLES_AND_CONSTRAINTS.md  # Decision variables and constraints reference
├── SPEED_LEVELS_GUIDE.md               # 🆕 Discrete speed levels guide
└── QUEUE_IMPLEMENTATION_SUMMARY.md     # Queue modeling documentation
```

## 🚀 Quick Start

### 1. Setup and Visualization

```python
from params import make_toy_params
from visualize_params import visualize_network

# Load problem instance (5 vehicles, 3 stations)
params = make_toy_params()

# Visualize the network
visualize_network(params)
```

### 2. Create and Evaluate a Solution

```python
from objectives import VehicleSolution, FleetSolution, print_solution_summary

# Create a solution (manually for demonstration)
v1 = VehicleSolution(
    vehicle_id=0,
    route=['A', 'J', 'S1', 'S2', 'M', 'B'],
    charging_stations=['S1'],
    charging_amounts={'S1': 12.0},
    arrival_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 45, 'M': 55, 'B': 68},
    departure_times={'A': 0, 'J': 15, 'S1': 42, 'S2': 45, 'M': 55, 'B': 68},
    soc_at_nodes={'A': 0.70, 'J': 0.59, 'S1': 0.50, 'S2': 0.74, 'M': 0.65, 'B': 0.54}
)

solution = FleetSolution(vehicle_solutions=[v1], params=params)

# Print comprehensive evaluation
print_solution_summary(solution)
```

### 3. Run Complete Example

```bash
python example_objectives.py
```

### 4. Visualize Solutions

```bash
python visualize_objectives.py
```

### 5. 🎬 Interactive Simulation (NEW!)

Watch your solution come to life with the **interactive animated simulation**:

```bash
python simulation_gui.py
```

**Features**:

- ✅ Real-time animation of vehicles moving through the network
- ✅ Queue visualization at charging stations
- ✅ Live charging progress bars
- ✅ Metrics dashboard updating in real-time
- ✅ Timeline showing complete journey for all vehicles
- ✅ Playback controls (play/pause, speed adjustment, reset)

**Controls**:

- **Play/Pause** button: Start/stop the animation
- **Speed slider**: Adjust from 0.1x to 5x playback speed
- **Reset** button: Restart simulation from beginning

**What You'll See**:

- 🔵 Colored circles moving = vehicles traveling through network
- 🟢 Green stations = upper branch (S1, S2)
- 🔴 Red stations = lower branch (S3)
- 🟠 Orange bars in timeline = active charging
- 🟡 Yellow bars in timeline = queue waiting
- 📊 Real-time metrics: traveling/charging/completed counts

**Usage in Your Code**:

```python
from simulation_gui import simulate_solution
from example_objectives import create_sample_solution
from params import make_toy_params

solution = create_sample_solution()
params = make_toy_params()

# Launch interactive simulation
simulate_solution(solution, params)
```

## 📊 Problem Instance Details

### Fleet Composition (5 Vehicles)

| Vehicle | Battery | Initial SOC | Type                  |
| ------- | ------- | ----------- | --------------------- |
| EV 1    | 40 kWh  | 62%         | Compact (Nissan Leaf) |
| EV 2    | 55 kWh  | 48%         | Sedan (Chevy Bolt)    |
| EV 3    | 62 kWh  | 45%         | Sedan+ (Leaf Plus)    |
| EV 4    | 75 kWh  | 52%         | SUV (Model Y)         |
| EV 5    | 80 kWh  | 47%         | Large SUV (e-tron)    |

### Charging Stations (3 Options)

| Station | Type     | Speed  | Price (EGP/kWh)  | Plugs |
| ------- | -------- | ------ | ---------------- | ----- |
| **S1**  | Budget   | 50 kW  | 13.0 (cheapest)  | 2     |
| **S2**  | Premium  | 180 kW | 27.0 (expensive) | 1     |
| **S3**  | Standard | 100 kW | 20.0 (medium)    | 1     |

### Route Characteristics

- **Upper Route (J→S1→S2→M)**: Longer time, more station options
- **Lower Route (J→S3→M)**: Shorter time, hilly terrain (more energy)

## 🎯 Objectives

### 1. Minimize Makespan

```python
from objectives import objective_makespan

makespan = objective_makespan(solution)  # Time when last vehicle finishes
```

**Use cases**: Time-critical deliveries, passenger transport

### 2. Minimize Total Cost

```python
from objectives import objective_total_cost

total_cost = objective_total_cost(solution)  # Sum of all charging costs
```

**Use cases**: Budget-constrained operations, cost minimization

### 3. Weighted Combination

```python
from objectives import objective_weighted

# Balanced: equal importance
obj = objective_weighted(solution, w_time=1.0, w_cost=1.0)

# Time-critical: prioritize speed
obj = objective_weighted(solution, w_time=2.0, w_cost=1.0)

# Cost-conscious: prioritize savings
obj = objective_weighted(solution, w_time=1.0, w_cost=3.0)
```

## 📈 Visualization Examples

### Network Topology

```python
from visualize_params import visualize_network
visualize_network(params, save_path='network.png')
```

**Shows**: Nodes, edges, travel times, energy consumption, station details

### Solution Analysis

```python
from visualize_objectives import visualize_solution
visualize_solution(solution, save_path='solution.png')
```

**Shows**: Completion times, costs, station utilization, route distribution

### Scenario Comparison

```python
from visualize_objectives import visualize_scenario_comparison

scenarios = [
    ("Balanced", 1.0, 1.0),
    ("Time-Critical", 2.0, 1.0),
    ("Cost-Conscious", 1.0, 3.0),
]

visualize_scenario_comparison(solution, scenarios, save_path='comparison.png')
```

**Shows**: How different weight settings affect objective values

## 🔬 Key Concepts

### Discrete Speed Levels (NEW! ⚡)

**5 Speed Options for Each Edge**:

- **Level 1 (Very Slow)**: Save 25% energy, take 40% more time
- **Level 2 (Slow)**: Save 10% energy, take 20% more time
- **Level 3 (Normal)**: Baseline (default if not specified)
- **Level 4 (Fast)**: Use 20% more energy, save 15% time
- **Level 5 (Very Fast)**: Use 50% more energy, save 30% time

**Usage Example**:

```python
# Create solution with speed level choices
vehicle = VehicleSolution(
    vehicle_id=0,
    route=['A', 'J', 'S1', 'S2', 'M', 'B'],
    speed_levels={
        ('A', 'J'): 3,    # Normal speed
        ('J', 'S1'): 5,   # Very fast (highway)
        ('S1', 'S2'): 2,  # Slow (save energy)
        ('S2', 'M'): 4,   # Fast
        ('M', 'B'): 3,    # Normal
    },
    ...
)
```

**View All Speed Options**:

```python
from params import make_toy_params

params = make_toy_params()
edge = ('A', 'J')

# Get all 5 speed options with time and energy values
options = params.get_all_speed_options(edge)
# Returns: [(1, "Very Slow", 21.0, 3.375), (2, "Slow", 18.0, 4.05), ...]
```

**Run Speed Levels Demo**:

```bash
python example_speed_levels.py
```

**Trade-offs**:

- Fast speeds → Less travel time BUT more energy needed
- Slow speeds → Less energy needed BUT more travel time
- Optimizer must balance: `travel_time + charging_time + cost`

**See**: `SPEED_LEVELS_GUIDE.md` for comprehensive documentation

### Queue Modeling at Charging Stations

**Realistic Queue Behavior**:

- Vehicles wait **at the station** when all plugs are occupied (not at previous nodes)
- FIFO (First-In-First-Out) queue discipline
- Separate tracking of queue waiting time vs. charging time

**Queue-Aware Fields** in `VehicleSolution`:

```python
charging_start_times: Dict[str, float]  # When charging actually starts (after queue wait)

# Example:
arrival_times={'S1': 24}        # Arrives at station
charging_start_times={'S1': 30}  # Starts charging (waited 6 min in queue)
departure_times={'S1': 45}      # Finishes charging
```

**Automatic Queue Processing**:

```python
from objectives import process_station_queues

# Create solution with just arrival times and charging amounts
solution = create_basic_solution()

# Automatically compute queue waiting and charging start times
solution = process_station_queues(solution, params)
# Now charging_start_times are populated based on FIFO and station capacity!
```

**Queue Metrics**:

- `get_total_queue_time()`: Time spent waiting in queues
- `get_total_charging_time()`: Time spent actually charging (excludes queue)
- `get_total_time_at_stations()`: Total time at stations (queue + charging)

### Charging Physics

**SOC-Dependent Power Curve**:

- Fast charging at low SOC (140 kW up to 80%)
- Tapers at high SOC (protects battery)
- Formula: `P(SOC) = min(base_curve(SOC), station_limit, ev_limit)`

**Charging Time Calculation**:

```
time = ∫ (Battery_capacity / efficiency) × dSOC / Power(SOC)
```

Computed using numerical integration (Riemann sum with 400 steps)

**Efficiency Losses**:

- Grid-to-battery efficiency: 95%
- To store 10 kWh in battery, need to buy 10.53 kWh from grid
- 0.53 kWh lost as heat

### Makespan vs. Total Time

- **Makespan**: max(completion_time) - time when LAST vehicle finishes
- **Total Time**: sum(completion_time) - sum of all vehicle times
- **Why makespan?**: Vehicles travel in parallel, fleet not done until all finish

### Trade-offs

1. **Route Choice**:

   - Upper: longer, but more station options
   - Lower: shorter, but hilly (more energy)

2. **Station Choice**:

   - S1: Slow but cheap
   - S2: Fast but expensive
   - S3: Balanced

3. **Charging Strategy**:
   - One big charge vs. multiple small charges
   - Early charging vs. late charging
   - Fast expensive station vs. slow cheap station

## 📚 Documentation

- **DOCUMENTATION.md**: Comprehensive guide to all files and concepts
- **LINE_BY_LINE_EXPLANATION.md**: Detailed explanation of every code section
- **Inline comments**: Every file extensively commented

## 🛠️ Next Steps: Building an Optimizer

This codebase provides the foundation. To build an optimization algorithm:

1. **Choose algorithm**: Genetic Algorithm, Simulated Annealing, or MILP
2. **Generate candidates**: Create random/heuristic initial solutions
3. **Evaluate**: Use `objective_makespan()` and `objective_total_cost()`
4. **Iterate**: Improve solutions through crossover, mutation, or search
5. **Visualize**: Use visualization tools to analyze results

**Example pseudocode**:

```python
def optimize(params):
    population = initialize_random_solutions(params)

    for generation in range(MAX_GENERATIONS):
        # Evaluate each solution
        for solution in population:
            solution.fitness = objective_weighted(solution)

        # Select best and create next generation
        parents = select_best(population)
        population = crossover_and_mutate(parents)

    return best_solution(population)
```

**Happy Optimizing! ⚡🚗**
