"""Thermal helpers for steam, condensing, boiling, and BPE-aware temperatures.

These are practical approximations for early-stage engineering utility and
should be replaced or complemented with more rigorous steam/property models
later.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from engineering_app.core.units import pressure_to_kpa_abs

MMHG_PER_KPA = 760.0 / 101.325
_WATER_ANTOINE_LOW = (8.07131, 1730.63, 233.426)   # -20 to 100 C, mmHg
_WATER_ANTOINE_HIGH = (8.14019, 1810.94, 244.485)  # 99 to 374 C, mmHg


@dataclass
class ThermalPoint:
    pressure_kpa_abs: float
    saturation_temperature_c: float
    boiling_temperature_c: float
    condensing_temperature_c: float
    bpe_c: float = 0.0


def _antoine_temperature_c(pressure_kpa_abs: float, coefficients: tuple[float, float, float]) -> float:
    if pressure_kpa_abs <= 0:
        raise ValueError("Pressure must be positive")
    pressure_mmhg = pressure_kpa_abs * MMHG_PER_KPA
    if pressure_mmhg <= 0:
        raise ValueError("Pressure must be positive")
    a, b, c = coefficients
    return b / (a - math.log10(pressure_mmhg)) - c


def saturation_temperature_c_from_kpa_abs(pressure_kpa_abs: float) -> float:
    """Approximate water saturation temperature from absolute pressure.

    Uses a piecewise Antoine correlation for water (pressure in mmHg,
    temperature in °C) with coefficient ranges of about -20 to 100 °C and
    99 to 374 °C. This is still a screening-level utility helper, but it is
    materially closer to steam-table behavior than the earlier single log fit.
    """
    if pressure_kpa_abs <= 0:
        raise ValueError("Pressure must be positive")

    low_temp_c = _antoine_temperature_c(pressure_kpa_abs, _WATER_ANTOINE_LOW)
    if low_temp_c <= 99.0:
        return low_temp_c

    high_temp_c = _antoine_temperature_c(pressure_kpa_abs, _WATER_ANTOINE_HIGH)
    if high_temp_c >= 99.0:
        return high_temp_c

    return 0.5 * (low_temp_c + high_temp_c)


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
