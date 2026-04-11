"""Thermal helpers for steam, condensing, boiling, and BPE-aware temperatures.

These are practical approximations for early-stage engineering utility and
should be replaced or complemented with more rigorous steam/property models
later.
"""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.units import pressure_to_kpa_abs


@dataclass
class ThermalPoint:
    pressure_kpa_abs: float
    saturation_temperature_c: float
    boiling_temperature_c: float
    condensing_temperature_c: float
    bpe_c: float = 0.0


def saturation_temperature_c_from_kpa_abs(pressure_kpa_abs: float) -> float:
    """Approximate water saturation temperature from absolute pressure.

    Coarse interpolation fit intended for field-utility estimates, not design-grade
    thermodynamics.
    """
    if pressure_kpa_abs <= 0:
        raise ValueError("Pressure must be positive")

    # rough log-based approximation near common plant vacuum/steam ranges
    import math

    return 45.0 * math.log10(pressure_kpa_abs) + 8.0


def condensing_temperature_c(pressure_value: float, pressure_unit: str) -> float:
    pressure_kpa_abs = pressure_to_kpa_abs(pressure_value, pressure_unit)
    return saturation_temperature_c_from_kpa_abs(pressure_kpa_abs)


def boiling_temperature_c(pressure_value: float, pressure_unit: str, bpe_c: float = 0.0) -> float:
    pressure_kpa_abs = pressure_to_kpa_abs(pressure_value, pressure_unit)
    sat_temp = saturation_temperature_c_from_kpa_abs(pressure_kpa_abs)
    return sat_temp + bpe_c


def build_thermal_point(pressure_value: float, pressure_unit: str, bpe_c: float = 0.0) -> ThermalPoint:
    pressure_kpa_abs = pressure_to_kpa_abs(pressure_value, pressure_unit)
    sat_temp = saturation_temperature_c_from_kpa_abs(pressure_kpa_abs)
    return ThermalPoint(
        pressure_kpa_abs=pressure_kpa_abs,
        saturation_temperature_c=sat_temp,
        boiling_temperature_c=sat_temp + bpe_c,
        condensing_temperature_c=sat_temp,
        bpe_c=bpe_c,
    )
