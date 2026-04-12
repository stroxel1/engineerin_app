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


# Multi-body crystallizer screening
@dataclass
class BodyResult:
    """Per-body results for a multi-body crystallizer train."""
    body_number: int
    temperature_c: float
    equilibrium_solids_wt_pct: float
    liquor_rate_in_kg_h: float
    liquor_solids_in_wt_pct: float
    liquor_solids_in_kg_h: float
    liquor_rate_out_kg_h: float
    liquor_solids_out_wt_pct: float
    crystals_produced_kg_h: float
    cumulative_crystals_kg_h: float
    residence_time_h: float | None
    notes: list[str]


@dataclass
class MultiBodyCrystallizerInputs:
    """Inputs for a multi-body cooling crystallizer train."""
    feed_rate_value: float
    feed_rate_unit: str
    feed_solids_wt_pct: float
    n_bodies: int
    body_temperatures_c: list[float]
    """Temperature of each body (typically decreasing from feed to last body)."""
    working_volume_per_body_m3: float = 0.0
    """Common working volume per body (m3)."""
    explicit_body_volumes_m3: list[float] | None = None
    """Optional per-body working volumes (overrides common volume)."""
    crystal_density_kg_m3: float = 1660.0
    mother_liquor_density_kg_m3: float = 1280.0
    supersaturation_screen_band_relative: float = 0.10
    supersaturation_high_warning_relative: float = 0.20
    include_secondary_feed_points: bool = False
    """Whether to allow secondary feed inlets at intermediate bodies."""
    secondary_feed_rates_value: list[float] | None = None
    secondary_feed_rates_unit: str = "kg/h"
    secondary_feed_solids_wt_pct: list[float] | None = None


@dataclass
class MultiBodyCrystallizerResult:
    """Screening result for a multi-body cooling crystallizer."""
    n_bodies: int
    feed_rate_kg_h: float
    total_secondary_feed_kg_h: float
    total_feed_solids_kg_h: float
    total_crystals_kg_h: float
    final_mother_liquor_kg_h: float
    final_mother_liquor_solids_wt_pct: float
    overall_yield_fraction: float
    total_working_volume_m3: float
    total_residence_time_h: float | None
    bodies: list[BodyResult]
    notes: list[str]


