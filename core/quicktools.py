"""Engineer-facing quick calculation wrappers."""

from __future__ import annotations

from engineering_app.core.hydraulics import calculate_hydraulics_with_units
from engineering_app.core.solutions import (
    calculate_brix_reconciliation,
    calculate_dilution_water,
    calculate_two_stream_blend,
    estimate_solution_properties,
)
from engineering_app.core.steam import duty_from_steam_flow, flash_steam_fraction, steam_flow_for_duty_kw
from engineering_app.core.tanks import estimate_tank_inventory_with_units
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


def brix_reconciliation(
    product: str,
    observed_brix: float,
    temperature_c: float,
    pressure_value: float,
    pressure_unit: str,
    lab_solids_wt_pct: float | None = None,
    measured_density_value: float | None = None,
    measured_density_unit: str = "kg/m3",
    flow_value: float | None = None,
    flow_unit: str = "kg/h",
):
    return calculate_brix_reconciliation(
        product=product,
        observed_brix=observed_brix,
        temperature_c=temperature_c,
        pressure_value=pressure_value,
        pressure_unit=pressure_unit,
        lab_solids_wt_pct=lab_solids_wt_pct,
        measured_density_value=measured_density_value,
        measured_density_unit=measured_density_unit,
        flow_value=flow_value,
        flow_unit=flow_unit,
    )


def dilution_water(product: str, feed_rate_value: float, feed_rate_unit: str, feed_solids_wt_pct: float, target_solids_wt_pct: float):
    return calculate_dilution_water(product, feed_rate_value, feed_rate_unit, feed_solids_wt_pct, target_solids_wt_pct)


def two_stream_blend(
    product: str,
    stream_a_rate_value: float,
    stream_a_rate_unit: str,
    stream_a_solids_wt_pct: float,
    stream_b_rate_value: float,
    stream_b_rate_unit: str,
    stream_b_solids_wt_pct: float,
    stream_a_temperature_c: float | None = None,
    stream_b_temperature_c: float | None = None,
):
    return calculate_two_stream_blend(
        product,
        stream_a_rate_value,
        stream_a_rate_unit,
        stream_a_solids_wt_pct,
        stream_b_rate_value,
        stream_b_rate_unit,
        stream_b_solids_wt_pct,
        stream_a_temperature_c,
        stream_b_temperature_c,
    )


def tank_inventory(
    tank_type: str,
    dimensions: dict[str, float],
    dimension_units: dict[str, str],
    liquid_level_value: float,
    liquid_level_unit: str,
    density_value: float | None = None,
    density_unit: str = "kg/m3",
    transfer_rate_value: float | None = None,
    transfer_rate_unit: str = "m3/h",
):
    return estimate_tank_inventory_with_units(
        tank_type=tank_type,
        dimensions=dimensions,
        dimension_units=dimension_units,
        liquid_level_value=liquid_level_value,
        liquid_level_unit=liquid_level_unit,
        density_value=density_value,
        density_unit=density_unit,
        transfer_rate_value=transfer_rate_value,
        transfer_rate_unit=transfer_rate_unit,
    )


__all__ = [
    "pressure_conversion",
    "thermal_point",
    "temperature_conversion",
    "hydraulics_tool",
    "steam_for_duty",
    "duty_from_steam",
    "flash_fraction",
    "solution_properties",
    "brix_reconciliation",
    "dilution_water",
    "two_stream_blend",
    "tank_inventory",
    "c_to_f",
    "f_to_c",
    "kg_h_to_mass_flow",
    "m3_h_to_volumetric_flow",
]
