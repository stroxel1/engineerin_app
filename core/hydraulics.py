"""Hydraulics and pipe-flow helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math

from engineering_app.core.pipe_data import get_common_fittings_map, get_schedule_10s_map
from engineering_app.core.units import length_to_m, volumetric_flow_to_m3_h


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


def _friction_factor_swamee_jain(reynolds_number: float, roughness_m: float, diameter_m: float) -> float:
    if reynolds_number <= 0:
        raise ValueError("Reynolds number must be positive")
    if reynolds_number < 2000:
        return 64.0 / reynolds_number
    return 0.25 / (math.log10(roughness_m / (3.7 * diameter_m) + 5.74 / (reynolds_number ** 0.9)) ** 2)


def calculate_hydraulics(inputs: HydraulicInputs) -> HydraulicResult:
    q_m3_s = inputs.volumetric_flow_m3_h / 3600.0
    diameter_m = inputs.pipe_id_mm / 1000.0
    area_m2 = math.pi * (diameter_m ** 2) / 4.0
    velocity = q_m3_s / area_m2
    viscosity_pa_s = inputs.viscosity_cp / 1000.0
    reynolds = inputs.density_kg_m3 * velocity * diameter_m / max(viscosity_pa_s, 1e-12)
    friction_factor = _friction_factor_swamee_jain(reynolds, inputs.roughness_mm / 1000.0, diameter_m)

    straight_loss_m = friction_factor * (inputs.pipe_length_m / diameter_m) * (velocity ** 2) / (2.0 * 9.80665)
    fitting_loss_m = inputs.fitting_k_total * (velocity ** 2) / (2.0 * 9.80665)
    total_head_loss = straight_loss_m + fitting_loss_m
    pressure_drop_kpa = total_head_loss * inputs.density_kg_m3 * 9.80665 / 1000.0
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
