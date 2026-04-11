"""Tank inventory and hold-up helpers for practical plant work."""

from __future__ import annotations

from dataclasses import dataclass
import math

from engineering_app.core.units import density_to_kg_m3, length_to_m, m3_h_to_volumetric_flow, volume_to_m3, volumetric_flow_to_m3_h


@dataclass
class TankInventoryResult:
    tank_type: str
    total_volume_m3: float
    liquid_volume_m3: float
    available_ullage_m3: float
    fill_fraction: float
    liquid_level_m: float
    liquid_mass_kg: float | None
    residence_time_h: float | None
    pump_out_time_h: float | None
    notes: list[str]


@dataclass
class VerticalCylindricalTankInputs:
    diameter_m: float
    straight_side_height_m: float
    liquid_level_m: float


@dataclass
class HorizontalCylindricalTankInputs:
    diameter_m: float
    straight_length_m: float
    liquid_level_m: float


@dataclass
class RectangularTankInputs:
    length_m: float
    width_m: float
    straight_side_height_m: float
    liquid_level_m: float


def _clamp_level(level_m: float, max_height_m: float) -> tuple[float, list[str]]:
    notes: list[str] = []
    clamped = max(0.0, min(level_m, max_height_m))
    if level_m < 0.0:
        notes.append("Liquid level below zero was clamped to 0.")
    if level_m > max_height_m:
        notes.append("Liquid level exceeded the entered tank height and was clamped to the maximum straight-side height.")
    return clamped, notes


def _add_common_notes(fill_fraction: float, transfer_rate_m3_h: float | None) -> list[str]:
    notes = []
    if fill_fraction < 0.1:
        notes.append("Tank is below 10% full; outlet vortexing, heel management, or level-instrument deadband may matter.")
    if fill_fraction > 0.9:
        notes.append("Tank is above 90% full; check freeboard, high-level alarm margin, and overflow routing.")
    if transfer_rate_m3_h is not None and transfer_rate_m3_h <= 0.0:
        notes.append("Transfer rate must be above zero to calculate residence or pump-out time.")
    return notes


def _finalize_result(
    tank_type: str,
    total_volume_m3: float,
    liquid_volume_m3: float,
    liquid_level_m: float,
    density_kg_m3: float | None,
    transfer_rate_m3_h: float | None,
    notes: list[str],
) -> TankInventoryResult:
    fill_fraction = liquid_volume_m3 / total_volume_m3 if total_volume_m3 > 0.0 else 0.0
    liquid_mass_kg = liquid_volume_m3 * density_kg_m3 if density_kg_m3 is not None else None
    residence_time_h = None
    pump_out_time_h = None
    if transfer_rate_m3_h is not None and transfer_rate_m3_h > 0.0:
        residence_time_h = liquid_volume_m3 / transfer_rate_m3_h
        pump_out_time_h = liquid_volume_m3 / transfer_rate_m3_h
    notes.extend(_add_common_notes(fill_fraction, transfer_rate_m3_h))
    return TankInventoryResult(
        tank_type=tank_type,
        total_volume_m3=total_volume_m3,
        liquid_volume_m3=liquid_volume_m3,
        available_ullage_m3=max(total_volume_m3 - liquid_volume_m3, 0.0),
        fill_fraction=fill_fraction,
        liquid_level_m=liquid_level_m,
        liquid_mass_kg=liquid_mass_kg,
        residence_time_h=residence_time_h,
        pump_out_time_h=pump_out_time_h,
        notes=notes,
    )


def estimate_vertical_cylindrical_tank_inventory(
    inputs: VerticalCylindricalTankInputs,
    density_kg_m3: float | None = None,
    transfer_rate_m3_h: float | None = None,
) -> TankInventoryResult:
    if inputs.diameter_m <= 0.0:
        raise ValueError("Tank diameter must be above zero.")
    if inputs.straight_side_height_m <= 0.0:
        raise ValueError("Tank straight-side height must be above zero.")
    level_m, notes = _clamp_level(inputs.liquid_level_m, inputs.straight_side_height_m)
    radius_m = inputs.diameter_m / 2.0
    cross_section_m2 = math.pi * radius_m * radius_m
    total_volume_m3 = cross_section_m2 * inputs.straight_side_height_m
    liquid_volume_m3 = cross_section_m2 * level_m
    return _finalize_result("vertical_cylindrical", total_volume_m3, liquid_volume_m3, level_m, density_kg_m3, transfer_rate_m3_h, notes)


def _horizontal_cylinder_segment_area(radius_m: float, level_m: float) -> float:
    if level_m <= 0.0:
        return 0.0
    if level_m >= 2.0 * radius_m:
        return math.pi * radius_m * radius_m
    return radius_m * radius_m * math.acos((radius_m - level_m) / radius_m) - (radius_m - level_m) * math.sqrt(max(2.0 * radius_m * level_m - level_m * level_m, 0.0))


