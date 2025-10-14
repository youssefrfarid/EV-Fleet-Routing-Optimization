# params.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple
import numpy as np

# ---- Types ----
Edge = Tuple[str, str]
PowerFn = Callable[[float, str], float]  # (soc in [0,1], station name) -> kW


@dataclass
class SingleForkParams:
    """
    Single-fork corridor:
        A -> J -> (Upper: S1 -> S2) / (Lower: S3) -> M -> B

    Units & conventions
    -------------------
    - Time in minutes
    - Energy in kWh
    - SOC in [0, 1] (fraction)
    - Power in kW
    - Prices in EGP/kWh
    - edges_* are dictionaries keyed by (u, v) directed edges that you will traverse in order.
    """

    # ---- Topology & travel ----
    nodes: Tuple[str, ...] = ("A", "J", "S1", "S2", "S3", "M", "B")
    upper_stations: Tuple[str, ...] = ("S1", "S2")
    lower_stations: Tuple[str, ...] = ("S3",)
    edges_time_min: Dict[Edge, float] = field(default_factory=dict)    # minutes
    edges_energy_kwh: Dict[Edge, float] = field(default_factory=dict)  # kWh

    # ---- Stations (capacity + flat price + caps) ----
    station_plugs: Dict[str, int] = field(default_factory=dict)        # concurrent plugs per station
    station_price: Dict[str, float] = field(default_factory=dict)      # flat EGP/kWh per station
    station_max_kw: Dict[str, float] = field(default_factory=dict)     # station hardware cap (kW)

    # ---- Charging model (universal, SOC-dependent) ----
    # One nonlinear curve shared by all EVs. Station argument is ignored here,
    # but kept in the signature so you can swap in station-specific curves later if desired.
    # Shape: near-constant up to ~80% SOC, then smooth taper (never zero).
    charge_power_kw_fn: PowerFn = staticmethod(
        lambda soc, _station: max(5.0, 140.0 if soc < 0.8 else 140.0 * (1.0 - (soc - 0.8) / 0.2) ** 0.5)
    )

    # Optional EV-side power cap (onboard charger / cable). Set to None to disable.
    ev_max_kw: float | None = None

    # Grid-to-battery efficiency (0<η≤1). If η<1, grid energy bought is larger than battery energy gained.
    eta_charge: float = 0.95

    # ---- Fleet ----
    m: int = 2
    battery_kwh: List[float] = field(default_factory=lambda: [55.0, 62.0])
    soc0: List[float] = field(default_factory=lambda: [0.60, 0.50])

    # ---- Objective weights & penalties (used by your evaluate()) ----
    w_time: float = 1.0
    w_cost: float = 1.0
    bigM: float = 1e6

    # =========================
    # Helper methods
    # =========================
    def price_at(self, station: str) -> float:
        """Flat price lookup (EGP/kWh)."""
        if station not in self.station_price:
            raise KeyError(f"No flat price for station '{station}'.")
        return float(self.station_price[station])

    def effective_power_kw(self, soc: float, station: str) -> float:
        """
        Universal curve value at this SOC, limited by station and (optional) EV caps.
        Returns a strictly positive kW to avoid infinite charging time near 100% SOC.
        """
        base = float(self.charge_power_kw_fn(soc, station))  # universal curve
        station_cap = self.station_max_kw.get(station, float("inf"))
        ev_cap = self.ev_max_kw if self.ev_max_kw is not None else float("inf")
        power = min(base, station_cap, ev_cap)
        return float(max(1e-6, power))

    def charge_time_seconds(
        self,
        soc_in: float,
        soc_out: float,
        battery_kwh: float,
        station: str,
        steps: int = 400,
    ) -> float:
        """
        Approximate time (seconds) to lift SOC from soc_in to soc_out at `station`.

        dt = ∫ (B/η) dSOC / P_eff(SOC) * 3600,
        where B=battery_kwh, η=eta_charge, and P_eff is effective_power_kw(soc, station).
        Uses a Riemann sum with `steps` partitions.
        """
        if soc_out <= soc_in:
            return 0.0
        # Clamp SOC bounds
        soc_in = max(0.0, min(1.0, soc_in))
        soc_out = max(0.0, min(1.0, soc_out))
        # Discretize SOC path
        socs = np.linspace(soc_in, soc_out, steps)
        d_soc = (soc_out - soc_in) / max(1, steps - 1)
        # Energy drawn from grid per step (kWh)
        dE_kwh = (battery_kwh / max(1e-9, self.eta_charge)) * d_soc
        # Time per step (h) = energy/power; then convert to seconds
        power_kw = np.array([self.effective_power_kw(float(s), station) for s in socs], dtype=float)
        dt_seconds = float(np.sum(dE_kwh / power_kw) * 3600.0)
        return dt_seconds

    def energy_bought_kwh(self, soc_in: float, soc_out: float, battery_kwh: float) -> float:
        """
        Grid energy (kWh) needed to raise SOC from soc_in to soc_out, accounting for η.
        """
        if soc_out <= soc_in:
            return 0.0
        return (battery_kwh * (soc_out - soc_in)) / max(1e-9, self.eta_charge)

    def validate(self) -> None:
        """Basic sanity checks for early failure."""
        node_set = set(self.nodes)

        # Edge keys reference known nodes
        all_edges = set(self.edges_time_min) | set(self.edges_energy_kwh)
        for (u, v) in all_edges:
            if u not in node_set or v not in node_set:
                raise ValueError(f"Edge ({u},{v}) references unknown nodes.")

        # Ensure both time and energy provided for each edge
        if set(self.edges_time_min) != set(self.edges_energy_kwh):
            missing_t = set(self.edges_energy_kwh) - set(self.edges_time_min)
            missing_e = set(self.edges_time_min) - set(self.edges_energy_kwh)
            if missing_t:
                raise ValueError(f"Missing travel time for edges: {sorted(missing_t)}")
            if missing_e:
                raise ValueError(f"Missing energy for edges: {sorted(missing_e)}")

        # Stations: have plugs, price, and a max kW (optional but recommended)
        for s in (*self.upper_stations, *self.lower_stations):
            if s not in self.station_plugs:
                raise ValueError(f"Missing plug count for station '{s}'.")
            if s not in self.station_price:
                raise ValueError(f"Missing flat price for station '{s}'.")
            # station_max_kw is optional; if absent we assume 'infinite' cap

        # Fleet arrays sizes
        if len(self.battery_kwh) != self.m or len(self.soc0) != self.m:
            raise ValueError("Lengths of battery_kwh and soc0 must match m (vehicle count).")
        if not all(0.0 <= s <= 1.0 for s in self.soc0):
            raise ValueError("Initial SOC values must be within [0,1].")
        if not (0.0 < self.eta_charge <= 1.0):
            raise ValueError("eta_charge must be in (0,1].")


