"""Engineer-facing quick calculation wrappers."""

from __future__ import annotations

from engineering_app.core.hydraulics import calculate_hydraulics_with_units
from engineering_app.core.solutions import (
    calculate_brix_reconciliation,
    calculate_dilution_water,
    calculate_ratio_target_blend,
    calculate_two_stream_blend,
    estimate_solution_properties,
)
from engineering_app.core.steam import (
    compare_electricity_costs,
    compare_steam_costs,
    duty_from_steam_flow,
    estimate_electricity_cost,
    estimate_steam_cost,
    flash_steam_fraction,
    steam_flow_for_duty_kw,
)
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


def steam_cost(
    steam_flow_value: float,
    steam_flow_unit: str,
    steam_cost_value: float,
    steam_cost_basis: str,
    operating_hours_per_day: float = 24.0,
    operating_days_per_year: float = 365.0,
):
    return estimate_steam_cost(
        steam_flow_value=steam_flow_value,
        steam_flow_unit=steam_flow_unit,
        steam_cost_value=steam_cost_value,
        steam_cost_basis=steam_cost_basis,
        operating_hours_per_day=operating_hours_per_day,
        operating_days_per_year=operating_days_per_year,
    )


def electricity_cost(
    shaft_power_value: float,
    shaft_power_unit: str,
    electricity_rate_per_kwh: float,
    load_pct: float = 100.0,
    motor_efficiency_pct: float = 90.0,
    operating_hours_per_day: float = 24.0,
    operating_days_per_year: float = 365.0,
):
    return estimate_electricity_cost(
        shaft_power_value=shaft_power_value,
        shaft_power_unit=shaft_power_unit,
        electricity_rate_per_kwh=electricity_rate_per_kwh,
        load_pct=load_pct,
        motor_efficiency_pct=motor_efficiency_pct,
        operating_hours_per_day=operating_hours_per_day,
        operating_days_per_year=operating_days_per_year,
    )


def steam_cost_comparison(
    current_steam_flow_value: float,
    proposed_steam_flow_value: float,
    steam_flow_unit: str,
    steam_cost_value: float,
    steam_cost_basis: str,
    operating_hours_per_day: float = 24.0,
    operating_days_per_year: float = 365.0,
):
    return compare_steam_costs(
        current_steam_flow_value=current_steam_flow_value,
        proposed_steam_flow_value=proposed_steam_flow_value,
        steam_flow_unit=steam_flow_unit,
        steam_cost_value=steam_cost_value,
        steam_cost_basis=steam_cost_basis,
        operating_hours_per_day=operating_hours_per_day,
        operating_days_per_year=operating_days_per_year,
    )


def electricity_cost_comparison(
    current_shaft_power_value: float,
    proposed_shaft_power_value: float,
    shaft_power_unit: str,
    electricity_rate_per_kwh: float,
    current_load_pct: float = 100.0,
    proposed_load_pct: float = 100.0,
    current_motor_efficiency_pct: float = 90.0,
    proposed_motor_efficiency_pct: float = 90.0,
    operating_hours_per_day: float = 24.0,
    operating_days_per_year: float = 365.0,
):
    return compare_electricity_costs(
        current_shaft_power_value=current_shaft_power_value,
        proposed_shaft_power_value=proposed_shaft_power_value,
        shaft_power_unit=shaft_power_unit,
        electricity_rate_per_kwh=electricity_rate_per_kwh,
        current_load_pct=current_load_pct,
        proposed_load_pct=proposed_load_pct,
        current_motor_efficiency_pct=current_motor_efficiency_pct,
        proposed_motor_efficiency_pct=proposed_motor_efficiency_pct,
        operating_hours_per_day=operating_hours_per_day,
        operating_days_per_year=operating_days_per_year,
    )


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


def ratio_target_blend(
    product: str,
    known_stream_rate_value: float,
    known_stream_rate_unit: str,
    known_stream_solids_wt_pct: float,
    target_stream_solids_wt_pct: float,
    target_blend_solids_wt_pct: float,
    known_stream_temperature_c: float | None = None,
    target_stream_temperature_c: float | None = None,
    known_stream_label: str = "Known stream",
    target_stream_label: str = "Targeted stream",
):
    return calculate_ratio_target_blend(
        product=product,
        known_stream_rate_value=known_stream_rate_value,
        known_stream_rate_unit=known_stream_rate_unit,
        known_stream_solids_wt_pct=known_stream_solids_wt_pct,
        target_stream_solids_wt_pct=target_stream_solids_wt_pct,
        target_blend_solids_wt_pct=target_blend_solids_wt_pct,
        known_stream_temperature_c=known_stream_temperature_c,
        target_stream_temperature_c=target_stream_temperature_c,
        known_stream_label=known_stream_label,
        target_stream_label=target_stream_label,
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
    "steam_cost",
    "electricity_cost",
    "steam_cost_comparison",
    "electricity_cost_comparison",
    "solution_properties",
    "brix_reconciliation",
    "dilution_water",
    "two_stream_blend",
    "ratio_target_blend",
    "tank_inventory",
    "c_to_f",
    "f_to_c",
    "kg_h_to_mass_flow",
    "m3_h_to_volumetric_flow",
]
