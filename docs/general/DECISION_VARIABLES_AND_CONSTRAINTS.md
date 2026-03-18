# Decision Variables and Constraints

## Overview

This document identifies the **decision variables** (what the optimizer chooses) and **constraints** (what must be satisfied) for the EV Fleet Routing Optimization problem.

---

## 📊 DECISION VARIABLES

Decision variables are what your optimization algorithm must determine. They represent the choices that define a solution.

### 1. Route Selection Variables

**What**: Which route does each vehicle take?

**Mathematical Notation**:

```
r_i ∈ {Upper, Lower}  for each vehicle i
```

**In Code (VehicleSolution)**:

- **Location**: `objectives.py`, class `VehicleSolution`
- **Attribute**: `route: List[str]`
- **Example**: `['A', 'J', 'S1', 'S2', 'M', 'B']` (Upper route)
- **Example**: `['A', 'J', 'S3', 'M', 'B']` (Lower route)

**Possible Values**:

```python
# Upper route options:
route = ['A', 'J', 'S1', 'S2', 'M', 'B']     # Via both S1 and S2

# Lower route options:
route = ['A', 'J', 'S3', 'M', 'B']           # Via S3
```

---

### 2. Charging Station Selection

**What**: At which stations does each vehicle charge?

**Mathematical Notation**:

```
x_{i,s} ∈ {0, 1}  for each vehicle i and station s
x_{i,s} = 1 if vehicle i charges at station s, 0 otherwise
```

**In Code (VehicleSolution)**:

- **Location**: `objectives.py`, class `VehicleSolution`
- **Attribute**: `charging_stations: List[str]`
- **Example**: `['S1', 'S2']` means vehicle charges at both S1 and S2
- **Example**: `['S3']` means vehicle only charges at S3
- **Example**: `[]` means vehicle doesn't charge anywhere

**Code Reference**:

```python
# From example_objectives.py, line 22
charging_stations=['S1']  # Decision: charge only at S1

# From example_objectives.py, line 40
charging_stations=['S1', 'S2']  # Decision: charge at both stations
```

---

### 3. Charging Amounts

**What**: How much energy (kWh) to charge at each selected station?

**Mathematical Notation**:

```
E_{i,s} ≥ 0  for each vehicle i at station s
E_{i,s} = energy charged (kWh) by vehicle i at station s
```

**In Code (VehicleSolution)**:

- **Location**: `objectives.py`, class `VehicleSolution`
- **Attribute**: `charging_amounts: Dict[str, float]`
- **Example**: `{'S1': 12.0, 'S2': 8.0}` means charge 12 kWh at S1, 8 kWh at S2

**Code Reference**:

```python
# From example_objectives.py, line 23
charging_amounts={'S1': 12.0}  # Decision: charge 12 kWh at S1

# From example_objectives.py, line 41
charging_amounts={'S1': 10.0, 'S2': 8.0}  # Decision: 10 kWh at S1, 8 at S2
```

**Impact on Solution**:

- Determines charging cost (more kWh = higher cost)
- Determines charging time (more kWh = longer time)
- Affects SOC at subsequent nodes

---

### 4. Speed Level Selection (NEW! ⚡)

**What**: How fast does each vehicle travel on each edge?

**Mathematical Notation**:

```
s_{i,e} ∈ {1, 2, 3, 4, 5}  for each vehicle i and edge e
s_{i,e} = speed level chosen by vehicle i on edge e
```

**Speed Level Definitions**:

```
1 = Very Slow  (Time ×1.40, Energy ×0.75) - most efficient
2 = Slow       (Time ×1.20, Energy ×0.90) - efficient
3 = Normal     (Time ×1.00, Energy ×1.00) - baseline [DEFAULT]
4 = Fast       (Time ×0.85, Energy ×1.20) - less efficient
5 = Very Fast  (Time ×0.70, Energy ×1.50) - least efficient
```

**In Code (VehicleSolution)**:

- **Location**: `objectives.py`, class `VehicleSolution`
- **Attribute**: `speed_levels: Dict[Tuple[str, str], int]`
- **Example**: `{('A', 'J'): 3, ('J', 'S1'): 5, ('S1', 'S2'): 2}`
- **Default**: If not specified or None, defaults to level 3 (Normal)

**Code Reference**:

