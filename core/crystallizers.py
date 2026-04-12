"""Practical crystallizer helpers for quick plant engineering checks."""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.units import mass_flow_to_kg_h, volume_to_m3


CITRIC_SOLUBILITY_WT_PCT_TABLE = [
    (10.0, 54.0),
    (20.0, 59.2),
    (30.0, 64.3),
    (40.0, 68.6),
    (50.0, 70.9),
    (60.0, 73.5),
    (70.0, 76.2),
    (80.0, 78.8),
    (90.0, 81.4),
    (100.0, 84.0),
]


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
    product: str = "generic"
    crystal_density_kg_m3: float = 1660.0
    mother_liquor_density_kg_m3: float = 1280.0
    target_crystal_volume_pct: float | None = None
    slurry_withdrawal_rate_value: float = 0.0
    slurry_withdrawal_rate_unit: str = "kg/h"
    supersaturation_screen_band_relative: float = 0.10
    supersaturation_high_warning_relative: float = 0.20


@dataclass
class CrystallizerResult:
    feed_rate_kg_h: float
    crystals_kg_h: float
    mother_liquor_kg_h: float
    estimated_slurry_rate_kg_h: float
    slurry_withdrawal_rate_kg_h: float | None
    circulation_rate_kg_h: float
    circulation_ratio: float
    residence_time_h: float | None
    yield_fraction_of_feed_solids: float
    mother_liquor_solids_wt_pct: float
    slurry_crystal_mass_fraction: float
    slurry_crystal_volume_fraction: float | None
    equilibrium_solids_wt_pct: float
    absolute_supersaturation_wt_pct: float
    relative_supersaturation: float
    supersaturation_ratio: float
    solids_above_equilibrium_kg_h: float
    supersaturation_zone: str
    notes: list[str]


def estimate_citric_solubility_wt_pct(temperature_c: float) -> float:
    points = CITRIC_SOLUBILITY_WT_PCT_TABLE
    if temperature_c <= points[0][0]:
        left, right = points[0], points[1]
    elif temperature_c >= points[-1][0]:
        left, right = points[-2], points[-1]
    else:
        left, right = points[0], points[1]
        for a, b in zip(points, points[1:]):
            if a[0] <= temperature_c <= b[0]:
                left, right = a, b
                break
    t1, s1 = left
    t2, s2 = right
    fraction = (temperature_c - t1) / max(t2 - t1, 1.0e-9)
    return s1 + fraction * (s2 - s1)


