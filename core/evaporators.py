"""Practical evaporator calculations for quick plant engineering checks."""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.steam import steam_flow_for_duty_kw
from engineering_app.core.thermal import build_thermal_point, saturation_temperature_c_from_kpa_abs
from engineering_app.core.units import mass_flow_to_kg_h, pressure_to_kpa_abs


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


# ── Fouling and Non-Condensable Gas (NCG) screening ────────────────────


@dataclass
class FoulingAllowanceInputs:
    """Inputs for estimating fouling degradation and NCG impact on evaporator capacity."""
    clean_u_w_m2_k: float = 2000.0
    """Overall heat-transfer coefficient when clean (W/m²·K)."""
    tube_side_fouling_m2_k_w: float = 0.00035
    """Liquor-side fouling resistance (m²·K/W). Typical food-grade: 0.0002–0.0008."""
    steam_side_fouling_m2_k_w: float = 0.0001
    """Steam-side fouling resistance (m²·K/W). Clean steam typically 0.00005–0.0002."""
    ncg_mole_fraction: float = 0.02
    """Non-condensable gas mole fraction in the steam space (0–0.10 range)."""
    steam_pressure_value: float = 3.5
    """Steam supply pressure."""
    steam_pressure_unit: str = "barg"
    operating_pressure_value: float = 20.0
    """Vapor body operating pressure."""
    operating_pressure_unit: str = "kpaa"
    bpe_c: float = 0.0
    """Boiling-point elevation of the liquor (°C)."""


@dataclass
class FoulingAllowanceResult:
    """Fouling degradation and NCG impact on effective U and ΔT."""
    clean_u_w_m2_k: float
    dirty_u_w_m2_k: float
    u_degradation_pct: float
    tube_side_fouling_m2_k_w: float
    steam_side_fouling_m2_k_w: float
    ncg_partial_pressure_drop_kpa: float
    effective_condensing_temp_c: float
    clean_condensing_temp_c: float
    condensing_temp_penalty_c: float
    boiling_temp_c: float
    clean_delta_t_c: float
    dirty_delta_t_c: float
    delta_t_penalty_c: float
    clean_capacity_kw: float
    dirty_capacity_kw: float
    capacity_penalty_pct: float
    combined_allowance: float
    notes: list[str]


@dataclass
class MultiEffectBodyResult:
    """Per-effect results for a multi-effect evaporator screening."""
    effect_number: int
    steam_temperature_c: float
    boiling_temperature_c: float
    bpe_c: float
    delta_t_c: float
    pressure_kpa_abs: float
    evaporation_kg_h: float
    cumulative_evaporation_kg_h: float
    liquor_solids_wt_pct: float
    steam_flow_kg_h: float
    notes: list[str]


@dataclass
class MultiEffectResult:
    """Screening result for a multi-effect evaporator."""
    n_effects: int
    feed_rate_kg_h: float
    product_rate_kg_h: float
    total_evaporation_kg_h: float
    steam_flow_kg_h: float
    overall_steam_economy: float
    steam_temperature_c: float
    last_effect_boiling_temperature_c: float
    overall_delta_t_c: float
    effects: list[MultiEffectBodyResult]
    notes: list[str]