```python
# Example from SPEED_LEVELS_GUIDE.md
speed_levels = {
    ('A', 'J'): 3,    # Normal speed on first segment
    ('J', 'S1'): 5,   # Very fast on highway
    ('S1', 'S2'): 2,  # Slow to save energy between stations
    ('S2', 'M'): 4,   # Fast
    ('M', 'B'): 3,    # Normal approaching destination
}

vehicle = VehicleSolution(
    vehicle_id=0,
    route=['A', 'J', 'S1', 'S2', 'M', 'B'],
    speed_levels=speed_levels,  # NEW decision variable
    ...
)
```

**Impact on Solution**:

- **Travel Time**: Higher speed = less time on edge
- **Energy Consumption**: Higher speed = more energy (air resistance)
- **Arrival Times**: Affects when vehicle reaches charging stations (queue impact)
- **Charging Needs**: More energy used = more charging required
- **Total Cost**: Indirect impact through energy consumption

**Trade-offs**:

```
Fast Speeds (4-5):
✅ Less travel time
✅ Earlier arrivals (may avoid queues)
❌ Higher energy consumption
❌ More charging needed

Slow Speeds (1-2):
✅ Lower energy consumption
✅ Less charging needed → lower cost
❌ More travel time
❌ Later arrivals (may encounter queues)
```

**Physics Basis**:

- Air resistance increases quadratically with speed
- Faster speeds consume disproportionately more energy
- Realistic multipliers based on EV physics

---

### 5. Timing Variables (Derived)

**What**: When does each vehicle arrive/depart at each node?

**Mathematical Notation**:

```
t_{i,n}^{arrival} ≥ 0    (arrival time at node n for vehicle i)
t_{i,n}^{departure} ≥ 0  (departure time at node n for vehicle i)
t_{i,s}^{charging_start} ≥ 0  (NEW: when charging actually starts at station s)
```

**In Code (VehicleSolution)**:

- **Location**: `objectives.py`, class `VehicleSolution`
- **Attributes**:
  - `arrival_times: Dict[str, float]`
  - `departure_times: Dict[str, float]`
  - `charging_start_times: Dict[str, float]` (NEW - optional, for queue modeling)
- **Example**: `arrival_times={'A': 0, 'J': 15, 'S1': 27, 'B': 68}`

**Code Reference with Queue Modeling**:

```python
# From example_objectives.py - Vehicle with queue waiting
arrival_times={'A': 0, 'J': 15, 'S3': 24, 'M': 70, 'B': 83}
charging_start_times={'S3': 38}  # NEW: Starts charging at 38 (waited 14 min)
departure_times={'A': 0, 'J': 15, 'S3': 56, 'M': 70, 'B': 83}
#                                    ^^  ^^  ^^
#                      Arrives 24, Starts charging 38, Departs 56
#                      Queue wait: 38-24 = 14 min
#                      Charging time: 56-38 = 18 min
```

**Queue Behavior at Stations**:

- `arrival_time[station]`: When vehicle arrives and joins queue
- `charging_start_time[station]`: When vehicle gets a plug and starts charging
- `departure_time[station]`: When charging completes and vehicle leaves

**Queue wait time** = charging_start_time - arrival_time  
**Actual charging time** = departure_time - charging_start_time  
**Total time at station** = departure_time - arrival_time

**Note**: These are **derived** from route, charging amounts, and physics:

- `arrival_time[next] = departure_time[current] + travel_time[edge]`
- `departure_time[station] = charging_start_time[station] + charging_time`
- If no queue: `charging_start_time[station] = arrival_time[station]`
- Charging time calculated in `params.py`, method `charge_time_seconds()`
- Queue processing automated in `objectives.py`, function `process_station_queues()`

---

### 5. State of Charge (SOC) at Nodes (Derived)

**What**: Battery level when arriving at each node?

**Mathematical Notation**:

```
SOC_{i,n} ∈ [0.10, 1]  for each vehicle i at node n
```

**In Code (VehicleSolution)**:

- **Location**: `objectives.py`, class `VehicleSolution`
- **Attribute**: `soc_at_nodes: Dict[str, float]`
- **Example**: `soc_at_nodes={'A': 0.70, 'J': 0.59, 'S1': 0.50, 'B': 0.54}`

**Code Reference**:

```python
# From example_objectives.py, line 26
soc_at_nodes={'A': 0.70, 'J': 0.59, 'S1': 0.50, 'S2': 0.74, 'M': 0.65, 'B': 0.54}
#              ^^^ Initial    ^^^ After travel  ^^^ After charging
```

**Note**: SOC is **derived** from initial SOC, energy consumption, and charging:

