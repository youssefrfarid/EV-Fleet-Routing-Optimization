# Discrete Speed Levels - Implementation Summary

## 🎯 Feature Overview

**Added**: Discrete speed level selection for traveling between nodes

**What it does**: Vehicles can now choose from **5 discrete speed levels** for each edge in their route, creating a trade-off between travel time and energy consumption.

## ✅ Implementation Complete

### Files Modified

1. **params.py**

   - ✅ Added `SPEED_LEVELS` dictionary (1-5 with names)
   - ✅ Added `SPEED_TIME_MULTIPLIERS` dictionary
   - ✅ Added `SPEED_ENERGY_MULTIPLIERS` dictionary
   - ✅ Added `get_edge_time(edge, speed_level)` method
   - ✅ Added `get_edge_energy(edge, speed_level)` method
   - ✅ Added `get_all_speed_options(edge)` method

2. **objectives.py**
   - ✅ Added `speed_levels: Dict[Tuple[str, str], int]` to `VehicleSolution`
   - ✅ Added `get_speed_level(edge)` method to `VehicleSolution`
   - ✅ Updated `_check_energy_balance()` to use speed-dependent energy
   - ✅ Added `_check_speed_levels()` constraint validation
   - ✅ Updated `is_feasible()` to call speed level validation

### Files Created

3. **example_speed_levels.py**

   - ✅ Comprehensive demonstration of speed levels feature
   - ✅ Shows all 5 speed options for each edge
   - ✅ Analyzes trade-offs between speeds
   - ✅ Compares different speed strategies

4. **SPEED_LEVELS_GUIDE.md**

   - ✅ Complete documentation and usage guide
   - ✅ Examples for manual solution creation
   - ✅ Examples for optimization algorithms
   - ✅ Best practices and implementation details

5. **test_speed_levels.py**
   - ✅ Unit tests for all speed level functionality
   - ✅ Tests validation and constraint checking
   - ✅ Tests backward compatibility

### Files Updated

6. **README.md**

   - ✅ Added speed levels to features list
   - ✅ Added new files to file structure
   - ✅ Added speed levels section to Key Concepts

7. **DECISION_VARIABLES_AND_CONSTRAINTS.md**
   - ✅ Added speed levels as decision variable #4
   - ✅ Updated summary tables
   - ✅ Added speed level validation constraint

## 📊 Speed Level Details

| Level | Name      | Time Multiplier | Energy Multiplier | Use Case                  |
| ----- | --------- | --------------- | ----------------- | ------------------------- |
| 1     | Very Slow | ×1.40           | ×0.75             | Maximum energy efficiency |
| 2     | Slow      | ×1.20           | ×0.90             | Good efficiency           |
| 3     | Normal    | ×1.00           | ×1.00             | **Default/Baseline**      |
| 4     | Fast      | ×0.85           | ×1.20             | Time-critical             |
| 5     | Very Fast | ×0.70           | ×1.50             | Maximum speed             |

### Physics Rationale

- **Air resistance**: Increases quadratically with speed
- **Energy consumption**: Higher at faster speeds due to aerodynamic drag
- **Time savings**: Linear reduction with increased speed
- **Trade-off**: Non-linear relationship creates optimization opportunity

## 🔧 Usage Examples

### Basic Usage

```python
from params import make_toy_params
from objectives import VehicleSolution, FleetSolution

params = make_toy_params()

# Create solution with speed choices
vehicle = VehicleSolution(
    vehicle_id=0,
    route=['A', 'J', 'S1', 'S2', 'M', 'B'],
    speed_levels={
        ('A', 'J'): 3,    # Normal
        ('J', 'S1'): 5,   # Very fast
        ('S1', 'S2'): 2,  # Slow
        ('S2', 'M'): 4,   # Fast
        ('M', 'B'): 3,    # Normal
    },
    charging_stations=['S1'],
    charging_amounts={'S1': 12.0},
    arrival_times={...},
    departure_times={...},
    soc_at_nodes={...}
)
```

### Query Speed Options

```python
# Get time and energy for specific speed
edge = ('A', 'J')
time = params.get_edge_time(edge, speed_level=5)  # Very Fast
energy = params.get_edge_energy(edge, speed_level=1)  # Very Slow

# Get all 5 options
options = params.get_all_speed_options(edge)
# Returns: [(1, "Very Slow", 21.0, 3.375), (2, "Slow", 18.0, 4.05), ...]
```

### For Optimization Algorithms

```python
import random

def generate_random_speed_levels(route):
    """Generate random speed levels for a route."""
    speed_levels = {}
    for i in range(len(route) - 1):
        edge = (route[i], route[i+1])
        speed_levels[edge] = random.randint(1, 5)
    return speed_levels

def mutate_speed(solution, mutation_rate=0.1):
    """Mutate speed levels in a solution."""
    for vs in solution.vehicle_solutions:
        if vs.speed_levels:
            for edge in vs.speed_levels:
                if random.random() < mutation_rate:
                    # Change by ±1 or random
                    current = vs.speed_levels[edge]
                    vs.speed_levels[edge] = max(1, min(5, current + random.choice([-1, 1])))
```

