"""Practical steam and utility helpers for field engineering.

These are intentionally lightweight approximations for quick calculations.
"""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.thermal import build_thermal_point, condensing_temperature_c
from engineering_app.core.units import mass_flow_to_kg_h, pressure_to_kpa_abs


@dataclass
class SteamDutyResult:
    duty_kw: float
    steam_flow_kg_h: float
    condensate_flow_kg_h: float
    condensing_temperature_c: float
    latent_heat_kj_kg: float
    notes: list[str]


@dataclass
class FlashSteamResult:
    flash_fraction: float
    flash_steam_kg_h: float
    remaining_liquid_kg_h: float
    flash_saturation_temperature_c: float
    notes: list[str]


@dataclass
class ThermoCompressorResult:
    suction_flow_kg_h: float
    motive_flow_kg_h: float
    discharge_flow_kg_h: float
    suction_pressure_kpa_abs: float
    motive_pressure_kpa_abs: float
    discharge_pressure_kpa_abs: float
    suction_temperature_c: float
    motive_temperature_c: float
    discharge_temperature_c: float
    suction_vapor_enthalpy_kj_kg: float
    motive_vapor_enthalpy_kj_kg: float
    discharge_vapor_enthalpy_kj_kg: float
    compression_ratio: float
    motive_expansion_ratio: float
    entrainment_ratio: float
    motive_to_suction_ratio: float
    notes: list[str]


@dataclass
class SteamHeaderPressureChangeResult:
    duty_kw: float
    same_steam_flow_kg_h: float
    current_pressure_kpa_abs: float
    reduced_pressure_kpa_abs: float
    current_condensing_temperature_c: float
    reduced_condensing_temperature_c: float
    current_latent_heat_kj_kg: float
    reduced_latent_heat_kj_kg: float
    current_steam_flow_kg_h: float
    reduced_steam_flow_kg_h: float
    additional_steam_required_kg_h: float
    additional_steam_required_pct: float
    current_available_duty_kw: float
    reduced_available_duty_kw: float
    duty_shortfall_kw: float
    duty_shortfall_pct: float
    process_boiling_temperature_c: float | None
    current_available_delta_t_c: float | None
    reduced_available_delta_t_c: float | None
    delta_t_change_c: float | None
    notes: list[str]


def estimate_latent_heat_kj_kg(condensing_temp_c: float) -> float:
    return max(2501.0 - 2.36 * condensing_temp_c, 1500.0)


def steam_flow_for_duty_kw(duty_kw: float, steam_pressure_value: float, steam_pressure_unit: str) -> SteamDutyResult:
    cond_temp = condensing_temperature_c(steam_pressure_value, steam_pressure_unit)
    latent_heat = estimate_latent_heat_kj_kg(cond_temp)
    steam_flow_kg_h = duty_kw * 3600.0 / latent_heat
    notes = [
        "Assumes saturated condensing steam.",
        "Does not include condensate subcooling or desuperheating corrections.",
    ]
    return SteamDutyResult(
        duty_kw=duty_kw,
        steam_flow_kg_h=steam_flow_kg_h,
        condensate_flow_kg_h=steam_flow_kg_h,
        condensing_temperature_c=cond_temp,
        latent_heat_kj_kg=latent_heat,
        notes=notes,
    )


def duty_from_steam_flow_kg_h(steam_flow_kg_h: float, steam_pressure_value: float, steam_pressure_unit: str) -> SteamDutyResult:
    cond_temp = condensing_temperature_c(steam_pressure_value, steam_pressure_unit)
    latent_heat = estimate_latent_heat_kj_kg(cond_temp)
    duty_kw = steam_flow_kg_h * latent_heat / 3600.0
    notes = [
        "Assumes saturated condensing steam.",
        "Does not include condensate subcooling or desuperheating corrections.",
    ]
    return SteamDutyResult(
        duty_kw=duty_kw,
        steam_flow_kg_h=steam_flow_kg_h,
        condensate_flow_kg_h=steam_flow_kg_h,
        condensing_temperature_c=cond_temp,
        latent_heat_kj_kg=latent_heat,
        notes=notes,
    )