- `SOC[next] = SOC[current] - energy_consumed[edge] / battery_capacity`
- `SOC[after_charge] = SOC[before_charge] + energy_charged / battery_capacity`

---

## 🔒 CONSTRAINTS

Constraints are rules that must be satisfied for a solution to be feasible.

### 1. Route Feasibility Constraint

**What**: Vehicle must follow a valid path from A to B.

**Mathematical Formulation**:

```
route[0] = 'A'  (must start at origin)
route[-1] = 'B'  (must end at destination)
All consecutive nodes must be connected by edges
```

**Where Enforced**:

- **Location**: `objectives.py`, lines 203-225
- **Method**: `FleetSolution._check_route_feasibility()`

**Implementation**: ✅ **FULLY ENFORCED**

**Code**:

```python
# objectives.py, lines 203-225
def _check_route_feasibility(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
    # Must start at A
    if not vs.route or vs.route[0] != 'A':
        if verbose:
            print(f"❌ Vehicle {vehicle_idx}: Route must start at 'A'")
        return False

    # Must end at B
    if vs.route[-1] != 'B':
        if verbose:
            print(f"❌ Vehicle {vehicle_idx}: Route must end at 'B'")
        return False

    # Check consecutive nodes are connected
    for i in range(len(vs.route) - 1):
        edge = (vs.route[i], vs.route[i+1])
        if edge not in self.params.edges_time_min:
            if verbose:
                print(f"❌ Vehicle {vehicle_idx}: Invalid edge {edge}")
            return False

    return True
```

**What it checks**:

- Route starts at 'A'
- Route ends at 'B'
- All consecutive nodes are connected by valid edges

---

### 2. SOC Bounds Constraint

**What**: Battery level must stay within valid range.

**Mathematical Formulation**:

```
0.10 ≤ SOC_{i,n} ≤ 1  for all vehicles i, all nodes n
```

**Where Enforced**:

- **Location**: `objectives.py`, lines 227-234
- **Method**: `FleetSolution._check_soc_bounds()`

**Implementation**: ✅ **FULLY ENFORCED**

**Code**:

```python
# objectives.py, lines 227-235
def _check_soc_bounds(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
    min_soc = 0.10
    tolerance = 1e-6
    for node, soc in vs.soc_at_nodes.items():
        if soc < min_soc - tolerance or soc > 1.0 + tolerance:
            if verbose:
                print(f"❌ Vehicle {vehicle_idx}: SOC at '{node}' = {soc:.3f} (must be in [0.10, 1.00])")
            return False
    return True
```

**Physical Meaning**:

- SOC = 0.10: Minimum safety reserve (10%) enforced for driveability
- SOC = 1: Battery completely full (100%)
- Violating this means infeasible solution

---

### 3. Energy Balance Constraint

**What**: SOC changes must be consistent with energy consumed and charged.

**Mathematical Formulation**:

```
SOC_{i,n+1} = SOC_{i,n} - (E_consumed[edge] / B_i) + (E_charged[n] / B_i)

Where:
- E_consumed = energy used traveling the edge (from params.edges_energy_kwh)
- E_charged = energy charged at node n (if it's a charging station)
- B_i = battery capacity of vehicle i
```

**Where Enforced**:

- **Location**: `objectives.py`, lines 236-268
- **Method**: `FleetSolution._check_energy_balance()`

**Implementation**: ✅ **FULLY ENFORCED**

**Code**:

```python
# objectives.py, lines 236-268
def _check_energy_balance(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
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

        # Subtract energy consumed on edge
        edge = (current_node, next_node)
        energy_consumed = self.params.edges_energy_kwh[edge]
        soc_expected = soc_after_charge - (energy_consumed / battery_kwh)

        # Check consistency
        soc_actual = vs.soc_at_nodes.get(next_node, 0.0)
        if abs(soc_expected - soc_actual) > tolerance:
            if verbose:
                print(f"❌ Vehicle {vehicle_idx}: Energy balance violated at edge {edge}")
            return False

    return True
```

**What it checks**:

- SOC changes are consistent with energy consumed traveling
- SOC increases properly when charging
- Tolerance of 0.0001 allows for numerical precision errors

---

### 4. Station Capacity Constraint

**What**: Number of vehicles charging simultaneously cannot exceed available plugs.

**Mathematical Formulation**:

```
∑_{i: charging at s during time t} 1 ≤ Capacity_s  for all stations s, all times t
```

**Where Enforced**:

- **Location**: `objectives.py`, lines 327-365
- **Method**: `FleetSolution._check_station_capacity()`