## ✅ Validation & Constraints

### Automatic Validation

The `is_feasible()` method now checks:

1. ✅ **Speed levels in valid range**: All speed levels must be in [1, 5]
2. ✅ **Energy balance with speeds**: SOC calculations use speed-dependent energy
3. ✅ **Consistent with route**: Speed levels only for edges in the route

### Error Messages

```python
solution.is_feasible(verbose=True)

# Examples of error messages:
# ❌ Vehicle 0: Invalid speed level 10 for edge ('A', 'J')
#    Speed level must be in [1, 2, 3, 4, 5]
#
# ❌ Vehicle 0: Energy balance violated at edge ('A', 'J')
#    Speed level: 5, Energy consumed: 6.750 kWh
#    Expected SOC at J: 0.500, Actual: 0.587
```

## 🔄 Backward Compatibility

✅ **Fully backward compatible!**

- Old solutions without `speed_levels` still work
- Defaults to level 3 (Normal) - equivalent to old behavior
- No changes required to existing code
- Existing examples continue to work

```python
# Old-style solution (still works)
vehicle = VehicleSolution(
    vehicle_id=0,
    route=['A', 'J', 'B'],
    charging_stations=[],
    charging_amounts={},
    arrival_times={...},
    departure_times={...},
    soc_at_nodes={...}
    # No speed_levels - defaults to 3
)
```

## 📈 Impact on Optimization

### Decision Space

**Before**: Route + Stations + Charging amounts
**Now**: Route + Stations + Charging amounts + **Speed levels**

For a route with 5 edges:

- Speed choices: 5^5 = **3,125 combinations**
- Total search space: **Massively expanded**

### Optimization Strategies

1. **Time-Critical**: Use fast speeds (4-5) everywhere

   - Pros: Minimize makespan
   - Cons: Higher energy costs

2. **Cost-Conscious**: Use slow speeds (1-2) everywhere

   - Pros: Minimize energy consumption and charging costs
   - Cons: Longer total journey time

3. **Mixed Strategy**: Adapt to conditions

   - Fast on highways
   - Slow in cities or near stations
   - Optimize based on terrain

4. **Queue Management**: Adjust speeds to avoid queues
   - Speed up to arrive before rush
   - Slow down to arrive after queue clears

## 🧪 Testing

Run tests to verify implementation:

```bash
# Comprehensive unit tests
python test_speed_levels.py

# Feature demonstration
python example_speed_levels.py
```

**All tests pass! ✅**

## 📚 Documentation

- **SPEED_LEVELS_GUIDE.md**: Complete feature documentation
- **example_speed_levels.py**: Working examples and demonstrations
- **README.md**: Updated with speed levels feature
- **DECISION_VARIABLES_AND_CONSTRAINTS.md**: Updated decision variables

## 🎯 Next Steps for Users

### For Manual Solution Creation

1. Decide on speed strategy (conservative, balanced, aggressive)
2. Set `speed_levels` dict for each edge
3. Calculate arrival times using `params.get_edge_time(edge, speed)`
4. Calculate SOC using `params.get_edge_energy(edge, speed)`
5. Validate with `solution.is_feasible(verbose=True)`

### For Optimization Algorithms

1. **Encoding**: Add speed level genes/variables to chromosome
2. **Initialization**: Random speed levels (1-5) for each edge
3. **Crossover**: Preserve speed level integrity during crossover
4. **Mutation**: Change speed levels (±1 or random)
5. **Evaluation**: System automatically uses speed-dependent values
6. **Fitness**: Objectives naturally account for speed choices

### For MILP Formulations

```python
# Binary variables: x[v,e,s] = 1 if vehicle v uses speed s on edge e
for v in vehicles:
    for e in edges:
        for s in [1, 2, 3, 4, 5]:
            x[v,e,s] = model.addVar(vtype=GRB.BINARY, name=f"speed_{v}_{e}_{s}")

        # Exactly one speed per edge
        model.addConstr(sum(x[v,e,s] for s in [1,2,3,4,5]) == 1)

# Time: sum(x[v,e,s] * time[e,s] for all s)
# Energy: sum(x[v,e,s] * energy[e,s] for all s)
```

## 🎉 Summary

✅ **Feature Complete**

- 5 discrete speed levels implemented
- Full constraint validation
- Backward compatible
- Well-documented
- Thoroughly tested

✅ **Ready for Optimization**

- Clear API for querying options
- Helper methods for calculations
- Integration with existing framework
- Examples for common use cases

✅ **Production Ready**

- All tests passing
- Comprehensive error handling
- Clear error messages
- Extensive documentation

---

**The discrete speed levels feature is fully implemented and ready to use! 🚗💨**
