"""Hydraulics and pipe-flow helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math

from engineering_app.core.pipe_data import get_common_fittings_map, get_schedule_10s_map
from engineering_app.core.units import length_to_m, pressure_to_kpa_abs, volumetric_flow_to_m3_h

G = 9.80665
PSI_PER_KPA = 0.1450377377
GPM_PER_M3_H = 4.4028675


@dataclass
class HydraulicInputs:
    volumetric_flow_m3_h: float
    density_kg_m3: float
    viscosity_cp: float
    pipe_id_mm: float
    pipe_length_m: float
    roughness_mm: float = 0.045
    elevation_change_m: float = 0.0
    fitting_k_total: float = 0.0


@dataclass
class HydraulicResult:
    velocity_m_s: float
    reynolds_number: float
    friction_factor: float
    pressure_drop_kpa: float
    head_loss_m: float
    total_dynamic_head_m: float
    residence_time_s: float
    line_volume_m3: float
    straight_loss_m: float
    fitting_loss_m: float
    notes: list[str]


@dataclass
class HydraulicComparisonRow:
    pipe_label: str
    pipe_id_mm: float
    velocity_m_s: float
    pressure_drop_kpa: float
    total_dynamic_head_m: float
    residence_time_s: float
    acceptable_velocity: bool


@dataclass
class PumpPowerResult:
    hydraulic_power_kw: float
    brake_power_kw: float
    brake_horsepower_hp: float
    notes: list[str]


@dataclass
class NPSHAResult:
    surface_pressure_kpa_abs: float
    vapor_pressure_kpa_abs: float
    static_head_m: float
    suction_line_loss_m: float
    velocity_head_m: float
    npsha_m: float
    notes: list[str]


@dataclass
class PipeSegment:
    name: str
    pipe_id_mm: float
    pipe_length_m: float
    roughness_mm: float = 0.045
    elevation_change_m: float = 0.0
    fitting_k_total: float = 0.0


@dataclass
class SegmentResult:
    name: str
    pressure_drop_kpa: float
    head_loss_m: float
    total_dynamic_head_m: float
    velocity_m_s: float
    notes: list[str]


@dataclass
class SegmentedSystemResult:
    segments: list[SegmentResult]
    total_pressure_drop_kpa: float
    total_head_loss_m: float
    total_dynamic_head_m: float
    notes: list[str]


@dataclass
class LineSizeRecommendation:
    pipe_label: str
    velocity_m_s: float
    pressure_drop_kpa: float
    total_dynamic_head_m: float
    reason: str


@dataclass
class ControlValveSizingResult:
    flow_m3_h: float
    flow_gpm: float
    differential_pressure_kpa: float
    differential_pressure_bar: float
    differential_pressure_psi: float
    specific_gravity: float
    required_kv: float
    required_cv: float
    valve_authority: float | None
    rated_cv: float | None
    rated_kv: float | None
    opening_fraction_linear: float | None
    opening_fraction_equal_percentage: float | None
    inlet_pressure_kpa_abs: float | None
    outlet_pressure_kpa_abs: float | None
    liquid_temperature_c: float | None
    vapor_pressure_kpa_abs: float | None
    pressure_recovery_factor_fl: float | None
    predicted_vena_contracta_pressure_kpa_abs: float | None
    liquid_critical_pressure_drop_kpa: float | None
    cavitation_index_sigma: float | None
    cavitation_status: str | None
    outlet_flashing_expected: bool | None
    notes: list[str]


@dataclass
class SystemCurvePoint:
    flow_m3_h: float
    total_dynamic_head_m: float


def _friction_factor_swamee_jain(reynolds_number: float, roughness_m: float, diameter_m: float) -> float:
    if reynolds_number <= 0:
        raise ValueError("Reynolds number must be positive")
    if reynolds_number < 2000:
        return 64.0 / reynolds_number
    return 0.25 / (math.log10(roughness_m / (3.7 * diameter_m) + 5.74 / (reynolds_number ** 0.9)) ** 2)


def _water_vapor_pressure_kpa_abs(temperature_c: float) -> float:
    return 0.611 * math.exp((17.27 * temperature_c) / (temperature_c + 237.3))


def calculate_hydraulics(inputs: HydraulicInputs) -> HydraulicResult:
    q_m3_s = inputs.volumetric_flow_m3_h / 3600.0
    diameter_m = inputs.pipe_id_mm / 1000.0
    area_m2 = math.pi * (diameter_m ** 2) / 4.0
    velocity = q_m3_s / area_m2
    viscosity_pa_s = inputs.viscosity_cp / 1000.0
    reynolds = inputs.density_kg_m3 * velocity * diameter_m / max(viscosity_pa_s, 1e-12)
    friction_factor = _friction_factor_swamee_jain(reynolds, inputs.roughness_mm / 1000.0, diameter_m)

    straight_loss_m = friction_factor * (inputs.pipe_length_m / diameter_m) * (velocity ** 2) / (2.0 * G)
    fitting_loss_m = inputs.fitting_k_total * (velocity ** 2) / (2.0 * G)
    total_head_loss = straight_loss_m + fitting_loss_m
    pressure_drop_kpa = total_head_loss * inputs.density_kg_m3 * G / 1000.0
    tdh = total_head_loss + inputs.elevation_change_m
    line_volume_m3 = area_m2 * inputs.pipe_length_m
    residence_time_s = line_volume_m3 / max(q_m3_s, 1e-12)

    notes: list[str] = []
    if velocity > 3.0:
        notes.append("Velocity is relatively high for many liquid services.")
    if velocity < 1.0:
        notes.append("Velocity is relatively low; solids settling or poor scouring may matter in some services.")
    if reynolds < 4000:
        notes.append("Flow may be transitional/laminar; review friction-factor assumptions.")

    return HydraulicResult(
        velocity_m_s=velocity,
        reynolds_number=reynolds,
        friction_factor=friction_factor,
        pressure_drop_kpa=pressure_drop_kpa,
        head_loss_m=total_head_loss,
        total_dynamic_head_m=tdh,
        residence_time_s=residence_time_s,
        line_volume_m3=line_volume_m3,
        straight_loss_m=straight_loss_m,
        fitting_loss_m=fitting_loss_m,
        notes=notes,
    )


def calculate_hydraulics_with_units(
    volumetric_flow_value: float,
    volumetric_flow_unit: str,
    density_kg_m3: float,
    viscosity_cp: float,
    pipe_id_value: float,
    pipe_id_unit: str,
    pipe_length_value: float,
    pipe_length_unit: str,
    roughness_mm: float = 0.045,
    elevation_change_value: float = 0.0,
    elevation_change_unit: str = "m",
    fitting_k_total: float = 0.0,
) -> HydraulicResult:
    return calculate_hydraulics(
        HydraulicInputs(
            volumetric_flow_m3_h=volumetric_flow_to_m3_h(volumetric_flow_value, volumetric_flow_unit),
            density_kg_m3=density_kg_m3,
            viscosity_cp=viscosity_cp,
            pipe_id_mm=length_to_m(pipe_id_value, pipe_id_unit) * 1000.0,
            pipe_length_m=length_to_m(pipe_length_value, pipe_length_unit),
            roughness_mm=roughness_mm,
            elevation_change_m=length_to_m(elevation_change_value, elevation_change_unit),
            fitting_k_total=fitting_k_total,
        )
    )


def fitting_k_from_counts(counts: dict[str, int | float]) -> tuple[float, list[str]]:
    library = get_common_fittings_map()
    total_k = 0.0
    notes: list[str] = []
    for key, count in counts.items():
        if not count:
            continue
        spec = library.get(key)
        if spec is None:
            notes.append(f"Unknown fitting key ignored: {key}")
            continue
        total_k += spec.k_value * float(count)
    return total_k, notes


def get_schedule_10s_pipe_options() -> dict[str, float]:
    return {label: spec.inside_diameter_in * 25.4 for label, spec in get_schedule_10s_map().items()}


def compare_schedule_10s_sizes(
    volumetric_flow_value: float,
    volumetric_flow_unit: str,
    density_kg_m3: float,
    viscosity_cp: float,
    pipe_length_value: float,
    pipe_length_unit: str,
    roughness_mm: float = 0.045,
    elevation_change_value: float = 0.0,
    elevation_change_unit: str = "m",
    fitting_k_total: float = 0.0,
) -> list[HydraulicComparisonRow]:
    rows: list[HydraulicComparisonRow] = []
    for label, pipe_id_mm in get_schedule_10s_pipe_options().items():
        result = calculate_hydraulics_with_units(
            volumetric_flow_value=volumetric_flow_value,
            volumetric_flow_unit=volumetric_flow_unit,
            density_kg_m3=density_kg_m3,
            viscosity_cp=viscosity_cp,
            pipe_id_value=pipe_id_mm,
            pipe_id_unit="mm",
            pipe_length_value=pipe_length_value,
            pipe_length_unit=pipe_length_unit,
            roughness_mm=roughness_mm,
            elevation_change_value=elevation_change_value,
            elevation_change_unit=elevation_change_unit,
            fitting_k_total=fitting_k_total,
        )
        rows.append(
            HydraulicComparisonRow(
                pipe_label=label,
                pipe_id_mm=pipe_id_mm,
                velocity_m_s=result.velocity_m_s,
                pressure_drop_kpa=result.pressure_drop_kpa,
                total_dynamic_head_m=result.total_dynamic_head_m,
                residence_time_s=result.residence_time_s,
                acceptable_velocity=1.0 <= result.velocity_m_s <= 3.0,
            )
        )
    return rows


def recommend_schedule_10s_size(rows: list[HydraulicComparisonRow]) -> LineSizeRecommendation | None:
    preferred = [row for row in rows if row.acceptable_velocity]
    candidate = min(preferred or rows, key=lambda row: row.total_dynamic_head_m)
    reason = "Within 1-3 m/s preferred velocity band with lowest TDH." if candidate.acceptable_velocity else "No size landed in the preferred velocity band; selected lowest TDH option."
    return LineSizeRecommendation(
        pipe_label=candidate.pipe_label,
        velocity_m_s=candidate.velocity_m_s,
        pressure_drop_kpa=candidate.pressure_drop_kpa,
        total_dynamic_head_m=candidate.total_dynamic_head_m,
        reason=reason,
    )


def calculate_pump_power(flow_m3_h: float, total_dynamic_head_m: float, density_kg_m3: float = 1000.0, pump_efficiency_fraction: float = 0.70) -> PumpPowerResult:
    q_m3_s = flow_m3_h / 3600.0
    hydraulic_power_kw = density_kg_m3 * G * q_m3_s * total_dynamic_head_m / 1000.0
    brake_power_kw = hydraulic_power_kw / max(pump_efficiency_fraction, 1e-9)
    notes = ["Pump power is based on hydraulic power divided by entered pump efficiency."]
    if pump_efficiency_fraction < 0.5:
        notes.append("Low pump efficiency entered; verify if this is intentional.")
    return PumpPowerResult(
        hydraulic_power_kw=hydraulic_power_kw,
        brake_power_kw=brake_power_kw,
        brake_horsepower_hp=brake_power_kw / 0.745699872,
        notes=notes,
    )


def estimate_npsha(
    surface_pressure_value: float,
    surface_pressure_unit: str,
    static_head_m: float,
    suction_line_loss_m: float,
    liquid_temperature_c: float,
    velocity_m_s: float,
    density_kg_m3: float = 1000.0,
) -> NPSHAResult:
    surface_pressure_kpa_abs = pressure_to_kpa_abs(surface_pressure_value, surface_pressure_unit)
    vapor_pressure_kpa_abs = _water_vapor_pressure_kpa_abs(liquid_temperature_c)
    pressure_head_m = surface_pressure_kpa_abs * 1000.0 / (density_kg_m3 * G)
    vapor_head_m = vapor_pressure_kpa_abs * 1000.0 / (density_kg_m3 * G)
    velocity_head_m = velocity_m_s ** 2 / (2.0 * G)
    npsha_m = pressure_head_m + static_head_m - suction_line_loss_m + velocity_head_m - vapor_head_m
    notes = ["NPSHa is estimated from surface pressure head + static head - suction loss + velocity head - vapor pressure head."]
    if npsha_m < 1.0:
        notes.append("Very low NPSHa; cavitation risk may be severe.")
    if liquid_temperature_c > 80.0:
        notes.append("Elevated liquid temperature materially increases vapor-pressure risk.")
    return NPSHAResult(
        surface_pressure_kpa_abs=surface_pressure_kpa_abs,
        vapor_pressure_kpa_abs=vapor_pressure_kpa_abs,
        static_head_m=static_head_m,
        suction_line_loss_m=suction_line_loss_m,
        velocity_head_m=velocity_head_m,
        npsha_m=npsha_m,
        notes=notes,
    )


def calculate_segmented_system(
    flow_m3_h: float,
    density_kg_m3: float,
    viscosity_cp: float,
    segments: list[PipeSegment],
) -> SegmentedSystemResult:
    segment_results: list[SegmentResult] = []
    notes: list[str] = []
    total_pressure_drop = 0.0
    total_head_loss = 0.0
    total_tdh = 0.0
    for segment in segments:
        result = calculate_hydraulics(
            HydraulicInputs(
                volumetric_flow_m3_h=flow_m3_h,
                density_kg_m3=density_kg_m3,
                viscosity_cp=viscosity_cp,
                pipe_id_mm=segment.pipe_id_mm,
                pipe_length_m=segment.pipe_length_m,
                roughness_mm=segment.roughness_mm,
                elevation_change_m=segment.elevation_change_m,
                fitting_k_total=segment.fitting_k_total,
            )
        )
        segment_results.append(
            SegmentResult(
                name=segment.name,
                pressure_drop_kpa=result.pressure_drop_kpa,
                head_loss_m=result.head_loss_m,
                total_dynamic_head_m=result.total_dynamic_head_m,
                velocity_m_s=result.velocity_m_s,
                notes=result.notes,
            )
        )
        total_pressure_drop += result.pressure_drop_kpa
        total_head_loss += result.head_loss_m
        total_tdh += result.total_dynamic_head_m
    if len(segment_results) > 1:
        notes.append("Segmented result sums friction and elevation across each entered section.")
    return SegmentedSystemResult(
        segments=segment_results,
        total_pressure_drop_kpa=total_pressure_drop,
        total_head_loss_m=total_head_loss,
        total_dynamic_head_m=total_tdh,
        notes=notes,
    )


def size_control_valve(
    flow_m3_h: float,
    differential_pressure_kpa: float,
    density_kg_m3: float,
    installed_pressure_drop_kpa: float | None = None,
    rated_cv: float | None = None,
    equal_percentage_rangeability: float = 50.0,
    inlet_pressure_value: float | None = None,
    inlet_pressure_unit: str = "kPa",
    liquid_temperature_c: float | None = None,
    pressure_recovery_factor_fl: float | None = None,
) -> ControlValveSizingResult:
    if differential_pressure_kpa <= 0:
        raise ValueError("Valve differential pressure must be positive.")
    specific_gravity = density_kg_m3 / 1000.0
    if specific_gravity <= 0:
        raise ValueError("Density / specific gravity must be positive.")
    if pressure_recovery_factor_fl is not None and not (0.0 < pressure_recovery_factor_fl <= 1.0):
        raise ValueError("Pressure recovery factor FL must be between 0 and 1.")

    flow_gpm = flow_m3_h * GPM_PER_M3_H
    differential_pressure_psi = differential_pressure_kpa * PSI_PER_KPA
    required_cv = flow_gpm * math.sqrt(specific_gravity / differential_pressure_psi)
    required_kv = flow_m3_h * math.sqrt(specific_gravity / (differential_pressure_kpa / 100.0))

    valve_authority = None
    rated_kv = None
    opening_linear = None
    opening_equal_percentage = None
    inlet_pressure_kpa_abs = None
    outlet_pressure_kpa_abs = None
    vapor_pressure_kpa_abs = None
    predicted_vena_contracta_pressure_kpa_abs = None
    liquid_critical_pressure_drop_kpa = None
    cavitation_index_sigma = None
    cavitation_status = None
    outlet_flashing_expected = None
    notes = [
        "Liquid control-valve sizing uses the standard screening relationship Kv = Q × sqrt(SG / ΔPbar); Cv is reported in US gpm/psi form.",
        "Cavitation/flashing checks are screening estimates only; confirm with vendor liquid-pressure-recovery data before final valve selection.",
    ]

    if installed_pressure_drop_kpa is not None and installed_pressure_drop_kpa >= 0:
        denominator = differential_pressure_kpa + installed_pressure_drop_kpa
        valve_authority = differential_pressure_kpa / denominator if denominator > 0 else None
        if valve_authority is not None:
            if valve_authority < 0.25:
                notes.append("Valve authority is low; controllability may be poor unless more ΔP is assigned to the valve.")
            elif valve_authority > 0.80:
                notes.append("Valve takes most of the available drop; verify pump head and turndown flexibility.")

    if rated_cv is not None:
        if rated_cv <= 0:
            raise ValueError("Rated Cv must be positive when provided.")
        if equal_percentage_rangeability <= 1.0:
            raise ValueError("Equal-percentage rangeability must be greater than 1.")
        rated_kv = rated_cv / 1.1560992283536566
        ratio = required_cv / rated_cv
        opening_linear = ratio
        opening_equal_percentage = math.log(1.0 + max(ratio, 0.0) * (equal_percentage_rangeability - 1.0)) / math.log(equal_percentage_rangeability)
        if ratio > 1.0:
            notes.append("Required Cv exceeds entered rated Cv; the valve would be undersized at the chosen ΔP.")
        elif ratio < 0.1:
            notes.append("Required Cv is well below the rated Cv; low-opening control stability may be weak.")

    if inlet_pressure_value is not None:
        inlet_pressure_kpa_abs = pressure_to_kpa_abs(inlet_pressure_value, inlet_pressure_unit)
        outlet_pressure_kpa_abs = inlet_pressure_kpa_abs - differential_pressure_kpa
        if outlet_pressure_kpa_abs <= 0.0:
            notes.append("Outlet pressure fell to zero/negative absolute pressure in the screen; recheck inlet pressure basis and valve ΔP.")
        if liquid_temperature_c is not None:
            vapor_pressure_kpa_abs = _water_vapor_pressure_kpa_abs(liquid_temperature_c)
            cavitation_index_sigma = (inlet_pressure_kpa_abs - vapor_pressure_kpa_abs) / max(differential_pressure_kpa, 1e-9)
            outlet_flashing_expected = outlet_pressure_kpa_abs <= vapor_pressure_kpa_abs
            if pressure_recovery_factor_fl is not None:
                liquid_critical_pressure_drop_kpa = max((pressure_recovery_factor_fl ** 2) * (inlet_pressure_kpa_abs - vapor_pressure_kpa_abs), 0.0)
                predicted_vena_contracta_pressure_kpa_abs = inlet_pressure_kpa_abs - differential_pressure_kpa / max(pressure_recovery_factor_fl ** 2, 1e-9)
            if outlet_flashing_expected:
                cavitation_status = "flashing_expected"
                notes.append("Estimated valve outlet pressure is at/below the liquid vapor pressure; flashing is expected downstream of the trim.")
            elif liquid_critical_pressure_drop_kpa is not None and differential_pressure_kpa >= liquid_critical_pressure_drop_kpa:
                cavitation_status = "critical_cavitation_risk"
                notes.append("Entered valve ΔP meets/exceeds the FL-based liquid critical drop screen; severe cavitation or choked-liquid behavior is likely.")
            elif cavitation_index_sigma <= 1.5:
                cavitation_status = "high_cavitation_risk"
                notes.append("Low cavitation index indicates high cavitation risk; hot liquid, low outlet pressure, or a higher-recovery trim would worsen this case.")
            elif cavitation_index_sigma <= 2.0:
                cavitation_status = "moderate_cavitation_risk"
                notes.append("Cavitation index is in a watch range; check valve style, trim, noise, and vendor recovery-factor data.")
            else:
                cavitation_status = "low_cavitation_risk"
                notes.append("Outlet pressure remains comfortably above vapor pressure in this screening check, so cavitation risk appears lower.")
            notes.append("Heuristic cavitation index uses σ = (P1 - Pv) / (P1 - P2) on an absolute-pressure basis.")
        elif inlet_pressure_kpa_abs is not None:
            notes.append("Add liquid temperature to enable vapor-pressure, flashing, and cavitation-risk screening.")
    elif liquid_temperature_c is not None:
        notes.append("Add inlet pressure to enable outlet-pressure, flashing, and cavitation-risk screening.")

    return ControlValveSizingResult(
        flow_m3_h=flow_m3_h,
        flow_gpm=flow_gpm,
        differential_pressure_kpa=differential_pressure_kpa,
        differential_pressure_bar=differential_pressure_kpa / 100.0,
        differential_pressure_psi=differential_pressure_psi,
        specific_gravity=specific_gravity,
        required_kv=required_kv,
        required_cv=required_cv,
        valve_authority=valve_authority,
        rated_cv=rated_cv,
        rated_kv=rated_kv,
        opening_fraction_linear=opening_linear,
        opening_fraction_equal_percentage=opening_equal_percentage,
        inlet_pressure_kpa_abs=inlet_pressure_kpa_abs,
        outlet_pressure_kpa_abs=outlet_pressure_kpa_abs,
        liquid_temperature_c=liquid_temperature_c,
        vapor_pressure_kpa_abs=vapor_pressure_kpa_abs,
        pressure_recovery_factor_fl=pressure_recovery_factor_fl,
        predicted_vena_contracta_pressure_kpa_abs=predicted_vena_contracta_pressure_kpa_abs,
        liquid_critical_pressure_drop_kpa=liquid_critical_pressure_drop_kpa,
        cavitation_index_sigma=cavitation_index_sigma,
        cavitation_status=cavitation_status,
        outlet_flashing_expected=outlet_flashing_expected,
        notes=notes,
    )


def build_system_curve(
    static_head_m: float,
    k_factor_m_per_m3h2: float,
    max_flow_m3_h: float,
    point_count: int = 20,
) -> list[SystemCurvePoint]:
    if max_flow_m3_h <= 0:
        raise ValueError("Maximum flow must be positive")
    points: list[SystemCurvePoint] = []
    for index in range(point_count + 1):
        flow = max_flow_m3_h * index / point_count
        head = static_head_m + k_factor_m_per_m3h2 * flow * flow
        points.append(SystemCurvePoint(flow_m3_h=flow, total_dynamic_head_m=head))
    return points


def find_pump_system_intersection(
    shutoff_head_m: float,
    head_at_max_flow_m: float,
    max_flow_m3_h: float,
    static_head_m: float,
    k_factor_m_per_m3h2: float,
) -> SystemCurvePoint | None:
    if max_flow_m3_h <= 0:
        return None
    pump_slope = (head_at_max_flow_m - shutoff_head_m) / max_flow_m3_h
    best_point = None
    best_error = None
    for step in range(1001):
        flow = max_flow_m3_h * step / 1000.0
        pump_head = shutoff_head_m + pump_slope * flow
        system_head = static_head_m + k_factor_m_per_m3h2 * flow * flow
        error = abs(pump_head - system_head)
        if best_error is None or error < best_error:
            best_error = error
            best_point = SystemCurvePoint(flow_m3_h=flow, total_dynamic_head_m=system_head)
    return best_point
