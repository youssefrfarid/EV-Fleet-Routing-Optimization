"""
Lightweight checks for the continuous speed model.

This script exercises the helper methods in `SingleForkParams` and the
speed validation logic in `FleetSolution` to make sure imports and defaults
work after the repository restructure.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

# Allow running directly via `python scripts/test_speed_levels.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from common.params import make_toy_params
from common.objectives import VehicleSolution, FleetSolution


def show_speed_bounds(edge: Tuple[str, str]) -> None:
    params = make_toy_params()
    min_speed, max_speed = params.get_edge_speed_bounds(edge)
    print("=" * 70)
    print("Speed bounds per edge")
    print("=" * 70)
    print(f"Edge {edge}: min {min_speed:.1f} km/h, max {max_speed:.1f} km/h\n")


def time_energy_tradeoff(edge: Tuple[str, str]) -> None:
    params = make_toy_params()
    speeds = [60.0, 80.0, 100.0]
    print("=" * 70)
    print("Time/energy trade-off across speeds")
    print("=" * 70)
    print(f"{'Speed (km/h)':<15}{'Time (min)':<15}{'Energy (kWh)':<15}")
    print("-" * 45)
    for speed in speeds:
        time_min = params.get_edge_time(edge, speed)
        energy = params.get_edge_energy(edge, speed)
        print(f"{speed:<15.1f}{time_min:<15.2f}{energy:<15.2f}")
    print()


def validate_speed_assignments(edge: Tuple[str, str]) -> None:
    params = make_toy_params()

    # Valid speeds stay within the per-edge limits
    vs_ok = VehicleSolution(
        vehicle_id=0,
        route=["A", "J", "S1", "S2", "M", "B"],
        charging_stations=["S1"],
        charging_amounts={"S1": 12.0},
        speed_levels={
            ("A", "J"): 65.0,
            ("J", "S1"): 90.0,
            ("S1", "S2"): 90.0,
            ("S2", "M"): 90.0,
            ("M", "B"): 70.0,
        },
        arrival_times={"A": 0, "J": 20, "S1": 40, "S2": 60, "M": 80, "B": 100},
        departure_times={"A": 0, "J": 20, "S1": 50, "S2": 60, "M": 80, "B": 100},
        soc_at_nodes={"A": 0.8, "J": 0.6, "S1": 0.4, "S2": 0.5, "M": 0.4, "B": 0.3},
    )
    fleet_ok = FleetSolution([vs_ok], params)
    ok_result = fleet_ok._check_speed_levels(vs_ok, verbose=True, vehicle_idx=0)

    # Invalid speed drops below edge minimum to demonstrate validation
    vs_bad = VehicleSolution(
        vehicle_id=1,
        route=["A", "J", "S1", "S2", "M", "B"],
        charging_stations=["S2"],
        charging_amounts={"S2": 8.0},
        speed_levels={
            ("A", "J"): 20.0,  # Below min bound
            ("J", "S1"): 90.0,
        },
        arrival_times={"A": 0, "J": 22, "S1": 44, "S2": 66, "M": 88, "B": 110},
        departure_times={"A": 0, "J": 22, "S1": 44, "S2": 76, "M": 88, "B": 110},
        soc_at_nodes={"A": 0.75, "J": 0.55, "S1": 0.35, "S2": 0.45, "M": 0.35, "B": 0.25},
    )
    fleet_bad = FleetSolution([vs_bad], params)
    bad_result = fleet_bad._check_speed_levels(vs_bad, verbose=True, vehicle_idx=1)

    print("=" * 70)
    print("Validation results")
    print("=" * 70)
    print(f"Within-bounds speeds: {ok_result}")
    print(f"Below-min speed rejected: {bad_result}")
    print()


def default_speed_fallback(edge: Tuple[str, str]) -> None:
    vs_default = VehicleSolution(
        vehicle_id=2,
        route=["A", "J", "S1", "S2", "M", "B"],
        charging_stations=[],
        charging_amounts={},
        speed_levels=None,
        arrival_times={"A": 0, "J": 20, "S1": 40, "S2": 60, "M": 80, "B": 100},
        departure_times={"A": 0, "J": 20, "S1": 40, "S2": 60, "M": 80, "B": 100},
        soc_at_nodes={"A": 0.8, "J": 0.7, "S1": 0.6, "S2": 0.5, "M": 0.4, "B": 0.3},
    )
    speed = vs_default.get_speed_level(edge)
    print("=" * 70)
    print("Default speed fallback")
    print("=" * 70)
    print(f"No speeds provided; {edge} falls back to {speed:.1f} km/h\n")


if __name__ == "__main__":
    target_edge = ("A", "J")
    show_speed_bounds(target_edge)
    time_energy_tradeoff(target_edge)
    validate_speed_assignments(target_edge)
    default_speed_fallback(target_edge)