# ---- Handy toy instance you can run immediately ----
def make_toy_params() -> SingleForkParams:
    """
    Create a small, reproducible instance with reasonable numbers.
    Upper branch is slightly longer but may be cheaper/faster to charge.
    """
    # Travel times (min)
    tt = {
        ("A", "J"): 10.0,
        ("J", "S1"): 8.0,
        ("S1", "S2"): 6.0,
        ("S2", "M"): 9.0,
        ("J", "S3"): 7.0,
        ("S3", "M"): 10.0,
        ("M", "B"): 11.0,
    }

    # Energy per edge (kWh) — toy linear model (~0.30 kWh/min)
    ee = {e: t * 0.30 for e, t in tt.items()}

    # Flat prices (EGP/kWh) and station caps (kW)
    station_price = {"S1": 0.12, "S2": 0.15, "S3": 0.20}
    station_max_kw = {"S1": 150.0, "S2": 120.0, "S3": 75.0}

    P = SingleForkParams(
        edges_time_min=tt,
        edges_energy_kwh=ee,
        station_plugs={"S1": 2, "S2": 1, "S3": 1},
        station_price=station_price,
        station_max_kw=station_max_kw,
        ev_max_kw=None,  # set to None if you don't want an EV-side cap
        m=2,
        battery_kwh=[55.0, 62.0],
        soc0=[0.60, 0.50],
        w_time=1.0,
        w_cost=1.0,
        bigM=1e6,
    )
    P.validate()
    return P
