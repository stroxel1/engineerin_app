"""Practical crystallizer helpers for quick plant engineering checks."""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.units import mass_flow_to_kg_h, volume_to_m3


@dataclass
class CrystallizerInputs:
    feed_rate_value: float
    feed_rate_unit: str
    feed_solids_wt_pct: float
    mother_liquor_solids_wt_pct: float
    target_slurry_solids_wt_pct: float
    circulation_rate_value: float = 0.0
    circulation_rate_unit: str = "kg/h"
    working_volume_value: float = 0.0
    working_volume_unit: str = "m3"
    operating_temperature_c: float | None = None


@dataclass
class CrystallizerResult:
    feed_rate_kg_h: float
    crystals_kg_h: float
    mother_liquor_kg_h: float
    estimated_slurry_rate_kg_h: float
    circulation_rate_kg_h: float
    circulation_ratio: float
    residence_time_h: float | None
    yield_fraction_of_feed_solids: float
    notes: list[str]


def estimate_crystallizer(inputs: CrystallizerInputs) -> CrystallizerResult:
    feed_rate_kg_h = mass_flow_to_kg_h(inputs.feed_rate_value, inputs.feed_rate_unit)
    circulation_rate_kg_h = mass_flow_to_kg_h(inputs.circulation_rate_value, inputs.circulation_rate_unit) if inputs.circulation_rate_value > 0 else 0.0
    feed_solids_kg_h = feed_rate_kg_h * inputs.feed_solids_wt_pct / 100.0
    mother_liquor_solids = max(inputs.mother_liquor_solids_wt_pct / 100.0, 1e-9)
    slurry_solids = max(inputs.target_slurry_solids_wt_pct / 100.0, 1e-9)

    crystals_kg_h = max(feed_solids_kg_h - feed_rate_kg_h * mother_liquor_solids, 0.0)
    estimated_slurry_rate_kg_h = crystals_kg_h / slurry_solids if crystals_kg_h > 0 else feed_rate_kg_h
    mother_liquor_kg_h = max(estimated_slurry_rate_kg_h - crystals_kg_h, 0.0)
    circulation_ratio = circulation_rate_kg_h / max(feed_rate_kg_h, 1e-9) if circulation_rate_kg_h > 0 else 0.0

    residence_time_h = None
    if inputs.working_volume_value > 0:
        working_volume_m3 = volume_to_m3(inputs.working_volume_value, inputs.working_volume_unit)
        slurry_density_assumed = 1200.0
        residence_time_h = working_volume_m3 * slurry_density_assumed / max(estimated_slurry_rate_kg_h, 1e-9)

    notes = [
        "Engineering estimate only; replace with real solubility data for design or optimization work.",
        "Mother liquor solids is the strongest assumption in this quick crystallizer screen.",
    ]
    if circulation_ratio and circulation_ratio < 3.0:
        notes.append("Low circulation ratio may be unrealistic for many forced-circulation crystallizers.")
    if circulation_ratio and circulation_ratio > 20.0:
        notes.append("Very high circulation ratio entered; confirm pump basis and units.")
    if inputs.operating_temperature_c is not None:
        notes.append(f"Operating temperature basis: {inputs.operating_temperature_c:.1f} C.")

    return CrystallizerResult(
        feed_rate_kg_h=feed_rate_kg_h,
        crystals_kg_h=crystals_kg_h,
        mother_liquor_kg_h=mother_liquor_kg_h,
        estimated_slurry_rate_kg_h=estimated_slurry_rate_kg_h,
        circulation_rate_kg_h=circulation_rate_kg_h,
        circulation_ratio=circulation_ratio,
        residence_time_h=residence_time_h,
        yield_fraction_of_feed_solids=crystals_kg_h / max(feed_solids_kg_h, 1e-9),
        notes=notes,
    )