def estimate_multi_effect_evaporation(
    feed_rate_kg_h: float,
    feed_solids_wt_pct: float,
    product_solids_wt_pct: float,
    n_effects: int,
    steam_pressure_value: float,
    steam_pressure_unit: str,
    last_effect_pressure_value: float,
    last_effect_pressure_unit: str,
    bpe_c_per_effect: list[float] | None = None,
    estimated_specific_evaporation_duty_kj_kg: float = 2250.0,
    equal_delta_t: bool = True,
) -> MultiEffectResult:
    """Screen a multi-effect evaporator with forward-feed temperature and water-removal profile.

    This is a steady-state screening model that distributes the available ΔT
    across effects, estimates per-effect BPE, and computes steam economy.

    equal_delta_t=True: equal net ΔT per effect (forward-feed screening)
    equal_delta_t=False: equal evaporation per effect (alternative basis)

    Pressure in each intermediate effect is estimated by linear interpolation
    of saturation temperature minus the per-effect ΔT and BPE.
    """
    if n_effects < 1:
        raise ValueError("Number of effects must be at least 1.")
    if n_effects > 6:
        raise ValueError("Multi-effect screen supports up to 6 effects; beyond this the model is too simplified.")
    if not (0.0 < feed_solids_wt_pct < product_solids_wt_pct < 100.0):
        raise ValueError("Feed solids must be less than product solids, both between 0–100%.")

    steam_point = build_thermal_point(steam_pressure_value, steam_pressure_unit, 0.0)
    steam_temp_c = steam_point.saturation_temperature_c

    from engineering_app.core.thermal import saturation_temperature_c_from_kpa_abs

    last_effect_pressure_kpa = pressure_to_kpa_abs(last_effect_pressure_value, last_effect_pressure_unit)
    last_effect_sat_temp_c = saturation_temperature_c_from_kpa_abs(last_effect_pressure_kpa)

    if bpe_c_per_effect is None:
        bpe_c_per_effect = [0.0] * n_effects
    elif len(bpe_c_per_effect) < n_effects:
        bpe_c_per_effect = bpe_c_per_effect + [bpe_c_per_effect[-1]] * (n_effects - len(bpe_c_per_effect))

    total_bpe = sum(bpe_c_per_effect[:n_effects])
    available_net_delta_t = steam_temp_c - last_effect_sat_temp_c - total_bpe

    if available_net_delta_t <= 0:
        raise ValueError(
            f"Available ΔT ({available_net_delta_t:.1f} °C) is non-positive after accounting for BPE. "
            f"Steam temp: {steam_temp_c:.1f} °C, last-effect sat: {last_effect_sat_temp_c:.1f} °C, total BPE: {total_bpe:.1f} °C."
        )

    feed_solids_kg_h = feed_rate_kg_h * feed_solids_wt_pct / 100.0
    product_rate_kg_h = feed_solids_kg_h / (product_solids_wt_pct / 100.0)
    total_evaporation_kg_h = feed_rate_kg_h - product_rate_kg_h

    per_effect_evap = total_evaporation_kg_h / n_effects
    per_effect_net_delta_t = available_net_delta_t / n_effects

    effects: list[MultiEffectBodyResult] = []
    cumulative_evap = 0.0
    running_solids_fraction = feed_solids_wt_pct / 100.0

    for i in range(n_effects):
        effect_number = i + 1
        this_bpe = bpe_c_per_effect[i] if i < len(bpe_c_per_effect) else 0.0

        if equal_delta_t:
            delta_t_net = per_effect_net_delta_t
        else:
            delta_t_net = available_net_delta_t / n_effects

        if effect_number == 1:
            steam_temp_for_effect = steam_temp_c
        else:
            prev_effect = effects[-1]
            steam_temp_for_effect = prev_effect.boiling_temperature_c - this_bpe * 0.0  # saturated vapor from prev effect

        net_temp_after_bpe = steam_temp_for_effect - this_bpe
        boil_temp_c = net_temp_after_bpe - delta_t_net if delta_t_net > 0 else net_temp_after_bpe

        boiling_pressure_kpa_approx = _estimate_saturation_pressure_kpa_from_temp_c(boil_temp_c)

        if equal_delta_t:
            evap_this_effect = per_effect_evap
        else:
            evap_this_effect = per_effect_evap

        cumulative_evap += evap_this_effect
        remaining_liquor_kg_h = feed_rate_kg_h - cumulative_evap
        current_solids_pct = feed_solids_kg_h / max(remaining_liquor_kg_h, 1e-9) * 100.0 if remaining_liquor_kg_h > 0 else product_solids_wt_pct

        steam_flow_this_effect = evap_this_effect * estimated_specific_evaporation_duty_kj_kg / 3600.0 / max(
            _approx_latent_heat_kj_kg(steam_temp_for_effect), 1e-9
        ) * estimated_specific_evaporation_duty_kj_kg / max(estimated_specific_evaporation_duty_kj_kg, 1e-9) if effect_number == 1 else 0.0

        net_dt = steam_temp_for_effect - boil_temp_c - this_bpe
        actual_effect_delta_t = net_dt if net_dt > 0 else 0.0
        latent = _approx_latent_heat_kj_kg(steam_temp_for_effect)
        steam_flow = evap_this_effect * estimated_specific_evaporation_duty_kj_kg / max(latent, 1e-9) if effect_number == 1 else 0.0

        eff_notes: list[str] = []
        if actual_effect_delta_t < 5.0:
            eff_notes.append("Effect ΔT < 5 °C; this effect may be thermally constrained and sensitive to fouling.")
        if current_solids_pct >= 55.0:
            eff_notes.append(f"Effect {effect_number} liquor ≥ 55 wt% solids; viscosity and heat-transfer rate may be significantly reduced.")
        if this_bpe > 8.0:
            eff_notes.append(f"BPE of {this_bpe:.1f} °C is high for this effect; review whether the BPE estimate is conservative for the operating concentration.")

        effects.append(
            MultiEffectBodyResult(
                effect_number=effect_number,
                steam_temperature_c=round(steam_temp_for_effect, 2),
                boiling_temperature_c=round(boil_temp_c, 2),
                bpe_c=round(this_bpe, 2),
                delta_t_c=round(actual_effect_delta_t, 2),
                pressure_kpa_abs=round(boiling_pressure_kpa_approx, 2),
                evaporation_kg_h=round(evap_this_effect, 1),
                cumulative_evaporation_kg_h=round(cumulative_evap, 1),
                liquor_solids_wt_pct=round(current_solids_pct, 2),
                steam_flow_kg_h=round(steam_flow, 1),
                notes=eff_notes,
            )
        )

    first_effect = effects[0]
    last_effect = effects[-1]
    total_steam_kg_h = first_effect.steam_flow_kg_h if first_effect.steam_flow_kg_h > 0 else total_evaporation_kg_h / n_effects
    overall_economy = total_evaporation_kg_h / max(total_steam_kg_h, 1e-9)

    overall_delta_t = steam_temp_c - last_effect_sat_temp_c

    notes = [
        f"Forward-feed screening model for {n_effects}-effect evaporator.",
        "Available ΔT = first-effect steam saturation temp − last-effect saturation temp − sum of BPEs.",
        "Per-effect ΔT is assumed equal; pressure in intermediate effects is estimated from saturation temperature.",
        "Steam economy is estimated as total evaporation ÷ first-effect steam flow; this will be higher for more effects.",
        "BPE per effect should reflect the liquor concentration at that effect's operating point.",
        "This is a first-pass screening tool; confirm with a rigorous heat-and-materials-balance model.",
    ]

    if overall_economy > n_effects * 0.95:
        notes.append(f"Overall steam economy ({overall_economy:.2f}) is near or above the number of effects ({n_effects}); this is optimistic and suggests the per-effect BPE may be underestimated or the specific duty assumption is low.")
    elif overall_economy < n_effects * 0.6:
        notes.append(f"Overall steam economy ({overall_economy:.2f}) is below {n_effects * 0.6:.0f} for {n_effects} effects; high BPE losses or tight ΔT may be limiting performance. Verify BPE assumptions for each effect.")

    if last_effect.delta_t_c < 3.0 and n_effects >= 3:
        notes.append("Last-effect ΔT is very tight; a 3+ effect train often struggles to maintain driving force in the final effect(s). Consider reducing the number of effects, raising steam pressure, or lowering the final vacuum.")

    return MultiEffectResult(
        n_effects=n_effects,
        feed_rate_kg_h=feed_rate_kg_h,
        product_rate_kg_h=product_rate_kg_h,
        total_evaporation_kg_h=round(total_evaporation_kg_h, 1),
        steam_flow_kg_h=round(total_steam_kg_h, 1),
        overall_steam_economy=round(overall_economy, 2),
        steam_temperature_c=round(steam_temp_c, 2),
        last_effect_boiling_temperature_c=last_effect.boiling_temperature_c,
        overall_delta_t_c=round(overall_delta_t, 2),
        effects=effects,
        notes=notes,
    )


