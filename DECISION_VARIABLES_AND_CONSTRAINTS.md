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

### 4. Timing Variables (Derived)

**What**: When does each vehicle arrive/depart at each node?

**Mathematical Notation**:
```
t_{i,n}^{arrival} ≥ 0    (arrival time at node n for vehicle i)
t_{i,n}^{departure} ≥ 0  (departure time at node n for vehicle i)
```

**In Code (VehicleSolution)**:
- **Location**: `objectives.py`, class `VehicleSolution`
- **Attributes**: 
  - `arrival_times: Dict[str, float]`
  - `departure_times: Dict[str, float]`
- **Example**: `arrival_times={'A': 0, 'J': 15, 'S1': 27, 'B': 68}`

**Code Reference**:
```python
# From example_objectives.py, lines 24-25
arrival_times={'A': 0, 'J': 15, 'S1': 27, 'S2': 45, 'M': 55, 'B': 68}
departure_times={'A': 0, 'J': 15, 'S1': 42, 'S2': 45, 'M': 55, 'B': 68}
#                                       ^^           ^^
#                                       Note: 42 > 27 at S1 (charging time)
```

**Note**: These are **derived** from route, charging amounts, and physics:
- `arrival_time[next] = departure_time[current] + travel_time[edge]`
- `departure_time[station] = arrival_time[station] + charging_time`
- Charging time calculated in `params.py`, method `charge_time_seconds()`

---

### 5. State of Charge (SOC) at Nodes (Derived)

**What**: Battery level when arriving at each node?

**Mathematical Notation**:
```
SOC_{i,n} ∈ [0, 1]  for each vehicle i at node n
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
- **Currently**: Manually when constructing solutions
- **Should check**: In `FleetSolution.is_feasible()` method

**Code Location**:
```python
# objectives.py, line 137-140
def is_feasible(self) -> bool:
    for vs in self.vehicle_solutions:
        # Check if route ends at 'B'
        if vs.route[-1] != 'B':
            return False
```

**Current Implementation**: ⚠️ **Partially Enforced**
- Checks ending at 'B'
- Does NOT check starting at 'A'
- Does NOT check edge connectivity

**Recommendation**: Add validation:
```python
# Check starts at A
if vs.route[0] != 'A':
    return False

# Check consecutive nodes are connected
for i in range(len(vs.route) - 1):
    edge = (vs.route[i], vs.route[i+1])
    if edge not in params.edges_time_min:
        return False
```

---

### 2. SOC Bounds Constraint

**What**: Battery level must stay within valid range.

**Mathematical Formulation**:
```
0 ≤ SOC_{i,n} ≤ 1  for all vehicles i, all nodes n
```

**Where Enforced**:
- **Location**: `objectives.py`, lines 141-143
- **Method**: `FleetSolution.is_feasible()`

**Code**:
```python
# Check if all SOC values are valid
if not all(0.0 <= soc <= 1.0 for soc in vs.soc_at_nodes.values()):
    return False
```

**Current Implementation**: ✅ **Fully Enforced**

**Physical Meaning**:
- SOC = 0: Battery completely empty (vehicle stranded)
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
- **Currently**: ⚠️ **NOT EXPLICITLY CHECKED**
- **Should be**: Either enforced during solution construction or validated

**Code Location**: Currently not validated in code

**How It Should Work**:
```python
def validate_energy_balance(vehicle_sol, params):
    """Check energy balance along route"""
    battery_kwh = params.battery_kwh[vehicle_sol.vehicle_id]
    
    for i in range(len(vehicle_sol.route) - 1):
        current_node = vehicle_sol.route[i]
        next_node = vehicle_sol.route[i + 1]
        
        # Get current SOC
        soc_current = vehicle_sol.soc_at_nodes[current_node]
        
        # Add charging if current node is a charging station
        if current_node in vehicle_sol.charging_stations:
            charged_kwh = vehicle_sol.charging_amounts[current_node]
            soc_after_charge = soc_current + (charged_kwh / battery_kwh)
        else:
            soc_after_charge = soc_current
        
        # Subtract energy consumed on edge
        edge = (current_node, next_node)
        energy_consumed = params.edges_energy_kwh[edge]
        soc_next = soc_after_charge - (energy_consumed / battery_kwh)
        
        # Check consistency
        expected_soc = vehicle_sol.soc_at_nodes[next_node]
        if abs(soc_next - expected_soc) > 1e-6:
            return False
    
    return True
```

**Recommendation**: Add this validation to `FleetSolution.is_feasible()`

---

### 4. Station Capacity Constraint

**What**: Number of vehicles charging simultaneously cannot exceed available plugs.

**Mathematical Formulation**:
```
∑_{i: charging at s during time t} 1 ≤ Capacity_s  for all stations s, all times t
```

**Where Enforced**:
- **Currently**: ⚠️ **NOT ENFORCED IN CODE**
- **Should be**: Checked when vehicles have overlapping charging times

**Code Location**: Not currently implemented

**Parameter Location**:
```python
# params.py, line 75
station_plugs: Dict[str, int] = field(default_factory=dict)

# Example from make_toy_params(), line 440
station_plugs={"S1": 3, "S2": 2, "S3": 2}
#              S1 has 3 plugs, S2 and S3 have 2 plugs each
```

**How to Check**:
```python
def check_capacity_constraints(solution):
    """Check if station capacity constraints are satisfied"""
    # For each station
    all_stations = set(solution.params.upper_stations + solution.params.lower_stations)
    
    for station in all_stations:
        # Collect all charging events at this station
        events = []
        for vs in solution.vehicle_solutions:
            if station in vs.charging_stations:
                arrival = vs.arrival_times[station]
                departure = vs.departure_times[station]
                events.append((arrival, 1))     # +1 vehicle arrives
                events.append((departure, -1))  # -1 vehicle departs
        
        # Sort by time and check max concurrent usage
        events.sort()
        current_usage = 0
        max_usage = 0
        
        for time, delta in events:
            current_usage += delta
            max_usage = max(max_usage, current_usage)
        
        # Check against capacity
        capacity = solution.params.station_plugs[station]
        if max_usage > capacity:
            return False  # Constraint violated
    
    return True
