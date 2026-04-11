"""Engineer-facing quick calculation wrappers."""

from __future__ import annotations

from engineering_app.core.hydraulics import calculate_hydraulics_with_units
from engineering_app.core.solutions import calculate_dilution_water, estimate_solution_properties
from engineering_app.core.steam import duty_from_steam_flow, flash_steam_fraction, steam_flow_for_duty_kw
from engineering_app.core.thermal import build_thermal_point
from engineering_app.core.units import (
    c_to_f,
    c_to_temperature,
    f_to_c,
    kg_h_to_mass_flow,
    kpa_abs_to_pressure,
    m3_h_to_volumetric_flow,
    pressure_to_kpa_abs,
)


def pressure_conversion(value: float, from_unit: str, to_unit: str) -> float:
    return kpa_abs_to_pressure(pressure_to_kpa_abs(value, from_unit), to_unit)


def thermal_point(value: float, unit: str, bpe_c: float = 0.0):
    return build_thermal_point(value, unit, bpe_c)


def temperature_conversion(value: float, from_unit: str, to_unit: str) -> float:
    value_c = f_to_c(value) if from_unit.strip().lower().startswith("f") else value
    return c_to_temperature(value_c, to_unit)


def hydraulics_tool(**kwargs):
    return calculate_hydraulics_with_units(**kwargs)


def steam_for_duty(duty_kw: float, pressure_value: float, pressure_unit: str):
    return steam_flow_for_duty_kw(duty_kw, pressure_value, pressure_unit)


def duty_from_steam(steam_flow_value: float, steam_flow_unit: str, pressure_value: float, pressure_unit: str):
    return duty_from_steam_flow(steam_flow_value, steam_flow_unit, pressure_value, pressure_unit)


def flash_fraction(condensate_temp_c: float, flash_pressure_value: float, flash_pressure_unit: str, condensate_flow_kg_h: float = 1.0):
    return flash_steam_fraction(condensate_temp_c, flash_pressure_value, flash_pressure_unit, condensate_flow_kg_h)


def solution_properties(
    product: str,
    solids_wt_pct: float,
    temperature_c: float,
    pressure_value: float,
    pressure_unit: str,
    flow_value: float | None = None,
    flow_unit: str = "kg/h",
):
    return estimate_solution_properties(product, solids_wt_pct, temperature_c, pressure_value, pressure_unit, flow_value, flow_unit)


def dilution_water(product: str, feed_rate_value: float, feed_rate_unit: str, feed_solids_wt_pct: float, target_solids_wt_pct: float):
    return calculate_dilution_water(product, feed_rate_value, feed_rate_unit, feed_solids_wt_pct, target_solids_wt_pct)


__all__ = [
    "pressure_conversion",
    "thermal_point",
    "temperature_conversion",
    "hydraulics_tool",
    "steam_for_duty",
    "duty_from_steam",
    "flash_fraction",
    "solution_properties",
    "dilution_water",
    "c_to_f",
    "f_to_c",
    "kg_h_to_mass_flow",
    "m3_h_to_volumetric_flow",
]
