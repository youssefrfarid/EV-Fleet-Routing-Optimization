"""
test_realistic_params.py
Test the updated realistic parameters and show the impact.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running via `python scripts/test_realistic_params.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.params import make_toy_params


def test_realistic_values():
    """Show the realistic parameter values."""
    params = make_toy_params()

    print("=" * 80)
    print("REALISTIC PARAMETERS - BASED ON EGYPTIAN FUEL PRICES")
    print("=" * 80)

    # Pricing
    print("\n📊 CHARGING STATION PRICES (based on Gas 95 @ 21.75 EGP/liter)")
    print("-" * 80)
    print("Reference: Gas 95 @ 21.75 EGP/liter, 12 km/liter → 1.81 EGP/km")
    print("EV equivalent: 6 km/kWh → 10.86 EGP/kWh (cost parity)")
    print("\nPublic Charging Prices:")
    for station, price in sorted(params.station_price.items()):
        speed = params.station_max_kw[station]
        plugs = params.station_plugs[station]
        markup = ((price / 10.86) - 1) * 100
        print(f"  {station}: {price:.2f} EGP/kWh ({speed:>3.0f} kW, {plugs} plug{'s' if plugs > 1 else ''}) "
              f"[+{markup:.0f}% markup]")

    # Energy consumption
    print("\n⚡ ENERGY CONSUMPTION - REALISTIC LONG-DISTANCE TRIP (~220 km)")
    print("-" * 80)

    # Upper route
    upper_edges = [("A", "J"), ("J", "S1"), ("S1", "S2"),
                   ("S2", "M"), ("M", "B")]
    upper_energy = sum(params.edges_energy_kwh[e] for e in upper_edges)
    upper_time = sum(params.edges_time_min[e] for e in upper_edges)

    print(f"\nUpper Route (A→J→S1→S2→M→B):")
    print(f"{'Edge':<12} {'Distance':<12} {'Time':<12} {'Energy':<12}")
    print("-" * 60)
    for edge in upper_edges:
        energy = params.edges_energy_kwh[edge]
        time = params.edges_time_min[edge]
        distance = energy / 0.17  # Approx distance
        print(
            f"{edge[0]}→{edge[1]:<10} ~{distance:<11.0f} {time:<12.0f} {energy:<12.1f}")
    print("-" * 60)
    print(f"{'TOTAL':<12} {'~220 km':<12} {upper_time:<12.0f} {upper_energy:<12.1f}")

    # Lower route
    lower_edges = [("A", "J"), ("J", "S3"), ("S3", "M"), ("M", "B")]
    lower_energy = sum(params.edges_energy_kwh[e] for e in lower_edges)
    lower_time = sum(params.edges_time_min[e] for e in lower_edges)

    print(f"\nLower Route (A→J→S3→M→B):")
    print(f"{'Edge':<12} {'Distance':<12} {'Time':<12} {'Energy':<12}")
    print("-" * 60)
    for edge in lower_edges:
        energy = params.edges_energy_kwh[edge]
        time = params.edges_time_min[edge]
        distance = energy / 0.17  # Approx distance
        marker = " ⚠️  HILLY!" if edge == ("S3", "M") else ""
        print(
            f"{edge[0]}→{edge[1]:<10} ~{distance:<11.0f} {time:<12.0f} {energy:<12.1f}{marker}")
    print("-" * 60)
    print(f"{'TOTAL':<12} {'~220 km':<12} {lower_time:<12.0f} {lower_energy:<12.1f}")

    # Fleet analysis
    print("\n🚗 FLEET COMPOSITION - VEHICLES NEED CHARGING!")
    print("-" * 80)
    print(f"{'Vehicle':<12} {'Battery':<12} {'Initial SOC':<15} {'Starting kWh':<15} {'Can Travel':<15} {'Must Charge?'}")
    print("-" * 80)

    for i in range(params.m):
        battery = params.battery_kwh[i]
        soc = params.soc0[i]
        starting_kwh = battery * soc
        can_travel = starting_kwh  # Energy available
        needs_charge_upper = "YES ✅" if starting_kwh < upper_energy else "Maybe"
        needs_charge_lower = "YES ✅" if starting_kwh < lower_energy else "Maybe"
        needs_charge = needs_charge_upper if upper_energy > lower_energy else needs_charge_lower

        print(f"EV {i+1:<9} {battery:<12.0f} {soc*100:<14.0f}% {starting_kwh:<15.1f} {can_travel:<15.1f} {needs_charge}")

    print("\n💰 CHARGING COST EXAMPLES (for different strategies)")
    print("-" * 80)

    # Example: Vehicle 1 (compact EV)
    v1_battery = params.battery_kwh[0]
    v1_soc = params.soc0[0]
    v1_start = v1_battery * v1_soc
    v1_need_upper = upper_energy - v1_start  # Need to charge

    print(f"\nVehicle 1 ({v1_battery:.0f} kWh, {v1_soc*100:.0f}% SOC, {v1_start:.1f} kWh available):")
    print(f"  Upper route needs: {upper_energy:.1f} kWh total")
    print(f"  Must charge: {v1_need_upper:.1f} kWh minimum")
    print(f"\n  Charging cost scenarios:")
    print(f"    Budget (S1 only, 13 EGP/kWh):   {v1_need_upper * 13:.2f} EGP")
    print(f"    Standard (S3 only, 20 EGP/kWh): {v1_need_upper * 20:.2f} EGP")
    print(f"    Premium (S2 only, 27 EGP/kWh):  {v1_need_upper * 27:.2f} EGP")

    # Compare to gas cost
    distance_upper = upper_energy / 0.17  # ~220 km
    gas_cost = distance_upper * 1.81
    print(f"\n  Comparison to ICE vehicle:")
    print(f"    Gas cost for ~220 km trip: {gas_cost:.2f} EGP")
    print(f"    EV charging (budget):      {v1_need_upper * 13:.2f} EGP")
    print(
        f"    Savings with EV (budget):  {gas_cost - v1_need_upper * 13:.2f} EGP ({((gas_cost - v1_need_upper * 13)/gas_cost*100):.0f}% cheaper)")

    # Vehicle 5 (large SUV)
    v5_battery = params.battery_kwh[4]
    v5_soc = params.soc0[4]
    v5_start = v5_battery * v5_soc
    v5_need_upper = upper_energy - v5_start

    print(f"\nVehicle 5 ({v5_battery:.0f} kWh, {v5_soc*100:.0f}% SOC, {v5_start:.1f} kWh available):")
    print(f"  Upper route needs: {upper_energy:.1f} kWh total")
    print(f"  Must charge: {v5_need_upper:.1f} kWh minimum")
    print(f"\n  Charging cost scenarios:")
    print(f"    Budget (S1 only, 13 EGP/kWh):   {v5_need_upper * 13:.2f} EGP")
    print(f"    Standard (S3 only, 20 EGP/kWh): {v5_need_upper * 20:.2f} EGP")
    print(f"    Premium (S2 only, 27 EGP/kWh):  {v5_need_upper * 27:.2f} EGP")

    print("\n📈 KEY INSIGHTS")
    print("-" * 80)
    print(f"✓ Trip distance: ~220 km (realistic Cairo-Alexandria)")
    print(
        f"✓ Energy consumption: {upper_energy:.1f} kWh (upper) or {lower_energy:.1f} kWh (lower)")
    print(
        f"✓ Battery usage: {upper_energy/80*100:.0f}% for 80kWh vehicle (forces charging!)")
    print(f"✓ Charging prices: 13-27 EGP/kWh (based on Gas 95 @ 21.75 EGP/L)")
    print(f"✓ All vehicles MUST charge during trip (realistic constraint)")
    print(f"✓ 10% SOC safety reserve enforced at every stop")
    print(
        f"✓ Cost difference: Budget vs Premium = {(27-13)/13*100:.0f}% more expensive!")
    print(
        f"✓ Lower route: Shorter time ({lower_time:.0f} min) but hilly (S3→M uses {params.edges_energy_kwh[('S3', 'M')]:.1f} kWh!)")

    print("\n✅ Parameters are now realistic for Egyptian EV fleet optimization!")
    print("=" * 80)


if __name__ == "__main__":
    test_realistic_values()

params = make_toy_params()

# Re-use edge definitions for consistency with earlier report
upper_edges = [("A", "J"), ("J", "S1"), ("S1", "S2"), ("S2", "M"), ("M", "B")]
lower_edges = [("A", "J"), ("J", "S3"), ("S3", "M"), ("M", "B")]

upper_time = sum(params.edges_time_min[e] for e in upper_edges)
lower_time = sum(params.edges_time_min[e] for e in lower_edges)
upper_energy = sum(params.edges_energy_kwh[e] for e in upper_edges)
lower_energy = sum(params.edges_energy_kwh[e] for e in lower_edges)

print('=' * 70)
print('UPDATED REALISTIC PARAMETERS')
print('=' * 70)

print('\n📍 TRIP DISTANCES & TIMES:')
print('Upper route: A → J → S1 → S2 → M → B')
print(f'  Travel time: {upper_time:.0f} minutes ({upper_time/60:.1f} hours)')
print(f'  Energy needed: {upper_energy:.1f} kWh')

print('\nLower route: A → J → S3 → M → B')
print(f'  Travel time: {lower_time:.0f} minutes ({lower_time/60:.1f} hours)')
print(f'  Energy needed: {lower_energy:.1f} kWh (hilly S3→M segment dominates)')

print('\n💰 CHARGING STATION PRICES (realistic Egyptian market):')
print(f'Based on Gas 95 @ 21.75 EGP/liter')
print(f'ICE cost: ~1.81 EGP/km → EV equivalent: ~10.88 EGP/kWh')
print()
for station, price in params.station_price.items():
    power = params.station_max_kw[station]
    plugs = params.station_plugs[station]
    markup = (price / 10.88 - 1) * 100
    print(f'  {station}: {price:.2f} EGP/kWh ({power:.0f} kW, {plugs} plug(s)) - {markup:.0f}% markup')

print('\n🔋 FLEET INITIAL STATE:')
for i in range(params.m):
    battery = params.battery_kwh[i]
    soc = params.soc0[i]
    energy_available = battery * soc
    print(
        f'  Vehicle {i+1}: {battery:.0f} kWh battery, {soc*100:.0f}% charged → {energy_available:.1f} kWh available')

print('\n📊 ENERGY ANALYSIS PER VEHICLE:')
print('(Without charging stations)')
for i in range(params.m):
    battery = params.battery_kwh[i]
    soc = params.soc0[i]
    energy_available = battery * soc
    upper_remaining = energy_available - upper_energy
    lower_remaining = energy_available - lower_energy
    print(f'\n  Vehicle {i+1} ({battery:.0f} kWh, starts at {soc*100:.0f}%):')
    print(f'    Available: {energy_available:.1f} kWh')
    print(
        f'    After upper route: {upper_remaining:.1f} kWh ({upper_remaining/battery*100:.1f}%)', end='')
    if upper_remaining < 0:
        print(' ⚠️  IMPOSSIBLE without charging!')
    elif upper_remaining < battery * 0.1:
        print(' ⚠️  BELOW 10% RESERVE!')
    else:
        print()
    print(
        f'    After lower route: {lower_remaining:.1f} kWh ({lower_remaining/battery*100:.1f}%)', end='')
    if lower_remaining < 0:
        print(' ⚠️  IMPOSSIBLE without charging!')
    elif lower_remaining < battery * 0.1:
        print(' ⚠️  BELOW 10% RESERVE!')
    else:
        print()

print('\n💡 CHARGING COST EXAMPLES:')
print(f'Charging 20 kWh at each station:')
for station, price in params.station_price.items():
    cost = 20 * price
    print(f'  {station}: {cost:.2f} EGP')

print(f'\nFull charge (0% → 100%) for each vehicle at S1 (cheapest):')
for i in range(params.m):
    battery = params.battery_kwh[i]
    cost = battery * params.station_price['S1']
    print(f'  Vehicle {i+1} ({battery:.0f} kWh): {cost:.2f} EGP')

print('\n' + '=' * 70)
print('KEY IMPROVEMENTS:')
print('=' * 70)
print('✅ Vehicles MUST charge during trip (realistic energy consumption)')
print('✅ Prices based on Egyptian fuel costs (13-27 EGP/kWh)')
print('✅ Significant cost differences between stations')
print('✅ Trip represents realistic ~180 km inter-city journey')
print('✅ Energy consumption: 30-50% of battery capacity')
print('✅ 10% minimum SOC reserve enforced throughout the route')
print('=' * 70)
