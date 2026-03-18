# Discrete Speed Levels Feature Guide

## Overview

The EV Fleet Routing Optimization now supports **5 discrete speed levels** for traveling between nodes. Each speed level represents a different driving strategy with trade-offs between travel time and energy consumption.

## 📊 Speed Level Definitions

| Level | Name      | Time Multiplier | Energy Multiplier | Description                             |
| ----- | --------- | --------------- | ----------------- | --------------------------------------- |
| **1** | Very Slow | ×1.40           | ×0.75             | Most energy-efficient, 40% slower       |
| **2** | Slow      | ×1.20           | ×0.90             | Energy-efficient, 20% slower            |
| **3** | Normal    | ×1.00           | ×1.00             | **Baseline** (default if not specified) |
| **4** | Fast      | ×0.85           | ×1.20             | Less efficient, 15% faster              |
| **5** | Very Fast | ×0.70           | ×1.50             | Least efficient, 30% faster             |

### Physics Rationale

- **Lower speeds** = Less air resistance → Less energy consumption
- **Higher speeds** = More air resistance (quadratic) → More energy consumption
- Trade-off: Time savings vs. Energy costs

## 🎯 Usage in Code

### 1. Viewing Speed Options

```python
from params import make_toy_params

params = make_toy_params()

# Get all speed options for an edge
edge = ('A', 'J')
options = params.get_all_speed_options(edge)

# Returns: [(level, name, time_minutes, energy_kwh), ...]
for level, name, time, energy in options:
    print(f"Level {level} ({name}): {time:.2f} min, {energy:.2f} kWh")
```

### 2. Getting Specific Speed Values

```python
# Get time for specific speed level
time = params.get_edge_time(('A', 'J'), speed_level=5)  # Very Fast

# Get energy for specific speed level
energy = params.get_edge_energy(('A', 'J'), speed_level=1)  # Very Slow
```

### 3. Creating Solutions with Speed Levels

```python
from objectives import VehicleSolution, FleetSolution

# Create vehicle solution with speed level choices
vehicle = VehicleSolution(
    vehicle_id=0,
    route=['A', 'J', 'S1', 'S2', 'M', 'B'],
    charging_stations=['S1'],
    charging_amounts={'S1': 12.0},
    speed_levels={
        ('A', 'J'): 3,    # Normal speed
        ('J', 'S1'): 5,   # Very fast (highway section)
        ('S1', 'S2'): 2,  # Slow (save energy between stations)
        ('S2', 'M'): 4,   # Fast
        ('M', 'B'): 3,    # Normal (approaching destination)
    },
    arrival_times={...},
    departure_times={...},
    soc_at_nodes={...}
)
```

**Important Notes:**

- If `speed_levels` is `None` or an edge is not specified, defaults to level 3 (Normal)
- Must specify speed level for every edge in the route for full control
- SOC calculations must account for speed-dependent energy consumption

## 🔄 Impact on Optimization

### Decision Variables (Updated)

The optimizer now has **4 types of decisions** per vehicle:

1. **Route Selection**: Which path to take (upper/lower)
2. **Charging Stations**: Where to charge
3. **Charging Amounts**: How much to charge at each station
4. **Speed Levels**: How fast to drive on each edge ← **NEW!**

### Example Decision Space

For a route with 5 edges:

- **Speed choices per edge**: 5 options
- **Total speed combinations**: 5^5 = 3,125 possibilities
- **Plus route, station, and charging decisions**: Huge search space!

### Strategic Trade-offs

```
Fast Driving Strategy:
✅ Less travel time
✅ Earlier arrival at stations (may avoid queues)
❌ Higher energy consumption
❌ More charging needed (longer charging time)
❌ May use expensive fast chargers

Slow Driving Strategy:
✅ Lower energy consumption
✅ Less charging needed (lower costs)
❌ More travel time
❌ Later arrival at stations (may face queues)
❌ Total journey time may still be longer
```

## 📈 Example Scenarios

### Scenario 1: Time-Critical Delivery

**Objective**: Minimize makespan

**Strategy**: Use fast speeds (levels 4-5) everywhere

- Accept higher energy costs
- Minimize total journey time
- May need more frequent/longer charging

### Scenario 2: Cost-Conscious Operation

**Objective**: Minimize charging cost

**Strategy**: Use slow speeds (levels 1-2) where possible

- Minimize energy consumption
- Reduce charging costs
- Accept longer travel times

### Scenario 3: Balanced Approach

**Objective**: Balance time and cost

**Strategy**: Mixed speeds based on conditions

- Fast on highways (level 4-5)
- Slow in cities (level 2-3)
- Normal elsewhere (level 3)
- Optimize based on route characteristics

