"""Motor and drive screening calculators for plant troubleshooting.

Provides motor sizing, pump motor power, VFD savings screening,
and motor efficiency assessments.  Screening-level only — not
substitute for detailed motor specifications.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Standard motor frame sizes (kW) -- IEC / NEMA common ratings
# ---------------------------------------------------------------------------

_IEC_STANDARD_MOTORS_KW = [
    0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
    11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110,
    132, 160, 200, 250, 315, 400, 500, 630,
]

_NEMA_STANDARD_MOTORS_HP = [
    1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60,
    75, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500,
]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class MotorSizeResult:
    shaft_power_kw: float
    load_factor: float
    required_motor_kw: float
    motor_efficiency_pct: float
    electrical_input_kw: float
    pf: float
    apparent_power_kva: float
    full_load_current_3ph: float
    service_factor: float
    next_standard_motor_kw: float
    loading_pct: float
    notes: list[str]


@dataclass
class PumpMotorResult:
    hydraulic_kw: float
    pump_efficiency_pct: float
    shaft_power_kw: float
    motor_efficiency_pct: float
    electrical_input_kw: float
    notes: list[str]


@dataclass
class VDFSavingsResult:
    rated_power_kw: float
    rated_speed_pct: float
    current_control_method: str
    assumed_efficiency_at_speed: float
    estimated_vfd_input_kw: float
    current_input_kw: float
    estimated_savings_kw: float
    estimated_annual_savings_kwh: float
    estimated_annual_cost_savings: float
    annual_operating_hours: float
    electricity_rate_per_kwh: float
    payback_months: float | None
    notes: list[str]


@dataclass
class MotorAssessmentResult:
    motor_rated_kw: float
    measured_input_kw: float
    motor_efficiency_pct: float
    motor_pf: float
    estimated_shaft_kw: float
    load_factor_pct: float
    is_undersized: bool
    is_oversized: bool
    estimated_annual_energy_kwh: float
    estimated_annual_cost: float
    electricity_rate: float
    annual_hours: float
    notes: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_standard_motor_kw(required_kw: float, standard: str = "iec") -> float:
    """Return the next standard motor size >= required_kw."""
    if standard.lower() == "iec":
        sizes = _IEC_STANDARD_MOTORS_KW
    else:
        sizes = [hp * 0.7457 for hp in _NEMA_STANDARD_MOTORS_HP]
    for s in sizes:
        if s >= required_kw:
            return s
    return required_kw


def _estimate_motor_efficiency(kw: float) -> float:
    """Rough motor efficiency estimate from rated power (IE2/IE3 bands)."""
    if kw < 1.5:
        return 78.0
    if kw < 4.0:
        return 82.0
    if kw < 7.5:
        return 85.0
    if kw < 15.0:
        return 88.0
    if kw < 30.0:
        return 90.0
    if kw < 75.0:
        return 92.0
    if kw < 200.0:
        return 94.0
    return 95.5


def _estimate_motor_pf(kw: float) -> float:
    """Approximate full-load power factor."""
    if kw < 2.2:
        return 0.70
    if kw < 7.5:
        return 0.78
    if kw < 30.0:
        return 0.84
    if kw < 75.0:
        return 0.87
    return 0.89


# ---------------------------------------------------------------------------
# Public calculation functions
# ---------------------------------------------------------------------------

def calculate_motor_size(
    shaft_power_kw: float,
    load_factor_pct: float = 80.0,
    service_factor: float = 1.15,
    motor_voltage_v: float = 480.0,
    standard: str = "iec",
) -> MotorSizeResult:
    """Select an appropriate motor size from shaft power demand."""
    notes: list[str] = []

    if shaft_power_kw <= 0:
        raise ValueError("Shaft power must be positive.")
    if not 0 < load_factor_pct <= 100:
        raise ValueError("Load factor must be between 0 and 100%.")
    if service_factor < 1.0:
        raise ValueError("Service factor must be >= 1.0.")

    load_frac = load_factor_pct / 100.0
    required_motor_kw = shaft_power_kw / load_frac
    next_standard = _next_standard_motor_kw(required_motor_kw * service_factor, standard)
    actual_loading = (shaft_power_kw / next_standard) * 100.0

    motor_eff = _estimate_motor_efficiency(next_standard)
    pf = _estimate_motor_pf(next_standard)
    electrical_kw = shaft_power_kw / (motor_eff / 100.0)
    apparent_kva = electrical_kw / pf if pf > 0 else 0.0
    three_phase_current = (electrical_kw * 1000.0) / (math.sqrt(3) * motor_voltage_v * pf) if pf > 0 else 0.0

    if actual_loading < 40:
        notes.append(f"Selected motor loading ({actual_loading:.1f}%) is low — consider whether a smaller motor or VFD turndown is more efficient.")
    elif actual_loading > 90:
        notes.append(f"Motor loading ({actual_loading:.1f}%) is high — verify that the service factor is adequate for sustained operation.")

    if actual_loading > 100:
        notes.append("MOTOR MAY BE UNDERSIZED: shaft demand exceeds nameplate rating even before service factor is considered.")

    return MotorSizeResult(
        shaft_power_kw=shaft_power_kw,
        load_factor=load_frac,
        required_motor_kw=required_motor_kw,
        motor_efficiency_pct=motor_eff,
        electrical_input_kw=electrical_kw,
        pf=pf,
        apparent_power_kva=apparent_kva,
        full_load_current_3ph=three_phase_current,
        service_factor=service_factor,
        next_standard_motor_kw=next_standard,
        loading_pct=actual_loading,
        notes=notes,
    )


def calculate_pump_motor(
    flow_m3_h: float,
    head_m: float,
    sg: float = 1.0,
    pump_efficiency_pct: float = 75.0,
    motor_efficiency_pct: float | None = None,
) -> PumpMotorResult:
    """Estimate the motor power needed for a pump duty."""
    notes: list[str] = []

    if flow_m3_h < 0:
        raise ValueError("Flow must be non-negative.")
    if head_m < 0:
        raise ValueError("Head must be non-negative.")
    if flow_m3_h <= 0 and head_m <= 0:
        raise ValueError("Either flow or head must be positive.")

    rho = sg * 1000.0
    g = 9.81
    volumetric_m3s = flow_m3_h / 3600.0
    hydraulic_w = rho * g * volumetric_m3s * head_m
    hydraulic_kw = hydraulic_w / 1000.0

    if hydraulic_kw <= 0:
        raise ValueError("Hydraulic power must be positive -- check flow, head, and SG inputs.")

    if not (30 <= pump_efficiency_pct <= 95):
        notes.append(f"Pump efficiency of {pump_efficiency_pct:.1f}% is outside typical range (30–95%); verify input.")
    pump_eff_frac = pump_efficiency_pct / 100.0

    shaft_kw = hydraulic_kw / pump_eff_frac

    if motor_efficiency_pct is None:
        motor_eff = _estimate_motor_efficiency(shaft_kw)
        notes.append(f"Motor efficiency estimated at {motor_eff:.1f}% based on shaft power.")
    else:
        motor_eff = motor_efficiency_pct
    eff_frac = motor_eff / 100.0

    electrical_kw = shaft_kw / eff_frac

    return PumpMotorResult(
        hydraulic_kw=hydraulic_kw,
        pump_efficiency_pct=pump_efficiency_pct,
        shaft_power_kw=shaft_kw,
        motor_efficiency_pct=motor_eff,
        electrical_input_kw=electrical_kw,
        notes=notes,
    )


def estimate_vfd_savings(
    rated_power_kw: float,
    rated_speed_pct: float,
    current_control: str = "throttle",
    annual_hours: float = 8000.0,
    electricity_rate_per_kwh: float = 0.10,
    efficiency_factor: float = 0.97,
    base_efficiency: float = 0.90,
) -> VDFSavingsResult:
    """Estimate annual kWh and cost savings from VFD installation."""
    notes: list[str] = []

    if rated_power_kw <= 0:
        raise ValueError("Rated power must be positive.")
    if rated_speed_pct < 0 or rated_speed_pct > 100:
        raise ValueError("Speed must be between 0 and 100%.")
    if annual_hours < 0 or annual_hours > 8760:
        raise ValueError("Annual operating hours must be between 0 and 8760.")
    if electricity_rate_per_kwh < 0:
        raise ValueError("Electricity rate cannot be negative.")

    speed_frac = rated_speed_pct / 100.0

    if current_control.lower() in ("throttle", "throttling", "control valve"):
        current_method_label = "Throttle / control valve"
        current_input_kw = rated_power_kw * max(speed_frac, 0.1)
        notes.append("Throttle method assumed: power scales approximately linearly with flow rate.")
    elif current_control.lower() in ("bypass", "spill"):
        current_method_label = "Bypass / spill"
        current_input_kw = rated_power_kw
        notes.append("Bypass method assumed: pump runs at full speed, excess flow bypassed.")
    else:
        current_method_label = current_control
        current_input_kw = rated_power_kw * (0.6 + 0.4 * speed_frac)
        notes.append("Generic throttling curve used for comparison.")

    # VFD power: affinity law P ∝ N³ with drive+motor efficiency
    vfd_input_kw = rated_power_kw * (speed_frac ** 3) / (efficiency_factor * base_efficiency)

    savings_kw = current_input_kw - vfd_input_kw
    annual_kwh = savings_kw * annual_hours
    annual_cost = annual_kwh * electricity_rate_per_kwh

    if speed_frac < 0.5:
        notes.append(f"At {rated_speed_pct:.0f}% speed, cubic affinity-law savings are substantial.")
    elif speed_frac < 0.7:
        notes.append(f"At {rated_speed_pct:.0f}% speed, VFD savings are moderate.")
    else:
        notes.append(f"At {rated_speed_pct:.0f}% speed, VFD savings are smaller — evaluate duty cycle variations.")

    payback = None
    if annual_cost > 0:
        vfd_cost = rated_power_kw * 50.0
        payback = (vfd_cost / annual_cost) * 12
        notes.append(f"Payback estimate: {payback:.1f} months (assuming ~$50/kW VFD cost).")

    return VDFSavingsResult(
        rated_power_kw=rated_power_kw,
        rated_speed_pct=rated_speed_pct,
        current_control_method=current_method_label,
        assumed_efficiency_at_speed=efficiency_factor * base_efficiency,
        estimated_vfd_input_kw=vfd_input_kw,
        current_input_kw=current_input_kw,
        estimated_savings_kw=savings_kw,
        estimated_annual_savings_kwh=annual_kwh,
        estimated_annual_cost_savings=annual_cost,
        annual_operating_hours=annual_hours,
        electricity_rate_per_kwh=electricity_rate_per_kwh,
        payback_months=payback,
        notes=notes,
    )


def assess_motor_loading(
    motor_rated_kw: float,
    measured_input_kw: float,
    motor_efficiency_pct: float = 90.0,
    electricity_rate_per_kwh: float = 0.10,
    annual_hours: float = 8000.0,
) -> MotorAssessmentResult:
    """Quick motor health check from nameplate and measured input."""
    notes: list[str] = []

    if motor_rated_kw <= 0:
        raise ValueError("Motor rated power must be positive.")
    if measured_input_kw < 0:
        raise ValueError("Measured input kW cannot be negative.")

    eff_frac = motor_efficiency_pct / 100.0
    shaft_kw = measured_input_kw * eff_frac
    shaft_rated = motor_rated_kw * eff_frac
    load_pct = (shaft_kw / shaft_rated * 100) if shaft_rated > 0 else 0

    is_undersized = load_pct > 100
    is_oversized = load_pct < 40

    annual_kwh = measured_input_kw * annual_hours
    annual_cost = annual_kwh * electricity_rate_per_kwh

    if is_undersized:
        notes.append(f"Motor appears overloaded: estimated shaft {shaft_kw:.1f} kW exceeds rated {shaft_rated:.1f} kW ({load_pct:.0f}%).")
        notes.append("Check bearing temperature, insulation class, and whether running continuously in service factor.")
    elif is_oversized:
        notes.append(f"Motor is lightly loaded ({load_pct:.0f}%). Consider right-sizing, VFD, or Y-Δ for better low-load efficiency.")
    else:
        notes.append(f"Motor loading ({load_pct:.0f}%) is within a reasonable operating range.")

    return MotorAssessmentResult(
        motor_rated_kw=motor_rated_kw,
        measured_input_kw=measured_input_kw,
        motor_efficiency_pct=motor_efficiency_pct,
        motor_pf=_estimate_motor_pf(motor_rated_kw),
        estimated_shaft_kw=shaft_kw,
        load_factor_pct=load_pct,
        is_undersized=is_undersized,
        is_oversized=is_oversized,
        estimated_annual_energy_kwh=annual_kwh,
        estimated_annual_cost=annual_cost,
        electricity_rate=electricity_rate_per_kwh,
        annual_hours=annual_hours,
        notes=notes,
    )
