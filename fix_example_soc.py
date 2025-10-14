"""
Helper script to calculate correct SOC values for example solution
"""
from params import make_toy_params

params = make_toy_params()

# Vehicle 1: 40 kWh, route: A→J→S1→S2→M→B, charges 12 kWh at S1
print("Vehicle 1 (40 kWh battery, initial SOC=0.70):")
soc = 0.70
print(f"  A: {soc:.4f}")
soc -= params.edges_energy_kwh[('A', 'J')] / 40.0
print(f"  J: {soc:.4f} (after consuming {params.edges_energy_kwh[('A', 'J')]} kWh)")
soc -= params.edges_energy_kwh[('J', 'S1')] / 40.0
print(f"  S1 (before charge): {soc:.4f} (after consuming {params.edges_energy_kwh[('J', 'S1')]} kWh)")
soc += 12.0 / 40.0
print(f"  S1 (after charge): {soc:.4f} (charged 12 kWh)")
soc -= params.edges_energy_kwh[('S1', 'S2')] / 40.0
print(f"  S2: {soc:.4f} (after consuming {params.edges_energy_kwh[('S1', 'S2')]} kWh)")
soc -= params.edges_energy_kwh[('S2', 'M')] / 40.0
print(f"  M: {soc:.4f} (after consuming {params.edges_energy_kwh[('S2', 'M')]} kWh)")
soc -= params.edges_energy_kwh[('M', 'B')] / 40.0
print(f"  B: {soc:.4f} (after consuming {params.edges_energy_kwh[('M', 'B')]} kWh)")

print("\nVehicle 2 (55 kWh battery, initial SOC=0.55):")
soc = 0.55
print(f"  A: {soc:.4f}")
soc -= params.edges_energy_kwh[('A', 'J')] / 55.0
print(f"  J: {soc:.4f}")
soc -= params.edges_energy_kwh[('J', 'S1')] / 55.0
print(f"  S1: {soc:.4f}")
soc -= params.edges_energy_kwh[('S1', 'S2')] / 55.0
print(f"  S2 (before charge): {soc:.4f}")
soc += 18.0 / 55.0
print(f"  S2 (after charge): {soc:.4f} (charged 18 kWh)")
soc -= params.edges_energy_kwh[('S2', 'M')] / 55.0
print(f"  M: {soc:.4f}")
soc -= params.edges_energy_kwh[('M', 'B')] / 55.0
print(f"  B: {soc:.4f}")

print("\nVehicle 3 (62 kWh battery, initial SOC=0.45):")
soc = 0.45
print(f"  A: {soc:.4f}")
soc -= params.edges_energy_kwh[('A', 'J')] / 62.0
print(f"  J: {soc:.4f}")
soc -= params.edges_energy_kwh[('J', 'S1')] / 62.0
print(f"  S1 (before charge): {soc:.4f}")
soc += 10.0 / 62.0
print(f"  S1 (after charge): {soc:.4f} (charged 10 kWh)")
soc -= params.edges_energy_kwh[('S1', 'S2')] / 62.0
print(f"  S2 (before charge): {soc:.4f}")
soc += 8.0 / 62.0
print(f"  S2 (after charge): {soc:.4f} (charged 8 kWh)")
soc -= params.edges_energy_kwh[('S2', 'M')] / 62.0
print(f"  M: {soc:.4f}")
soc -= params.edges_energy_kwh[('M', 'B')] / 62.0
print(f"  B: {soc:.4f}")

print("\nVehicle 4 (75 kWh battery, initial SOC=0.60):")
soc = 0.60
print(f"  A: {soc:.4f}")
soc -= params.edges_energy_kwh[('A', 'J')] / 75.0
print(f"  J: {soc:.4f}")
soc -= params.edges_energy_kwh[('J', 'S3')] / 75.0
print(f"  S3 (before charge): {soc:.4f}")
soc += 20.0 / 75.0
print(f"  S3 (after charge): {soc:.4f} (charged 20 kWh)")
soc -= params.edges_energy_kwh[('S3', 'M')] / 75.0
print(f"  M: {soc:.4f}")
soc -= params.edges_energy_kwh[('M', 'B')] / 75.0
print(f"  B: {soc:.4f}")

print("\nVehicle 5 (80 kWh battery, initial SOC=0.50):")
soc = 0.50
print(f"  A: {soc:.4f}")
soc -= params.edges_energy_kwh[('A', 'J')] / 80.0
print(f"  J: {soc:.4f}")
soc -= params.edges_energy_kwh[('J', 'S3')] / 80.0
print(f"  S3 (before charge): {soc:.4f}")
soc += 25.0 / 80.0
print(f"  S3 (after charge): {soc:.4f} (charged 25 kWh)")
soc -= params.edges_energy_kwh[('S3', 'M')] / 80.0
print(f"  M: {soc:.4f}")
soc -= params.edges_energy_kwh[('M', 'B')] / 80.0
print(f"  B: {soc:.4f}")