**Implementation**: ✅ **FULLY ENFORCED**

**Parameter Location**:

```python
# params.py, line 75
station_plugs: Dict[str, int] = field(default_factory=dict)

# Example from make_toy_params(), line 440
station_plugs={"S1": 2, "S2": 1, "S3": 1}
```

**Code**:

```python
# objectives.py, lines 327-365
def _check_station_capacity(self, verbose: bool) -> bool:
    all_stations = set(self.params.upper_stations + self.params.lower_stations)

    for station in all_stations:
        # Collect all charging events at this station
        events = []
        for vs in self.vehicle_solutions:
            if station in vs.charging_stations:
                arrival = vs.arrival_times.get(station, 0.0)
                departure = vs.departure_times.get(station, 0.0)
                events.append((arrival, 1, vs.vehicle_id))      # +1 vehicle arrives
                events.append((departure, -1, vs.vehicle_id))   # -1 vehicle departs

        if not events:
            continue  # No vehicles use this station

        # Sort by time and check max concurrent usage
        events.sort(key=lambda x: (x[0], -x[1]))  # Arrivals before departures at same time
        current_usage = 0
        max_usage = 0

        for time, delta, _ in events:
            current_usage += delta
            max_usage = max(max_usage, current_usage)

        # Check against capacity
        capacity = self.params.station_plugs.get(station, 0)
        if max_usage > capacity:
            if verbose:
                print(f"❌ Station capacity violated at '{station}'")
                print(f"   Max concurrent: {max_usage}, Available plugs: {capacity}")
            return False

    return True
```

**How it works**:

- Tracks **CHARGING START/END events** (when plugs are actually occupied)
- Uses `charging_start_times` if provided (queue-aware)
- Falls back to `arrival_times` if no queue tracking (backward compatible)
- Sorts events chronologically (departures before arrivals at same time to free plugs first)
- Counts concurrent **CHARGING** vehicles (not just vehicles at station)
- Compares peak usage against plug capacity

**Queue-Aware Enhancement**:
The constraint checker now distinguishes between:

- **Being at station**: arrival_time → departure_time (includes queue waiting)
- **Occupying a plug**: charging_start_time → departure_time (actual charging only)

Only plug occupation counts toward capacity constraint. This allows multiple vehicles to be at a station with only a subset actually charging.

---

### 5. Time Consistency Constraint

**What**: Departure time must be after or equal to arrival time.

**Mathematical Formulation**:

```
t_{i,n}^{departure} ≥ t_{i,n}^{arrival}  for all vehicles i, nodes n
```

**Where Enforced**:

- **Location**: `objectives.py`, lines 270-282
- **Method**: `FleetSolution._check_time_consistency()`

**Implementation**: ✅ **FULLY ENFORCED**

**Code**:

```python
# objectives.py, lines 270-282
def _check_time_consistency(self, vs: VehicleSolution, verbose: bool, vehicle_idx: int) -> bool:
    for node in vs.route:
        arrival = vs.arrival_times.get(node, 0.0)
        departure = vs.departure_times.get(node, 0.0)

        if departure < arrival - 1e-6:  # Small tolerance for floating point
            if verbose:
                print(f"❌ Vehicle {vehicle_idx}: Time inconsistency at '{node}'")
                print(f"   Arrival: {arrival:.2f}, Departure: {departure:.2f}")
            return False

    return True
```

**What it checks**:

- Vehicles don't depart before arriving at any node
- Small tolerance (1e-6) for floating-point precision errors

---

### 6. Minimum SOC at Destination (Optional)

**What**: Vehicle should reach destination with minimum battery level.

**Mathematical Formulation**:

```
SOC_{i,B} ≥ SOC_min  for all vehicles i
```

**Where Enforced**:

- **Currently**: ⚠️ **NOT ENFORCED**
- **Typical Value**: SOC_min = 0.1 or 0.2 (10-20% reserve)

**How to Add**:

```python
# In params.py, add parameter:
soc_min_destination: float = 0.1  # Minimum 10% at destination

# In objectives.py, check in is_feasible():
if vs.soc_at_nodes['B'] < self.params.soc_min_destination:
    return False
```

---

### 7. Maximum Charging Constraint

**What**: Cannot charge more than battery capacity allows.

**Mathematical Formulation**:

```
SOC_{i,n} + (E_charged / B_i) ≤ 1  for all charging events
```

**Where Enforced**:

