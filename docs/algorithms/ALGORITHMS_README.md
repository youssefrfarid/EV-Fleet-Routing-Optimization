# EV Fleet Optimization - Algorithm Documentation

This directory contains comprehensive documentation for the optimization algorithms used in the EV Fleet Routing project.

## 📚 Documentation Files

### 1. [Genetic Algorithm Documentation](../GA_DOCUMENTATION.md)

Complete guide to the **Genetic Algorithm (GA)** implementation:
- **Algorithm Concept**: Population-based evolutionary search
- **Implementation Details**: Selection, crossover, mutation, elitism
- **Feasibility Handling**: Repair mechanisms and constraint satisfaction
- **Performance**: 41.9% better than SA, excels at cost optimization
- **When to Use**: Complex problems requiring best solution quality

**Key Results** (Double Fork, seed=42):
- Best fitness: 1657.99
- 50.1% cost savings vs SA
- Execution time: ~71 seconds

### 2. [Simulated Annealing Documentation](../SA_DOCUMENTATION.md)

Complete guide to the **Simulated Annealing (SA)** implementation:
- **Algorithm Concept**: Temperature-based probabilistic search
- **Implementation Details**: Cooling schedule, acceptance criterion, neighborhood operators
- **Feasibility Handling**: Rejection and repair strategies
- **Performance**: Fast convergence, good baseline solutions
- **When to Use**: Time-critical applications, quick results needed

**Key Results** (Double Fork, seed=42):
- Best cost: 2853.87
- Good baseline quality
- Execution time: ~34 seconds (2x faster than GA)

### 3. [Particle Swarm Optimization Documentation](PSO_DOCUMENTATION.md)

Complete guide to the **Particle Swarm Optimization (PSO)** implementation:
- **Algorithm Concept**: Swarm search with inertia + cognitive/social components
- **Implementation Details**: Hybrid route swaps and continuous speed/charge updates
- **Feasibility Handling**: Penalty evaluation plus shared repair helpers
- **Performance**: Strongest weighted objective among the three (seed=42)
- **When to Use**: Mixed discrete/continuous decisions where crossover is expensive

**Key Results** (Double Fork, seed=42):
- Best weighted objective: 1483.59
- Feasible solution after queue processing
- Execution time: ~154 seconds

## 🔄 Quick Comparison

| Aspect | Simulated Annealing | Genetic Algorithm | Particle Swarm |
|--------|---------------------|-------------------|----------------|
| **Paradigm** | Single-solution trajectory | Population-based evolution | Swarm with social learning |
| **Exploration** | Temperature-controlled | Crossover + mutation | Velocity toward pbest/gbest + mutations |
| **Speed** | ⚡ Fast (~34s) | Moderate (~71s) | Slower (~154s) |
| **Quality** | Good (2853.87) | Excellent (1657.99) | Best so far (1483.59) |
| **Memory** | Low (2 solutions) | Higher (60 solutions) | Moderate (40 particles) |
| **Best For** | Quick results | Best quality | Mixed discrete/continuous tuning |

## 📖 What Each Document Covers

All documentation files follow the same comprehensive structure:

1. **Algorithm Concept**
   - What is the algorithm?
   - Core principles and intuition
   - Visual diagrams and pseudocode

2. **Why This Algorithm?**
   - Problem characteristics
   - Algorithm strengths
   - When to choose this approach

3. **Implementation Details**
   - Solution representation
   - Initialization strategies
   - Core operators (mutations for SA, selection/crossover for GA)
   - Main algorithm loop with code examples

4. **Feasibility Handling**
   - Constraint types in our problem
   - Repair mechanisms
   - Strategies for maintaining feasibility

5. **Performance & Results**
   - Benchmark results on Double Fork instance
   - Convergence analysis
   - Comparison with other algorithms
   - Tuning guidelines

6. **Usage Examples**
   - Basic usage
   - Custom configurations
   - Visualization options

## 🚀 Running the Algorithms

### Simulated Annealing

```python
from simulated_annealing import simulated_annealing
from params import make_double_fork_params

params = make_double_fork_params()
result = simulated_annealing(params, seed=42)

print(f"SA Best Cost: {result.best_cost:.2f}")
print(f"Feasible: {result.best_solution.is_feasible()}")
```

### Genetic Algorithm

```python
from genetic_algorithm import genetic_algorithm
from params import make_double_fork_params

params = make_double_fork_params()
result = genetic_algorithm(params, seed=42)

print(f"GA Best Fitness: {result.best_fitness:.2f}")
print(f"Feasible: {result.best_solution.is_feasible()}")
```

### Particle Swarm Optimization

```python
from algorithms.pso.particle_swarm import particle_swarm_optimization
from common.params import make_double_fork_params

params = make_double_fork_params()
result = particle_swarm_optimization(params, seed=42, show_plots=False)

print(f"PSO Best Weighted: {result.best_cost:.2f}")
print(f"Feasible: {result.best_solution.is_feasible()}")
```

