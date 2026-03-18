"""
case_studies.py

Defines reusable case-study scenarios for benchmarking analysis. Each case
instantiates a parameter object with explicit metadata so scripts can document
inputs, run optimizers, and export results tables automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from common.params import DoubleForkParams, SingleForkParams, make_double_fork_params, make_toy_params


def _build_double_fork_baseline() -> DoubleForkParams:
    """Standard double-fork baseline with 3 vehicles."""
    params = make_double_fork_params()
    # Use default 3 vehicles with standard configuration
    params.validate()
    return params


@dataclass(frozen=True)
class CaseStudy:
    """Metadata for a reproducible case study."""

    case_id: str
    name: str
    description: str
    topology: str
    build_params: Callable[[], SingleForkParams]
    inputs: Dict[str, str]


def _build_single_baseline() -> SingleForkParams:
    """Original single-fork instance from single-fork baseline."""
    params = make_toy_params()
    params.validate()
    return params


def _build_double_fork_congested() -> DoubleForkParams:
    """Double fork with tighter charging capacity and larger fleet."""
    params = make_double_fork_params()
    params.m = 6
    params.battery_kwh = [40.0, 50.0, 55.0, 62.0, 75.0, 85.0]
    params.soc0 = [0.70, 0.55, 0.58, 0.54, 0.50, 0.45]
    params.station_plugs = {station: max(1, plugs - 1) for station, plugs in params.station_plugs.items()}
    params.validate()
    return params


def _build_double_fork_high_demand() -> DoubleForkParams:
    """Double fork with high demand (7 vehicles) and expensive energy."""
    params = make_double_fork_params()
    params.m = 7
    params.battery_kwh = [45.0, 55.0, 62.0, 70.0, 80.0, 90.0, 95.0]
    params.soc0 = [0.65, 0.58, 0.52, 0.48, 0.45, 0.50, 0.40]
    params.station_price = {
        station: price * 1.15 for station, price in params.station_price.items()
    }
    params.station_plugs["S2"] = 2
    params.station_plugs["S5"] = 2
    params.validate()
    return params


CASE_STUDIES: List[CaseStudy] = [
    CaseStudy(
        case_id="double_baseline",
        name="Double Fork – Baseline",
        description="Standard 3-vehicle double-fork instance with default settings.",
        topology="double",
        build_params=_build_double_fork_baseline,
        inputs={
            "vehicles": "3 EVs (50, 60, 70 kWh)",
            "stations": "6 stations (S1-S6) with standard pricing",
            "objective_weights": "w_time=1.0, w_cost=1.0",
        },
    ),
    CaseStudy(
        case_id="double_congested",
        name="Double Fork – Congested Grid",
        description="6 vehicles with reduced charging plugs to force queues.",
        topology="double",
        build_params=_build_double_fork_congested,
        inputs={
            "vehicles": "6 EVs (40–85 kWh), tighter SOC range",
            "station_plugs": "All plugs reduced by one (min 1)",
            "objective_weights": "w_time=1.0, w_cost=1.0",
        },
    ),
    CaseStudy(
        case_id="double_high_demand",
        name="Double Fork – High Demand & Pricing",
        description="7 vehicles with increased public charging tariffs.",
        topology="double",
        build_params=_build_double_fork_high_demand,
        inputs={
            "vehicles": "7 EVs up to 95 kWh",
            "pricing": "+15% multiplier on station prices",
            "plugs": "Fast stations S2/S5 upgraded to 2 plugs",
        },
    ),
    CaseStudy(
        case_id="single_small",
        name="Single Fork – Small Fleet",
        description="3 vehicles on single-fork topology for baseline comparison.",
        topology="single",
        build_params=lambda: make_toy_params(),
        inputs={
            "vehicles": "3 EVs (40, 60, 80 kWh)",
            "stations": "S1, S2, S3",
            "objective_weights": "w_time=1.0, w_cost=1.0",
        },
    ),
    CaseStudy(
        case_id="single_large",
        name="Single Fork – Large Fleet",
        description="7 vehicles on single-fork to test scalability.",
        topology="single",
        build_params=lambda: _build_single_large(),
        inputs={
            "vehicles": "7 EVs (40-95 kWh)",
            "stations": "S1, S2, S3 with standard capacity",
            "objective_weights": "w_time=1.0, w_cost=1.0",
        },
    ),
    CaseStudy(
        case_id="double_sparse",
        name="Double Fork – Sparse Network",
        description="4 vehicles with minimal station capacity.",
        topology="double",
        build_params=lambda: _build_double_sparse(),
        inputs={
            "vehicles": "4 EVs (45-75 kWh)",
            "stations": "All stations with 1 plug only",
            "objective_weights": "w_time=1.0, w_cost=1.0",
        },
    ),
    CaseStudy(
        case_id="double_balanced",
        name="Double Fork – Balanced Fleet",
        description="5 vehicles with mixed battery capacities and moderate pricing.",
        topology="double",
        build_params=lambda: _build_double_balanced(),
        inputs={
            "vehicles": "5 EVs (40-80 kWh)",
            "stations": "Standard capacity, moderate pricing",
            "objective_weights": "w_time=1.0, w_cost=1.0",
        },
    ),
    CaseStudy(
        case_id="double_premium",
        name="Double Fork – Premium Charging",
        description="4 vehicles with expensive fast charging options.",
        topology="double",
        build_params=lambda: _build_double_premium(),
        inputs={
            "vehicles": "4 EVs (55-85 kWh)",
            "stations": "+25% pricing, 2 plugs at fast stations",
            "objective_weights": "w_time=1.0, w_cost=1.0",
        },
    ),
]


def _build_single_large() -> SingleForkParams:
    """Single-fork with 7 vehicles."""
    params = make_toy_params()
    params.m = 7
    params.battery_kwh = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 95.0]
    params.soc0 = [0.65, 0.60, 0.55, 0.50, 0.48, 0.45, 0.42]
    params.validate()
    return params


def _build_double_sparse() -> DoubleForkParams:
    """Double-fork with minimal capacity."""
    params = make_double_fork_params()
    params.m = 4
    params.battery_kwh = [45.0, 55.0, 65.0, 75.0]
    params.soc0 = [0.60, 0.55, 0.50, 0.48]
    # All stations have only 1 plug
    params.station_plugs = {station: 1 for station in params.station_plugs.keys()}
    params.validate()
    return params


def _build_double_balanced() -> DoubleForkParams:
    """Double-fork with 5 vehicles and balanced settings."""
    params = make_double_fork_params()
    params.m = 5
    params.battery_kwh = [40.0, 52.0, 63.0, 72.0, 80.0]
    params.soc0 = [0.62, 0.58, 0.54, 0.50, 0.47]
    params.validate()
    return params


def _build_double_premium() -> DoubleForkParams:
    """Double-fork with expensive charging."""
    params = make_double_fork_params()
    params.m = 4
    params.battery_kwh = [55.0, 65.0, 75.0, 85.0]
    params.soc0 = [0.58, 0.52, 0.48, 0.45]
    # Increase all prices by 25%
    params.station_price = {
        station: price * 1.25 for station, price in params.station_price.items()
    }
    # Upgrade fast stations
    params.station_plugs["S2"] = 2
    params.station_plugs["S5"] = 2
    params.validate()
    return params


def get_case_study(case_id: str) -> CaseStudy:
    """Return a case-study object by id."""
    for case in CASE_STUDIES:
        if case.case_id == case_id:
            return case
    raise KeyError(f"Unknown case study '{case_id}'. Available: {[c.case_id for c in CASE_STUDIES]}")


def list_case_studies() -> List[CaseStudy]:
    """Ordered list for UI / scripts."""
    return CASE_STUDIES.copy()
