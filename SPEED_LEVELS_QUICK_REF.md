# Speed Levels Quick Reference

## 🎯 5 Discrete Speed Levels

| Level | Name      | Time  | Energy | Description                 |
| :---: | --------- | :---: | :----: | --------------------------- |
| **1** | Very Slow | ×1.4  | ×0.75  | 🐢 Most efficient, slowest  |
| **2** | Slow      | ×1.2  |  ×0.9  | 🚶 Efficient, slower        |
| **3** | Normal    | ×1.0  |  ×1.0  | 🚗 **Baseline (default)**   |
| **4** | Fast      | ×0.85 |  ×1.2  | 🏃 Less efficient, faster   |
| **5** | Very Fast | ×0.7  |  ×1.5  | 🚀 Least efficient, fastest |

## 📝 Usage

```python
from params import make_toy_params
from objectives import VehicleSolution

params = make_toy_params()

# Query options
time = params.get_edge_time(('A', 'J'), speed_level=5)
energy = params.get_edge_energy(('A', 'J'), speed_level=1)
options = params.get_all_speed_options(('A', 'J'))

# In solution
vehicle = VehicleSolution(
    vehicle_id=0,
    route=['A', 'J', 'S1', 'M', 'B'],
    speed_levels={
        ('A', 'J'): 3,   # Normal
        ('J', 'S1'): 5,  # Very fast
        ('S1', 'M'): 2,  # Slow
        ('M', 'B'): 3,   # Normal
    },
    ...
)
```

## 🔄 Trade-offs

**Fast (4-5)**: ✅ Less time ❌ More energy  
**Slow (1-2)**: ✅ Less energy ❌ More time  
**Normal (3)**: Baseline balance

## ✅ Validation

- Speed levels must be in [1, 5]
- Energy balance uses speed-dependent values
- Defaults to 3 if not specified
- Check with `solution.is_feasible(verbose=True)`

## 📚 Documentation

- `SPEED_LEVELS_GUIDE.md` - Full guide
- `example_speed_levels.py` - Examples
- `test_speed_levels.py` - Tests
- `SPEED_LEVELS_IMPLEMENTATION.md` - Summary

## 🚀 Run Examples

```bash
python example_speed_levels.py  # Demo
python test_speed_levels.py     # Tests
```