def estimate_multi_body_crystallizer(
    inputs: MultiBodyCrystallizerInputs,
    product: str = "citric_acid",
) -> MultiBodyCrystallizerResult:
    """Screen a multi-body cooling crystallizer train for citric acid (or generic product).
    
    Forward-feed cascade: liquor enters body 1, then flows through successive
    bodies at progressively lower temperatures. In each body, the liquor is
    cooled below its equilibrium solubility at that temperature, and the
    excess solids precipitate as crystals.
    
    Solubility is taken from the citric-acid-in-water table (or user-entered
    equilibrium values).
    
    Mass balance is tracked through the train:
      Feed + secondary feeds = total crystals + final mother liquor
    """
    from engineering_app.core.crystallizers import estimate_citric_solubility_wt_pct
    from engineering_app.core.units import mass_flow_to_kg_h, volume_to_m3

    n = max(1, min(inputs.n_bodies, 6))
    if n != inputs.n_bodies:
        raise ValueError(f"Number of bodies must be 1-6; got {inputs.n_bodies}.")

    feed_rate_kg_h = mass_flow_to_kg_h(inputs.feed_rate_value, inputs.feed_rate_unit)
    if inputs.feed_solids_wt_pct <= 0 or inputs.feed_solids_wt_pct >= 100:
        raise ValueError("Feed solids must be between 0 and 100 wt%.")
    feed_solids_kg_h = feed_rate_kg_h * inputs.feed_solids_wt_pct / 100.0

    body_temps = inputs.body_temperatures_c
    if len(body_temps) != n:
        raise ValueError(f"Need {n} body temperatures, got {len(body_temps)}.")

    # Validate decreasing temperatures (cooling crystallizer)
    for i in range(1, n):
        if body_temps[i] >= body_temps[i - 1]:
            raise ValueError(
                f"Body {i + 1} temperature ({body_temps[i]:.1f} C) should be lower than "
                f"body {i} temperature ({body_temps[i - 1]:.1f} C) for a cooling crystallizer."
            )

    # Volumes
    volumes: list[float] = []
    if inputs.explicit_body_volumes_m3 and len(inputs.explicit_body_volumes_m3) == n:
        volumes = list(inputs.explicit_body_volumes_m3)
    elif inputs.working_volume_per_body_m3 > 0:
        volumes = [inputs.working_volume_per_body_m3] * n

    # Secondary feeds
    sec_feed_rates_kg_h: list[float] = [0.0] * n
    sec_feed_solids_kg_h: list[float] = [0.0] * n
    total_sec_feed_kg_h = 0.0
    if inputs.include_secondary_feed_points and inputs.secondary_feed_rates_value:
        for i in range(min(len(inputs.secondary_feed_rates_value), n)):
            sec_rate = mass_flow_to_kg_h(inputs.secondary_feed_rates_value[i], inputs.secondary_feed_rates_unit)
            sec_feed_rates_kg_h[i] = sec_rate
            total_sec_feed_kg_h += sec_rate
            if inputs.secondary_feed_solids_wt_pct and i < len(inputs.secondary_feed_solids_wt_pct):
                sec_feed_solids_kg_h[i] = sec_rate * inputs.secondary_feed_solids_wt_pct[i] / 100.0

    total_feed_solids_kg_h = feed_solids_kg_h + sum(sec_feed_solids_kg_h)

    bodies: list[BodyResult] = []
    cumulative_crystals = 0.0

    # Feed stream entering body 1
    liquor_in_kg_h = feed_rate_kg_h
    liquor_solids_wt_pct = inputs.feed_solids_wt_pct
    liquor_solids_kg_h = feed_solids_kg_h

    for i in range(n):
        body_num = i + 1
        body_temp = body_temps[i]
        working_vol = volumes[i] if i < len(volumes) else 0.0

        # Add any secondary feed for this body
        total_liquor_in = liquor_in_kg_h + sec_feed_rates_kg_h[i]
        total_solids_in = liquor_solids_kg_h + sec_feed_solids_kg_h[i]
        total_solids_wt_pct_in = total_solids_in / max(total_liquor_in, 1e-9) * 100.0

        # Solubility at this body's temperature
        if product == "citric_acid":
            equilibrium = estimate_citric_solubility_wt_pct(body_temp)
        else:
            equilibrium = 65.0  # generic fallback

        eq_fraction = equilibrium / 100.0

        # Crystals form when feed solids concentration exceeds equilibrium solubility.
        # Proper mass balance: C = (S_in - L_in * x) / (1 - x)
        # where S_in = dissolved solids entering, L_in = total mass entering, x = equilibrium fraction
        if total_solids_in / max(total_liquor_in, 1e-9) > eq_fraction:
            excess_solids = (total_solids_in - total_liquor_in * eq_fraction) / max(1.0 - eq_fraction, 1e-9)
            mother_liquor_out = total_liquor_in - excess_solids
            mother_liquor_solids_out = max(
                mother_liquor_out * eq_fraction, 0.0
            )  # liquor leaves at equilibrium
        else:
            excess_solids = 0.0
            mother_liquor_out = total_liquor_in
            mother_liquor_solids_out = total_solids_in

        mother_liquor_solids_wt_pct_out = (
            mother_liquor_solids_out / max(mother_liquor_out, 1e-9) * 100.0
        )

        # Supersaturation check
        abs_ss = total_solids_wt_pct_in - equilibrium
        rel_ss = abs_ss / max(equilibrium, 1e-9)
        if abs_ss <= 0:
            ss_zone = "No crystallization — feed at or below solubility"
        elif rel_ss <= inputs.supersaturation_screen_band_relative:
            ss_zone = "Low supersaturation — crystal growth dominant"
        elif rel_ss <= inputs.supersaturation_high_warning_relative:
            ss_zone = "Moderate supersaturation — nucleation may occur"
        else:
            ss_zone = "High supersaturation — expect fines/nucleation"

        # Residence time for this body
        body_residence_h = None
        if working_vol > 0 and total_liquor_in > 1e-9:
            slurry_density = (inputs.crystal_density_kg_m3 + inputs.mother_liquor_density_kg_m3) / 2
            body_residence_h = working_vol * slurry_density / max(total_liquor_in, 1e-9)

        cumulative_crystals += excess_solids

        # Notes for this body
        bnotes: list[str] = []
        if excess_solids <= 0:
            bnotes.append(f"Body {body_num}: no crystallization predicted at {body_temp:.1f} C (feed solids ≤ solubility).")
        if abs_ss < 0 and body_num == 1:
            bnotes.append("Feed liquor is undersaturated at the first-body temperature; consider feeding at a lower concentration or raising the first-body temperature.")
        if working_vol > 0 and body_residence_h is not None:
            if body_residence_h < 1.0:
                bnotes.append(f"Body {body_num} residence time of {body_residence_h:.2f} h is short; typical citric crystallizers operate at 2-8 hours.")
            elif body_residence_h > 12:
                bnotes.append(f"Body {body_num} residence time of {body_residence_h:.1f} h is long; confirm vessel sizing and slurry holdup basis.")
        if equilibrium > 80:
            bnotes.append(f"Body {body_num} equilibrium solubility > 80 wt%; viscosity will be high and crystal growth may be limited by mass-transfer constraints.")

        bodies.append(BodyResult(
            body_number=body_num,
            temperature_c=body_temp,
            equilibrium_solids_wt_pct=round(equilibrium, 1),
            liquor_rate_in_kg_h=round(total_liquor_in, 1),
            liquor_solids_in_wt_pct=round(total_solids_wt_pct_in, 2),
            liquor_solids_in_kg_h=round(total_solids_in, 1),
            liquor_rate_out_kg_h=round(mother_liquor_out, 1),
            liquor_solids_out_wt_pct=round(mother_liquor_solids_wt_pct_out, 2),
            crystals_produced_kg_h=round(excess_solids, 1),
            cumulative_crystals_kg_h=round(cumulative_crystals, 1),
            residence_time_h=round(body_residence_h, 2) if body_residence_h is not None else None,
            notes=bnotes,
        ))

        # Output from this body becomes input to next body
        liquor_in_kg_h = mother_liquor_out
        liquor_solids_wt_pct = mother_liquor_solids_wt_pct_out
        liquor_solids_kg_h = mother_liquor_solids_out

    # Final results
    final_ml = bodies[-1].liquor_rate_out_kg_h
    final_ml_solids = bodies[-1].liquor_solids_out_wt_pct
    total_vol = sum(volumes) if volumes else 0.0
    total_residence = None
    if total_vol > 0 and feed_rate_kg_h + total_sec_feed_kg_h > 1e-9:
        total_residence = total_vol * (inputs.crystal_density_kg_m3 + inputs.mother_liquor_density_kg_m3) / 2 / max(feed_rate_kg_h + total_sec_feed_kg_h, 1e-9)

    overall_yield = total_crystals / max(total_feed_solids_kg_h, 1e-9)

    notes = [
        f"Multi-body cooling crystallizer screening feed model for {n} effects.",
        "Liquor flows forward through bodies at progressively lower temperatures.",
        "In each body, solids precipitate when the liquor concentration exceeds the equilibrium solubility at that body's operating temperature.",
        "Citric-acid solubility is estimated from published data with linear interpolation between table points.",
        "This is a first-pass screening tool; confirm with a rigorous population-balance and crystal-growth model.",
    ]

    if overall_yield < 0.5:
        notes.append(f"Overall yield of {overall_yield * 100:.1f}% may be lower than desired; consider adding more bodies or lowering the final-body temperature to improve yield.")
    elif overall_yield > 0.95:
        notes.append(f"Overall yield of {overall_yield * 100:.1f}% is high; confirm this against plant trial data as the screening model may overpredict due to ignoring mother-liquor inclusions and crystal-surface liquid carryover.")

    # Sum temperature span
    temp_span = body_temps[0] - body_temps[-1]
    if temp_span < 5:
        notes.append(f"Total temperature span of {temp_span:.1f} C across {n} bodies is tight; each body has limited driving force for crystallization and the train may be underperforming.")
    elif temp_span > 50:
        notes.append(f"Total temperature span of {temp_span:.1f} C across {n} bodies is large; confirm that the cooling medium can actually provide this range and check for scaling risks.")

    return MultiBodyCrystallizerResult(
        n_bodies=n,
        feed_rate_kg_h=round(feed_rate_kg_h, 1),
        total_secondary_feed_kg_h=round(total_sec_feed_kg_h, 1),
        total_feed_solids_kg_h=round(total_feed_solids_kg_h, 1),
        total_crystals_kg_h=round(cumulative_crystals, 1),
        final_mother_liquor_kg_h=round(final_ml, 1),
        final_mother_liquor_solids_wt_pct=round(final_ml_solids, 2),
        overall_yield_fraction=round(overall_yield, 3),
        total_working_volume_m3=round(total_vol, 2),
        total_residence_time_h=round(total_residence, 2) if total_residence is not None else None,
        bodies=bodies,
        notes=notes,
    )