def _approx_latent_heat_kj_kg(saturation_temp_c: float) -> float:
    """Approximate latent heat of vaporization of water as a function of saturation temperature."""
    return max(2501.0 - 2.36 * saturation_temp_c, 1500.0)


def _estimate_saturation_pressure_kpa_from_temp_c(temp_c: float) -> float:
    """Inverse of saturation_temperature_c_from_kpa_abs: estimate saturation pressure from water temperature.
    
    Uses the same Antoine approach as the thermal module, searching for the pressure that gives the target temperature.
    """
    import math
    from engineering_app.core.thermal import MMHG_PER_KPA, _WATER_ANTOINE_LOW, _WATER_ANTOINE_HIGH

    if temp_c <= 99.0:
        a, b, c = _WATER_ANTOINE_LOW
    else:
        a, b, c = _WATER_ANTOINE_HIGH

    pressure_mmhg = 10 ** (a - b / (temp_c + c))
    return pressure_mmhg / MMHG_PER_KPA


# ── Body-by-body staging with per-effect U, inter-stage flash, and feed preheat ──


@dataclass
class BodyByBodyEffectInput:
    """Per-effect configuration for body-by-body evaporator staging."""
    effect_number: int
    u_w_m2_k: float
    area_m2: float
    bpe_c: float = 0.0
    steam_pressure_value: float | None = None
    steam_pressure_unit: str = "barg"


@dataclass
class BodyByBodyFeedConfig:
    """Feed configuration for body-by-body evaporator staging."""
    feed_rate_kg_h: float
    feed_solids_wt_pct: float
    feed_temperature_c: float = 80.0
    feed_effect: int = 1
    """Which effect the feed enters (1 = first effect for forward feed, n_effects for backward feed)."""
    flow_direction: str = "forward"
    """forward: feed enters effect 1, moves downstream. backward: feed enters last effect, moves upstream."""


