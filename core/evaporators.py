"""Practical evaporator calculations for quick plant engineering checks."""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.steam import steam_flow_for_duty_kw
from engineering_app.core.thermal import build_thermal_point
from engineering_app.core.units import mass_flow_to_kg_h


@dataclass
class EvaporatorInputs:
    feed_rate_value: float
    feed_rate_unit: str
    feed_solids_wt_pct: float
    product_solids_wt_pct: float
    steam_pressure_value: float
    steam_pressure_unit: str
    operating_pressure_value: float
    operating_pressure_unit: str
    passes: int = 1
    recirculation_ratio: float = 0.0
    bpe_c: float = 0.0
    estimated_specific_evaporation_duty_kj_kg: float = 2250.0


@dataclass
class EvaporatorResult:
    feed_rate_kg_h: float
    product_rate_kg_h: float
    evaporation_rate_kg_h: float
    concentration_factor: float
    boiling_temperature_c: float
    condensing_temperature_c: float
    delta_t_c: float
    estimated_duty_kw: float
    estimated_steam_flow_kg_h: float
    steam_economy_kg_evap_per_kg_steam: float
    notes: list[str]


def estimate_evaporation(inputs: EvaporatorInputs) -> EvaporatorResult:
    feed_rate_kg_h = mass_flow_to_kg_h(inputs.feed_rate_value, inputs.feed_rate_unit)
    feed_solids = feed_rate_kg_h * inputs.feed_solids_wt_pct / 100.0
    product_rate = feed_solids / max(inputs.product_solids_wt_pct / 100.0, 1e-9)
    evaporation_rate = max(feed_rate_kg_h - product_rate, 0.0)
    concentration_factor = max(inputs.product_solids_wt_pct / max(inputs.feed_solids_wt_pct, 1e-9), 0.0)

    boiling_point = build_thermal_point(inputs.operating_pressure_value, inputs.operating_pressure_unit, inputs.bpe_c)
    condensing_point = build_thermal_point(inputs.steam_pressure_value, inputs.steam_pressure_unit, 0.0)
    duty_kw = evaporation_rate * inputs.estimated_specific_evaporation_duty_kj_kg / 3600.0
    steam_result = steam_flow_for_duty_kw(duty_kw, inputs.steam_pressure_value, inputs.steam_pressure_unit)
    delta_t = condensing_point.condensing_temperature_c - boiling_point.boiling_temperature_c
    steam_economy = evaporation_rate / max(steam_result.steam_flow_kg_h, 1e-9)

    notes = [
        "Engineering estimate only; not a design-grade evaporator model.",
        "Boiling temperature includes the user-supplied BPE.",
        "Steam flow assumes saturated condensing steam and lumped evaporation duty.",
    ]
    if inputs.passes > 1:
        notes.append(f"Multi-pass heuristic only; passes entered: {inputs.passes}.")
    if inputs.recirculation_ratio > 0:
        notes.append(f"Recirculation ratio entered: {inputs.recirculation_ratio:.2f}.")
    if delta_t < 8.0:
        notes.append("Temperature driving force is getting tight; review operability and fouling risk.")
    if inputs.product_solids_wt_pct >= 60.0:
        notes.append("High final concentration may sharply increase viscosity and scaling risk.")

    return EvaporatorResult(
        feed_rate_kg_h=feed_rate_kg_h,
        product_rate_kg_h=product_rate,
        evaporation_rate_kg_h=evaporation_rate,
        concentration_factor=concentration_factor,
        boiling_temperature_c=boiling_point.boiling_temperature_c,
        condensing_temperature_c=condensing_point.condensing_temperature_c,
        delta_t_c=delta_t,
        estimated_duty_kw=duty_kw,
        estimated_steam_flow_kg_h=steam_result.steam_flow_kg_h,
        steam_economy_kg_evap_per_kg_steam=steam_economy,
        notes=notes,
    )