### Compare All Three

```python
from scripts.compare_pso_ga_sa import compare_algorithms_pso_ga_sa

(pso_result, pso_time), (ga_result, ga_time), (sa_result, sa_time) = (
    compare_algorithms_pso_ga_sa(seed=42, verbose=True)
)
print(f"PSO: {pso_result.best_cost:.2f} in {pso_time:.2f}s")
print(f"GA: {ga_result.best_fitness:.2f} in {ga_time:.2f}s")
print(f"SA: {sa_result.best_cost:.2f} in {sa_time:.2f}s")
```

### Interactive Visualization

```bash
python visualize_comparison.py  # Auto-opens comparison dashboard in browser
```

## 🎯 Recommendation Guide

### Choose **Simulated Annealing** if:
- ✅ You need results quickly (<1 minute)
- ✅ You have limited computational resources
- ✅ A good baseline solution is sufficient
- ✅ You prefer simpler algorithm mechanics
- ✅ Time to solution is more important than optimal quality

### Choose **Genetic Algorithm** if:
- ✅ You need the absolute best solution quality
- ✅ Cost optimization is critical (50% savings!)
- ✅ You can afford longer computation time (1-2 minutes)
- ✅ You want to explore diverse solution strategies
- ✅ The problem is complex with many local optima

### Choose **Particle Swarm** if:
- ✅ You want strong performance on mixed discrete/continuous decisions
- ✅ You can afford longer runtime for better quality
- ✅ You prefer fewer hyperparameters (w, c1, c2, swarm size)
- ✅ You want a swarm alternative that reuses SA mutation operators

### Use **Both** if:
- 🔄 Run SA first for quick baseline
- 🔄 Run GA for final optimized solution
- 🔄 Use PSO when you need better quality than GA delivered or to validate GA
- 🔄 Use SA for real-time decisions, GA/PSO for planning

## 🔧 Key Concepts Explained

### Feasibility

Both algorithms maintain **strict feasibility** - every solution must satisfy:
1. **Route validity**: Valid path from A to B
2. **SOC bounds**: Battery stays between 10-100%
3. **Energy balance**: Charging covers consumption
4. **Time consistency**: Logical arrival/departure times
5. **Charging limits**: Cannot exceed battery capacity
6. **Queue capacity**: Respect station plug limits
7. **Speed validity**: Within edge-specific bounds

### Objective Function

Both optimize the **weighted objective**:
```
Objective = w_time × makespan + w_cost × total_cost
```

Where:
- `makespan` = time when last vehicle completes journey
- `total_cost` = sum of all charging costs
- Default weights: `w_time = 1.0`, `w_cost = 1.0`

### Repair Mechanisms

When mutations/crossover create infeasible solutions:
1. **Diagnose**: Identify which constraint is violated
2. **Repair**: Apply targeted fix (add charging, adjust speed, etc.)
3. **Retry**: Check feasibility again
4. **Fallback**: If repair fails, reject/skip this candidate

## 📊 Visualization & Analysis

The project includes comprehensive visualization tools:

- **Convergence plots**: See how each algorithm improves over time
- **Solution dashboards**: Interactive HTML showing routes, charging, speeds
- **Comparison view**: Side-by-side GA vs SA vs PSO with detailed metrics
- **Execution time tracking**: Performance analysis

Run `python visualize_comparison.py` to see everything!

## 📝 Additional Resources

- **Implementation Code**:
  - [`algorithms/sa/simulated_annealing.py`](../../algorithms/sa/simulated_annealing.py) - SA algorithm
  - [`algorithms/ga/genetic_algorithm.py`](../../algorithms/ga/genetic_algorithm.py) - GA algorithm
  - `algorithms/pso/particle_swarm.py` - PSO algorithm

- **Core Libraries**:
  - [`common/params.py`](../../common/params.py) - Problem parameters
  - [`common/objectives.py`](../../common/objectives.py) - Evaluation functions
  - [`common/visualization.py`](../../common/visualization.py) - Dashboard generation

## 🎓 Learning Path

**New to optimization?** Read in this order:
1. Start with [SA_DOCUMENTATION.md](../SA_DOCUMENTATION.md) - simpler concept
2. Then read [GA_DOCUMENTATION.md](../GA_DOCUMENTATION.md) - builds on SA
3. Continue with `PSO_DOCUMENTATION.md` for the swarm-based approach
4. Run `scripts/compare_pso_ga_sa.py` to see all three in action
5. Experiment with parameters using the tuning guidelines

**Want to extend the algorithms?**
All documentation files include detailed implementation sections showing:
- How to add new mutation operators
- How to customize objectives
- How to tune parameters
- How to integrate with other components

---

**Last Updated**: 2025-11-21  
**Maintained by**: EV Fleet Optimization Project