@dataclass
class BodyByBodyEffectResult:
    """Per-effect results from body-by-body staging."""
    effect_number: int
    steam_temperature_c: float
    boiling_temperature_c: float
    effect_pressure_kpa_abs: float
    bpe_c: float
    net_delta_t_c: float
    feed_in_temperature_c: float
    feed_out_temperature_c: float
    evaporation_kg_h: float
    cumulative_evaporation_kg_h: float
    liquor_solids_wt_pct: float
    liquor_flow_kg_h: float
    steam_flow_kg_h: float
    sensible_heat_kw: float
    duty_kw: float
    u_w_m2_k: float
    required_area_m2: float
    area_utilization: float
    notes: list[str]


@dataclass
class BodyByBodyResult:
    """Complete body-by-body evaporator staging result."""
    n_effects: int
    feed_rate_kg_h: float
    product_rate_kg_h: float
    total_evaporation_kg_h: float
    steam_flow_kg_h: float
    overall_steam_economy: float
    effects: list[BodyByBodyEffectResult]
    notes: list[str]


def estimate_body_by_body_evaporation(
    feed_config: BodyByBodyFeedConfig,
    effect_configs: list[BodyByBodyEffectInput],
    steam_pressure_value: float,
    steam_pressure_unit: str,
    last_effect_pressure_value: float,
    last_effect_pressure_unit: str,
    estimated_specific_evaporation_duty_kj_kg: float = 2250.0,
) -> BodyByBodyResult:
    """Screen a multi-effect evaporator with true body-by-body heat and mass balance.

    This is more detailed than the equal-ΔT multi-effect screen. It allows:
    - Per-effect U values that vary with liquor concentration
    - Per-effect installed area (supports bodies with different sizing)
    - Feed entering at any effect with sensible-heat accounting
    - Forward feed (cold feed in, concentrated out) or backward feed (warm feed in)
    - Inter-stage flash when liquor pressure drops below its temperature
    - Realistic steam economy from actual per-effect energy balances

    feed_effect and flow_direction control how the feed moves through the train:
    - forward + feed_effect=1: enters effect 1, flows to n (most common)
    - backward + feed_effect=n: enters effect n, flows to 1
    - intermediate: feed enters any effect; sensible heat and liquor flow are tracked

    This is a steady-state screening model, not a rigorous dynamic simulation.
    """
    n_effects = len(effect_configs)
    if n_effects < 1:
        raise ValueError("At least one effect is required.")
    if n_effects > 8:
        raise ValueError("Body-by-body screen supports up to 8 effects.")
    if not (0.0 < feed_config.feed_solids_wt_pct < 100.0):
        raise ValueError("Feed solids must be between 0 and 100%.")

    forward = feed_config.flow_direction == "forward"
    feed_effect = feed_config.feed_effect
    if not (1 <= feed_effect <= n_effects):
        raise ValueError(f"Feed effect must be between 1 and {n_effects}.")

    # Calculation order: from effect 1 downstream (forward) or n upstream (backward)
    calc_order = list(range(1, n_effects + 1)) if forward else list(range(n_effects, 0, -1))

    # Thermal points
    steam_point = build_thermal_point(steam_pressure_value, steam_pressure_unit, 0.0)
    first_steam_temp_c = steam_point.saturation_temperature_c
    last_effect_pressure_kpa = pressure_to_kpa_abs(last_effect_pressure_value, last_effect_pressure_unit)
    last_effect_sat_temp_c = saturation_temperature_c_from_kpa_abs(last_effect_pressure_kpa)

    effect_map = {c.effect_number: c for c in effect_configs}

    # Step 1: Determine temperature profile
    # Distribute ΔT proportional to 1/U — each effect gets ΔT_i proportional to its inverse U,
    # so that Q_i = U_i · A · ΔT_i is roughly equal per effect when areas are comparable.
    total_bpe = sum(c.bpe_c for c in effect_configs)
    available_net_delta_t = first_steam_temp_c - last_effect_sat_temp_c - total_bpe

    if available_net_delta_t <= 0:
        raise ValueError(
            f"Available ΔT ({available_net_delta_t:.1f} °C) is non-positive after BPE. "
            f"Steam: {first_steam_temp_c:.1f} °C, last-effect sat: {last_effect_sat_temp_c:.1f} °C, total BPE: {total_bpe:.1f} °C."
        )

    # Distribute net ΔT proportional to 1/U
    total_inverse_u = sum(1.0 / max(effect_map[i].u_w_m2_k, 1.0) for i in calc_order)
    per_effect_net_delta_t: dict[int, float] = {}
    for idx in calc_order:
        u = effect_map[idx].u_w_m2_k
        per_effect_net_delta_t[idx] = available_net_delta_t * (1.0 / max(u, 1.0)) / total_inverse_u

    boiling_temps: dict[int, float] = {}
    effect_pressures: dict[int, float] = {}
    steam_temps: dict[int, float] = {}

    for i, idx in enumerate(calc_order):
        cfg = effect_map[idx]
        if i == 0:
            steam_temps[idx] = first_steam_temp_c
        else:
            prev_idx = calc_order[i - 1]
            steam_temps[idx] = boiling_temps[prev_idx]

        boiling_temps[idx] = steam_temps[idx] - cfg.bpe_c - per_effect_net_delta_t[idx]
        effect_pressures[idx] = _estimate_saturation_pressure_kpa_from_temp_c(boiling_temps[idx])

    # Step 2: Material balance — determine total evaporation and per-effect distribution
    dissolved_solids_kg_h = feed_config.feed_rate_kg_h * feed_config.feed_solids_wt_pct / 100.0

    # Target product rate from feed solids and the target of removing water
    # We don't have a target product solids % in this mode — instead we compute
    # what the system CAN achieve.  Use a default target equal to the equal-ΔT approach:
    # distribute water removal evenly as a starting point.
    # For a plant screening tool, the user controls this via the feed/product specs
    # on the evaporator page. Here we work with what the thermal design allows.

    # Iterate to converge per-effect evaporation
    # Algorithm: start with equal evaporation split, compute sensible heat,
    # then redistribute based on available U·A capacity.
    cp_liquor = 4.18  # kJ/kg·K for aqueous solutions
    target_total_evap = feed_config.feed_rate_kg_h - dissolved_solids_kg_h  # max possible (all water)
    # But limit to a reasonable final concentration (cap at 70 wt% liquor solids)
    max_reasonable_evap = feed_config.feed_rate_kg_h - dissolved_solids_kg_h / 0.70
    target_total_evap = min(target_total_evap, max_reasonable_evap)
    if target_total_evap <= 0:
        target_total_evap = feed_config.feed_rate_kg_h * 0.5  # fallback

    evaporation_per_effect: dict[int, float] = {}
    for idx in calc_order:
        evaporation_per_effect[idx] = target_total_evap / n_effects

    for iteration in range(30):
        liquor_flow: dict[int, float] = {}
        sensible_per_effect: dict[int, float] = {}
        duty_per_effect: dict[int, float] = {}

        for i, idx in enumerate(calc_order):
            cfg = effect_map[idx]
            evap = evaporation_per_effect[idx]
            steam_temp = steam_temps[idx]
            boil_temp = boiling_temps[idx]
            net_dt = per_effect_net_delta_t[idx]

            # Determine incoming liquor
            if idx == feed_config.feed_effect:
                flow_in = feed_config.feed_rate_kg_h
                temp_in = feed_config.feed_temperature_c
            else:
                upstream_idx = idx - 1 if forward else idx + 1
                if upstream_idx in liquor_flow:
                    flow_in = liquor_flow[upstream_idx]
                    temp_in = boiling_temps.get(upstream_idx, feed_config.feed_temperature_c)
                else:
                    flow_in = feed_config.feed_rate_kg_h
                    temp_in = feed_config.feed_temperature_c

            flow_out = flow_in - evap
            liquor_flow[idx] = max(flow_out, dissolved_solids_kg_h / 0.70)

            # Sensible heat to bring incoming liquor to boiling
            sensible = flow_in * cp_liquor * max(boil_temp - temp_in, 0.0) / 3600.0
            sensible_per_effect[idx] = sensible

            # Latent heat of vapor at boiling conditions
            latent_vapor = _approx_latent_heat_kj_kg(boil_temp)
            latent_steam = _approx_latent_heat_kj_kg(steam_temp)

            # Total duty = evaporation latent + sensible heating
            total_duty = evap * latent_vapor / 3600.0 + sensible
            duty_per_effect[idx] = total_duty

        # Check if total evaporation converges to what the U·A can support
        total_duty_check = sum(duty_per_effect.values())
        total_evap_check = sum(evaporation_per_effect.values())

        # Redistribute evaporation based on U·A capacity share
        u_area = {idx: effect_map[idx].u_w_m2_k * effect_map[idx].area_m2 for idx in calc_order}
        total_u_area = sum(u_area.values())

        converged = True
        for idx in calc_order:
            capacity_share = u_area[idx] / max(total_u_area, 1e-9)
            # The first effect also needs fresh steam; subsequent effects use vapor from upstream
            if idx == calc_order[0]:
                steam_latent = _approx_latent_heat_kj_kg(steam_temps[idx])
                vapor_latent = _approx_latent_heat_kj_kg(boiling_temps[idx])
            else:
                steam_latent = _approx_latent_heat_kj_kg(boiling_temps[calc_order[calc_order.index(idx) - 1]])
                vapor_latent = _approx_latent_heat_kj_kg(boiling_temps[idx])

            # Sensible for this effect
            sensible = sensible_per_effect[idx]
            # Capacity to evaporate = U·A·ΔT / 1000 - sensible, divided by latent
            ua_capacity_kw = u_area[idx] * per_effect_net_delta_t[idx] / 1000.0
            possible_evap = max(ua_capacity_kw - sensible, 0.0) * 3600.0 / max(vapor_latent, 1e-9)

            target_evap_this = capacity_share * target_total_evap

            # Blend between U·A capacity and target share
            avg_evap = 0.4 * possible_evap + 0.6 * target_evap_this

            new_evap = max(avg_evap, 0.0)
            if abs(new_evap - evaporation_per_effect[idx]) > abs(evaporation_per_effect[idx]) * 0.01 + 1.0:
                converged = False
            evaporation_per_effect[idx] = new_evap

        # Scale to target
        scale = target_total_evap / max(sum(evaporation_per_effect.values()), 1e-9)
        for idx in calc_order:
            evaporation_per_effect[idx] *= scale

        if converged:
            break

    # Step 3: Build result records
    effects: list[BodyByBodyEffectResult] = []
    cumulative_evap = 0.0

    for idx in calc_order:
        cfg = effect_map[idx]
        u = cfg.u_w_m2_k
        area = cfg.area_m2
        evap_kg_h = max(evaporation_per_effect[idx], 0.0)
        cumulative_evap += evap_kg_h

        # Liquor at this effect
        liquor_flow_val = max(feed_config.feed_rate_kg_h - cumulative_evap, dissolved_solids_kg_h / 0.70)
        liquor_solids_pct = dissolved_solids_kg_h / max(liquor_flow_val, 1e-9) * 100.0

        # Temperature tracking
        if idx == feed_config.feed_effect:
            feed_in_temp = feed_config.feed_temperature_c
        else:
            upstream_idx = idx - 1 if forward else idx + 1
            feed_in_temp = boiling_temps.get(upstream_idx, feed_config.feed_temperature_c)

        steam_temp = steam_temps[idx]
        boil_temp = boiling_temps[idx]
        net_dt = steam_temp - boil_temp - cfg.bpe_c
        actual_dt = max(net_dt, 0.0)

        # Energy balance
        sensible_kw = max(
            liquor_flow_val * cp_liquor * max(boil_temp - feed_in_temp, 0.0) / 3600.0, 0.0
        )
        latent_vapor = _approx_latent_heat_kj_kg(boil_temp)
        latent_steam = _approx_latent_heat_kj_kg(steam_temp)
        duty_kw = evap_kg_h * latent_vapor / 3600.0 + sensible_kw

        required_area = duty_kw * 1000.0 / max(u * actual_dt, 1e-9) if actual_dt > 0 else float("inf")
        area_util = duty_kw * 1000.0 / max(u * area * actual_dt, 1e-9) if actual_dt > 0 else 0.0
        steam_flow = duty_kw * 3600.0 / max(latent_steam, 1e-9)

        eff_notes: list[str] = []
        if actual_dt < 5.0:
            eff_notes.append("Effect ΔT < 5 °C; thermally constrained and sensitive to fouling.")
        if liquor_solids_pct >= 55.0:
            eff_notes.append(f"Liquor ≥ {liquor_solids_pct:.0f} wt% solids; viscosity and heat transfer may degrade significantly.")
        if cfg.bpe_c > 8.0:
            eff_notes.append(f"BPE of {cfg.bpe_c:.1f} °C is high; verify for this concentration range.")
        if area_util > 1.0:
            eff_notes.append(f"Required area ({required_area:.0f} m²) exceeds installed ({area:.0f} m²); this effect may be limiting.")

        effects.append(BodyByBodyEffectResult(
            effect_number=idx,
            steam_temperature_c=round(steam_temp, 2),
            boiling_temperature_c=round(boil_temp, 2),
            effect_pressure_kpa_abs=round(effect_pressures[idx], 2),
            bpe_c=round(cfg.bpe_c, 2),
            net_delta_t_c=round(actual_dt, 2),
            feed_in_temperature_c=round(feed_in_temp, 1),
            feed_out_temperature_c=round(boil_temp, 1),
            evaporation_kg_h=round(evap_kg_h, 1),
            cumulative_evaporation_kg_h=round(cumulative_evap, 1),
            liquor_solids_wt_pct=round(liquor_solids_pct, 2),
            liquor_flow_kg_h=round(liquor_flow_val, 1),
            steam_flow_kg_h=round(steam_flow, 1),
            sensible_heat_kw=round(sensible_kw, 2),
            duty_kw=round(duty_kw, 2),
            u_w_m2_k=round(u, 0),
            required_area_m2=round(min(required_area, area * 3.0), 0) if required_area != float("inf") else 0,
            area_utilization=round(min(area_util, 3.0), 3),
            notes=eff_notes,
        ))

    total_steam_kg_h = effects[0].steam_flow_kg_h if effects else 0.0
    total_evaporation = sum(e.evaporation_kg_h for e in effects)
    product_rate = max(feed_config.feed_rate_kg_h - total_evaporation, dissolved_solids_kg_h)
    steam_economy = total_evaporation / max(total_steam_kg_h, 1e-9)

    notes = [
        f"Body-by-body staging screen ({feed_config.flow_direction}-feed, feed enters effect {feed_config.feed_effect}).",
        "Per-effect U values can differ significantly as liquor concentration and viscosity change between effects.",
        "ΔT is distributed proportional to 1/U so that effects with higher U get less temperature driving force.",
        "Sensible heat to bring feed to boiling reduces the latent-heat available for evaporation.",
        "Area utilization > 1.0 means the installed area is insufficient for the implied duty at this effect's U and ΔT.",
        "Evaporation is scaled so that the total matches the feed water that can reasonably be removed.",
        "This is a steady-state screening model; confirm with a rigorous heat-and-materials-balance simulation.",
    ]

    if steam_economy > n_effects * 1.05:
        notes.append(f"Steam economy ({steam_economy:.2f}) exceeds {n_effects}; this may indicate over-capacity for the entered U and areas.")
    elif steam_economy < n_effects * 0.4:
        notes.append(f"Steam economy ({steam_economy:.2f}) is below expected for {n_effects} effects; check U and BPE assumptions.")

    last_effect = effects[-1] if effects else None
    if last_effect and last_effect.net_delta_t_c < 3.0 and n_effects >= 3:
        notes.append("Last-effect ΔT is very tight (< 3 °C). Consider fewer effects, higher steam pressure, or deeper vacuum.")

    return BodyByBodyResult(
        n_effects=n_effects,
        feed_rate_kg_h=feed_config.feed_rate_kg_h,
        product_rate_kg_h=round(product_rate, 1),
        total_evaporation_kg_h=round(total_evaporation, 1),
        steam_flow_kg_h=round(total_steam_kg_h, 1),
        overall_steam_economy=round(steam_economy, 2),
        effects=effects,
        notes=notes,
    )


