"""Citric acid solubility curves and crystallizer operating parameter planning aid.

Provides enhanced solubility modeling with polynomial fits, solubility curve 
generation, yield prediction across a temperature sweep, and metastable zone
estimation for cooling crystallizer design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math


# ── Citric acid monohydrate solubility in water (g anhydrous / 100 g water) ──
# Source: Published solubility tables, converted to wt% basis
# These are the raw solubility values used to build higher-fidelity fits

_CITRIC_SOLUBILITY_RAW = {
    0: 46.6,     # g/100g water
    10: 54.0,
    20: 59.2,
    30: 64.3,
    40: 68.6,
    50: 70.9,
    60: 73.5,
    70: 76.2,
    80: 78.8,
    90: 81.4,
    100: 84.0,
}

# Pre-computed wt% = 100 * g_per_100g_water / (100 + g_per_100g_water)
_CITRIC_SOLUBILITY_WT_PCT = [(t, 100.0 * g / (100.0 + g)) for t, g in sorted(_CITRIC_SOLUBILITY_RAW.items())]


@dataclass
class SolubilityCurvePoint:
    """A point on the solubility curve."""
    temperature_c: float
    solubility_g_per_100g_water: float
    solubility_wt_pct: float


@dataclass
class SolubilityCurveFitResult:
    """Results of fitting a polynomial to the solubility data."""
    degree: int
    coefficients: list[float]
    r_squared: float
    max_error_wt_pct: float
    mean_error_wt_pct: float


@dataclass
class CrystallizerYieldSweepResult:
    """Yield prediction across a temperature range for a cooling crystallizer."""
    feed_solids_wt_pct: float
    feed_temperature_c: float
    sweep_start_c: float
    sweep_end_c: float
    points: list[dict]
    max_yield_fraction: float
    optimal_temperature_c: float
    notes: list[str]


@dataclass
class MetastableZoneEstimate:
    """Estimated metastable zone boundaries for crystallizer operation."""
    temperature_c: float
    equilibrium_solids_wt_pct: float
    upper_metastable_limit_wt_pct: float
    lower_metastable_limit_wt_pct: float
    labile_zone_start_wt_pct: float
    notes: list[str]


def _g_per_100g_to_wt_pct(g_per_100g: float) -> float:
    """Convert solubility in g anhydrous per 100g water to wt%."""
    return 100.0 * g_per_100g / (100.0 + g_per_100g)


def _wt_pct_to_g_per_100g(wt_pct: float) -> float:
    """Convert wt% to g anhydrous per 100g water."""
    return 100.0 * wt_pct / max(100.0 - wt_pct, 1e-9)


def solubility_table_points() -> list[SolubilityCurvePoint]:
    """Return the raw published solubility data as structured points."""
    return [
        SolubilityCurvePoint(
            temperature_c=float(t),
            solubility_g_per_100g_water=float(g),
            solubility_wt_pct=_g_per_100g_to_wt_pct(float(g)),
        )
        for t, g in sorted(_CITRIC_SOLUBILITY_RAW.items())
    ]


def fit_solubility_polynomial(degree: int = 3) -> SolubilityCurveFitResult:
    """Fit a polynomial to the citric acid solubility data (wt% vs temperature).

    Uses least-squares normal equation approach (no numpy dependency).
    Returns the polynomial coefficients and fitting statistics.
    """
    ts = [float(t) for t, _ in _CITRIC_SOLUBILITY_WT_PCT]
    ws = [w for _, w in _CITRIC_SOLUBILITY_WT_PCT]
    n = len(ts)

    # Build normal equations: (X^T X) * coeff = X^T * w
    # X is the Vandermonde matrix with columns [T^0, T^1, ..., T^degree]
    def vander(vals, deg):
        return [[v ** j for j in range(deg + 1)] for v in vals]

    X = vander(ts, degree)
    XtX = [[sum(X[k][i] * X[k][j] for k in range(n)) for j in range(degree + 1)] for i in range(degree + 1)]
    Xtw = [sum(X[k][i] * ws[k] for k in range(n)) for i in range(degree + 1)]

    # Solve via Gaussian elimination with partial pivoting
    augmented = [row + [Xtw[i]] for i, row in enumerate(XtX)]
    size = len(augmented)

    for col in range(size):
        # Partial pivoting
        max_row = col
        max_val = abs(augmented[col][col])
        for row in range(col + 1, size):
            if abs(augmented[row][col]) > max_val:
                max_val = abs(augmented[row][col])
                max_row = row
        augmented[col], augmented[max_row] = augmented[max_row], augmented[col]

        pivot = augmented[col][col]
        if abs(pivot) < 1e-15:
            raise ValueError("Singular matrix — polynomial degree may be too high for the data.")

        for j in range(col, size + 1):
            augmented[col][j] /= pivot

        for row in range(size):
            if row != col:
                factor = augmented[row][col]
                for j in range(col, size + 1):
                    augmented[row][j] -= factor * augmented[col][j]

    coefficients = [augmented[i][size] for i in range(size)]

    # Calculate fit statistics
    def eval_poly(t):
        return sum(c * (t ** i) for i, c in enumerate(coefficients))

    predicted = [eval_poly(t) for t in ts]
    mean_w = sum(ws) / n
    ss_tot = sum((w - mean_w) ** 2 for w in ws)
    ss_res = sum((w - p) ** 2 for w, p in zip(ws, predicted))
    r_squared = 1.0 - ss_res / max(ss_tot, 1e-15)

    errors = [abs(w - p) for w, p in zip(ws, predicted)]
    max_error = max(errors)
    mean_error = sum(errors) / n

    return SolubilityCurveFitResult(
        degree=degree,
        coefficients=[round(c, 10) for c in coefficients],
        r_squared=round(r_squared, 10),
        max_error_wt_pct=round(max_error, 6),
        mean_error_wt_pct=round(mean_error, 6),
    )


def solubility_from_fit(temperature_c: float, fit: SolubilityCurveFitResult | None = None) -> float:
    """Estimate citric acid solubility (wt%) at a given temperature using a fitted polynomial."""
    if fit is None:
        fit = fit_solubility_polynomial(degree=3)

    return sum(c * (temperature_c ** i) for i, c in enumerate(fit.coefficients))


def solubility_wt_pct_interpolated(temperature_c: float) -> float:
    """Linear interpolation of published solubility table (wt% vs temperature).

    This is the same approach used in the crystallizers module — included here
    for solubility curve generation and comparison.
    """
    points = _CITRIC_SOLUBILITY_WT_PCT
    if temperature_c <= points[0][0]:
        return points[0][1]
    if temperature_c >= points[-1][0]:
        return points[-1][1]

    for i in range(len(points) - 1):
        t1, s1 = points[i]
        t2, s2 = points[i + 1]
        if t1 <= temperature_c <= t2:
            frac = (temperature_c - t1) / max(t2 - t1, 1e-9)
            return s1 + frac * (s2 - s1)
    return points[-1][1]


def generate_solubility_curve(
    temp_min: float = 0.0,
    temp_max: float = 100.0,
    num_points: int = 50,
    use_polynomial: bool = True,
    include_raw_data: bool = True,
) -> dict:
    """Generate solubility curve data for plotting.

    Returns a dict with 'temperatures', 'solubility_wt_pct', 'solubility_g_per_100g',
    and 'raw_data_points' for overlay on charts.
    """
    temps = [temp_min + i * (temp_max - temp_min) / max(num_points - 1, 1) for i in range(num_points)]

    if use_polynomial:
        fit = fit_solubility_polynomial(degree=3)
        solubility_wt = [solubility_from_fit(t, fit) for t in temps]
    else:
        solubility_wt = [solubility_wt_pct_interpolated(t) for t in temps]

    solubility_g = [_wt_pct_to_g_per_100g(sw) for sw in solubility_wt]

    raw_data = None
    if include_raw_data:
        raw_data = [
            {"temperature_c": float(t), "solubility_wt_pct": w, "solubility_g_per_100g_water": float(g)}
            for t, w in _CITRIC_SOLUBILITY_WT_PCT
            for g_raw_key, g in _CITRIC_SOLUBILITY_RAW.items()
            if g_raw_key == t
        ]
        # Deduplicate by rebuilding properly
        raw_data = [
            {"temperature_c": float(t), "solubility_wt_pct": w, "solubility_g_per_100g_water": float(g)}
            for (t, w), g in zip(_CITRIC_SOLUBILITY_WT_PCT, _CITRIC_SOLUBILITY_RAW.values())
        ]

    return {
        "temperatures": temps,
        "solubility_wt_pct": solubility_wt,
        "solubility_g_per_100g": solubility_g,
        "raw_data_points": raw_data,
    }


def predict_crystallizer_yield_sweep(
    feed_solids_wt_pct: float,
    feed_temperature_c: float,
    sweep_start_c: float | None = None,
    sweep_end_c: float = 20.0,
    feed_rate_kg_h: float = 10000.0,
    use_polynomial: bool = True,
    metastable_offset_wt_pct: float = 2.0,
    num_points: int = 20,
) -> CrystallizerYieldSweepResult:
    """Sweep crystallizer yield across a temperature range.

    For each temperature in the sweep, computes:
      - Equilibrium solubility at that temperature
      - Maximum theoretical crystal yield (feed solids - equilibrium solids) 
      - Yield fraction relative to feed solids
      - Whether the solution would be undersaturated, in the metastable zone, or labile
    """
    if feed_solids_wt_pct <= 0 or feed_solids_wt_pct >= 100:
        raise ValueError("Feed solids must be between 0 and 100 wt%.")

    if sweep_start_c is None:
        sweep_start_c = feed_temperature_c

    if sweep_end_c >= sweep_start_c:
        raise ValueError("Sweep end temperature must be below the start temperature for a cooling crystallizer.")

    if use_polynomial:
        fit = fit_solubility_polynomial(degree=3)
        solubility_fn = lambda t: solubility_from_fit(t, fit)
    else:
        solubility_fn = solubility_wt_pct_interpolated

    feed_solids_fraction = feed_solids_wt_pct / 100.0
    total_solids_kg_h = feed_rate_kg_h * feed_solids_fraction

    temps = [sweep_start_c - i * (sweep_start_c - sweep_end_c) / max(num_points - 1, 1) for i in range(num_points)]

    points = []
    max_yield = 0.0
    optimal_temp = sweep_end_c

    for temp in temps:
        eq_solids = solubility_fn(temp)
        eq_solids_frac = eq_solids / 100.0

        if eq_solids_frac >= feed_solids_fraction:
            crystals_kg_h = 0.0
            yield_fraction = 0.0
            region = "Undersaturated / no crystallization"
        else:
            # Proper mass balance: C = (S - L_eq * x_eq) / (1 - x_eq)
            # where S = total solids, L_eq = remaining liquor mass, x_eq = equilibrium fraction
            # C + L_eq = feed_rate
            # S_in = feed_solids, S_in = C + L_eq * x_eq
            # C = S_in - L_eq * x_eq = S_in - (feed_rate - C) * x_eq
            # C * (1 - x_eq) = S_in - feed_rate * x_eq
            # C = (S_in - feed_rate * x_eq) / (1 - x_eq)
            crystals_kg_h = max((total_solids_kg_h - feed_rate_kg_h * eq_solids_frac) / max(1.0 - eq_solids_frac, 1e-9), 0.0)
            yield_fraction = crystals_kg_h / max(total_solids_kg_h, 1e-9)
            excess = feed_solids_wt_pct - eq_solids
            meta_limit = eq_solids + metastable_offset_wt_pct
            if feed_solids_wt_pct > meta_limit:
                region = "Labile (spontaneous nucleation expected)"
            else:
                region = "Metastable (crystal growth, controlled nucleation)"

        if yield_fraction > max_yield:
            max_yield = yield_fraction
            optimal_temp = temp

        liquor_rate = max(feed_rate_kg_h - crystals_kg_h, 0.0)
        if liquor_rate > 1e-9:
            liquor_solids_pct = max((total_solids_kg_h - crystals_kg_h) / liquor_rate * 100.0, 0.0)
        else:
            liquor_solids_pct = eq_solids

        points.append({
            "temperature_c": round(temp, 1),
            "equilibrium_solids_wt_pct": round(eq_solids, 2),
            "crystals_kg_h": round(crystals_kg_h, 1),
            "yield_fraction": round(yield_fraction, 4),
            "yield_pct": round(yield_fraction * 100, 2),
            "liquor_rate_kg_h": round(liquor_rate, 1),
            "liquor_solids_wt_pct": round(liquor_solids_pct, 2),
            "region": region,
        })

    notes = [
        f"Yield sweep from {sweep_start_c:.1f} °C to {sweep_end_c:.1f} °C for feed at {feed_solids_wt_pct:.1f} wt% solids.",
        f"Feed rate: {feed_rate_kg_h:,.0f} kg/h ({total_solids_kg_h:,.0f} kg/h dissolved solids).",
        "Yield is the theoretical maximum assuming perfect equilibrium crystallization at each temperature.",
        "Actual plant yields will be lower due to crystal inclusions, surface liquid carryover, and non-ideal residence time.",
    ]
    if max_yield > 0.9:
        notes.append(f"Maximum yield of {max_yield * 100:.1f}% is very high — the screening model may overestimate due to ignoring mother-liquor retention in the crystal bed.")
    if optimal_temp <= sweep_end_c:
        notes.append(f"Optimal (lowest) temperature in the sweep: {optimal_temp:.1f} °C with {max_yield * 100:.1f}% yield.")

    return CrystallizerYieldSweepResult(
        feed_solids_wt_pct=feed_solids_wt_pct,
        feed_temperature_c=feed_temperature_c,
        sweep_start_c=sweep_start_c,
        sweep_end_c=sweep_end_c,
        points=points,
        max_yield_fraction=round(max_yield, 4),
        optimal_temperature_c=round(optimal_temp, 1),
        notes=notes,
    )


def estimate_metastable_zone(
    temperature_c: float,
    metastable_width_wt_pct: float = 2.0,
    use_polynomial: bool = True,
) -> MetastableZoneEstimate:
    """Estimate metastable zone boundaries at a given temperature.

    The metastable zone is the concentration range between equilibrium
    solubility and the labile point (spontaneous nucleation threshold).

    metastable_width_wt_pct is the estimated width of the metastable zone
    above equilibrium solubility. Typical values for citric acid: 1-5 wt%
    depending on cooling rate, agitation, and seed crystal presence.
    """
    if use_polynomial:
        fit = fit_solubility_polynomial(degree=3)
        eq_solids = solubility_from_fit(temperature_c, fit)
    else:
        eq_solids = solubility_wt_pct_interpolated(temperature_c)

    metastable_upper = eq_solids + metastable_width_wt_pct
    labile_start = eq_solids + metastable_width_wt_pct * 2.0
    metastable_lower = max(eq_solids - metastable_width_wt_pct * 0.5, 0.0)

    notes = [
        f"Metastable zone estimate at {temperature_c:.1f} °C with assumed width of {metastable_width_wt_pct:.1f} wt%.",
        "Actual metastable zone widths depend on cooling rate, agitation, seed loading, and impurities.",
        "Citric acid monohydrate typically shows narrow metastable zones (1-5 wt%) under moderate cooling.",
    ]
    if metastable_width_wt_pct < 1.0:
        notes.append("Very narrow metastable zone assumed; crystallization may initiate with minimal supersaturation.")
    elif metastable_width_wt_pct > 5.0:
        notes.append("Wide metastable zone assumed; the system may sustain significant supersaturation before nucleating.")

    return MetastableZoneEstimate(
        temperature_c=temperature_c,
        equilibrium_solids_wt_pct=round(eq_solids, 2),
        upper_metastable_limit_wt_pct=round(metastable_upper, 2),
        lower_metastable_limit_wt_pct=round(metastable_lower, 2),
        labile_zone_start_wt_pct=round(labile_start, 2),
        notes=notes,
    )
