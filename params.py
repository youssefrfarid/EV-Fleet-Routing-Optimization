# params.py
"""
Parameter definitions for EV Fleet Routing Optimization.

This module defines the problem structure including:
- Network topology (nodes, edges, travel times, energy consumption)
- Charging station characteristics (capacity, pricing, power limits)
- EV fleet specifications (battery sizes, initial state of charge)
- Physical charging models (SOC-dependent curves, efficiency losses)

All parameters are bundled in the SingleForkParams dataclass.
"""

from __future__ import annotations  # Enables forward type references
from dataclasses import dataclass, field  # For clean data structures
from typing import Callable, Dict, List, Tuple  # Type hints for clarity
import numpy as np  # For numerical integration

# ========================================
# Type Definitions
# ========================================

# Edge: Directed edge between two nodes, e.g., ('A', 'J') means A→J
Edge = Tuple[str, str]

# PowerFn: Charging power function signature
# Takes: SOC (0-1 fraction), station name
# Returns: Charging power in kW
PowerFn = Callable[[float, str], float]

# Speed levels: 5 discrete options for travel speed
# Each level affects travel time and energy consumption
# Lower speed = more time but less energy
# Higher speed = less time but more energy
SPEED_LEVELS = {
    1: "Very Slow",   # Most energy-efficient, slowest
    2: "Slow",        # Energy-efficient, slow
    3: "Normal",      # Baseline (current default)
    4: "Fast",        # Less efficient, faster
    5: "Very Fast",   # Least efficient, fastest
}

# Speed multipliers for time and energy
# For a baseline edge with time T and energy E:
# - Speed level affects travel time: time = T × time_multiplier
# - Speed level affects energy: energy = E × energy_multiplier
# Physics: Higher speed → less time but more energy (air resistance increases quadratically)
SPEED_TIME_MULTIPLIERS = {
    1: 1.40,   # 40% more time (very slow)
    2: 1.20,   # 20% more time (slow)
    3: 1.00,   # Baseline time (normal)
    4: 0.85,   # 15% less time (fast)
    5: 0.70,   # 30% less time (very fast)
}