```

**Recommendation**: Implement this check and call from `FleetSolution.is_feasible()`

---

### 5. Time Consistency Constraint

**What**: Departure time must be after or equal to arrival time.

**Mathematical Formulation**:
```
t_{i,n}^{departure} ≥ t_{i,n}^{arrival}  for all vehicles i, nodes n
```

**Where Enforced**:
- **Currently**: ⚠️ **NOT EXPLICITLY CHECKED**
- **Should be**: Validated for all nodes

**How to Check**:
```python
def validate_time_consistency(vehicle_sol):
    """Check time consistency"""
    for node in vehicle_sol.route:
        arrival = vehicle_sol.arrival_times.get(node, 0)
        departure = vehicle_sol.departure_times.get(node, 0)
        
        if departure < arrival:
            return False  # Violation: can't depart before arriving
    
    return True
```

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

| **Decision Variable** | **Location in Code** | **Example Value** | **Type** |
|----------------------|---------------------|-------------------|----------|
| Route selection | `VehicleSolution.route` | `['A','J','S1','S2','M','B']` | List[str] |
| Charging stations | `VehicleSolution.charging_stations` | `['S1', 'S2']` | List[str] |
| Charging amounts | `VehicleSolution.charging_amounts` | `{'S1': 12.0}` | Dict[str, float] |
| Arrival times | `VehicleSolution.arrival_times` | `{'A': 0, 'B': 68}` | Dict[str, float] |
| Departure times | `VehicleSolution.departure_times` | `{'A': 0, 'B': 68}` | Dict[str, float] |
| SOC at nodes | `VehicleSolution.soc_at_nodes` | `{'A': 0.7, 'B': 0.54}` | Dict[str, float] |

| **Constraint** | **Status** | **Location** | **Mathematical Form** |
|----------------|-----------|--------------|----------------------|
| Route feasibility | ⚠️ Partial | `objectives.py:137-140` | `route[0]='A'`, `route[-1]='B'` |
| SOC bounds | ✅ Full | `objectives.py:141-143` | `0 ≤ SOC ≤ 1` |
| Energy balance | ❌ Missing | Not implemented | `SOC_{n+1} = SOC_n - consumed + charged` |
| Station capacity | ❌ Missing | Not implemented | `concurrent_vehicles ≤ plugs` |
| Time consistency | ❌ Missing | Not implemented | `departure ≥ arrival` |
| Min SOC at dest | ❌ Missing | Not implemented | `SOC_B ≥ SOC_min` |
| Max charging | ⚠️ Implicit | Via SOC bounds | `SOC + charged ≤ 1` |
| Non-negativity | ⚠️ Implicit | Via types | `E ≥ 0`, `t ≥ 0` |

**Legend**:
- ✅ Fully enforced in code
- ⚠️ Partially enforced or implicit
- ❌ Not currently enforced

---

## 🔧 RECOMMENDED ADDITIONS

To make the problem formulation complete, add these validations to `objectives.py`:

```python
def is_feasible(self) -> bool:
    """Enhanced feasibility check with all constraints"""
    for vs in self.vehicle_solutions:
        # 1. Route feasibility
        if vs.route[0] != 'A' or vs.route[-1] != 'B':
            return False
        
        # 2. SOC bounds (already implemented)
        if not all(0.0 <= soc <= 1.0 for soc in vs.soc_at_nodes.values()):
            return False
        
        # 3. Energy balance (NEW)
        if not self._validate_energy_balance(vs):
            return False
        
        # 4. Time consistency (NEW)
        if not self._validate_time_consistency(vs):
            return False
        
        # 5. Charging limits (NEW)
        if not self._validate_charging_limits(vs):
            return False
    
    # 6. Station capacity (NEW)
    if not self._check_capacity_constraints():
        return False
    
    return True
```

---

## 🎯 FOR OPTIMIZATION ALGORITHM DEVELOPERS

When building your optimization algorithm:

### Primary Decision Variables (What to Optimize)
1. **Route choice** for each vehicle (upper/lower branch)
2. **Which stations** to visit
3. **How much to charge** at each station

### Derived Variables (Computed from decisions)
1. **Timing** (arrival/departure) - computed from route and charging
2. **SOC trajectory** - computed from initial SOC, consumption, and charging

### Constraints to Enforce
1. **Must enforce**: SOC bounds, route feasibility, energy balance
2. **Should enforce**: Station capacity, time consistency
3. **Optional**: Minimum destination SOC, charging rate limits

### Objectives to Minimize
1. **Makespan**: `max(completion_time_i)`
2. **Total Cost**: `sum(charged_kwh_i × price)`
3. **Weighted**: `w_time × makespan + w_cost × total_cost`

---

## 📚 REFERENCES IN CODE

**Decision Variables Defined**: `objectives.py`, lines 16-47 (VehicleSolution class)

**Constraints Checked**: `objectives.py`, lines 122-144 (is_feasible method)

**Objective Functions**: `objectives.py`, lines 148-183

**Parameters**: `params.py`, lines 48-142 (SingleForkParams class)

**Example Solutions**: `example_objectives.py`, lines 11-103 (create_sample_solution function)
