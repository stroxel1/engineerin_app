"""Product-specific solution property and dilution helpers for plant screening.

These are deliberately lightweight field estimates. They are meant to give
operators and process engineers a practical first-pass check for syrup/solution
handling, evaporator BPE screening, and blend-back dilution work.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from engineering_app.core.citric_bpe import estimate_citric_bpe
from engineering_app.core.thermal import build_thermal_point
from engineering_app.core.units import density_to_kg_m3, mass_flow_to_kg_h


@dataclass(frozen=True)
class ProductProfile:
    key: str
    display_name: str
    solids_label: str
    density_linear_coeff: float
    density_quadratic_coeff: float
    density_temp_coeff: float
    bpe_linear_coeff: float
    bpe_quadratic_coeff: float
    viscosity_factor: float
    max_recommended_solids_wt_pct: float
    notes: tuple[str, ...]


@dataclass
class SolutionPropertyResult:
    product: str
    solids_wt_pct: float
    temperature_c: float
    pressure_kpa_abs: float
    estimated_density_kg_m3: float
    estimated_bpe_c: float
    estimated_viscosity_cp: float
    dissolved_solids_kg_h: float | None
    water_kg_h: float | None
    boiling_temperature_c: float
    saturation_temperature_c: float
    notes: list[str]


@dataclass
class DilutionResult:
    product: str
    feed_rate_kg_h: float
    feed_solids_wt_pct: float
    target_solids_wt_pct: float
    required_water_addition_kg_h: float
    final_rate_kg_h: float
    final_water_kg_h: float
    solids_kg_h: float
    notes: list[str]


@dataclass
class TwoStreamBlendResult:
    product: str
    stream_a_rate_kg_h: float
    stream_b_rate_kg_h: float
    stream_a_solids_wt_pct: float
    stream_b_solids_wt_pct: float
    total_rate_kg_h: float
    blended_solids_wt_pct: float
    blended_water_kg_h: float
    blended_solids_kg_h: float
    stream_a_temperature_c: float | None
    stream_b_temperature_c: float | None
    blended_temperature_c: float | None
    notes: list[str]


@dataclass
class BrixReconciliationResult:
    product: str
    observed_brix: float
    corrected_solids_wt_pct: float
    reference_solids_wt_pct: float | None
    reference_source: str
    lab_solids_wt_pct: float | None
    measured_density_kg_m3: float | None
    density_implied_solids_wt_pct: float | None
    brix_offset_deg_bx: float | None
    brix_factor: float | None
    solids_error_wt_pct: float | None
    expected_density_kg_m3: float
    estimated_bpe_c: float
    estimated_viscosity_cp: float
    boiling_temperature_c: float
    saturation_temperature_c: float
    dissolved_solids_kg_h: float | None
    water_kg_h: float | None
    notes: list[str]


PRODUCT_PROFILES: dict[str, ProductProfile] = {
    "citric_acid": ProductProfile(
        key="citric_acid",
        display_name="Citric acid solution",
        solids_label="citric acid wt%",
        density_linear_coeff=8.2,
        density_quadratic_coeff=0.025,
        density_temp_coeff=0.35,
        bpe_linear_coeff=0.012,
        bpe_quadratic_coeff=0.0019,
        viscosity_factor=0.080,
        max_recommended_solids_wt_pct=70.0,
        notes=(
            "Useful for citric liquor concentration screening and rough BPE checks.",
            "High-strength citric liquors can deviate sharply near crystallization limits.",
        ),
    ),
    "fructose": ProductProfile(
        key="fructose",
        display_name="Fructose syrup",
        solids_label="fructose solids wt%",
        density_linear_coeff=6.1,
        density_quadratic_coeff=0.018,
        density_temp_coeff=0.30,
        bpe_linear_coeff=0.008,
        bpe_quadratic_coeff=0.0012,
        viscosity_factor=0.070,
        max_recommended_solids_wt_pct=82.0,
        notes=(
            "Targets day-to-day syrup handling and evaporator concentration checks.",
            "Viscosity increases quickly above about 70 wt% fructose solids.",
        ),
    ),
    "dextrose": ProductProfile(
        key="dextrose",
        display_name="Dextrose syrup",
        solids_label="dextrose solids wt%",
        density_linear_coeff=5.6,
        density_quadratic_coeff=0.017,
        density_temp_coeff=0.30,
        bpe_linear_coeff=0.007,
        bpe_quadratic_coeff=0.0010,
        viscosity_factor=0.074,
        max_recommended_solids_wt_pct=80.0,
        notes=(
            "Handy for starch-sugar liquor screens where density and BPE are needed quickly.",
            "Confirm with supplier data if approaching candy-grade or crystallization service.",
        ),
    ),
    "sucrose": ProductProfile(
        key="sucrose",
        display_name="Sucrose syrup",
        solids_label="sucrose solids wt%",
        density_linear_coeff=6.3,
        density_quadratic_coeff=0.020,
        density_temp_coeff=0.30,
        bpe_linear_coeff=0.009,
        bpe_quadratic_coeff=0.0011,
        viscosity_factor=0.076,
        max_recommended_solids_wt_pct=82.0,
        notes=(
            "Useful for generic sugar syrup screening when plant data are not yet mapped in.",
            "Watch for inversion, color, and crystal onset outside this quick estimate basis.",
        ),
    ),
}


def list_supported_products() -> list[str]:
    return list(PRODUCT_PROFILES.keys())


def get_product_profile(product: str) -> ProductProfile:
    try:
        return PRODUCT_PROFILES[product]
    except KeyError as exc:
        raise ValueError(f"Unsupported product: {product}") from exc


def _estimate_density_kg_m3(profile: ProductProfile, solids_wt_pct: float, temperature_c: float) -> float:
    density = (
        998.0
        + profile.density_linear_coeff * solids_wt_pct
        + profile.density_quadratic_coeff * solids_wt_pct * solids_wt_pct
        - profile.density_temp_coeff * max(temperature_c - 20.0, 0.0)
    )
    return max(density, 900.0)


def _estimate_solids_from_density_kg_m3(profile: ProductProfile, density_kg_m3: float, temperature_c: float) -> float:
    adjusted_density = density_kg_m3 - 998.0 + profile.density_temp_coeff * max(temperature_c - 20.0, 0.0)
    a = profile.density_quadratic_coeff
    b = profile.density_linear_coeff
    if a <= 0.0:
        return max(adjusted_density / max(b, 1e-9), 0.0)
    discriminant = max(b * b + 4.0 * a * adjusted_density, 0.0)
    solids = (-b + sqrt(discriminant)) / (2.0 * a)
    return max(solids, 0.0)


def estimate_solution_properties(
    product: str,
    solids_wt_pct: float,
    temperature_c: float,
    pressure_value: float,
    pressure_unit: str,
    flow_value: float | None = None,
    flow_unit: str = "kg/h",
) -> SolutionPropertyResult:
    profile = get_product_profile(product)
    solids = max(solids_wt_pct, 0.0)
    density = _estimate_density_kg_m3(profile, solids, temperature_c)
    if product == "citric_acid":
        citric_bpe = estimate_citric_bpe(solids, pressure_value, pressure_unit, method="auto")
        bpe_c = citric_bpe.bpe_c
    else:
        citric_bpe = None
        bpe_c = max(profile.bpe_linear_coeff * solids + profile.bpe_quadratic_coeff * solids * solids, 0.0)
    viscosity_cp = max(1.0 + 0.02 * solids + profile.viscosity_factor * solids * solids / 10.0, 0.5)

    thermal_point = build_thermal_point(pressure_value, pressure_unit, bpe_c)

    dissolved_solids_kg_h = None
    water_kg_h = None
    if flow_value is not None:
        flow_kg_h = mass_flow_to_kg_h(flow_value, flow_unit)
        dissolved_solids_kg_h = flow_kg_h * solids / 100.0
        water_kg_h = flow_kg_h - dissolved_solids_kg_h

    notes = list(profile.notes)
    if citric_bpe is not None:
        notes.extend(citric_bpe.notes)
    notes.append("Property outputs are quick field estimates; verify against plant or supplier data before design use.")
    if solids > profile.max_recommended_solids_wt_pct:
        notes.append(
            f"Solids exceed the normal screening range for {profile.display_name}; expect larger density, viscosity, and BPE error."
        )
    if thermal_point.boiling_temperature_c >= 100.0:
        notes.append("Boiling point is at or above atmospheric-water boiling; check heater skin temperature and fouling sensitivity.")

    return SolutionPropertyResult(
        product=product,
        solids_wt_pct=solids,
        temperature_c=temperature_c,
        pressure_kpa_abs=thermal_point.pressure_kpa_abs,
        estimated_density_kg_m3=density,
        estimated_bpe_c=bpe_c,
        estimated_viscosity_cp=viscosity_cp,
        dissolved_solids_kg_h=dissolved_solids_kg_h,
        water_kg_h=water_kg_h,
        boiling_temperature_c=thermal_point.boiling_temperature_c,
        saturation_temperature_c=thermal_point.saturation_temperature_c,
        notes=notes,
    )


def calculate_brix_reconciliation(
    product: str,
    observed_brix: float,
    temperature_c: float,
    pressure_value: float,
    pressure_unit: str,
    lab_solids_wt_pct: float | None = None,
    measured_density_value: float | None = None,
    measured_density_unit: str = "kg/m3",
    flow_value: float | None = None,
    flow_unit: str = "kg/h",
) -> BrixReconciliationResult:
    profile = get_product_profile(product)
    if observed_brix < 0.0:
        raise ValueError("Observed Brix must be zero or greater.")
    if lab_solids_wt_pct is not None and not 0.0 <= lab_solids_wt_pct <= 100.0:
        raise ValueError("Lab solids must stay within 0 to 100 wt%.")

    measured_density_kg_m3 = None
    density_implied_solids_wt_pct = None
    if measured_density_value is not None:
        measured_density_kg_m3 = density_to_kg_m3(measured_density_value, measured_density_unit)
        density_implied_solids_wt_pct = _estimate_solids_from_density_kg_m3(profile, measured_density_kg_m3, temperature_c)

    reference_solids_wt_pct = None
    reference_source = "uncorrected_brix"
    if lab_solids_wt_pct is not None:
        reference_solids_wt_pct = lab_solids_wt_pct
        reference_source = "lab_solids"
    elif density_implied_solids_wt_pct is not None:
        reference_solids_wt_pct = density_implied_solids_wt_pct
        reference_source = "density_model"

    corrected_solids_wt_pct = reference_solids_wt_pct if reference_solids_wt_pct is not None else observed_brix
    corrected_solids_wt_pct = max(min(corrected_solids_wt_pct, 100.0), 0.0)

    properties = estimate_solution_properties(
        product=product,
        solids_wt_pct=corrected_solids_wt_pct,
        temperature_c=temperature_c,
        pressure_value=pressure_value,
        pressure_unit=pressure_unit,
        flow_value=flow_value,
        flow_unit=flow_unit,
    )

    brix_offset = None if reference_solids_wt_pct is None else reference_solids_wt_pct - observed_brix
    brix_factor = None
    if reference_solids_wt_pct is not None and observed_brix > 0.0:
        brix_factor = reference_solids_wt_pct / observed_brix

    notes = [
        f"°Bx is a sucrose-based dissolved-solids indication; for {profile.display_name}, use it as an approximate solids reading until it is checked against plant lab or density data.",
        "Reference basis comes from the first trusted source available: lab solids first, then product-density back-calculation.",
        "Use the suggested offset/factor to align field refractometer readings with the current product and temperature range.",
    ]
    if reference_source == "uncorrected_brix":
        notes.append("No lab solids or density reference was entered, so corrected solids default to the observed Brix value.")
    if density_implied_solids_wt_pct is not None:
        notes.append("Density-implied solids come from the app's product density estimate and are intended for screening, not custody-transfer accuracy.")
    if lab_solids_wt_pct is not None and density_implied_solids_wt_pct is not None:
        gap = abs(lab_solids_wt_pct - density_implied_solids_wt_pct)
        if gap > 1.0:
            notes.append(
                f"Lab solids and density-implied solids differ by {gap:.2f} wt%; verify sample temperature, entrained air, and density basis before using one calibration broadly."
            )
    solids_error = None if reference_solids_wt_pct is None else observed_brix - reference_solids_wt_pct
    if solids_error is not None and abs(solids_error) > 1.0:
        notes.append(
            f"Observed Brix differs from the selected reference by {solids_error:+.2f} wt%; this is large enough to materially affect downstream dilution and evaporator screens."
        )
    if corrected_solids_wt_pct > profile.max_recommended_solids_wt_pct:
        notes.append(
            f"Corrected solids exceed the normal screening range for {profile.display_name}; expect larger error in the density and viscosity back-checks."
        )

    return BrixReconciliationResult(
        product=product,
        observed_brix=observed_brix,
        corrected_solids_wt_pct=corrected_solids_wt_pct,
        reference_solids_wt_pct=reference_solids_wt_pct,
        reference_source=reference_source,
        lab_solids_wt_pct=lab_solids_wt_pct,
        measured_density_kg_m3=measured_density_kg_m3,
        density_implied_solids_wt_pct=density_implied_solids_wt_pct,
        brix_offset_deg_bx=brix_offset,
        brix_factor=brix_factor,
        solids_error_wt_pct=solids_error,
        expected_density_kg_m3=properties.estimated_density_kg_m3,
        estimated_bpe_c=properties.estimated_bpe_c,
        estimated_viscosity_cp=properties.estimated_viscosity_cp,
        boiling_temperature_c=properties.boiling_temperature_c,
        saturation_temperature_c=properties.saturation_temperature_c,
        dissolved_solids_kg_h=properties.dissolved_solids_kg_h,
        water_kg_h=properties.water_kg_h,
        notes=notes + properties.notes,
    )


def calculate_dilution_water(
    product: str,
    feed_rate_value: float,
    feed_rate_unit: str,
    feed_solids_wt_pct: float,
    target_solids_wt_pct: float,
) -> DilutionResult:
    profile = get_product_profile(product)
    if target_solids_wt_pct <= 0:
        raise ValueError("Target solids must be above zero.")
    if target_solids_wt_pct > feed_solids_wt_pct:
        raise ValueError("Target solids must be less than or equal to the feed solids for a dilution calculation.")

    feed_rate_kg_h = mass_flow_to_kg_h(feed_rate_value, feed_rate_unit)
    solids_kg_h = feed_rate_kg_h * max(feed_solids_wt_pct, 0.0) / 100.0
    final_rate_kg_h = solids_kg_h / max(target_solids_wt_pct / 100.0, 1e-9)
    required_water = max(final_rate_kg_h - feed_rate_kg_h, 0.0)
    final_water = final_rate_kg_h - solids_kg_h

    notes = [
        f"Computed on a solids-only balance for {profile.display_name}.",
        "Assumes the added stream is water and no evaporation or side losses occur during blending.",
    ]
    if required_water == 0:
        notes.append("No dilution water required on the entered basis.")
    if target_solids_wt_pct < 20.0:
        notes.append("Very low final solids may materially change density, pumping, and residence-time assumptions.")

    return DilutionResult(
        product=product,
        feed_rate_kg_h=feed_rate_kg_h,
        feed_solids_wt_pct=feed_solids_wt_pct,
        target_solids_wt_pct=target_solids_wt_pct,
        required_water_addition_kg_h=required_water,
        final_rate_kg_h=final_rate_kg_h,
        final_water_kg_h=final_water,
        solids_kg_h=solids_kg_h,
        notes=notes,
    )


def calculate_two_stream_blend(
    product: str,
    stream_a_rate_value: float,
    stream_a_rate_unit: str,
    stream_a_solids_wt_pct: float,
    stream_b_rate_value: float,
    stream_b_rate_unit: str,
    stream_b_solids_wt_pct: float,
    stream_a_temperature_c: float | None = None,
    stream_b_temperature_c: float | None = None,
) -> TwoStreamBlendResult:
    profile = get_product_profile(product)
    stream_a_rate_kg_h = mass_flow_to_kg_h(stream_a_rate_value, stream_a_rate_unit)
    stream_b_rate_kg_h = mass_flow_to_kg_h(stream_b_rate_value, stream_b_rate_unit)
    if stream_a_rate_kg_h < 0.0 or stream_b_rate_kg_h < 0.0:
        raise ValueError("Stream flow rates must be zero or greater.")

    total_rate_kg_h = stream_a_rate_kg_h + stream_b_rate_kg_h
    if total_rate_kg_h <= 0.0:
        raise ValueError("At least one stream must have a flow above zero.")

    stream_a_solids = max(stream_a_solids_wt_pct, 0.0) / 100.0
    stream_b_solids = max(stream_b_solids_wt_pct, 0.0) / 100.0
    if stream_a_solids > 1.0 or stream_b_solids > 1.0:
        raise ValueError("Stream solids must stay within 0 to 100 wt%.")

    blended_solids_kg_h = stream_a_rate_kg_h * stream_a_solids + stream_b_rate_kg_h * stream_b_solids
    blended_water_kg_h = total_rate_kg_h - blended_solids_kg_h
    blended_solids_wt_pct = blended_solids_kg_h / total_rate_kg_h * 100.0

    blended_temperature_c = None
    if stream_a_temperature_c is not None and stream_b_temperature_c is not None:
        blended_temperature_c = (
            stream_a_rate_kg_h * stream_a_temperature_c + stream_b_rate_kg_h * stream_b_temperature_c
        ) / total_rate_kg_h

    notes = [
        f"Computed on total-mass and dissolved-solids balances for {profile.display_name}.",
        "Blend temperature uses a flow-weighted average and ignores heat of solution, flashing, and unequal heat capacities.",
        "For precise blend tank temperature or density, validate against plant tests when one stream is much hotter or materially different in composition.",
    ]
    if stream_a_solids_wt_pct == 0.0 or stream_b_solids_wt_pct == 0.0:
        notes.append("A zero-solids stream is treated as water or condensate dilution on this screening basis.")
    if blended_solids_wt_pct > profile.max_recommended_solids_wt_pct:
        notes.append(
            f"Blended solids exceed the normal screening range for {profile.display_name}; downstream density, BPE, and viscosity estimates will be less certain."
        )

    return TwoStreamBlendResult(
        product=product,
        stream_a_rate_kg_h=stream_a_rate_kg_h,
        stream_b_rate_kg_h=stream_b_rate_kg_h,
        stream_a_solids_wt_pct=stream_a_solids_wt_pct,
        stream_b_solids_wt_pct=stream_b_solids_wt_pct,
        total_rate_kg_h=total_rate_kg_h,
        blended_solids_wt_pct=blended_solids_wt_pct,
        blended_water_kg_h=blended_water_kg_h,
        blended_solids_kg_h=blended_solids_kg_h,
        stream_a_temperature_c=stream_a_temperature_c,
        stream_b_temperature_c=stream_b_temperature_c,
        blended_temperature_c=blended_temperature_c,
        notes=notes,
    )


__all__ = [
    "BrixReconciliationResult",
    "DilutionResult",
    "PRODUCT_PROFILES",
    "ProductProfile",
    "SolutionPropertyResult",
    "TwoStreamBlendResult",
    "calculate_brix_reconciliation",
    "calculate_dilution_water",
    "calculate_two_stream_blend",
    "estimate_solution_properties",
    "get_product_profile",
    "list_supported_products",
]
