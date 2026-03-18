# Genetic Algorithm Documentation

## Overview

This document explains the **Genetic Algorithm (GA)** optimization approach for the EV Fleet Routing Problem, covering both the theoretical concepts and our specific implementation.

## Table of Contents

1. [Algorithm Concept](#algorithm-concept)
2. [Why Genetic Algorithms?](#why-genetic-algorithms)
3. [Implementation Details](#implementation-details)
4. [Feasibility Handling](#feasibility-handling)
5. [Performance & Results](#performance--results)

---

## Algorithm Concept

### What is a Genetic Algorithm?

A Genetic Algorithm is a **population-based metaheuristic** inspired by natural evolution. Instead of improving a single solution, GA maintains a **population of candidate solutions** that evolve over generations through:

1. **Selection** - Choosing better solutions as "parents"
2. **Crossover** - Combining parent solutions to create "offspring"
3. **Mutation** - Randomly varying solutions for diversity
4. **Elitism** - Preserving the best solutions

### The Evolution Cycle

```
Generation 0: Random population of 60 solutions
    ↓
[Selection] Pick parents based on fitness
    ↓
[Crossover] Combine parents → create offspring
    ↓
[Mutation] Randomly modify some offspring
    ↓
[Repair] Fix any infeasible solutions
    ↓
Generation 1: New population (elites + offspring)
    ↓
    ... Repeat for 150 generations ...
    ↓
Final Result: Best solution found across all generations
```

### Key Advantages

✅ **Exploration**: Population searches multiple regions simultaneously  
✅ **Recombination**: Crossover combines good features from different solutions  
✅ **Diversity**: Multiple solutions prevent premature convergence  
✅ **Robustness**: Less likely to get stuck in local optima  

---

## Why Genetic Algorithms?

### EV Fleet Routing Challenges

Our problem is **combinatorially complex**:
- Route selection: 4 options per vehicle (UU, UL, LU, LL)
- Charging decisions: Which stations? How much?
- Speed choices: Continuous values per edge
- Queue constraints: Station capacity limits
- Trade-offs: Time vs. Cost optimization

This creates a **vast, multimodal search space** with:
- Many local optima (good but not best solutions)
- Complex interactions between variables
- No clear gradient to follow

### GA Strengths for This Problem

1. **Population Diversity**: Explores multiple route combinations simultaneously
2. **Crossover Power**: Can combine a good route from one solution with good charging strategy from another
3. **Flexible Representation**: Naturally handles discrete (routes) + continuous (speeds, charging) variables
4. **Feasibility Repair**: Can recover from constraint violations

---

## Implementation Details

### Solution Representation

Each individual in the population is a **fleet configuration** (`List[VehiclePlan]`):

```python
@dataclass
class VehiclePlan:
    vehicle_id: int
    route: List[str]                      # e.g., ["A", "J1", "S1", "S2", "M1", ...]
    charging_amounts: Dict[str, float]    # e.g., {"S1": 15.2, "S4": 22.8}
    speed_levels: Dict[Edge, float]       # e.g., {("A","J1"): 75.3, ...}
```

**Why this representation?**
- **Route**: Discrete choice → easy to crossover entire routes
- **Charging**: Continuous values → can blend amounts from parents
- **Speed**: Continuous optimization → allows smooth variations

### Population Initialization

```python
def create_initial_population(params, pop_size=60, rng):
    # Generate 60 diverse, FEASIBLE starting solutions
    population = []
    for i in range(pop_size):
        plans = _generate_random_initial_plans(params, rng)
        # Each plan has:
        # - Random route (UU/UL/LU/LL)
        # - Conservative speeds (lower = less energy)
        # - Calculated charging (covers energy deficit + buffer)
        population.append(plans)
    return population
```

**Key insight**: Start with feasible solutions to avoid wasting early generations on repairs.

### Selection Operators

#### Tournament Selection (Primary)

```python
def tournament_selection(population, fitness_scores, tournament_size=4, rng):
    # 1. Randomly pick 4 individuals
    tournament = random.sample(population, tournament_size)
    
    # 2. Return the BEST one (lowest fitness)
    return min(tournament, key=lambda x: fitness_scores[x])
```

**Why tournaments?**
- **Pressure control**: Larger tournaments = more selection pressure
- **Diversity**: Weaker solutions still have a chance
- **Simplicity**: No complex probability calculations

#### Roulette Wheel Selection (Alternative)

Fitness-proportionate selection where better solutions have higher selection probability. Less commonly used in our implementation but available.

### Crossover Operators

#### Fleet-Level Crossover

```python
def crossover_fleet(parent1, parent2, params, rng):
    offspring1, offspring2 = [], []
    
    for i in range(len(parent1)):
        if rng.random() < 0.5:
            # Vehicle i: P1 → O1, P2 → O2
            offspring1.append(parent1[i].copy())
            offspring2.append(parent2[i].copy())
        else:
            # Vehicle i: P2 → O1, P1 → O2 (SWAP)
            offspring1.append(parent2[i].copy())
            offspring2.append(parent1[i].copy())
    
    return offspring1, offspring2
```

**Uniform crossover**: Each vehicle independently inherited from random parent.

#### Vehicle-Level Crossover

```python
def crossover_vehicle(plan1, plan2, params, rng):
    child = plan1.copy()
    
    # Route: Inherit from one parent
    if rng.random() < 0.5:
        child.route = plan2.route
    
    # Charging: BLEND if same route
    if plan1.route == plan2.route:
        for station in all_stations:
            amt1 = plan1.charging_amounts.get(station, 0)
            amt2 = plan2.charging_amounts.get(station, 0)
            weight = rng.random()
            child.charging_amounts[station] = weight * amt1 + (1-weight) * amt2
    
    # Speed: BLEND if same route
    if plan1.route == plan2.route:
        for edge in route_edges:
            speed1 = plan1.speed_levels.get(edge, 80.0)
            speed2 = plan2.speed_levels.get(edge, 80.0)
            weight = rng.random()
            child.speed_levels[edge] = weight * speed1 + (1-weight) * speed2
    
    return child
```

**Smart blending**: Only blend continuous variables when routes match.

### Mutation Operators

We reuse proven operators from Simulated Annealing:

```python
def mutate_fleet(plans, params, mutation_rate=0.15, rng):
    for plan in plans:
        if rng.random() < mutation_rate:  # 15% chance per vehicle
            mutation_type = rng.choice([
                "speed_step",      # Small speed adjustment ±10 km/h
                "speed_random",    # Random speed in valid range
                "charge_step",     # Small charge adjustment ±4 kWh
                "charge_random",   # Random charge amount
                "route_toggle",    # Switch to different route
                "station_add",     # Add charging station
                "station_remove",  # Remove charging station
            ])
            apply_mutation(plan, mutation_type)
```

**Why multiple mutation types?**
- **Speed mutations**: Fine-tune time/energy trade-off
- **Charge mutations**: Optimize cost
- **Route mutations**: Explore different path options
- **Station mutations**: Change charging strategy

### Elitism Strategy

```python
# Preserve top N solutions each generation
elite_size = 3  # For double fork
sorted_population = sort_by_fitness(population)
elites = sorted_population[:elite_size]

# New generation = elites + offspring
new_generation = elites + best_offspring
```

**Why elitism?**
- **Monotonic improvement**: Best solution never gets worse
- **Convergence guarantee**: Always have high-quality baseline
- **Small elite size** (3 out of 60): Doesn't stifle exploration

### Main GA Loop

```python
def genetic_algorithm(params, pop_size=60, num_generations=150, ...):
    # 1. Initialize
    population = create_initial_population(params, pop_size, rng)
    best_solution = evaluate_and_find_best(population)
    
    # 2. Evolve
    for generation in range(num_generations):
        # 2a. Preserve elites
        elites = select_top_n(population, elite_size=3)
        
        # 2b. Generate offspring
        offspring = []
        while len(offspring) < pop_size - elite_size:
            # Selection
            parent1 = tournament_selection(population, fitness_scores, size=4)
            parent2 = tournament_selection(population, fitness_scores, size=4)
            
            # Crossover (80% probability)
            if rng.random() < 0.8:
                child1, child2 = crossover_fleet(parent1, parent2)
            else:
                child1, child2 = parent1.copy(), parent2.copy()
            
            # Mutation (15% per individual)
            child1 = mutate_fleet(child1, mutation_rate=0.15)
            child2 = mutate_fleet(child2, mutation_rate=0.15)
            
            # Repair if needed
            child1 = repair_if_infeasible(child1)
            child2 = repair_if_infeasible(child2)
            
            offspring.extend([child1, child2])
        
        # 2c. Form new generation
        population = elites + offspring[:pop_size - elite_size]
        
        # 2d. Update best
        current_best = find_best(population)
        if current_best_fitness < best_fitness:
            best_solution = current_best
            best_fitness = current_best_fitness
    
    return best_solution
```

---

## Feasibility Handling

### Constraint Types

Our EV routing problem has **hard constraints**:

1. **Route validity**: Must start at A, end at B, use valid edges
2. **SOC bounds**: Battery must stay between 10% and 100%
3. **Energy balance**: Consumption + charging must match SOC changes
4. **Time consistency**: Departure ≥ arrival at all nodes
5. **Charging limits**: Cannot charge beyond battery capacity
6. **Queue capacity**: Station plugs limit (managed by queue simulation)
7. **Speed validity**: Must respect per-edge speed limits

**All solutions must be feasible** - infeasible = infinite penalty.

### Repair Mechanisms

When crossover or mutation creates an infeasible solution, we **repair** it:

```python
def repair_individual(plans, params, rng, max_attempts=10):
    for attempt in range(max_attempts):
        solution = build_solution_from_plans(plans, params)
        feasible, code, message = solution.is_feasible(return_reason=True)
        
        if feasible:
            return plans  # Success!
        
        # Apply targeted repair based on violation type
        if code == 2:  # SOC too low
            # Increase charging at a station
            station = ensure_station_exists(plans, params, rng)
            plans[vehicle].charging_amounts[station] += 6.0
        
        elif code == 5:  # Charging exceeds capacity
            # Reduce all charging amounts
            for plan in plans:
                for station in plan.charging_amounts:
                    plan.charging_amounts[station] *= 0.85
        
        elif code == 7:  # Invalid speed
            # Clamp speeds to valid range
            for plan in plans:
                for edge, speed in plan.speed_levels.items():
                    min_s, max_s = params.get_edge_speed_bounds(edge)
                    plan.speed_levels[edge] = clamp(speed, min_s, max_s)
        
        # ... other repair strategies ...
    
    return None  # Repair failed after max attempts
```

**Repair strategy**: Diagnosis → targeted fix → retry up to 10 times.

### Handling Repair Failures

```python
# In main GA loop
offspring1 = crossover_and_mutate(parent1, parent2)
repaired = repair_individual(offspring1, params, rng)

if repaired is None:
    # Repair failed - discard this offspring
    continue  # Try generating a different offspring
else:
    # Success - add to new generation
    new_generation.append(repaired)
```

**Philosophy**: Better to skip a failed repair than accept an infeasible solution.

---

## Performance & Results

### Double Fork Instance (5 vehicles, 6 stations)

**Configuration:**
- Population size: 60
- Generations: 150
- Tournament size: 4
- Mutation rate: 15%
- Crossover rate: 80%
- Elite size: 3

**Results (seed=42):**

| Metric | SA | GA | GA Improvement |
|--------|----|----|----------------|
| **Objective** | 2853.87 | 1657.99 | **41.9% better** ✨ |
| **Makespan** | 498.72 min | 481.78 min | 3.4% faster |
| **Cost** | 2355.15 EGP | 1176.22 EGP | **50.1% cheaper** 💰 |
| **Execution Time** | 34.24 s | 70.60 s | 2.06x slower ⏱️ |

**Key Takeaways:**

1. **Solution Quality**: GA finds significantly better solutions (41.9% improvement)
2. **Cost Optimization**: Excels at minimizing charging costs (50% savings)
3. **Time Trade-off**: Takes ~2x longer but finds much better solutions
4. **Diversity Benefit**: Population-based search explores more options

### Convergence Behavior

```
Generation   0: Best = 2681.64 (initial)
Generation  10: Best = 2112.22 (21% improvement)
Generation  50: Best = 1848.83 (31% improvement)
Generation 100: Best = 1798.39 (33% improvement)
Generation 150: Best = 1657.99 (38% improvement) ← Final
```

**Observation**: Steady improvement throughout, suggesting good exploration-exploitation balance.

### Population Diversity

Diversity metric tracks how many different route configurations exist in population:

```
Generation   0: Diversity = 0.988 (very diverse)
Generation  50: Diversity = 0.196 (converging)
Generation 150: Diversity = 0.205 (maintained)
```

**Healthy convergence**: Diversity decreases but stabilizes, indicating population hasn't prematurely converged.

---

## Comparison with Simulated Annealing

| Aspect | Simulated Annealing | Genetic Algorithm |
|--------|---------------------|-------------------|
| **Search Type** | Single solution | Population (60 individuals) |
| **Exploration** | Sequential neighborhood | Parallel search |
| **Information Sharing** | None (one trajectory) | Crossover combines solutions |
| **Convergence** | Fast (~34s) | Slower (~71s) |
| **Solution Quality** | Good baseline | 42% better |
| **Best For** | Time-critical, quick results | Complex problems, best quality |

---

## Usage Examples

### Basic Usage

```python
from genetic_algorithm import genetic_algorithm
from params import make_double_fork_params

# Create problem instance
params = make_double_fork_params()

# Run GA
result = genetic_algorithm(
    params,
    pop_size=60,
    num_generations=150,
    seed=42
)

# Check results
print(f"Best fitness: {result.best_fitness:.2f}")
print(f"Feasible: {result.best_solution.is_feasible()}")
```

### Custom Configuration

```python
# Larger population for more exploration
result = genetic_algorithm(
    params,
    pop_size=100,         # More individuals
    num_generations=200,   # More time to evolve
    elite_size=5,          # Preserve more elites
    tournament_size=6,     # Higher selection pressure
    mutation_rate=0.20,    # More mutations
    crossover_rate=0.85,   # More crossover
    seed=42
)
```

### Comparison Run

```python
from compare_ga_sa import compare_algorithms_double_fork

# Run both algorithms and compare
sa_result, ga_result, sa_time, ga_time = compare_algorithms_double_fork(seed=42)

print(f"SA: {sa_result.best_cost:.2f} in {sa_time:.2f}s")
print(f"GA: {ga_result.best_fitness:.2f} in {ga_time:.2f}s")
```

---

## Implementation Files

- **[genetic_algorithm.py](file:///Users/yousseframy/Documents/optimization-project/genetic_algorithm.py)** - Main GA implementation
- **[compare_ga_sa.py](file:///Users/yousseframy/Documents/optimization-project/compare_ga_sa.py)** - Comparison script
- **[visualize_comparison.py](file:///Users/yousseframy/Documents/optimization-project/visualize_comparison.py)** - Interactive visualization
- **[objectives.py](file:///Users/yousseframy/Documents/optimization-project/objectives.py)** - Fitness evaluation and feasibility checks
- **[params.py](file:///Users/yousseframy/Documents/optimization-project/params.py)** - Problem parameters

---

## References & Further Reading

**Genetic Algorithms:**
- Goldberg, D. E. (1989). *Genetic Algorithms in Search, Optimization, and Machine Learning*
- Holland, J. H. (1975). *Adaptation in Natural and Artificial Systems*

**EV Routing:**
- Schneider, M., et al. (2014). "The Electric Vehicle-Routing Problem with Time Windows and Recharging Stations"

**Metaheuristics:**
- Talbi, E. G. (2009). *Metaheuristics: From Design to Implementation*

---

**Last Updated**: 2025-11-21  
**Implementation**: Python 3.13 with NumPy, Matplotlib
