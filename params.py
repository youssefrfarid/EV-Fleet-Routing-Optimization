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
        lambda soc, _station: max(5.0, 140.0 if soc < 0.8 else 140.0 * (1.0 - (soc - 0.8) / 0.2) ** 0.5)
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
        power_kw = np.array([self.effective_power_kw(float(s), station) for s in socs], dtype=float)
        
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


# ========================================
# Factory Function for Test Instance
# ========================================

def make_toy_params() -> SingleForkParams:
    """
    Create a realistic test instance with 5 vehicles and 3 stations.
    
    This function builds a complete problem instance that can be used immediately
    for testing, visualization, and optimization algorithm development.
    
    Fleet Composition:
        - Vehicle 1: 40 kWh (compact, like Nissan Leaf base)
        - Vehicle 2: 55 kWh (sedan, like Chevy Bolt)
        - Vehicle 3: 62 kWh (extended sedan, like Nissan Leaf Plus)
        - Vehicle 4: 75 kWh (SUV, like Tesla Model Y)
        - Vehicle 5: 80 kWh (large SUV, like Audi e-tron)
    
    Station Types:
        - S1: Budget (slow 50kW, cheap 0.10 EGP/kWh, 3 plugs)
        - S2: Premium (fast 180kW, expensive 0.25 EGP/kWh, 2 plugs)
        - S3: Standard (medium 100kW, medium 0.16 EGP/kWh, 2 plugs)
    
    Network Design:
        - Upper route (S1→S2): Longer time, more charging options
        - Lower route (S3): Shorter time, hilly terrain (more energy)
    
    Returns:
        SingleForkParams: Fully configured and validated parameter object
        
    Example:
        >>> params = make_toy_params()
        >>> print(f"Fleet size: {params.m}")
        Fleet size: 5
    """
    # ========================================
    # Travel Times (minutes)
    # ========================================
    # Realistic highway/urban mix with varied conditions
    tt = {
        ("A", "J"): 15.0,      # 15 min to junction
        ("J", "S1"): 12.0,     # 12 min to first upper station
        ("S1", "S2"): 8.0,     # 8 min between upper stations
        ("S2", "M"): 10.0,     # 10 min to merge point
        ("J", "S3"): 9.0,      # 9 min to lower station (shorter route)
        ("S3", "M"): 14.0,     # 14 min to merge (longer after station)
        ("M", "B"): 13.0,      # 13 min to destination
    }

    # ========================================
    # Energy Consumption (kWh per edge)
    # ========================================
    # Varies by road type, gradient, and driving conditions
    # Reference rates:
    #   - Highway (flat): ~0.30 kWh/min
    #   - Urban (stop-go): ~0.30 kWh/min  
    #   - Hills (climbing): ~0.40 kWh/min
    ee = {
        ("A", "J"): 4.5,       # Urban start (0.30 kWh/min)
        ("J", "S1"): 3.6,      # Highway (0.30 kWh/min)
        ("S1", "S2"): 2.4,     # Highway flat (0.30 kWh/min)
        ("S2", "M"): 3.5,      # Mixed terrain (0.35 kWh/min)
        ("J", "S3"): 2.7,      # Highway efficient (0.30 kWh/min)
        ("S3", "M"): 5.6,      # Hilly terrain (0.40 kWh/min)
        ("M", "B"): 4.2,       # Urban finish (0.32 kWh/min)
    }

    # ========================================
    # Station Characteristics
    # ========================================
    # Three distinct station types creating optimization trade-offs:
    #   S1: Budget option (slow but cheap with high capacity)
    #   S2: Premium option (fast but expensive with limited capacity)
    #   S3: Balanced option (medium speed and price)
    station_price = {
        "S1": 0.10,   # Budget: 0.10 EGP/kWh
        "S2": 0.25,   # Premium: 0.25 EGP/kWh
        "S3": 0.16,   # Mid-tier: 0.16 EGP/kWh
    }
    
    station_max_kw = {
        "S1": 50.0,   # Slow charging (Level 2)
        "S2": 180.0,  # Ultra-fast DC (Premium)
        "S3": 100.0,  # Fast DC (Standard)
    }

    # ========================================
    # Fleet Configuration
    # ========================================
    # 5 vehicles representing different EV market segments
    # Different initial SOCs create varied charging needs
    P = SingleForkParams(
        edges_time_min=tt,
        edges_energy_kwh=ee,
        station_plugs={"S1": 2, "S2": 1, "S3": 1},  # S1 has more plugs (slower)
        station_price=station_price,
        station_max_kw=station_max_kw,
        ev_max_kw=None,  # No EV-side power cap
        m=5,  # 5 vehicles
        battery_kwh=[40.0, 55.0, 62.0, 75.0, 80.0],  # Different ranges
        soc0=[0.70, 0.55, 0.45, 0.60, 0.50],  # Different initial states
        w_time=1.0,
        w_cost=1.0,
        bigM=1e6,
    )
    # Validate all parameters before returning
    # This catches any configuration errors early
    P.validate()
    
    return P