def estimate_horizontal_cylindrical_tank_inventory(
    inputs: HorizontalCylindricalTankInputs,
    density_kg_m3: float | None = None,
    transfer_rate_m3_h: float | None = None,
) -> TankInventoryResult:
    if inputs.diameter_m <= 0.0:
        raise ValueError("Tank diameter must be above zero.")
    if inputs.straight_length_m <= 0.0:
        raise ValueError("Tank straight length must be above zero.")
    level_m, notes = _clamp_level(inputs.liquid_level_m, inputs.diameter_m)
    radius_m = inputs.diameter_m / 2.0
    cross_section_m2 = math.pi * radius_m * radius_m
    total_volume_m3 = cross_section_m2 * inputs.straight_length_m
    liquid_area_m2 = _horizontal_cylinder_segment_area(radius_m, level_m)
    liquid_volume_m3 = liquid_area_m2 * inputs.straight_length_m
    notes.append("Horizontal-cylinder volume is based on a straight shell with no head-volume allowance.")
    return _finalize_result("horizontal_cylindrical", total_volume_m3, liquid_volume_m3, level_m, density_kg_m3, transfer_rate_m3_h, notes)


def estimate_rectangular_tank_inventory(
    inputs: RectangularTankInputs,
    density_kg_m3: float | None = None,
    transfer_rate_m3_h: float | None = None,
) -> TankInventoryResult:
    if inputs.length_m <= 0.0 or inputs.width_m <= 0.0:
        raise ValueError("Tank length and width must be above zero.")
    if inputs.straight_side_height_m <= 0.0:
        raise ValueError("Tank straight-side height must be above zero.")
    level_m, notes = _clamp_level(inputs.liquid_level_m, inputs.straight_side_height_m)
    total_volume_m3 = inputs.length_m * inputs.width_m * inputs.straight_side_height_m
    liquid_volume_m3 = inputs.length_m * inputs.width_m * level_m
    return _finalize_result("rectangular", total_volume_m3, liquid_volume_m3, level_m, density_kg_m3, transfer_rate_m3_h, notes)


def estimate_tank_inventory_with_units(
    tank_type: str,
    dimensions: dict[str, float],
    dimension_units: dict[str, str],
    liquid_level_value: float,
    liquid_level_unit: str,
    density_value: float | None = None,
    density_unit: str = "kg/m3",
    transfer_rate_value: float | None = None,
    transfer_rate_unit: str = "m3/h",
) -> TankInventoryResult:
    density_kg_m3 = density_to_kg_m3(density_value, density_unit) if density_value is not None else None
    transfer_rate_m3_h = volumetric_flow_to_m3_h(transfer_rate_value, transfer_rate_unit) if transfer_rate_value is not None else None

    if tank_type == "vertical_cylindrical":
        return estimate_vertical_cylindrical_tank_inventory(
            VerticalCylindricalTankInputs(
                diameter_m=length_to_m(dimensions["diameter"], dimension_units["diameter"]),
                straight_side_height_m=length_to_m(dimensions["height"], dimension_units["height"]),
                liquid_level_m=length_to_m(liquid_level_value, liquid_level_unit),
            ),
            density_kg_m3=density_kg_m3,
            transfer_rate_m3_h=transfer_rate_m3_h,
        )
    if tank_type == "horizontal_cylindrical":
        return estimate_horizontal_cylindrical_tank_inventory(
            HorizontalCylindricalTankInputs(
                diameter_m=length_to_m(dimensions["diameter"], dimension_units["diameter"]),
                straight_length_m=length_to_m(dimensions["length"], dimension_units["length"]),
                liquid_level_m=length_to_m(liquid_level_value, liquid_level_unit),
            ),
            density_kg_m3=density_kg_m3,
            transfer_rate_m3_h=transfer_rate_m3_h,
        )
    if tank_type == "rectangular":
        return estimate_rectangular_tank_inventory(
            RectangularTankInputs(
                length_m=length_to_m(dimensions["length"], dimension_units["length"]),
                width_m=length_to_m(dimensions["width"], dimension_units["width"]),
                straight_side_height_m=length_to_m(dimensions["height"], dimension_units["height"]),
                liquid_level_m=length_to_m(liquid_level_value, liquid_level_unit),
            ),
            density_kg_m3=density_kg_m3,
            transfer_rate_m3_h=transfer_rate_m3_h,
        )
    raise ValueError(f"Unsupported tank type: {tank_type}")


__all__ = [
    "HorizontalCylindricalTankInputs",
    "RectangularTankInputs",
    "TankInventoryResult",
    "VerticalCylindricalTankInputs",
    "estimate_horizontal_cylindrical_tank_inventory",
    "estimate_rectangular_tank_inventory",
    "estimate_tank_inventory_with_units",
    "estimate_vertical_cylindrical_tank_inventory",
    "m3_h_to_volumetric_flow",
    "volume_to_m3",
]