def duty_from_steam_flow(steam_flow_value: float, steam_flow_unit: str, steam_pressure_value: float, steam_pressure_unit: str) -> SteamDutyResult:
    return duty_from_steam_flow_kg_h(
        mass_flow_to_kg_h(steam_flow_value, steam_flow_unit),
        steam_pressure_value,
        steam_pressure_unit,
    )


def flash_steam_fraction(
    hot_condensate_temp_c: float,
    flash_pressure_value: float,
    flash_pressure_unit: str,
    condensate_flow_kg_h: float = 1.0,
) -> FlashSteamResult:
    flash_sat_temp = condensing_temperature_c(flash_pressure_value, flash_pressure_unit)
    sensible_excess = max(hot_condensate_temp_c - flash_sat_temp, 0.0) * 4.186
    latent = estimate_latent_heat_kj_kg(flash_sat_temp)
    fraction = max(min(sensible_excess / latent, 1.0), 0.0)
    notes = [
        "Assumes condensate behaves approximately like liquid water.",
        "Useful for quick flash estimates only.",
    ]
    return FlashSteamResult(
        flash_fraction=fraction,
        flash_steam_kg_h=fraction * condensate_flow_kg_h,
        remaining_liquid_kg_h=(1.0 - fraction) * condensate_flow_kg_h,
        flash_saturation_temperature_c=flash_sat_temp,
        notes=notes,
    )


def saturated_vapor_enthalpy_kj_kg(pressure_value: float, pressure_unit: str) -> tuple[float, float]:
    """Return saturated-vapor enthalpy and saturation temperature for a screening model.

    Uses a lightweight approximation suitable for plant troubleshooting rather than
    design-grade steam-table work.
    """
    temperature_c = condensing_temperature_c(pressure_value, pressure_unit)
    enthalpy_kj_kg = 2500.9 + 1.82 * temperature_c
    return enthalpy_kj_kg, temperature_c


