"""Practical steam and utility helpers for field engineering.

These are intentionally lightweight approximations for quick calculations.
"""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.thermal import condensing_temperature_c
from engineering_app.core.units import mass_flow_to_kg_h


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