def estimate_crystallizer(inputs: CrystallizerInputs) -> CrystallizerResult:
    feed_rate_kg_h = mass_flow_to_kg_h(inputs.feed_rate_value, inputs.feed_rate_unit)
    circulation_rate_kg_h = mass_flow_to_kg_h(inputs.circulation_rate_value, inputs.circulation_rate_unit) if inputs.circulation_rate_value > 0 else 0.0
    slurry_withdrawal_rate_kg_h = mass_flow_to_kg_h(inputs.slurry_withdrawal_rate_value, inputs.slurry_withdrawal_rate_unit) if inputs.slurry_withdrawal_rate_value > 0 else None
    feed_solids_kg_h = feed_rate_kg_h * inputs.feed_solids_wt_pct / 100.0

    mother_liquor_solids_wt_pct = inputs.mother_liquor_solids_wt_pct
    if inputs.product == "citric_acid" and inputs.operating_temperature_c is not None:
        mother_liquor_solids_wt_pct = estimate_citric_solubility_wt_pct(inputs.operating_temperature_c)
    mother_liquor_solids = max(mother_liquor_solids_wt_pct / 100.0, 1.0e-9)

    absolute_supersaturation_wt_pct = inputs.feed_solids_wt_pct - mother_liquor_solids_wt_pct
    relative_supersaturation = absolute_supersaturation_wt_pct / max(mother_liquor_solids_wt_pct, 1.0e-9)
    supersaturation_ratio = inputs.feed_solids_wt_pct / max(mother_liquor_solids_wt_pct, 1.0e-9)
    solids_above_equilibrium_kg_h = max(feed_rate_kg_h * absolute_supersaturation_wt_pct / 100.0, 0.0)

    if absolute_supersaturation_wt_pct <= 0.0:
        supersaturation_zone = "Undersaturated / at equilibrium"
    elif relative_supersaturation <= inputs.supersaturation_screen_band_relative:
        supersaturation_zone = "Within controllable supersaturation band"
    elif relative_supersaturation <= inputs.supersaturation_high_warning_relative:
        supersaturation_zone = "Elevated supersaturation / metastable screening band"
    else:
        supersaturation_zone = "High supersaturation / fines risk"

    crystals_kg_h = max(feed_solids_kg_h - feed_rate_kg_h * mother_liquor_solids, 0.0)
    mother_liquor_kg_h = max(feed_rate_kg_h - crystals_kg_h, 0.0)

    slurry_crystal_volume_fraction = None
    if inputs.target_crystal_volume_pct is not None:
        slurry_crystal_volume_fraction = min(max(inputs.target_crystal_volume_pct / 100.0, 1.0e-9), 0.95)
        crystal_volume_m3_h = crystals_kg_h / max(inputs.crystal_density_kg_m3, 1.0e-9)
        mother_liquor_volume_m3_h = crystal_volume_m3_h * (1.0 - slurry_crystal_volume_fraction) / slurry_crystal_volume_fraction
        mother_liquor_kg_h = mother_liquor_volume_m3_h * inputs.mother_liquor_density_kg_m3
        dissolved_solids_in_liquor_kg_h = mother_liquor_kg_h * mother_liquor_solids
        available_solids_for_crystals_kg_h = max(feed_solids_kg_h - dissolved_solids_in_liquor_kg_h, 0.0)
        crystals_kg_h = min(crystals_kg_h, available_solids_for_crystals_kg_h)
        crystal_volume_m3_h = crystals_kg_h / max(inputs.crystal_density_kg_m3, 1.0e-9)
        mother_liquor_volume_m3_h = crystal_volume_m3_h * (1.0 - slurry_crystal_volume_fraction) / slurry_crystal_volume_fraction if crystals_kg_h > 0.0 else 0.0
        mother_liquor_kg_h = mother_liquor_volume_m3_h * inputs.mother_liquor_density_kg_m3

    estimated_slurry_rate_kg_h = crystals_kg_h + mother_liquor_kg_h
    slurry_crystal_mass_fraction = crystals_kg_h / max(estimated_slurry_rate_kg_h, 1.0e-9)
    circulation_ratio = circulation_rate_kg_h / max(feed_rate_kg_h, 1e-9) if circulation_rate_kg_h > 0 else 0.0

    residence_time_h = None
    residence_basis_kg_h = slurry_withdrawal_rate_kg_h if slurry_withdrawal_rate_kg_h is not None else estimated_slurry_rate_kg_h
    if inputs.working_volume_value > 0 and residence_basis_kg_h > 1.0e-9:
        working_volume_m3 = volume_to_m3(inputs.working_volume_value, inputs.working_volume_unit)
        if slurry_crystal_volume_fraction is not None:
            slurry_density_assumed = slurry_crystal_volume_fraction * inputs.crystal_density_kg_m3 + (1.0 - slurry_crystal_volume_fraction) * inputs.mother_liquor_density_kg_m3
        else:
            slurry_density_assumed = 1200.0
        residence_time_h = working_volume_m3 * slurry_density_assumed / max(residence_basis_kg_h, 1e-9)

    notes = [
        "Engineering estimate only; replace with validated plant/vessel data for design or optimization work.",
        "Supersaturation classification is a screening aid built from feed solids versus equilibrium mother-liquor solids at the operating temperature.",
    ]
    if inputs.product == "citric_acid" and inputs.operating_temperature_c is not None:
        notes.append("Citric mother-liquor solubility is auto-estimated from published water-solubility data on the Citric acid Wikipedia page: 54.0 wt% at 10 C rising to 84.0 wt% at 100 C, with linear interpolation between listed temperatures.")
    else:
        notes.append("Mother liquor solids remains a manual assumption in this quick crystallizer screen.")
    if inputs.target_crystal_volume_pct is not None:
        notes.append("Target slurry basis is crystal volume percent; mother-liquor mass is back-calculated from crystal density and assumed liquor density.")
    if slurry_withdrawal_rate_kg_h is not None:
        notes.append(f"Residence time uses the entered slurry withdrawal rate of {slurry_withdrawal_rate_kg_h:.1f} kg/h instead of the internally estimated slurry production rate.")
        mismatch_fraction = abs(slurry_withdrawal_rate_kg_h - estimated_slurry_rate_kg_h) / max(estimated_slurry_rate_kg_h, 1.0e-9)
        if mismatch_fraction > 0.25:
            notes.append("Entered slurry withdrawal differs materially from the estimated slurry generation rate; confirm whether the screen should represent net withdrawal, recycle split, or a non-steady-state condition.")
    if circulation_ratio and circulation_ratio < 3.0:
        notes.append("Low circulation ratio may be unrealistic for many forced-circulation crystallizers.")
    if circulation_ratio and circulation_ratio > 20.0:
        notes.append("Very high circulation ratio entered; confirm pump basis and units.")
    if inputs.operating_temperature_c is not None:
        notes.append(f"Operating temperature basis: {inputs.operating_temperature_c:.1f} C.")
    if mother_liquor_solids_wt_pct >= inputs.feed_solids_wt_pct:
        notes.append("Feed solids is at or below the mother-liquor solubility basis, so little or no crystallization is predicted at this temperature.")
    elif relative_supersaturation > inputs.supersaturation_high_warning_relative:
        notes.append("Relative supersaturation is above the user-entered high-warning band; expect stronger spontaneous nucleation / fines tendency unless residence time and classification control are robust.")
    elif relative_supersaturation > inputs.supersaturation_screen_band_relative:
        notes.append("Relative supersaturation sits above the controllable screening band but below the high-warning band; confirm seed loading and crystal classification capacity.")
    else:
        notes.append("Relative supersaturation is within the user-entered controllable screening band.")

    return CrystallizerResult(
        feed_rate_kg_h=feed_rate_kg_h,
        crystals_kg_h=crystals_kg_h,
        mother_liquor_kg_h=mother_liquor_kg_h,
        estimated_slurry_rate_kg_h=estimated_slurry_rate_kg_h,
        slurry_withdrawal_rate_kg_h=slurry_withdrawal_rate_kg_h,
        circulation_rate_kg_h=circulation_rate_kg_h,
        circulation_ratio=circulation_ratio,
        residence_time_h=residence_time_h,
        yield_fraction_of_feed_solids=crystals_kg_h / max(feed_solids_kg_h, 1e-9),
        mother_liquor_solids_wt_pct=mother_liquor_solids_wt_pct,
        slurry_crystal_mass_fraction=slurry_crystal_mass_fraction,
        slurry_crystal_volume_fraction=slurry_crystal_volume_fraction,
        equilibrium_solids_wt_pct=mother_liquor_solids_wt_pct,
        absolute_supersaturation_wt_pct=absolute_supersaturation_wt_pct,
        relative_supersaturation=relative_supersaturation,
        supersaturation_ratio=supersaturation_ratio,
        solids_above_equilibrium_kg_h=solids_above_equilibrium_kg_h,
        supersaturation_zone=supersaturation_zone,
        notes=notes,
    )