def evaluate_steam_header_pressure_change(
    duty_kw: float,
    current_pressure_value: float,
    current_pressure_unit: str,
    reduced_pressure_value: float,
    reduced_pressure_unit: str,
    process_pressure_value: float | None = None,
    process_pressure_unit: str = "kPa",
    process_bpe_c: float = 0.0,
) -> SteamHeaderPressureChangeResult:
    if duty_kw <= 0.0:
        raise ValueError("Duty must be positive.")

    current_case = steam_flow_for_duty_kw(duty_kw, current_pressure_value, current_pressure_unit)
    reduced_case = steam_flow_for_duty_kw(duty_kw, reduced_pressure_value, reduced_pressure_unit)
    reduced_available_case = duty_from_steam_flow_kg_h(
        current_case.steam_flow_kg_h,
        reduced_pressure_value,
        reduced_pressure_unit,
    )

    current_pressure_kpa_abs = pressure_to_kpa_abs(current_pressure_value, current_pressure_unit)
    reduced_pressure_kpa_abs = pressure_to_kpa_abs(reduced_pressure_value, reduced_pressure_unit)
    additional_steam_required_kg_h = reduced_case.steam_flow_kg_h - current_case.steam_flow_kg_h
    additional_steam_required_pct = additional_steam_required_kg_h / max(current_case.steam_flow_kg_h, 1e-9) * 100.0
    duty_shortfall_kw = current_case.duty_kw - reduced_available_case.duty_kw
    duty_shortfall_pct = duty_shortfall_kw / max(current_case.duty_kw, 1e-9) * 100.0

    process_boiling_temperature_c: float | None = None
    current_available_delta_t_c: float | None = None
    reduced_available_delta_t_c: float | None = None
    delta_t_change_c: float | None = None
    if process_pressure_value is not None:
        process_point = build_thermal_point(process_pressure_value, process_pressure_unit, process_bpe_c)
        process_boiling_temperature_c = process_point.boiling_temperature_c
        current_available_delta_t_c = current_case.condensing_temperature_c - process_boiling_temperature_c
        reduced_available_delta_t_c = reduced_case.condensing_temperature_c - process_boiling_temperature_c
        delta_t_change_c = reduced_available_delta_t_c - current_available_delta_t_c

    notes = [
        "Pressure-change screen assumes saturated condensing steam and compares latent-heat effects only.",
        "Same-steam-flow duty assumes the original steam mass flow stays fixed after the header pressure change.",
    ]
    if reduced_pressure_kpa_abs < current_pressure_kpa_abs:
        notes.append("Reduced header pressure lowers condensing temperature and latent heat, so more steam is required for the same duty.")
    elif reduced_pressure_kpa_abs > current_pressure_kpa_abs:
        notes.append("Higher header pressure raises condensing temperature and latent heat in this screening model.")
    else:
        notes.append("Current and reduced pressures are equal; the comparison is effectively a no-change check.")
    if abs(additional_steam_required_pct) >= 5.0:
        notes.append("Steam-flow change exceeds 5%; this is often large enough to matter in plant utility balances.")
    if process_boiling_temperature_c is not None and reduced_available_delta_t_c is not None:
        if reduced_available_delta_t_c <= 0.0:
            notes.append("Reduced-pressure case leaves zero or negative condensing-to-boiling ΔT; heating duty may not be feasible.")
        elif reduced_available_delta_t_c < 5.0:
            notes.append("Reduced-pressure case leaves very little condensing ΔT; expect weak capacity or poor controllability.")

    return SteamHeaderPressureChangeResult(
        duty_kw=duty_kw,
        same_steam_flow_kg_h=current_case.steam_flow_kg_h,
        current_pressure_kpa_abs=current_pressure_kpa_abs,
        reduced_pressure_kpa_abs=reduced_pressure_kpa_abs,
        current_condensing_temperature_c=current_case.condensing_temperature_c,
        reduced_condensing_temperature_c=reduced_case.condensing_temperature_c,
        current_latent_heat_kj_kg=current_case.latent_heat_kj_kg,
        reduced_latent_heat_kj_kg=reduced_case.latent_heat_kj_kg,
        current_steam_flow_kg_h=current_case.steam_flow_kg_h,
        reduced_steam_flow_kg_h=reduced_case.steam_flow_kg_h,
        additional_steam_required_kg_h=additional_steam_required_kg_h,
        additional_steam_required_pct=additional_steam_required_pct,
        current_available_duty_kw=current_case.duty_kw,
        reduced_available_duty_kw=reduced_available_case.duty_kw,
        duty_shortfall_kw=duty_shortfall_kw,
        duty_shortfall_pct=duty_shortfall_pct,
        process_boiling_temperature_c=process_boiling_temperature_c,
        current_available_delta_t_c=current_available_delta_t_c,
        reduced_available_delta_t_c=reduced_available_delta_t_c,
        delta_t_change_c=delta_t_change_c,
        notes=notes,
    )


