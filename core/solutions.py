"""Product-specific solution property and dilution helpers for plant screening.

These are deliberately lightweight field estimates. They are meant to give
operators and process engineers a practical first-pass check for syrup/solution
handling, evaporator BPE screening, and blend-back dilution work.
"""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.citric_bpe import estimate_citric_bpe
from engineering_app.core.thermal import build_thermal_point
from engineering_app.core.units import mass_flow_to_kg_h


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
    density = (
        998.0
        + profile.density_linear_coeff * solids
        + profile.density_quadratic_coeff * solids * solids
        - profile.density_temp_coeff * max(temperature_c - 20.0, 0.0)
    )
    density = max(density, 900.0)
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


__all__ = [
    "DilutionResult",
    "PRODUCT_PROFILES",
    "ProductProfile",
    "SolutionPropertyResult",
    "calculate_dilution_water",
    "estimate_solution_properties",
    "get_product_profile",
    "list_supported_products",
]
