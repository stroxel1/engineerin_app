"""Centrifugal pump sizing workflow for preliminary industrial screening."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from engineering_app.core.hydraulics import (
        G,
        HydraulicInputs,
        calculate_hydraulics,
        calculate_pump_power,
        estimate_npsha,
    )
except ModuleNotFoundError:  # pragma: no cover - repo-root test fallback
    from core.hydraulics import (
        G,
        HydraulicInputs,
        calculate_hydraulics,
        calculate_pump_power,
        estimate_npsha,
    )


@dataclass
class PumpSizingInputs:
    flow_m3_h: float
    flow_gpm: float
    density_kg_m3: float
    viscosity_cp: float
    liquid_temperature_c: float
    suction_static_head_m: float
    discharge_static_head_m: float
    suction_pipe_length_m: float
    discharge_pipe_length_m: float
    suction_pipe_id_mm: float
    discharge_pipe_id_mm: float
    suction_roughness_mm: float
    discharge_roughness_mm: float
    suction_k_total: float
    discharge_k_total: float
    surface_pressure_kpa_abs: float
    minimum_npsh_margin_ratio: float
    pump_efficiency_fraction: float
    motor_efficiency_fraction: float
    motor_service_factor: float
    required_npshr_m: float | None = None
    vapor_pressure_kpa_abs: float | None = None
    curve_shutoff_head_m: float | None = None
    curve_max_flow_m3_h: float | None = None
    curve_head_at_max_flow_m: float | None = None
    base_speed_rpm: float | None = None
    new_speed_rpm: float | None = None
    base_impeller_diameter_m: float | None = None
    new_impeller_diameter_m: float | None = None


@dataclass
class PumpSizingResult:
    required_flow_m3_h: float
    required_tdh_m: float
    static_head_total_m: float
    suction_line_loss_m: float
    discharge_line_loss_m: float
    suction_velocity_m_s: float
    discharge_velocity_m_s: float
    npsha_m: float
    npshr_m: float
    npsh_margin_m: float
    npsh_margin_ratio: float
    hydraulic_power_kw: float
    brake_power_kw: float
    brake_horsepower_hp: float
    motor_required_kw: float
    recommended_motor_kw: float
    recommended_motor_hp: float
    curve_head_at_duty_m: float | None
    curve_head_margin_m: float | None
    estimated_bep_flow_m3_h: float | None
    duty_flow_fraction_of_bep: float | None
    warnings: list[str]
    assumptions: list[str]


def atmospheric_pressure_kpa_abs_from_elevation(elevation_m: float) -> float:
    """Barometric approximation valid for typical industrial elevations."""
    bounded = min(max(elevation_m, -1000.0), 10000.0)
    return 101.325 * (1.0 - 2.25577e-5 * bounded) ** 5.25588


def _nearest_standard_motor_kw(required_kw: float) -> float:
    # Common IEC/NEMA-aligned nominal sizes.
    standards_kw = [
        0.55,
        0.75,
        1.1,
        1.5,
        2.2,
        3.0,
        4.0,
        5.5,
        7.5,
        11.0,
        15.0,
        18.5,
        22.0,
        30.0,
        37.0,
        45.0,
        55.0,
        75.0,
        90.0,
        110.0,
        132.0,
        160.0,
        200.0,
        250.0,
        315.0,
        400.0,
        500.0,
    ]
    for size in standards_kw:
        if required_kw <= size:
            return size
    return standards_kw[-1]


def _validate_inputs(inputs: PumpSizingInputs) -> None:
    if inputs.flow_m3_h <= 0.0:
        raise ValueError("Flow must be greater than zero.")
    if inputs.flow_gpm < 5.0 or inputs.flow_gpm > 1000.0:
        raise ValueError("Flow must be between 5 and 1000 gpm for this preliminary sizing workflow.")
    if inputs.density_kg_m3 <= 0.0:
        raise ValueError("Density must be greater than zero.")
    if inputs.viscosity_cp <= 0.0:
        raise ValueError("Viscosity must be greater than zero.")
    if inputs.suction_pipe_id_mm <= 0.0 or inputs.discharge_pipe_id_mm <= 0.0:
        raise ValueError("Pipe inside diameter must be greater than zero.")
    if inputs.pump_efficiency_fraction <= 0.0 or inputs.pump_efficiency_fraction >= 1.0:
        raise ValueError("Pump efficiency must be entered as a fraction between 0 and 1.")
    if inputs.motor_efficiency_fraction <= 0.0 or inputs.motor_efficiency_fraction > 1.0:
        raise ValueError("Motor efficiency must be entered as a fraction between 0 and 1.")
    if inputs.motor_service_factor < 1.0:
        raise ValueError("Motor service factor should be at least 1.0.")
    if inputs.minimum_npsh_margin_ratio < 1.0:
        raise ValueError("Minimum acceptable NPSH margin ratio must be at least 1.0.")
    if inputs.required_npshr_m is not None and inputs.required_npshr_m <= 0.0:
        raise ValueError("Required NPSHr must be positive when provided.")
    if inputs.vapor_pressure_kpa_abs is not None and inputs.vapor_pressure_kpa_abs <= 0.0:
        raise ValueError("Vapor pressure must be positive when provided.")


def calculate_pump_sizing(inputs: PumpSizingInputs) -> PumpSizingResult:
    _validate_inputs(inputs)

    suction = calculate_hydraulics(
        HydraulicInputs(
            volumetric_flow_m3_h=inputs.flow_m3_h,
            density_kg_m3=inputs.density_kg_m3,
            viscosity_cp=inputs.viscosity_cp,
            pipe_id_mm=inputs.suction_pipe_id_mm,
            pipe_length_m=inputs.suction_pipe_length_m,
            roughness_mm=inputs.suction_roughness_mm,
            elevation_change_m=0.0,
            fitting_k_total=inputs.suction_k_total,
        )
    )
    discharge = calculate_hydraulics(
        HydraulicInputs(
            volumetric_flow_m3_h=inputs.flow_m3_h,
            density_kg_m3=inputs.density_kg_m3,
            viscosity_cp=inputs.viscosity_cp,
            pipe_id_mm=inputs.discharge_pipe_id_mm,
            pipe_length_m=inputs.discharge_pipe_length_m,
            roughness_mm=inputs.discharge_roughness_mm,
            elevation_change_m=0.0,
            fitting_k_total=inputs.discharge_k_total,
        )
    )

    static_head_total_m = inputs.discharge_static_head_m - inputs.suction_static_head_m
    required_tdh_m = static_head_total_m + suction.head_loss_m + discharge.head_loss_m

    npsh_assumptions: list[str] = []
    if inputs.vapor_pressure_kpa_abs is None:
        npsha_calc = estimate_npsha(
            surface_pressure_value=inputs.surface_pressure_kpa_abs,
            surface_pressure_unit="kPaA",
            static_head_m=inputs.suction_static_head_m,
            suction_line_loss_m=suction.head_loss_m,
            liquid_temperature_c=inputs.liquid_temperature_c,
            velocity_m_s=suction.velocity_m_s,
            density_kg_m3=inputs.density_kg_m3,
        )
        npsha_m = npsha_calc.npsha_m
        npsh_assumptions.extend(npsha_calc.notes)
    else:
        pressure_head_m = inputs.surface_pressure_kpa_abs * 1000.0 / (inputs.density_kg_m3 * G)
        vapor_head_m = inputs.vapor_pressure_kpa_abs * 1000.0 / (inputs.density_kg_m3 * G)
        velocity_head_m = suction.velocity_m_s ** 2 / (2.0 * G)
        npsha_m = pressure_head_m + inputs.suction_static_head_m - suction.head_loss_m + velocity_head_m - vapor_head_m
        npsh_assumptions.append("NPSHa was calculated using entered vapor pressure instead of temperature-derived water vapor pressure.")

    assumed_npshr = False
    if inputs.required_npshr_m is None:
        npshr_m = max(1.5, 0.03 * required_tdh_m)
        assumed_npshr = True
    else:
        npshr_m = inputs.required_npshr_m

    npsh_margin_m = npsha_m - npshr_m
    npsh_margin_ratio = npsha_m / max(npshr_m, 1.0e-9)

    power = calculate_pump_power(
        flow_m3_h=inputs.flow_m3_h,
        total_dynamic_head_m=required_tdh_m,
        density_kg_m3=inputs.density_kg_m3,
        pump_efficiency_fraction=inputs.pump_efficiency_fraction,
    )
    motor_required_kw = power.brake_power_kw / max(inputs.motor_efficiency_fraction, 1.0e-9) * inputs.motor_service_factor
    recommended_motor_kw = _nearest_standard_motor_kw(motor_required_kw)
    recommended_motor_hp = recommended_motor_kw / 0.745699872

    curve_head_at_duty_m = None
    curve_head_margin_m = None
    estimated_bep_flow_m3_h = None
    duty_flow_fraction_of_bep = None

    if (
        inputs.curve_shutoff_head_m is not None
        and inputs.curve_max_flow_m3_h is not None
        and inputs.curve_head_at_max_flow_m is not None
        and inputs.curve_max_flow_m3_h > 0.0
    ):
        slope = (inputs.curve_head_at_max_flow_m - inputs.curve_shutoff_head_m) / inputs.curve_max_flow_m3_h
        curve_head_at_duty_m = inputs.curve_shutoff_head_m + slope * inputs.flow_m3_h
        curve_head_margin_m = curve_head_at_duty_m - required_tdh_m
        estimated_bep_flow_m3_h = 0.85 * inputs.curve_max_flow_m3_h
        duty_flow_fraction_of_bep = inputs.flow_m3_h / max(estimated_bep_flow_m3_h, 1.0e-9)

    warnings: list[str] = []
    assumptions: list[str] = []

    if inputs.suction_static_head_m < 0.0:
        lift_m = abs(inputs.suction_static_head_m)
        min_flooded_m = lift_m + (npshr_m if inputs.required_npshr_m is not None else 1.5)
        warnings.append(
            f"Suction lift of {lift_m:.2f} m is present. "
            f"Ensure the pump is self-priming or has a foot valve. "
            f"Raising the suction source by at least {min_flooded_m:.1f} m would eliminate the lift and improve NPSHa."
        )
    if suction.velocity_m_s > 1.8:
        # Recommend the pipe ID that would bring velocity to ~1.2 m/s
        target_area_m2 = (inputs.flow_m3_h / 3600.0) / 1.2
        target_id_mm = ((target_area_m2 / 3.14159265) ** 0.5) * 2000.0
        warnings.append(
            f"Suction velocity is {suction.velocity_m_s:.2f} m/s (target ≤ 1.8 m/s). "
            f"Increase the suction pipe diameter to at least {target_id_mm:.0f} mm ID "
            f"to bring velocity down to ~1.2 m/s and reduce NPSHa losses."
        )
    if discharge.velocity_m_s > 3.5:
        target_area_m2 = (inputs.flow_m3_h / 3600.0) / 2.5
        target_id_mm = ((target_area_m2 / 3.14159265) ** 0.5) * 2000.0
        warnings.append(
            f"Discharge velocity is {discharge.velocity_m_s:.2f} m/s (target ≤ 3.5 m/s). "
            f"Increase discharge pipe diameter to at least {target_id_mm:.0f} mm ID "
            f"to bring velocity down to ~2.5 m/s and reduce friction losses."
        )
    if npsh_margin_m < 0.0:
        additional_head_m = abs(npsh_margin_m) + 0.5
        warnings.append(
            f"NPSHa ({npsha_m:.2f} m) is {abs(npsh_margin_m):.2f} m below NPSHr ({npshr_m:.2f} m); cavitation is likely. "
            f"Recommended fixes: (1) raise the suction source level by at least {additional_head_m:.1f} m, "
            f"(2) increase suction pipe diameter to cut suction-line friction losses "
            f"(current loss: {suction.head_loss_m:.2f} m), or "
            f"(3) confirm with the vendor whether a lower-NPSHr impeller trim is available."
        )
    elif npsh_margin_ratio < inputs.minimum_npsh_margin_ratio:
        needed_npsha_m = npshr_m * inputs.minimum_npsh_margin_ratio
        shortfall_m = needed_npsha_m - npsha_m
        warnings.append(
            f"NPSH margin ratio is {npsh_margin_ratio:.2f}x (target ≥ {inputs.minimum_npsh_margin_ratio:.2f}x). "
            f"NPSHa needs to increase by {shortfall_m:.2f} m to meet the margin target. "
            f"Options: raise suction source level, increase suction pipe diameter "
            f"(current suction loss: {suction.head_loss_m:.2f} m), or reduce suction-line fittings."
        )

    if curve_head_margin_m is not None and curve_head_margin_m < 0.0:
        head_shortfall_m = abs(curve_head_margin_m)
        # Fraction of current shutoff head that would satisfy the duty
        required_shutoff_fraction = required_tdh_m / max(inputs.curve_shutoff_head_m or required_tdh_m, 1.0e-9)
        warnings.append(
            f"Pump curve head at duty flow is {abs(curve_head_at_duty_m):.2f} m, "
            f"which is {head_shortfall_m:.2f} m short of the required TDH ({required_tdh_m:.2f} m). "
            f"To resolve: (1) select a pump whose curve provides at least {required_tdh_m:.1f} m at "
            f"{inputs.flow_m3_h:.1f} m³/h duty flow, "
            f"(2) increase impeller diameter (higher shutoff and head throughout the curve), or "
            f"(3) reduce system head by enlarging the discharge pipe or reducing fittings "
            f"(current discharge loss: {discharge.head_loss_m:.2f} m)."
        )
    if duty_flow_fraction_of_bep is not None and (duty_flow_fraction_of_bep < 0.8 or duty_flow_fraction_of_bep > 1.1):
        bep_flow_m3_h = estimated_bep_flow_m3_h or 0.0
        if duty_flow_fraction_of_bep < 0.8:
            target_min_flow = 0.80 * bep_flow_m3_h
            target_max_flow = 1.10 * bep_flow_m3_h
            warnings.append(
                f"Duty flow ({inputs.flow_m3_h:.1f} m³/h) is only {duty_flow_fraction_of_bep * 100.0:.0f}% of estimated BEP "
                f"({bep_flow_m3_h:.1f} m³/h). The pump is oversized for this duty. "
                f"Recommended fixes: (1) select a smaller pump whose BEP is closer to {inputs.flow_m3_h:.1f} m³/h, "
                f"(2) trim the impeller to reduce BEP flow into the {target_min_flow:.1f}–{target_max_flow:.1f} m³/h range, or "
                f"(3) add a VFD to reduce speed and shift the BEP toward the operating point."
            )
        else:
            target_min_flow = 0.80 * bep_flow_m3_h
            target_max_flow = 1.10 * bep_flow_m3_h
            warnings.append(
                f"Duty flow ({inputs.flow_m3_h:.1f} m³/h) is {duty_flow_fraction_of_bep * 100.0:.0f}% of estimated BEP "
                f"({bep_flow_m3_h:.1f} m³/h). The pump is running past BEP (run-out). "
                f"Recommended fixes: (1) select a pump with a higher max-flow curve so BEP sits in the "
                f"{target_min_flow:.1f}–{target_max_flow:.1f} m³/h range, or "
                f"(2) increase impeller diameter to shift the BEP to a higher flow."
            )
    if required_tdh_m >= 0.95 * max(inputs.curve_shutoff_head_m or 0.0, 1.0e-9):
        margin_pct = (1.0 - required_tdh_m / max(inputs.curve_shutoff_head_m or required_tdh_m, 1.0e-9)) * 100.0
        min_shutoff_m = required_tdh_m / 0.85
        warnings.append(
            f"Required TDH ({required_tdh_m:.2f} m) is within {margin_pct:.1f}% of shutoff head "
            f"({inputs.curve_shutoff_head_m:.2f} m). At this operating point the pump is near dead-head. "
            f"Select a pump with a shutoff head of at least {min_shutoff_m:.1f} m "
            f"(current TDH should not exceed ~85% of shutoff head)."
        )

    if assumed_npshr:
        assumptions.append("NPSHr was not provided. Preliminary estimate used NPSHr = max(1.5 m, 3% of TDH).")
    if inputs.curve_shutoff_head_m is None:
        assumptions.append("No pump curve provided; operating-point/BEP checks were not performed.")

    if inputs.base_speed_rpm and inputs.new_speed_rpm and inputs.base_speed_rpm > 0.0:
        speed_ratio = inputs.new_speed_rpm / inputs.base_speed_rpm
        assumptions.append(
            f"Speed affinity screen ratio N2/N1 = {speed_ratio:.3f} (flow ~N, head ~N^2, power ~N^3)."
        )
    if (
        inputs.base_impeller_diameter_m
        and inputs.new_impeller_diameter_m
        and inputs.base_impeller_diameter_m > 0.0
    ):
        impeller_ratio = inputs.new_impeller_diameter_m / inputs.base_impeller_diameter_m
        assumptions.append(
            f"Impeller affinity screen ratio D2/D1 = {impeller_ratio:.3f} (flow ~D, head ~D^2, power ~D^3)."
        )

    assumptions.extend(npsh_assumptions)
    assumptions.extend(power.notes)

    return PumpSizingResult(
        required_flow_m3_h=inputs.flow_m3_h,
        required_tdh_m=required_tdh_m,
        static_head_total_m=static_head_total_m,
        suction_line_loss_m=suction.head_loss_m,
        discharge_line_loss_m=discharge.head_loss_m,
        suction_velocity_m_s=suction.velocity_m_s,
        discharge_velocity_m_s=discharge.velocity_m_s,
        npsha_m=npsha_m,
        npshr_m=npshr_m,
        npsh_margin_m=npsh_margin_m,
        npsh_margin_ratio=npsh_margin_ratio,
        hydraulic_power_kw=power.hydraulic_power_kw,
        brake_power_kw=power.brake_power_kw,
        brake_horsepower_hp=power.brake_horsepower_hp,
        motor_required_kw=motor_required_kw,
        recommended_motor_kw=recommended_motor_kw,
        recommended_motor_hp=recommended_motor_hp,
        curve_head_at_duty_m=curve_head_at_duty_m,
        curve_head_margin_m=curve_head_margin_m,
        estimated_bep_flow_m3_h=estimated_bep_flow_m3_h,
        duty_flow_fraction_of_bep=duty_flow_fraction_of_bep,
        warnings=warnings,
        assumptions=assumptions,
    )