def thermo_compressor_balance(
    suction_flow_value: float,
    suction_flow_unit: str,
    suction_pressure_value: float,
    suction_pressure_unit: str,
    motive_pressure_value: float,
    motive_pressure_unit: str,
    discharge_pressure_value: float,
    discharge_pressure_unit: str,
    suction_superheat_c: float = 0.0,
    motive_superheat_c: float = 0.0,
) -> ThermoCompressorResult:
    suction_flow_kg_h = mass_flow_to_kg_h(suction_flow_value, suction_flow_unit)
    if suction_flow_kg_h <= 0.0:
        raise ValueError("Suction vapor flow must be positive.")

    suction_pressure_kpa_abs = pressure_to_kpa_abs(suction_pressure_value, suction_pressure_unit)
    motive_pressure_kpa_abs = pressure_to_kpa_abs(motive_pressure_value, motive_pressure_unit)
    discharge_pressure_kpa_abs = pressure_to_kpa_abs(discharge_pressure_value, discharge_pressure_unit)

    if discharge_pressure_kpa_abs <= suction_pressure_kpa_abs:
        raise ValueError("Discharge pressure must exceed suction pressure for a thermo-compressor screen.")
    if motive_pressure_kpa_abs <= discharge_pressure_kpa_abs:
        raise ValueError("Motive pressure must exceed discharge pressure for a thermo-compressor screen.")

    suction_enthalpy_sat, suction_sat_temperature_c = saturated_vapor_enthalpy_kj_kg(suction_pressure_value, suction_pressure_unit)
    motive_enthalpy_sat, motive_sat_temperature_c = saturated_vapor_enthalpy_kj_kg(motive_pressure_value, motive_pressure_unit)
    discharge_enthalpy_sat, discharge_sat_temperature_c = saturated_vapor_enthalpy_kj_kg(discharge_pressure_value, discharge_pressure_unit)

    cp_superheat_kj_kg_c = 2.08
    suction_temperature_c = suction_sat_temperature_c + max(suction_superheat_c, 0.0)
    motive_temperature_c = motive_sat_temperature_c + max(motive_superheat_c, 0.0)
    suction_vapor_enthalpy_kj_kg = suction_enthalpy_sat + cp_superheat_kj_kg_c * max(suction_superheat_c, 0.0)
    motive_vapor_enthalpy_kj_kg = motive_enthalpy_sat + cp_superheat_kj_kg_c * max(motive_superheat_c, 0.0)
    discharge_vapor_enthalpy_kj_kg = discharge_enthalpy_sat
    discharge_temperature_c = discharge_sat_temperature_c

    denominator = max(motive_vapor_enthalpy_kj_kg - discharge_vapor_enthalpy_kj_kg, 1e-6)
    motive_flow_kg_h = suction_flow_kg_h * max(discharge_vapor_enthalpy_kj_kg - suction_vapor_enthalpy_kj_kg, 0.0) / denominator
    discharge_flow_kg_h = suction_flow_kg_h + motive_flow_kg_h
    entrainment_ratio = suction_flow_kg_h / max(motive_flow_kg_h, 1e-9)
    motive_to_suction_ratio = motive_flow_kg_h / suction_flow_kg_h
    compression_ratio = discharge_pressure_kpa_abs / suction_pressure_kpa_abs
    motive_expansion_ratio = motive_pressure_kpa_abs / discharge_pressure_kpa_abs

    notes = [
        "Screening model only: uses approximate saturated-steam enthalpy and simple adiabatic mixing.",
        "Use vendor curves or steam-table software before equipment selection or rerating decisions.",
    ]
    if compression_ratio > 3.0:
        notes.append("Compression ratio is high for a single-stage thermo-compressor; check whether a multi-stage or different motive pressure is needed.")
    elif compression_ratio > 2.0:
        notes.append("Compression ratio is toward the upper end of common plant thermo-compressor service; compare against vendor curves.")
    if entrainment_ratio < 0.25:
        notes.append("Low entrainment ratio: motive steam demand is heavy relative to suction vapor load.")
    elif entrainment_ratio > 2.0:
        notes.append("High entrainment ratio: result may be optimistic without vendor performance confirmation.")
    if motive_superheat_c > 0.0 or suction_superheat_c > 0.0:
        notes.append("Superheat is handled with a constant vapor heat capacity approximation.")

    return ThermoCompressorResult(
        suction_flow_kg_h=suction_flow_kg_h,
        motive_flow_kg_h=motive_flow_kg_h,
        discharge_flow_kg_h=discharge_flow_kg_h,
        suction_pressure_kpa_abs=suction_pressure_kpa_abs,
        motive_pressure_kpa_abs=motive_pressure_kpa_abs,
        discharge_pressure_kpa_abs=discharge_pressure_kpa_abs,
        suction_temperature_c=suction_temperature_c,
        motive_temperature_c=motive_temperature_c,
        discharge_temperature_c=discharge_temperature_c,
        suction_vapor_enthalpy_kj_kg=suction_vapor_enthalpy_kj_kg,
        motive_vapor_enthalpy_kj_kg=motive_vapor_enthalpy_kj_kg,
        discharge_vapor_enthalpy_kj_kg=discharge_vapor_enthalpy_kj_kg,
        compression_ratio=compression_ratio,
        motive_expansion_ratio=motive_expansion_ratio,
        entrainment_ratio=entrainment_ratio,
        motive_to_suction_ratio=motive_to_suction_ratio,
        notes=notes,
    )