- **Currently**: Implicitly through SOC bounds (constraint #2)
- **Better**: Check explicitly during charging

**How to Check**:

```python
def validate_charging_limits(vehicle_sol, params):
    """Check charging doesn't exceed battery capacity"""
    battery_kwh = params.battery_kwh[vehicle_sol.vehicle_id]

    for station in vehicle_sol.charging_stations:
        soc_before = vehicle_sol.soc_at_nodes[station]
        energy_charged = vehicle_sol.charging_amounts[station]
        soc_after = soc_before + (energy_charged / battery_kwh)

        if soc_after > 1.0:
            return False  # Tried to overcharge

    return True
```

---

### 8. Non-Negativity Constraints

**What**: Certain variables must be non-negative.

**Mathematical Formulation**:

```
E_{i,s} ≥ 0  (charging amounts)
t_{i,n} ≥ 0  (times)
SOC_{i,n} ≥ 0  (already covered in constraint #2)
```

**Where Enforced**:

- **Currently**: Partially (through data types and construction)
- **Should be**: Explicitly validated

---

## 📋 SUMMARY TABLE

| **Decision Variable** | **Location in Code**                   | **Example Value**               | **Type**         |
| --------------------- | -------------------------------------- | ------------------------------- | ---------------- |
| Route selection       | `VehicleSolution.route`                | `['A','J','S1','S2','M','B']`   | List[str]        |
| **Speed levels** 🆕   | `VehicleSolution.speed_levels`         | `{('A','J'): 3, ('J','S1'): 5}` | Dict[Edge, int]  |
| Charging stations     | `VehicleSolution.charging_stations`    | `['S1', 'S2']`                  | List[str]        |
| Charging amounts      | `VehicleSolution.charging_amounts`     | `{'S1': 12.0}`                  | Dict[str, float] |
| Arrival times         | `VehicleSolution.arrival_times`        | `{'A': 0, 'B': 68}`             | Dict[str, float] |
| Departure times       | `VehicleSolution.departure_times`      | `{'A': 0, 'B': 68}`             | Dict[str, float] |
| Charging start times  | `VehicleSolution.charging_start_times` | `{'S1': 30}` (queue-aware)      | Dict[str, float] |
| SOC at nodes          | `VehicleSolution.soc_at_nodes`         | `{'A': 0.7, 'B': 0.54}`         | Dict[str, float] |

| **Constraint**              | **Status**      | **Location**                             | **Mathematical Form**                                |
| --------------------------- | --------------- | ---------------------------------------- | ---------------------------------------------------- |
| Route feasibility           | ✅ **ENFORCED** | `objectives.py:_check_route_feasibility` | `route[0]='A'`, `route[-1]='B'`, valid edges         |
| SOC bounds                  | ✅ **ENFORCED** | `objectives.py:_check_soc_bounds`        | `0.10 ≤ SOC ≤ 1`                                     |
| Energy balance              | ✅ **ENFORCED** | `objectives.py:_check_energy_balance`    | `SOC_{n+1} = SOC_n - E_consumed(speed) + charged` 🆕 |
| Station capacity            | ✅ **ENFORCED** | `objectives.py:_check_station_capacity`  | `concurrent_vehicles ≤ plugs`                        |
| Time consistency            | ✅ **ENFORCED** | `objectives.py:_check_time_consistency`  | `departure ≥ arrival`                                |
| Charging limits             | ✅ **ENFORCED** | `objectives.py:_check_charging_limits`   | `SOC + charged ≤ 1`                                  |
| Non-negativity              | ✅ **ENFORCED** | `objectives.py:_check_non_negativity`    | `E ≥ 0`, `t ≥ 0`                                     |
| **Speed level validity** 🆕 | ✅ **ENFORCED** | `objectives.py:_check_speed_levels`      | `speed ∈ {1,2,3,4,5}`                                |
| Min SOC at dest             | ⚠️ Optional     | Not implemented                          | `SOC_B ≥ SOC_min` (can be added if needed)           |

**Legend**:

- ✅ Fully enforced in code
- ⚠️ Partially enforced or implicit
- ❌ Not currently enforced
- 🆕 New feature (speed levels)

---

## ✅ ALL CONSTRAINTS IMPLEMENTED

All essential constraints are now **FULLY ENFORCED** in `objectives.py`:

### Main Method: `is_feasible(verbose=False, return_reason=False)`

```python
# objectives.py, lines 152-205
def is_feasible(self, verbose: bool = False, return_reason: bool = False):
    """Comprehensive feasibility check with all constraints"""

    def make_response(feasible: bool, code: int, message: str):
        ...
        return (feasible, code, message) if return_reason else feasible

    # Check each vehicle individually
    for i, vs in enumerate(self.vehicle_solutions):
        if not self._check_route_feasibility(vs, verbose, i):
            return make_response(False, 1, "Route infeasible")
        if not self._check_soc_bounds(vs, verbose, i):
            return make_response(False, 2, "SOC bounds violated")
        if not self._check_energy_balance(vs, verbose, i):
            return make_response(False, 3, "Energy balance violated")
        if not self._check_time_consistency(vs, verbose, i):
            return make_response(False, 4, "Time consistency violated")
        if not self._check_charging_limits(vs, verbose, i):
            return make_response(False, 5, "Charging limits exceeded")
        if not self._check_non_negativity(vs, verbose, i):
            return make_response(False, 6, "Negative value encountered")

    # Check fleet-wide constraints
    if not self._check_station_capacity(verbose):
        return make_response(False, 8, "Station capacity violated")

    return make_response(True, 0, "Feasible")
```

### Usage Example

```python
# Check if solution is feasible
if solution.is_feasible():
    print("✓ Solution is valid!")
else:
    print("✗ Solution violates constraints")

# Get detailed violation information
feasible, code, reason = solution.is_feasible(return_reason=True)
print(feasible, code, reason)
# Optionally still print verbose diagnostics
solution.is_feasible(verbose=True)
```

### Diagnostic Codes

| Code | Meaning                          |
| ---- | -------------------------------- |
| 0    | Feasible                         |
| 1    | Route infeasible                 |
| 2    | SOC bounds violated              |
| 3    | Energy balance violated          |
| 4    | Time consistency violated        |
| 5    | Charging limits exceeded         |
| 6    | Negative value encountered       |
| 7    | Invalid speed level selection    |
| 8    | Station capacity violated        |

### Optional Future Additions

If needed, you can add:

1. **Minimum SOC at destination**:

```python
# In params.py
soc_min_destination: float = 0.1  # Reserve 10% battery

# In objectives.py, add to is_feasible():
if vs.soc_at_nodes['B'] < self.params.soc_min_destination:
    return False
```

2. **Maximum waiting time** (to avoid excessive delays)
3. **Time windows** (must arrive within specified periods)
4. **Route restrictions** (certain vehicles can only use certain paths)

---

## 🎯 FOR OPTIMIZATION ALGORITHM DEVELOPERS

When building your optimization algorithm:

### Primary Decision Variables (What to Optimize)

1. **Route choice** for each vehicle (upper/lower branch)
2. **Which stations** to visit
3. **How much to charge** at each station

### Derived Variables (Computed from decisions)

1. **Timing** (arrival/departure) - computed from route and charging
2. **Charging start times** - computed automatically via `process_station_queues()` (handles FIFO queue)
3. **SOC trajectory** - computed from initial SOC, consumption, and charging

### Queue Processing Automation

Use the **`process_station_queues()`** helper to automatically compute:

- When each vehicle starts charging (based on FIFO)
- Queue waiting times at each station
- Updated departure times including queue wait

```python
from objectives import process_station_queues

# Your algorithm only needs to specify:
# - route, arrival_times, charging_amounts

solution = your_optimization_algorithm(params)

# Automatically handle queue logic
solution = process_station_queues(solution, params)
# Now charging_start_times are computed!
```

### Constraints to Enforce

1. **Must enforce**: SOC bounds, route feasibility, energy balance
2. **Automatically enforced**: Station capacity (via queue processing)
3. **Should enforce**: Time consistency
4. **Optional**: Minimum destination SOC, charging rate limits

### Objectives to Minimize

1. **Makespan**: `max(completion_time_i)`
2. **Total Cost**: `sum(charged_kwh_i × price)`
3. **Weighted**: `w_time × makespan + w_cost × total_cost`

### Testing Your Solutions

Use the interactive simulation to visually verify:

```python
from simulation_gui import simulate_solution
simulate_solution(your_solution, params)
# Watch vehicles move, queues form, and charging happen in real-time!
```

---

## 📚 REFERENCES IN CODE

**Decision Variables Defined**: `objectives.py`, lines 16-47 (VehicleSolution class)

**Constraints Checked**: `objectives.py`, lines 122-144 (is_feasible method)

**Objective Functions**: `objectives.py`, lines 148-183

**Parameters**: `params.py`, lines 48-142 (SingleForkParams class)

**Example Solutions**: `example_objectives.py`, lines 11-103 (create_sample_solution function)