SPEED_ENERGY_MULTIPLIERS = {
    1: 0.75,   # 25% less energy (very efficient)
    2: 0.90,   # 10% less energy (efficient)
    3: 1.00,   # Baseline energy (normal)
    4: 1.20,   # 20% more energy (less efficient)
    5: 1.50,   # 50% more energy (high consumption due to air resistance)
}


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

    # ========================================
    # Network Topology & Travel Parameters
    # ========================================

    # All nodes in the network (A=start, B=end, J=junction, M=merge, S*=stations)
    nodes: Tuple[str, ...] = ("A", "J", "S1", "S2", "S3", "M", "B")

    # Charging stations on upper branch (longer path, more options)
    upper_stations: Tuple[str, ...] = ("S1", "S2")

    # Charging stations on lower branch (shorter path, fewer options)
    lower_stations: Tuple[str, ...] = ("S3",)

    # Travel time for each directed edge (minutes)
    # Key: (source_node, destination_node), Value: travel time
    edges_time_min: Dict[Edge, float] = field(default_factory=dict)

    # Energy consumed on each directed edge (kWh)
    # Depends on distance, speed, terrain, weather
    edges_energy_kwh: Dict[Edge, float] = field(default_factory=dict)

    # ========================================
    # Charging Station Characteristics
    # ========================================

    # Number of concurrent charging plugs per station (capacity constraint)
    # If N vehicles arrive simultaneously, max N can charge at once
    station_plugs: Dict[str, int] = field(default_factory=dict)

    # Flat price per kWh at each station (EGP/kWh)
    # Different stations may have different pricing strategies
    station_price: Dict[str, float] = field(default_factory=dict)

    # Maximum power output of station hardware (kW)
    # Physical limit of the charging equipment
    station_max_kw: Dict[str, float] = field(default_factory=dict)

    # ========================================
    # Charging Physics Model
    # ========================================

    # Universal SOC-dependent charging power curve
    # Physics: Batteries charge fast at low SOC, then taper at high SOC to avoid damage
    # - Below 80% SOC: constant 140 kW (fast charging)
    # - Above 80% SOC: smooth taper using square root function
    # - Minimum 5 kW floor to avoid infinite charging time
    # Station argument currently ignored (same curve for all), but kept for extensibility
    charge_power_kw_fn: PowerFn = staticmethod(
        lambda soc, _station: max(
            5.0, 140.0 if soc < 0.8 else 140.0 * (1.0 - (soc - 0.8) / 0.2) ** 0.5)
    )

    # Optional EV-side power limit (onboard charger / cable maximum)
    # Set to None to disable EV-side limitation (only station limits apply)
    # Set to a value (e.g., 50.0) to limit all vehicles to that power
    ev_max_kw: float | None = None

    # Grid-to-battery charging efficiency (η, eta)
    # Range: 0 < η ≤ 1.0
    # If η < 1, energy drawn from grid > energy stored in battery
    # Example: η=0.95 means 5% losses → need 10.53 kWh from grid to store 10 kWh
    eta_charge: float = 0.95

    # ========================================
    # Fleet Specification
    # ========================================

    # Number of vehicles in the fleet
    m: int = 2

    # Battery capacity for each vehicle (kWh)
    # List of length m, one value per vehicle
    # Larger batteries = more range but heavier vehicle
    battery_kwh: List[float] = field(default_factory=lambda: [55.0, 62.0])

    # Initial state of charge for each vehicle (fraction 0-1)
    # List of length m, one value per vehicle
    # Example: 0.60 = 60% charged
    soc0: List[float] = field(default_factory=lambda: [0.60, 0.50])

    # ========================================
    # Optimization Parameters
    # ========================================

    # Weight for time objective (higher = prioritize speed)
    # Used in weighted objective: w_time × makespan + w_cost × total_cost
    w_time: float = 1.0

    # Weight for cost objective (higher = prioritize savings)
    # Used in weighted objective: w_time × makespan + w_cost × total_cost
    w_cost: float = 1.0

    # Big-M constant for penalty terms in optimization
    # Large number used to enforce hard constraints
    # Typical in Mixed Integer Programming formulations
    bigM: float = 1e6

    # ========================================
    # Helper Methods
    # ========================================

    def get_edge_time(self, edge: Edge, speed_level: int = 3) -> float:
        """
        Get travel time for an edge at a specific speed level.

        Args:
            edge: Directed edge tuple (source, destination)
            speed_level: Speed level (1-5, default 3 = Normal)
                1 = Very Slow, 2 = Slow, 3 = Normal, 4 = Fast, 5 = Very Fast

        Returns:
            Travel time in minutes

        Raises:
            KeyError: If edge not found
            ValueError: If speed_level not in [1, 5]
        """
        if edge not in self.edges_time_min:
            raise KeyError(f"Edge {edge} not found in network.")
        if speed_level not in SPEED_LEVELS:
            raise ValueError(
                f"Speed level must be in [1, 5], got {speed_level}")

        base_time = self.edges_time_min[edge]
        multiplier = SPEED_TIME_MULTIPLIERS[speed_level]
        return base_time * multiplier

    def get_edge_energy(self, edge: Edge, speed_level: int = 3) -> float:
        """
        Get energy consumption for an edge at a specific speed level.

        Args:
            edge: Directed edge tuple (source, destination)
            speed_level: Speed level (1-5, default 3 = Normal)
                1 = Very Slow, 2 = Slow, 3 = Normal, 4 = Fast, 5 = Very Fast

        Returns:
            Energy consumption in kWh

        Raises:
            KeyError: If edge not found
            ValueError: If speed_level not in [1, 5]
        """
        if edge not in self.edges_energy_kwh:
            raise KeyError(f"Edge {edge} not found in network.")
        if speed_level not in SPEED_LEVELS:
            raise ValueError(
                f"Speed level must be in [1, 5], got {speed_level}")

        base_energy = self.edges_energy_kwh[edge]
        multiplier = SPEED_ENERGY_MULTIPLIERS[speed_level]
        return base_energy * multiplier

    def get_all_speed_options(self, edge: Edge) -> List[Tuple[int, str, float, float]]:
        """
        Get all 5 speed options for an edge with their time and energy values.

        Args:
            edge: Directed edge tuple (source, destination)

        Returns:
            List of tuples: (speed_level, speed_name, time_minutes, energy_kwh)

        Example:
            >>> params.get_all_speed_options(('A', 'J'))
            [
                (1, "Very Slow", 21.0, 3.375),
                (2, "Slow", 18.0, 4.05),
                (3, "Normal", 15.0, 4.5),
                (4, "Fast", 12.75, 5.4),
                (5, "Very Fast", 10.5, 6.75)
            ]
        """
        options = []
        for level in range(1, 6):
            name = SPEED_LEVELS[level]
            time = self.get_edge_time(edge, level)
            energy = self.get_edge_energy(edge, level)
            options.append((level, name, time, energy))
        return options

    def price_at(self, station: str) -> float:
        """
        Get the flat price at a given charging station.

        Args:
            station: Station name (e.g., 'S1', 'S2', 'S3')

        Returns:
            Price in EGP per kWh

        Raises:
            KeyError: If station not found in station_price dictionary
        """
        if station not in self.station_price:
            raise KeyError(f"No flat price for station '{station}'.")
        return float(self.station_price[station])

    def effective_power_kw(self, soc: float, station: str) -> float:
        """
        Calculate actual charging power at given SOC and station.

        Takes the minimum of:
        1. Base charging curve value (physics-based)
        2. Station hardware limit
        3. EV onboard charger limit (if specified)

        Args:
            soc: State of charge (0-1 fraction)
            station: Station name (e.g., 'S1')

        Returns:
            Effective charging power in kW (strictly positive)
            Minimum return value is 1e-6 kW to avoid division by zero

        Example:
            At 50% SOC at station S1 (50 kW limit):
            - Base curve: 140 kW
            - Station limit: 50 kW
            - EV limit: None
            - Result: min(140, 50, inf) = 50 kW
        """
        # Get base power from universal charging curve
        base = float(self.charge_power_kw_fn(soc, station))

        # Get station hardware limit (infinity if not specified)
        station_cap = self.station_max_kw.get(station, float("inf"))

        # Get EV-side limit (infinity if not specified)
        ev_cap = self.ev_max_kw if self.ev_max_kw is not None else float("inf")

        # Take minimum of all three limits
        power = min(base, station_cap, ev_cap)

        # Ensure strictly positive (avoid infinite charging time)
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
        Calculate charging time using numerical integration (Riemann sum).

        Physics formula:
            time = ∫ (Battery_capacity / efficiency) × dSOC / Power(SOC) × 3600

        Why numerical integration?
        Power varies with SOC (charging curve), so we can't use a simple formula.
        We divide the SOC range into small steps and sum up time for each step.

        Args:
            soc_in: Starting state of charge (0-1)
            soc_out: Target state of charge (0-1)
            battery_kwh: Battery capacity in kWh
            station: Station name (affects power limits)
            steps: Number of integration steps (default 400 for accuracy)

        Returns:
            Charging time in seconds

        Example:
            Charging from 20% to 80% on a 60 kWh battery at station S1:
            time_sec = params.charge_time_seconds(0.2, 0.8, 60.0, 'S1')
        """
        # No charging needed if target <= starting SOC
        if soc_out <= soc_in:
            return 0.0

        # Clamp SOC to valid range [0, 1] to handle edge cases
        soc_in = max(0.0, min(1.0, soc_in))
        soc_out = max(0.0, min(1.0, soc_out))

        # Create array of SOC values from start to end (integration points)
        # Example: [0.2, 0.2015, 0.203, ..., 0.8] for 400 steps
        socs = np.linspace(soc_in, soc_out, steps)

        # Calculate SOC increment per step
        d_soc = (soc_out - soc_in) / max(1, steps - 1)

        # Energy drawn from GRID per SOC step (accounts for efficiency loss)
        # Battery gains (battery_kwh × d_soc) kWh, but grid provides more due to losses
        # Example: 0.95 efficiency means grid provides 1.0526× battery gain
        dE_kwh = (battery_kwh / max(1e-9, self.eta_charge)) * d_soc

        # Calculate charging power at each SOC point
        # Power varies with SOC due to charging curve
        power_kw = np.array([self.effective_power_kw(
            float(s), station) for s in socs], dtype=float)

        # Time for each step = Energy / Power (in hours), then convert to seconds
        # Sum all steps to get total charging time
        dt_seconds = float(np.sum(dE_kwh / power_kw) * 3600.0)
        return dt_seconds

    def energy_bought_kwh(self, soc_in: float, soc_out: float, battery_kwh: float) -> float:
        """
        Calculate grid energy needed to increase SOC (accounts for charging efficiency).

        Formula:
            Grid_energy = (Battery_capacity × ΔSOC) / efficiency

        Why divide by efficiency?
        Not all grid energy makes it into the battery. Some is lost as heat.

        Args:
            soc_in: Starting SOC (0-1)
            soc_out: Target SOC (0-1)
            battery_kwh: Battery capacity

        Returns:
            Energy purchased from grid in kWh

        Example:
            60 kWh battery, charge from 20% to 80%, 95% efficiency:
            Battery gains: 60 × (0.8 - 0.2) = 36 kWh
            Grid provides: 36 / 0.95 = 37.89 kWh
            Lost as heat: 1.89 kWh
        """
        # No energy needed if not increasing SOC
        if soc_out <= soc_in:
            return 0.0

        # Calculate grid energy accounting for efficiency losses
        return (battery_kwh * (soc_out - soc_in)) / max(1e-9, self.eta_charge)

    def validate(self) -> None:
        """
        Validate all parameters for consistency and correctness.

        Performs comprehensive checks on:
        - Network topology (nodes, edges)
        - Station specifications (plugs, prices, power)
        - Fleet configuration (battery sizes, initial SOC)
        - Physical constraints (efficiency, SOC ranges)

        Raises:
            ValueError: If any parameter is invalid or inconsistent

        Why validate?
        Fail fast with clear error messages rather than mysterious bugs later.
        """
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
                raise ValueError(
                    f"Missing travel time for edges: {sorted(missing_t)}")
            if missing_e:
                raise ValueError(
                    f"Missing energy for edges: {sorted(missing_e)}")

        # Stations: have plugs, price, and a max kW (optional but recommended)
        for s in (*self.upper_stations, *self.lower_stations):
            if s not in self.station_plugs:
                raise ValueError(f"Missing plug count for station '{s}'.")
            if s not in self.station_price:
                raise ValueError(f"Missing flat price for station '{s}'.")
            # station_max_kw is optional; if absent we assume 'infinite' cap

        # Fleet arrays sizes
        if len(self.battery_kwh) != self.m or len(self.soc0) != self.m:
            raise ValueError(
                "Lengths of battery_kwh and soc0 must match m (vehicle count).")
        if not all(0.10 <= s <= 1.0 for s in self.soc0):
            raise ValueError("Initial SOC values must be within [0.10, 1.0].")
        if not (0.0 < self.eta_charge <= 1.0):
            raise ValueError("eta_charge must be in (0,1].")


# ========================================
# Factory Function for Test Instance
# ========================================

def make_toy_params() -> SingleForkParams:
    """
    Create a realistic test instance with 5 vehicles and 3 stations.

    This function builds a complete problem instance representing a realistic
    inter-city trip (e.g., Cairo to Alexandria, ~220 km total distance).

    Fleet Composition:
        - Vehicle 1: 40 kWh (compact, like Nissan Leaf base) - starts at 62%
        - Vehicle 2: 55 kWh (sedan, like Chevy Bolt) - starts at 48%
        - Vehicle 3: 62 kWh (extended sedan, like Nissan Leaf Plus) - starts at 45%
        - Vehicle 4: 75 kWh (SUV, like Tesla Model Y) - starts at 52%
        - Vehicle 5: 80 kWh (large SUV, like Audi e-tron) - starts at 47%

    Station Pricing (based on Gas 95 @ 21.75 EGP/liter):
        - S1: Budget AC charging (13.0 EGP/kWh, slow 50kW, 2 plugs)
        - S2: Premium ultra-fast DC (27.0 EGP/kWh, fast 180kW, 1 plug)
        - S3: Standard DC fast (20.0 EGP/kWh, medium 100kW, 1 plug)

    Pricing rationale:
        - Gas 95: 21.75 EGP/liter, 12 km/liter → 1.81 EGP/km
        - EV: 6 km/kWh → 10.86 EGP/kWh cost parity
        - Public charging markup: +20% to +150% over home charging

    Energy Consumption:
        - Trip uses 40-60% of battery capacity (realistic long-distance)
        - Total distance: ~220 km (Cairo to Alexandria distance)
        - Upper route (A→J→S1→S2→M→B): 48.1 kWh (~60% of 80kWh battery)
        - Lower route (A→J→S3→M→B): 44.6 kWh (~56% of 80kWh battery)
        - Vehicles MUST charge during trip to complete journey!

    Network Design:
        - Upper route (S1→S2): Longer distance, more charging options
        - Lower route (S3): Shorter distance, but VERY hilly (S3→M uses 15.3 kWh!)

    Returns:
        SingleForkParams: Fully configured and validated parameter object

    Example:
        >>> params = make_toy_params()
        >>> print(f"Fleet size: {params.m}")
        Fleet size: 5
        >>> print(f"Trip energy (upper route): {8.4+11.5+8.7+8.7+10.8:.1f} kWh")
        Trip energy (upper route): 48.1 kWh
        >>> print(f"Charging needed for 40kWh EV starting at 62%: ~{48.1 - 40*0.62:.1f} kWh")
        Charging needed for 40kWh EV starting at 62%: ~23.3 kWh
    """
    # ========================================
    # Travel Times (minutes)
    # ========================================
    # Realistic inter-city trip (e.g., Cairo to Alexandria ~220 km)
    # Total travel time: ~2.5-3.5 hours depending on route and speed
    tt = {
        ("A", "J"): 30.0,      # 30 min to highway junction (urban exit, traffic)
        ("J", "S1"): 45.0,     # 45 min highway to first station (~70 km)
        ("S1", "S2"): 35.0,    # 35 min between upper route stations (~55 km)
        ("S2", "M"): 32.0,     # 32 min to merge point (~50 km)
        ("J", "S3"): 38.0,     # 38 min to lower station (~60 km, slower road)
        ("S3", "M"): 48.0,     # 48 min to merge (hilly terrain, ~65 km)
        ("M", "B"): 40.0,      # 40 min to destination (final approach, ~60 km)
    }

    # ========================================
    # Energy Consumption (kWh per edge)
    # ========================================
    # Realistic long-distance consumption for ~220 km trip
    # Based on realistic EV consumption: 0.16-0.20 kWh/km (5-6 km/kWh)
    # Trip uses 40-60% of battery capacity (realistic for long trips)
    #
    # Distance estimates and consumption:
    #   A→J: 40 km × 0.21 kWh/km = 8.4 kWh (urban exit, traffic)
    #   J→S1: 70 km × 0.165 kWh/km = 11.5 kWh (highway, efficient cruise)
    #   S1→S2: 55 km × 0.158 kWh/km = 8.7 kWh (highway flat, optimal)
    #   S2→M: 50 km × 0.174 kWh/km = 8.7 kWh (mixed terrain)
    #   J→S3: 60 km × 0.168 kWh/km = 10.1 kWh (alternative highway)
    #   S3→M: 65 km × 0.235 kWh/km = 15.3 kWh (hilly climb, HIGH!)
    #   M→B: 60 km × 0.180 kWh/km = 10.8 kWh (city approach)
    #
    # Total energy consumption:
    #   Upper route (A→J→S1→S2→M→B): 8.4+11.5+8.7+8.7+10.8 = 48.1 kWh (~60% of 80kWh battery)
    #   Lower route (A→J→S3→M→B): 8.4+10.1+15.3+10.8 = 44.6 kWh (~56% of 80kWh battery)
    ee = {
        ("A", "J"): 8.4,       # Urban exit, 40 km, heavy traffic
        ("J", "S1"): 11.5,     # Highway cruise, 70 km, efficient
        ("S1", "S2"): 8.7,     # Highway flat, 55 km, optimal conditions
        ("S2", "M"): 8.7,      # Mixed terrain, 50 km
        ("J", "S3"): 10.1,     # Highway alternative, 60 km
        ("S3", "M"): 15.3,     # HILLY CLIMB, 65 km - VERY HIGH consumption!
        ("M", "B"): 10.8,      # City approach, 60 km
    }

    # ========================================
    # Station Characteristics
    # ========================================
    # Realistic Egyptian charging prices (based on Gas 95 @ 21.75 EGP/liter)
    # Calculation basis:
    #   - Gas 95: 21.75 EGP/liter
    #   - Average ICE: 12 km/liter → 1.81 EGP/km
    #   - Average EV: 6 km/kWh → equivalent 10.86 EGP/kWh (cost parity)
    #   - Public charging markup over home charging (~5 EGP/kWh home rate):
    #       Budget AC slow: +160% → 13.0 EGP/kWh
    #       Standard DC fast: +300% → 20.0 EGP/kWh
    #       Premium ultra-fast: +440% → 27.0 EGP/kWh
    station_price = {
        "S1": 13.0,   # Budget AC charging: 13.0 EGP/kWh (cheapest, slowest)
        # Premium ultra-fast DC: 27.0 EGP/kWh (expensive, fastest)
        "S2": 27.0,
        "S3": 20.0,   # Standard DC fast: 20.0 EGP/kWh (balanced)
    }

    station_max_kw = {
        "S1": 50.0,   # Slow AC charging (Level 2)
        "S2": 180.0,  # Ultra-fast DC (Premium Tesla Supercharger-style)
        "S3": 100.0,  # Fast DC (Standard public charger)
    }

    # ========================================
    # Fleet Configuration
    # ========================================
    # 5 vehicles representing different EV market segments
    # Moderate initial SOCs (45-62%) keep >10% reserve yet require charging mid-trip
    # Trip consumes 40-60% of battery capacity, forcing strategic charging decisions
    P = SingleForkParams(
        edges_time_min=tt,
        edges_energy_kwh=ee,
        # S1 has more plugs (slower)
        station_plugs={"S1": 2, "S2": 1, "S3": 1},
        station_price=station_price,
        station_max_kw=station_max_kw,
        ev_max_kw=None,  # No EV-side power cap
        m=5,  # 5 vehicles
        # Different battery capacities
        battery_kwh=[40.0, 55.0, 62.0, 75.0, 80.0],
        # Initial SOCs high enough to keep >10% reserve, still require charging
        soc0=[0.62, 0.48, 0.45, 0.52, 0.47],
        w_time=1.0,
        w_cost=1.0,
        bigM=1e6,
    )
    # Validate all parameters before returning
    # This catches any configuration errors early
    P.validate()

    return P
    # Validate all parameters before returning
    # This catches any configuration errors early
    P.validate()

    return P
