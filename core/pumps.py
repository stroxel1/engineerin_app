"""Pump calculations for centrifugal and positive displacement pumps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class PumpInputs:
    flow_rate: float  # m3/h
    head: float       # m
    density: float    # kg/m3
    efficiency: float # 0-1 (decimal, e.g., 0.75 for 75%)
    npsh_available: Optional[float] = None  # m
    npsh_required: Optional[float] = None   # m
    speed: Optional[float] = None           # rpm
    diameter: Optional[float] = None        # mm or inches (context-dependent)


@dataclass
class PumpResults:
    hydraulic_power_kw: float
    shaft_power_kw: float
    motor_power_kw: float
    npsh_margin: Optional[float] = None
    notes: list[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


def pump_power(inputs: PumpInputs) -> PumpResults:
    """
    Calculate pump power requirements.
    
    Hydraulic Power (kW) = (Flow m3/h × Head m × Density kg/m3 × 9.81) / (3600 × 1000)
    Shaft Power = Hydraulic Power / Efficiency
    Motor Power = Shaft Power / Motor Efficiency (assume 90% if not specified)
    """
    # Convert flow to m3/s
    flow_m3_s = inputs.flow_rate / 3600.0
    
    # Hydraulic power in kW
    hydraulic_power_kw = (flow_m3_s * inputs.head * inputs.density * 9.80665) / 1000.0
    
    # Shaft power
    shaft_power_kw = hydraulic_power_kw / inputs.efficiency
    
    # Motor power (assuming 90% motor efficiency)
    motor_efficiency = 0.90
    motor_power_kw = shaft_power_kw / motor_efficiency
    
    # NPSH margin
    npsh_margin = None
    if inputs.npsh_available is not None and inputs.npsh_required is not None:
        npsh_margin = inputs.npsh_available - inputs.npsh_required
    
    notes = []
    if inputs.efficiency < 0.5 or inputs.efficiency > 0.95:
        notes.append("Pump efficiency outside typical range (50-95%)")
    if inputs.flow_rate < 1:
        notes.append("Very low flow rate - consider if pump is appropriate")
    if inputs.head < 1:
        notes.append("Very low head - consider if pump is appropriate")
    if npsh_margin is not None and npsh_margin < 0.5:
        notes.append("NPSH margin is low (< 0.5 m) - cavitation risk")
    elif npsh_margin is not None and npsh_margin > 3.0:
        notes.append("NPSH margin is adequate (> 3.0 m)")
    
    return PumpResults(
        hydraulic_power_kw=hydraulic_power_kw,
        shaft_power_kw=shaft_power_kw,
        motor_power_kw=motor_power_kw,
        npsh_margin=npsh_margin,
        notes=notes
    )


def affinity_law_flow(q1: float, n1: float, n2: float) -> float:
    """
    Affinity law for flow: Q2/Q1 = N2/N1
    Returns flow at new speed (m3/h)
    """
    return q1 * (n2 / n1)


def affinity_law_head(h1: float, n1: float, n2: float) -> float:
    """
    Affinity law for head: H2/H1 = (N2/N1)^2
    Returns head at new speed (m)
    """
    return h1 * ((n2 / n1) ** 2)


def affinity_law_power(p1: float, n1: float, n2: float) -> float:
    """
    Affinity law for power: P2/P1 = (N2/N1)^3
    Returns power at new speed (kW)
    """
    return p1 * ((n2 / n1) ** 3)


def suction_specific_speed(n: float, q: float, npsh: float) -> float:
    """
    Calculate suction specific speed (NSS)
    N = rpm, Q = m3/h, NPSH = m
    NSS = N * sqrt(Q) / (NPSH^0.75)
    """
    if npsh <= 0:
        raise ValueError("NPSH must be positive")
    return n * math.sqrt(q) / (npsh ** 0.75)


def specific_speed(n: float, q: float, h: float) -> float:
    """
    Calculate specific speed (Ns)
    N = rpm, Q = m3/h, H = m
    Ns = N * sqrt(Q) / (H^0.75)
    """
    if h <= 0:
        raise ValueError("Head must be positive")
    return n * math.sqrt(q) / (h ** 0.75)


