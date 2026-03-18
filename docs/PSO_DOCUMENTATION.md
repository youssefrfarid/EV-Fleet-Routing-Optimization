# Particle Swarm Optimization Documentation

## Overview

This document explains the **Particle Swarm Optimization (PSO)** approach for the EV Fleet Routing Problem, covering both the theoretical concepts and the specifics of our implementation.

## Table of Contents

1. [Algorithm Concept](#algorithm-concept)
2. [Why Particle Swarm?](#why-particle-swarm)
3. [Implementation Details](#implementation-details)
4. [Feasibility Handling](#feasibility-handling)
5. [Performance & Results](#performance--results)
6. [Usage Examples](#usage-examples)

---

## Algorithm Concept

### What is Particle Swarm Optimization?

PSO is a **population-based metaheuristic** where a swarm of particles flies through the search space. Each particle tracks:

- **Position (`x`)**: A candidate solution (fleet plan)
- **Velocity (`v`)**: How the particle moves in the search space
- **Personal best (`pbest`)**: Best solution seen by the particle
- **Global best (`gbest`)**: Best solution seen by the entire swarm

At every iteration:

```
v = w * v                # inertia (keep momentum)
  + c1 * r1 * (pbest - x)  # cognitive pull (learn from self)
  + c2 * r2 * (gbest - x)  # social pull (learn from swarm)

x = x + v
```

### The Swarm Cycle

```
Initialize feasible swarm (40 particles)
    |
[Evaluate] objective_weighted + feasibility penalty
    |
[Update] routes (swap velocity) + speeds/charging (continuous velocity)
    |
[Repair/Mutate] lightweight fixes + SA-inspired mutations
    |
Track pbest / gbest  → adjust inertia (adaptive w)
    |
Repeat for 150 iterations → return best solution
```

### Key Advantages

- **Blended search**: Handles continuous (speed/charge) + discrete (routes)
- **Social learning**: Shares good patterns across vehicles via `gbest`
- **Low parameter count**: Primarily `w`, `c1`, `c2`, swarm size, iterations
- **Strong anytime behavior**: Returns best-so-far at any iteration

---

## Why Particle Swarm?

### EV Fleet Routing Challenges

- Mixed variable types: continuous speeds/charging + discrete routes/stations
- Coupled constraints: SOC feasibility, station queues, edge speed limits
- Wide search space: Many feasible-but-different route/charging mixes

### PSO Strengths for This Problem

1. **Continuous-friendly core** for tuning speeds/charging amounts
2. **Permutation-aware route updates** (swap-based velocity) without breaking edges
3. **Fast exploitation** once good global patterns emerge
4. **Hybrid exploration** via SA-style mutations to escape stagnation

---

## Implementation Details

### Particle Representation

Each particle stores:
- `plans: List[VehiclePlan]` — same dataclass used by SA/GA (route, charging, speed)
- `velocity: Dict[Tuple, object]` — per-edge speed deltas, per-station charge deltas, and route swap sequences
- `best_plans`, `best_cost` — personal best snapshot

### Swarm Initialization (`create_initial_swarm`)

- Uses `_generate_random_initial_plans` (feasible by construction) for diversity
- Evaluates with `objective_weighted`; infeasible solutions get `1e9` penalty
- Personal bests seeded from these initial feasible plans

### Velocity Updates (`update_particle`)

- **Routes (discrete):**  
  - Compute swap sequences toward `pbest` and `gbest` (`_subtract_permutations`)  
  - Scale by `w`, `c1`, `c2`, apply if resulting route keeps valid edges  
  - Fallback adoption of `pbest/gbest` routes or SA route toggle when swaps fail
- **Speeds (continuous):**  
  - PSO update with clamping to edge bounds; stored per-edge velocity key (`"speed", edge`)  
  - Rounded to 0.1 km/h for stability
- **Charging (continuous):**  
  - PSO update with non-negativity and 95% battery cap; stored per-station velocity key (`"charge", vid, station"`)
- **Exploration bumps:** 5% chance to toggle route; 10% mutation using SA operators (speed/charge steps, random nudges, station add/remove)

### Main Loop (`particle_swarm_optimization`)

- Default hyperparameters: `swarm_size=40`, `max_iterations=150`, `w=0.5`, `c1=c2=1.7`
- **Adaptive inertia (`use_adaptive_weight=True`):** nudges `w` within `[0.2, 0.9]` based on improvement vs. current best:
  - If `use_adaptive_weight=False`, keep inertia `w` fixed for all iterations.
  - If `use_adaptive_weight=True`, after each iteration compute  
    `m = (best_cost - current_cost) / (best_cost + current_cost)` (using the neighborhood/global best vs. the current particle) and  
    update `w = w0 + (w - w0) * ((exp(m) - 1) / (exp(m) + 1))`.
  - Velocity update remains `v = w*v + c1*r1*(pbest - x) + c2*r2*(gbest - x)`; the inertia adjustment is applied right after evaluating fitness.
- Tracks `history = [(iteration, best, avg, worst)]` for convergence plots
- Final solution repaired via `process_station_queues` before reporting metrics

### Discrete PSO Operator Definitions (Routes)

1. Particle position = a permutation (route ordering) per vehicle.
2. Particle velocity = list of swap operations.
3. Subtracting two permutations yields the swap sequence to convert one into the other.
4. Multiplying a velocity by a scalar truncates the swap list accordingly.
5. Adding velocity to position applies the swaps in order to produce a new route.
6. Motion update uses these discrete operators in place of numeric vector arithmetic.
7. Fitness selection compares route cost/feasibility via the weighted objective (time + charging cost) to pick pbest/gbest correctly.

---

## Feasibility Handling

- **Penalty for infeasible evaluations:** `INFEASIBLE_PENALTY = 1e9` keeps swarm focused on feasible regions.
- **Lightweight repairs:** `_attempt_repair` calls shared `_repair_plans_for_reason` up to 3 times when feasibility codes are returned.
- **Safety defaults:** `_ensure_speed_defaults` and `_ensure_station_exists` prevent empty charging plans or missing speeds after updates.
- **Queue post-processing:** `process_station_queues` adjusts station waiting times before final objective calculation.

---

## Performance & Results

**Instance:** Double Fork benchmark, `seed=42`  
**Settings:** `swarm_size=40`, `iterations=150`, `w=0.5`, `c1=1.7`, `c2=1.7`, adaptive inertia on

- **Best weighted objective:** `1483.59`
- **Makespan:** `520.71` minutes
- **Total cost:** `962.87` EGP
- **Runtime:** `153.9` seconds
- **Feasible:** `True`

### Quick Comparison (seed=42)

| Metric | PSO | GA | SA |
|--------|-----|----|----|
| Weighted objective | **1483.59** | 1657.99 | 2853.87 |
| Runtime | 153.9 s | ~71 s | ~34 s |
| Behavior | Balanced continuous/discrete search | Strong recombination | Fast baseline |

---

## Usage Examples

### Basic Run

```python
from algorithms.pso.particle_swarm import particle_swarm_optimization
from common.params import make_double_fork_params

params = make_double_fork_params()
result = particle_swarm_optimization(
    params,
    swarm_size=40,
    max_iterations=150,
    w=0.5,
    c1=1.7,
    c2=1.7,
    seed=42,
    show_plots=False,
)

print(f"Best weighted objective: {result.best_cost:.2f}")
print(f"Feasible: {result.best_solution.is_feasible()}")
```

### Benchmark vs GA/SA

```python
from scripts.compare_pso_ga_sa import compare_algorithms_pso_ga_sa

(pso_result, pso_time), (ga_result, ga_time), (sa_result, sa_time) = (
    compare_algorithms_pso_ga_sa(seed=42, verbose=True)
)
```

---

## Implementation Files

- `algorithms/pso/particle_swarm.py` — Main PSO implementation and demos
- `algorithms/pso/compare_weights.py` — Weight tuning study for w, c1, c2
- `algorithms/pso/pso_experiments.py` — Swarm size / iteration sweeps
- `scripts/compare_pso_ga_sa.py` — PSO vs GA vs SA benchmark script

---

**Last Updated**: 2025-11-30  
**Implementation**: Python 3.13 with NumPy, Matplotlib
