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


@dataclass
class EvaporatorDesignCalibrationInputs:
    feed_rate_value: float
    feed_rate_unit: str
    feed_solids_wt_pct: float
    target_product_solids_wt_pct: float
    steam_pressure_value: float
    steam_pressure_unit: str
    operating_pressure_value: float
    operating_pressure_unit: str
    bpe_c: float = 0.0
    estimated_specific_evaporation_duty_kj_kg: float = 2250.0
    overall_u_w_m2_k: float = 1800.0
    installed_area_m2: float = 250.0
    availability_factor: float = 1.0


@dataclass
class EvaporatorDesignCalibrationResult:
    feed_rate_kg_h: float
    dissolved_solids_kg_h: float
    target_product_rate_kg_h: float
    target_evaporation_rate_kg_h: float
    achievable_product_rate_kg_h: float
    achievable_evaporation_rate_kg_h: float
    concentration_factor_target: float
    concentration_factor_achievable: float
    boiling_temperature_c: float
    condensing_temperature_c: float
    delta_t_c: float
    required_duty_kw: float
    available_duty_kw: float
    required_area_m2: float
    installed_area_m2: float
    area_utilization_fraction: float
    required_steam_flow_kg_h: float
    available_steam_flow_kg_h: float
    target_steam_economy_kg_evap_per_kg_steam: float
    achievable_steam_economy_kg_evap_per_kg_steam: float
    overall_u_w_m2_k: float
    availability_factor: float
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


def estimate_design_calibrated_evaporation(inputs: EvaporatorDesignCalibrationInputs) -> EvaporatorDesignCalibrationResult:
    feed_rate_kg_h = mass_flow_to_kg_h(inputs.feed_rate_value, inputs.feed_rate_unit)
    dissolved_solids_kg_h = feed_rate_kg_h * inputs.feed_solids_wt_pct / 100.0
    target_product_rate_kg_h = dissolved_solids_kg_h / max(inputs.target_product_solids_wt_pct / 100.0, 1e-9)
    target_evaporation_rate_kg_h = max(feed_rate_kg_h - target_product_rate_kg_h, 0.0)

    boiling_point = build_thermal_point(inputs.operating_pressure_value, inputs.operating_pressure_unit, inputs.bpe_c)
    condensing_point = build_thermal_point(inputs.steam_pressure_value, inputs.steam_pressure_unit, 0.0)
    delta_t_c = condensing_point.condensing_temperature_c - boiling_point.boiling_temperature_c

    required_duty_kw = target_evaporation_rate_kg_h * inputs.estimated_specific_evaporation_duty_kj_kg / 3600.0
    effective_u = max(inputs.overall_u_w_m2_k, 0.0)
    effective_area = max(inputs.installed_area_m2, 0.0)
    availability_factor = min(max(inputs.availability_factor, 0.0), 1.5)
    available_duty_kw = effective_u * effective_area * max(delta_t_c, 0.0) * availability_factor / 1000.0

    achievable_evaporation_rate_kg_h = available_duty_kw * 3600.0 / max(inputs.estimated_specific_evaporation_duty_kj_kg, 1e-9)
    max_evaporation_from_feed_kg_h = max(feed_rate_kg_h - dissolved_solids_kg_h, 0.0)
    achievable_evaporation_rate_kg_h = min(max(achievable_evaporation_rate_kg_h, 0.0), max_evaporation_from_feed_kg_h)
    achievable_product_rate_kg_h = max(feed_rate_kg_h - achievable_evaporation_rate_kg_h, dissolved_solids_kg_h)

    concentration_factor_target = max(inputs.target_product_solids_wt_pct / max(inputs.feed_solids_wt_pct, 1e-9), 0.0)
    achievable_product_solids_wt_pct = 100.0 * dissolved_solids_kg_h / max(achievable_product_rate_kg_h, 1e-9)
    concentration_factor_achievable = max(achievable_product_solids_wt_pct / max(inputs.feed_solids_wt_pct, 1e-9), 0.0)

    required_area_m2 = required_duty_kw * 1000.0 / max(effective_u * max(delta_t_c, 0.0) * availability_factor, 1e-9)
    area_utilization_fraction = required_duty_kw / max(available_duty_kw, 1e-9) if available_duty_kw > 0.0 else float("inf")

    required_steam = steam_flow_for_duty_kw(required_duty_kw, inputs.steam_pressure_value, inputs.steam_pressure_unit)
    available_steam = steam_flow_for_duty_kw(available_duty_kw, inputs.steam_pressure_value, inputs.steam_pressure_unit)
    target_steam_economy = target_evaporation_rate_kg_h / max(required_steam.steam_flow_kg_h, 1e-9)
    achievable_steam_economy = achievable_evaporation_rate_kg_h / max(available_steam.steam_flow_kg_h, 1e-9)

    notes = [
        "Design-calibrated mode estimates available evaporation from installed heat-transfer area, overall U, and available ΔT.",
        "Use this to screen whether an existing body should hit the target concentration before changing steam pressure, area, or U assumptions.",
        "This is still a first-pass plant model; it does not include liquor-side flashing details, non-condensables, detailed LMTD, or stage-by-stage effects.",
    ]
    if delta_t_c < 8.0:
        notes.append("Available temperature driving force is tight; achievable evaporation may be very sensitive to fouling and pressure error.")
    if area_utilization_fraction > 1.0:
        notes.append("Required duty exceeds available U·A·ΔT capacity; the target concentration is likely not achievable without more area, higher U, more ΔT, or lower throughput.")
    else:
        notes.append("Installed U·A·ΔT appears sufficient for the entered target on this first-pass screen.")
    if availability_factor < 1.0:
        notes.append("Availability factor below 1.0 reduces usable area to represent fouling, bypassing, or partial service.")
    if achievable_evaporation_rate_kg_h >= max_evaporation_from_feed_kg_h - 1.0e-9:
        notes.append("Available duty is high enough to remove essentially all entered feed water; achievable concentration is capped at the dry-solids limit rather than a practical liquor endpoint.")
    if achievable_product_solids_wt_pct >= 60.0:
        notes.append("High achievable final concentration may sharply increase viscosity, fouling, and circulation sensitivity.")

    return EvaporatorDesignCalibrationResult(
        feed_rate_kg_h=feed_rate_kg_h,
        dissolved_solids_kg_h=dissolved_solids_kg_h,
        target_product_rate_kg_h=target_product_rate_kg_h,
        target_evaporation_rate_kg_h=target_evaporation_rate_kg_h,
        achievable_product_rate_kg_h=achievable_product_rate_kg_h,
        achievable_evaporation_rate_kg_h=achievable_evaporation_rate_kg_h,
        concentration_factor_target=concentration_factor_target,
        concentration_factor_achievable=concentration_factor_achievable,
        boiling_temperature_c=boiling_point.boiling_temperature_c,
        condensing_temperature_c=condensing_point.condensing_temperature_c,
        delta_t_c=delta_t_c,
        required_duty_kw=required_duty_kw,
        available_duty_kw=available_duty_kw,
        required_area_m2=required_area_m2,
        installed_area_m2=effective_area,
        area_utilization_fraction=area_utilization_fraction,
        required_steam_flow_kg_h=required_steam.steam_flow_kg_h,
        available_steam_flow_kg_h=available_steam.steam_flow_kg_h,
        target_steam_economy_kg_evap_per_kg_steam=target_steam_economy,
        achievable_steam_economy_kg_evap_per_kg_steam=achievable_steam_economy,
        overall_u_w_m2_k=effective_u,
        availability_factor=availability_factor,
        notes=notes,
    )