### Scenario 4: Queue Avoidance

**Objective**: Avoid congested charging stations

**Strategy**: Adjust speeds to change arrival times

- Speed up to arrive before queue forms
- Slow down to arrive after queue clears
- Strategic timing based on other vehicles

## 🔧 Implementation Details

### Files Modified

1. **params.py**:

   - Added `SPEED_LEVELS`, `SPEED_TIME_MULTIPLIERS`, `SPEED_ENERGY_MULTIPLIERS`
   - Added `get_edge_time(edge, speed_level)` method
   - Added `get_edge_energy(edge, speed_level)` method
   - Added `get_all_speed_options(edge)` method

2. **objectives.py**:
   - Added `speed_levels: Dict[Tuple[str, str], int]` to `VehicleSolution`
   - Added `get_speed_level(edge)` method
   - Updated `_check_energy_balance()` to use speed-dependent energy
   - Added `_check_speed_levels()` constraint validation

### Backward Compatibility

✅ **Fully backward compatible!**

- Existing solutions without `speed_levels` still work
- Defaults to level 3 (Normal) - equivalent to old behavior
- No changes needed to existing code

### Constraint Checking

The `is_feasible()` method now validates:

1. ✅ Speed levels are in valid range [1, 5]
2. ✅ Energy balance uses correct speed-dependent energy
3. ✅ SOC trajectories are consistent with speed choices

## 📝 Best Practices

### For Manual Solution Creation

1. **Calculate energy carefully**: Use `params.get_edge_energy(edge, speed_level)`
2. **Calculate times carefully**: Use `params.get_edge_time(edge, speed_level)`
3. **Update SOC consistently**: Account for speed-dependent energy consumption
4. **Validate solution**: Always call `solution.is_feasible(verbose=True)`

### For Optimization Algorithms

1. **Encode speed levels**: Include in chromosome/solution representation
2. **Initialize randomly**: Random speed levels (1-5) for each edge
3. **Crossover carefully**: Ensure speed levels stay in valid range
4. **Mutation operator**: Change speed level ±1 or random
5. **Fitness evaluation**: Automatically uses speed-dependent values

## 🎮 Example: Running the Demo

```bash
python example_speed_levels.py
```

This demonstrates:

- All speed options for each edge
- Trade-off analysis (time vs. energy)
- Speed strategy comparison
- Creating solutions with different speeds

## 🚀 Next Steps for Optimization

### Genetic Algorithm Example

```python
def create_random_solution(params):
    """Create random solution with random speed levels."""
    vehicle_sol = VehicleSolution(...)

    # Randomly assign speed levels
    speed_levels = {}
    for i in range(len(route) - 1):
        edge = (route[i], route[i+1])
        speed_levels[edge] = random.randint(1, 5)  # Random speed

    vehicle_sol.speed_levels = speed_levels
    return vehicle_sol

def mutate_speed_levels(solution, mutation_rate=0.1):
    """Mutate speed levels in solution."""
    for vs in solution.vehicle_solutions:
        for edge in vs.speed_levels:
            if random.random() < mutation_rate:
                # Change speed by ±1 or random
                current = vs.speed_levels[edge]
                vs.speed_levels[edge] = max(1, min(5, current + random.choice([-1, 1])))
```

### Mixed Integer Linear Programming (MILP)

```python
# Binary variables for speed selection
# x[v,e,s] = 1 if vehicle v uses speed s on edge e
for v in vehicles:
    for e in edges:
        for s in [1, 2, 3, 4, 5]:
            x[v,e,s] = model.addVar(vtype=GRB.BINARY)

        # Exactly one speed per edge
        model.addConstr(sum(x[v,e,s] for s in [1,2,3,4,5]) == 1)

# Time calculation: sum over speeds
arrival_time[v,n] = departure_time[v,prev] + sum(
    x[v,e,s] * time_at_speed[e,s] for s in [1,2,3,4,5]
)
```

## 📚 Summary

### What's New

✅ 5 discrete speed levels for each edge  
✅ Speed-dependent time and energy calculations  
✅ Full constraint validation  
✅ Backward compatible  
✅ Well-documented with examples

### Key Benefits

🎯 More realistic modeling (drivers choose speeds)  
🎯 Additional optimization dimension  
🎯 Rich trade-off analysis (time vs. energy)  
🎯 Strategic timing control

### Optimization Impact

📊 Larger search space (5^edges combinations)  
📊 More complex trade-offs  
📊 Better solution quality potential  
📊 More realistic cost/time estimates

---

**Ready to optimize with speed choices! 🚗💨**