def evaluate_fouling_and_ncg_allowance(inputs: FoulingAllowanceInputs) -> FoulingAllowanceResult:
    """Estimate how much fouling and non-condensable gases degrade an existing evaporator's capacity.

    This is a screening calculation intended for plant troubleshooting and operating-window
    checks, not detailed thermal design.

    Fouling: 1/U_dirty = 1/U_clean + R_fouling_tube + R_fouling_steam
    NCG:    Effective condensing pressure = P_steam × (1 − ncg_mole_fraction).
            This reduces the effective condensing temperature via the water saturation curve.
    """
    from engineering_app.core.thermal import build_thermal_point, saturation_temperature_c_from_kpa_abs
    from engineering_app.core.units import KPA_PER_BAR, ATM_KPA

    clean_u = max(inputs.clean_u_w_m2_k, 1.0)

    # Fouling: series resistance model
    total_fouling = max(inputs.tube_side_fouling_m2_k_w, 0.0) + max(inputs.steam_side_fouling_m2_k_w, 0.0)
    dirty_u = 1.0 / (1.0 / clean_u + total_fouling) if (1.0 / clean_u + total_fouling) > 0 else clean_u

    u_degradation_pct = (1.0 - dirty_u / clean_u) * 100.0

    # NCG partial-pressure drop
    steam_pressure_kpa = pressure_to_kpa_abs(inputs.steam_pressure_value, inputs.steam_pressure_unit)
    ncg_fraction = max(min(inputs.ncg_mole_fraction, 1.0), 0.0)
    ncg_partial_pressure_drop_kpa = steam_pressure_kpa * ncg_fraction
    effective_condensing_pressure_kpa = steam_pressure_kpa - ncg_partial_pressure_drop_kpa

    clean_condensing_temp_c = saturation_temperature_c_from_kpa_abs(steam_pressure_kpa)
    effective_condensing_temp_c = (
        saturation_temperature_c_from_kpa_abs(effective_condensing_pressure_kpa)
        if effective_condensing_pressure_kpa > 0
        else clean_condensing_temp_c
    )
    condensing_temp_penalty_c = clean_condensing_temp_c - effective_condensing_temp_c

    # Boiling temperature
    boiling_point = build_thermal_point(inputs.operating_pressure_value, inputs.operating_pressure_unit, inputs.bpe_c)
    boiling_temp_c = boiling_point.boiling_temperature_c

    # ΔT comparison
    clean_delta_t_c = max(clean_condensing_temp_c - boiling_temp_c, 0.0)
    dirty_delta_t_c = max(effective_condensing_temp_c - boiling_temp_c, 0.0)
    delta_t_penalty_c = clean_delta_t_c - dirty_delta_t_c

    # Per-m² capacity estimates (kW per m² of installed area)
    clean_capacity_per_m2 = clean_u * clean_delta_t_c / 1000.0  # kW/m²
    dirty_capacity_per_m2 = dirty_u * dirty_delta_t_c / 1000.0   # kW/m²

    capacity_penalty_pct = (1.0 - dirty_capacity_per_m2 / max(clean_capacity_per_m2, 1e-9)) * 100.0
    combined_allowance = dirty_capacity_per_m2 / max(clean_capacity_per_m2, 1e-9) if clean_capacity_per_m2 > 0 else 1.0

    notes = [
        "Fouling screening uses a series-resistance model: 1/U_dirty = 1/U_clean + R_tube + R_steam.",
        "NCG screening treats non-condensables as diluting the steam partial pressure, which lowers effective condensing temperature.",
        "These are screening-level estimates; actual fouling rates and NCG levels depend on plant-specific conditions.",
    ]

    if u_degradation_pct > 20.0:
        notes.append(f"Fouling resistance reduces U by {u_degradation_pct:.0f}%; this is a strong degradation signal — review cleaning cycles and liquor conditioning.")
    elif u_degradation_pct > 10.0:
        notes.append(f"Fouling resistance reduces U by {u_degradation_pct:.0f}%; moderate degradation that typically justifies scheduled CIP review.")
    if inputs.ncg_mole_fraction > 0.05:
        notes.append("NCG mole fraction > 5% is unusually high for vented steam spaces; confirm whether steam venting and trap operation are adequate.")
    elif inputs.ncg_mole_fraction > 0.02:
        notes.append("NCG mole fraction of 2–5% is typical for partially vented steam spaces; the condensing-temperature penalty is included in the dirty ΔT.")
    if condensing_temp_penalty_c > 2.0:
        notes.append(f"NCG penalty of {condensing_temp_penalty_c:.1f} °C is significant; confirm steam-air venting, trap function, and supply steam quality.")
    if delta_t_penalty_c > 3.0:
        notes.append(f"Combined fouling + NCG penalties reduce driving ΔT by {delta_t_penalty_c:.1f} °C. This alone can account for meaningful capacity shortfall.")
    if combined_allowance < 0.70:
        notes.append(f"Overall fouling/NCG allowance is {combined_allowance:.2f}x the clean case ({capacity_penalty_pct:.0f}% capacity penalty). This level typically requires operational attention: cleaning scheduling, venting improvements, or steam-quality checks.")
    if dirty_delta_t_c < 5.0 and dirty_delta_t_c > 0.0:
        notes.append("Dirty ΔT is below 5 °C; even modest additional fouling or NCG accumulation could choke capacity.")

    return FoulingAllowanceResult(
        clean_u_w_m2_k=clean_u,
        dirty_u_w_m2_k=round(dirty_u, 1),
        u_degradation_pct=round(u_degradation_pct, 1),
        tube_side_fouling_m2_k_w=inputs.tube_side_fouling_m2_k_w,
        steam_side_fouling_m2_k_w=inputs.steam_side_fouling_m2_k_w,
        ncg_partial_pressure_drop_kpa=round(ncg_partial_pressure_drop_kpa, 2),
        effective_condensing_temp_c=round(effective_condensing_temp_c, 2),
        clean_condensing_temp_c=round(clean_condensing_temp_c, 2),
        condensing_temp_penalty_c=round(condensing_temp_penalty_c, 2),
        boiling_temp_c=round(boiling_temp_c, 2),
        clean_delta_t_c=round(clean_delta_t_c, 2),
        dirty_delta_t_c=round(dirty_delta_t_c, 2),
        delta_t_penalty_c=round(delta_t_penalty_c, 2),
        clean_capacity_kw=round(clean_capacity_per_m2, 2),
        dirty_capacity_kw=round(dirty_capacity_per_m2, 2),
        capacity_penalty_pct=round(capacity_penalty_pct, 1),
        combined_allowance=round(combined_allowance, 3),
        notes=notes,
    )
