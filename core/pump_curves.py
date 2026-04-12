from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class PumpCurvePoint:
    flow_m3_h: float
    head_m: float


@dataclass
class PumpCurveModel:
    name: str
    family: str
    points: list[PumpCurvePoint]
    notes: list[str]


@dataclass
class PumpCurveIntersection:
    flow_m3_h: float
    head_m: float
    head_error_m: float
    fraction_of_curve_max_flow: float


@dataclass
class PumpCurveAffinityResult:
    base_curve_name: str
    speed_ratio: float
    impeller_ratio: float
    scaled_curve: PumpCurveModel
    notes: list[str]


@dataclass
class PumpCurveRerateScreenResult:
    base_curve: PumpCurveModel
    scaled_curve: PumpCurveModel
    base_intersection: PumpCurveIntersection | None
    scaled_intersection: PumpCurveIntersection | None
    speed_ratio: float
    impeller_ratio: float
    relative_power_factor: float
    relative_npshr_factor: float
    notes: list[str]


@dataclass
class PumpCurveMeasuredPointComparison:
    measured_flow_m3_h: float
    measured_head_m: float
    curve_head_m: float | None
    head_delta_m: float | None
    head_delta_pct_of_curve: float | None
    flow_fraction_of_curve_max: float | None
    status: str
    notes: list[str]


BUILTIN_PUMP_CURVES: dict[str, PumpCurveModel] = {
    "ansi_50hz_trimmed": PumpCurveModel(
        name="ANSI process pump - trimmed impeller",
        family="Built-in library",
        points=[
            PumpCurvePoint(0.0, 68.0),
            PumpCurvePoint(20.0, 66.0),
            PumpCurvePoint(40.0, 61.0),
            PumpCurvePoint(60.0, 53.0),
            PumpCurvePoint(80.0, 42.0),
            PumpCurvePoint(95.0, 31.0),
        ],
        notes=[
            "Built-in example curve for first-pass troubleshooting; replace with vendor data when available.",
            "Monotonically decreasing head with flow is assumed.",
        ],
    ),
    "ansi_50hz_full": PumpCurveModel(
        name="ANSI process pump - full impeller",
        family="Built-in library",
        points=[
            PumpCurvePoint(0.0, 82.0),
            PumpCurvePoint(25.0, 79.0),
            PumpCurvePoint(50.0, 74.0),
            PumpCurvePoint(75.0, 66.0),
            PumpCurvePoint(100.0, 55.0),
            PumpCurvePoint(120.0, 42.0),
        ],
        notes=[
            "Built-in example curve for first-pass troubleshooting; replace with vendor data when available.",
            "Use multiple points from vendor data if testing rerates or impeller trims.",
        ],
    ),
    "high_head_small_flow": PumpCurveModel(
        name="High-head low-flow service pump",
        family="Built-in library",
        points=[
            PumpCurvePoint(0.0, 115.0),
            PumpCurvePoint(10.0, 112.0),
            PumpCurvePoint(20.0, 105.0),
            PumpCurvePoint(30.0, 94.0),
            PumpCurvePoint(40.0, 78.0),
            PumpCurvePoint(48.0, 62.0),
        ],
        notes=[
            "Built-in example curve for higher-head services such as recirculation or transfer through restrictive systems.",
            "Replace with vendor curve before equipment decisions.",
        ],
    ),
}


def available_builtin_curve_options() -> list[str]:
    return list(BUILTIN_PUMP_CURVES.keys())


def get_builtin_curve(key: str) -> PumpCurveModel:
    if key not in BUILTIN_PUMP_CURVES:
        raise KeyError(f"Unknown built-in pump curve: {key}")
    return BUILTIN_PUMP_CURVES[key]


def build_curve_from_xy_rows(
    name: str,
    rows: list[dict],
    flow_column: str,
    head_column: str,
    family: str = "Uploaded / manual",
) -> PumpCurveModel:
    points: list[PumpCurvePoint] = []
    for row in rows:
        flow_raw = row.get(flow_column)
        head_raw = row.get(head_column)
        if flow_raw in (None, "") or head_raw in (None, ""):
            continue
        flow = float(flow_raw)
        head = float(head_raw)
        if flow < 0.0:
            raise ValueError("Pump curve flow values must be zero or greater.")
        points.append(PumpCurvePoint(flow_m3_h=flow, head_m=head))
    if len(points) < 2:
        raise ValueError("Pump curve needs at least two valid flow/head points.")

    points.sort(key=lambda point: point.flow_m3_h)
    deduped: list[PumpCurvePoint] = []
    for point in points:
        if deduped and abs(point.flow_m3_h - deduped[-1].flow_m3_h) < 1.0e-9:
            deduped[-1] = point
        else:
            deduped.append(point)

    notes = [
        "Curve was built from uploaded/manual flow-head points.",
        "Head interpolation is piecewise-linear between entered points.",
    ]
    if any(deduped[idx + 1].head_m > deduped[idx].head_m for idx in range(len(deduped) - 1)):
        notes.append("Curve head is not monotonically decreasing over all points; verify the source data and units.")

    return PumpCurveModel(name=name, family=family, points=deduped, notes=notes)


def interpolate_pump_head(curve: PumpCurveModel, flow_m3_h: float) -> float | None:
    if flow_m3_h < curve.points[0].flow_m3_h or flow_m3_h > curve.points[-1].flow_m3_h:
        return None
    for left, right in zip(curve.points, curve.points[1:]):
        if left.flow_m3_h <= flow_m3_h <= right.flow_m3_h:
            span = max(right.flow_m3_h - left.flow_m3_h, 1.0e-12)
            fraction = (flow_m3_h - left.flow_m3_h) / span
            return left.head_m + fraction * (right.head_m - left.head_m)
    return curve.points[-1].head_m


def find_curve_system_intersection(
    curve: PumpCurveModel,
    static_head_m: float,
    k_factor_m_per_m3h2: float,
    point_count: int = 400,
) -> PumpCurveIntersection | None:
    if point_count < 2:
        point_count = 2
    min_flow = curve.points[0].flow_m3_h
    max_flow = curve.points[-1].flow_m3_h
    best: PumpCurveIntersection | None = None
    for step in range(point_count + 1):
        flow = min_flow + (max_flow - min_flow) * step / point_count
        pump_head = interpolate_pump_head(curve, flow)
        if pump_head is None:
            continue
        system_head = static_head_m + k_factor_m_per_m3h2 * flow * flow
        error = abs(pump_head - system_head)
        if best is None or error < best.head_error_m:
            best = PumpCurveIntersection(
                flow_m3_h=flow,
                head_m=system_head,
                head_error_m=error,
                fraction_of_curve_max_flow=flow / max(max_flow, 1.0e-12),
            )
    return best


def scale_curve_by_affinity_laws(
    curve: PumpCurveModel,
    speed_ratio: float = 1.0,
    impeller_ratio: float = 1.0,
) -> PumpCurveAffinityResult:
    if speed_ratio <= 0.0:
        raise ValueError("Speed ratio must be positive.")
    if impeller_ratio <= 0.0:
        raise ValueError("Impeller ratio must be positive.")

    flow_factor = speed_ratio * impeller_ratio
    head_factor = (speed_ratio ** 2) * (impeller_ratio ** 2)
    scaled_points = [
        PumpCurvePoint(
            flow_m3_h=point.flow_m3_h * flow_factor,
            head_m=point.head_m * head_factor,
        )
        for point in curve.points
    ]
    notes = [
        "Scaled with centrifugal-pump affinity laws using Q ∝ N·D, H ∝ N²·D², and power demand implication P ∝ N³·D³.",
        "Use this as a screening rerate tool; confirm with vendor curves before final decisions.",
    ]
    if abs(speed_ratio - 1.0) > 1.0e-9:
        notes.append(f"Speed ratio applied: {speed_ratio:.4f}.")
    if abs(impeller_ratio - 1.0) > 1.0e-9:
        notes.append(f"Impeller diameter ratio applied: {impeller_ratio:.4f}.")
    if speed_ratio > 1.1 or impeller_ratio > 1.05:
        notes.append("Materially higher speed or diameter can sharply increase power draw and NPSH sensitivity; check motor margin and suction conditions.")

    return PumpCurveAffinityResult(
        base_curve_name=curve.name,
        speed_ratio=speed_ratio,
        impeller_ratio=impeller_ratio,
        scaled_curve=PumpCurveModel(
            name=f"{curve.name} (scaled)",
            family=f"{curve.family} / affinity-scaled",
            points=scaled_points,
            notes=curve.notes + notes,
        ),
        notes=notes,
    )


def screen_affinity_rerate(
    curve: PumpCurveModel,
    static_head_m: float,
    k_factor_m_per_m3h2: float,
    speed_ratio: float = 1.0,
    impeller_ratio: float = 1.0,
    point_count: int = 400,
) -> PumpCurveRerateScreenResult:
    affinity = scale_curve_by_affinity_laws(
        curve,
        speed_ratio=speed_ratio,
        impeller_ratio=impeller_ratio,
    )
    base_intersection = find_curve_system_intersection(
        curve,
        static_head_m,
        k_factor_m_per_m3h2,
        point_count=point_count,
    )
    scaled_intersection = find_curve_system_intersection(
        affinity.scaled_curve,
        static_head_m,
        k_factor_m_per_m3h2,
        point_count=point_count,
    )
    relative_power_factor = (speed_ratio ** 3) * (impeller_ratio ** 3)
    relative_npshr_factor = (speed_ratio ** 2) * (impeller_ratio ** 2)
    notes = list(affinity.notes)
    notes.append(
        "Relative power factor is screened with P ∝ N³·D³. Check motor amps, service factor, and shaft limits before increasing speed or diameter."
    )
    notes.append(
        "Relative NPSHr factor is screened with NPSHr ∝ N²·D² as a practical approximation. Verify against vendor data before concluding suction margin is adequate."
    )
    if base_intersection is not None and scaled_intersection is not None:
        delta_flow_pct = (
            (scaled_intersection.flow_m3_h - base_intersection.flow_m3_h)
            / max(base_intersection.flow_m3_h, 1.0e-9)
            * 100.0
        )
        delta_head_pct = (
            (scaled_intersection.head_m - base_intersection.head_m)
            / max(base_intersection.head_m, 1.0e-9)
            * 100.0
        )
        notes.append(
            f"On the current system curve, the screened rerate shifts the operating point by {delta_flow_pct:+.1f}% flow and {delta_head_pct:+.1f}% head."
        )

    return PumpCurveRerateScreenResult(
        base_curve=curve,
        scaled_curve=affinity.scaled_curve,
        base_intersection=base_intersection,
        scaled_intersection=scaled_intersection,
        speed_ratio=speed_ratio,
        impeller_ratio=impeller_ratio,
        relative_power_factor=relative_power_factor,
        relative_npshr_factor=relative_npshr_factor,
        notes=notes,
    )


# ────────────────── BEP (Best Efficiency Point) helpers ──────────────────


@dataclass
class BEPEstimate:
    """Estimated best-efficiency point on a pump curve."""
    flow_m3_h: float       # estimated BEP flow
    head_m: float          # estimated BEP head
    flow_fraction_of_max: float  # BEP flow as fraction of curve max flow
    recommended_zone_lo: float   # lower bound of acceptable BEP band (fraction)
    recommended_zone_hi: float   # upper bound of acceptable BEP band (fraction)
    method: str            # how BEP was estimated
    notes: list[str]


@dataclass
class BEPProximityResult:
    """How close a measured operating point is to the pump's BEP."""
    measured_flow_m3_h: float
    measured_head_m: float
    bep_flow_m3_h: float
    bep_head_m: float
    flow_offset_fraction: float     # (measured - BEP) / BEP flow
    head_offset_fraction: float     # (measured - BEP) / BEP head
    inside_preferred_zone: bool
    proximity_status: str           # "at_bep", "within_preferred", "moderate_right", "moderate_left", "far_right", "far_left"
    reliability_risk: str | None    # potential risk from operating off-BEP
    notes: list[str]


@dataclass
class InstrumentBiasScreen:
    """Quick screen for whether gauge/instrument error could explain a head-flow discrepancy."""
    measured_flow_m3_h: float
    measured_head_m: float
    expected_flow_m3_h: float
    expected_head_m: float
    flow_discrepancy_m3_h: float
    head_discrepancy_m: float
    flow_bias_pct: float           # pct of reading that gauge error would need to explain gap
    head_bias_pct: float
    flow_explainable_with_2pct_gauge: bool
    head_explainable_with_2pct_gauge: bool
    flow_explainable_with_5pct_gauge: bool
    head_explainable_with_5pct_gauge: bool
    likely_explainable: bool
    notes: list[str]


def estimate_bep_from_curve(
    curve: PumpCurveModel,
    preferred_zone: tuple[float, float] = (0.70, 0.95),
) -> BEPEstimate:
    """Estimate the BEP from a pump curve using the maximum-head-slope heuristic.

    Centrifugal-pump BEP typically sits in the 70-95% flow range on the curve.
    This method picks the point in that zone with the lowest head (closest to
    the curve's run-out end) — a practical screening approximation when vendor
    BEP data is unavailable.

    A better heuristic is to find the flow at which the head curve crosses 85%
    of shut-off head, since many centrifugals peak efficiency near there.
    """
    if len(curve.points) < 2:
        raise ValueError("Need at least two curve points to estimate BEP.")

    shut_off_head = curve.points[0].head_m
    max_flow = curve.points[-1].flow_m3_h
    min_flow = curve.points[0].flow_m3_h
    flow_range = max_flow - min_flow

    # Default: BEP is near the point whose head is ~85% of shutoff head
    target_head = 0.85 * shut_off_head

    # Find the curve segment bracketing the target head
    best_point: PumpCurvePoint | None = None
    best_distance = float("inf")

    for i, pt in enumerate(curve.points):
        # Prefer points in the preferred zone
        flow_frac = (pt.flow_m3_h - min_flow) / max(flow_range, 1e-12)
        in_zone = preferred_zone[0] <= flow_frac <= preferred_zone[1]

        head_dist = abs(pt.head_m - target_head)

        # Points outside the zone get a penalty factor of 3x
        if not in_zone:
            head_dist *= 3.0

        if head_dist < best_distance:
            best_distance = head_dist
            best_point = pt

    if best_point is None:
        # Fallback: just take the midpoint of the curve
        mid_idx = len(curve.points) // 2
        best_point = curve.points[mid_idx]

    bep_flow_frac = (best_point.flow_m3_h - min_flow) / max(flow_range, 1e-12)

    notes = [
        f"BEP estimated from curve shape using 85% shut-off-head heuristic ({shut_off_head:.1f} m shutoff → {target_head:.1f} m target).",
        f"Estimated BEP: {best_point.flow_m3_h:.1f} m3/h @ {best_point.head_m:.1f} m — {bep_flow_frac:.0%} of curve flow range.",
        "Vendor data, efficiency curves, or affinity-test results should replace this screening estimate for design or reliability decisions.",
    ]

    lo_frac, hi_frac = preferred_zone

    return BEPEstimate(
        flow_m3_h=best_point.flow_m3_h,
        head_m=best_point.head_m,
        flow_fraction_of_max=bep_flow_frac,
        recommended_zone_lo=lo_frac,
        recommended_zone_hi=hi_frac,
        method="85pct_shutoff_head_heuristic",
        notes=notes,
    )


def assess_bep_proximity(
    curve: PumpCurveModel,
    measured_flow_m3_h: float,
    measured_head_m: float,
    preferred_zone: tuple[float, float] | None = None,
    bep_estimate: BEPEstimate | None = None,
) -> BEPProximityResult:
    """Assess how close the measured operating point is to BEP."""
    if bep_estimate is None:
        bep_estimate = estimate_bep_from_curve(curve, preferred_zone=preferred_zone or (0.70, 0.95))

    bep_flow = bep_estimate.flow_m3_h
    bep_head = bep_estimate.head_m
    lo_frac = bep_estimate.recommended_zone_lo
    hi_frac = bep_estimate.recommended_zone_hi

    min_flow = curve.points[0].flow_m3_h
    max_flow = curve.points[-1].flow_m3_h
    flow_range = max_flow - min_flow
    lo_flow = min_flow + lo_frac * flow_range
    hi_flow = min_flow + hi_frac * flow_range

    # Offset from BEP
    flow_offset = (measured_flow_m3_h - bep_flow) / max(bep_flow, 1e-12)
    head_offset = (measured_head_m - bep_head) / max(bep_head, 1e-12)

    inside_zone = lo_flow <= measured_flow_m3_h <= hi_flow

    # Classify proximity
    if inside_zone:
        if abs(flow_offset) < 0.05:
            proximity = "at_bep"
        else:
            proximity = "within_preferred"

        reliability_risk = None
    else:
        if measured_flow_m3_h > hi_flow:
            frac_above = (measured_flow_m3_h - hi_flow) / max(flow_range, 1e-12)
            if frac_above < 0.15:
                proximity = "moderate_right"
                reliability_risk = "Moderately right of BEP — watch for increased NPSHr, possible cavitation, and rising bearing load."
            else:
                proximity = "far_right"
                reliability_risk = "Far right of BEP — high risk of cavitation, excessive radial thrust, premature seal/bearing failure, and possible motor overload."
        else:
            frac_below = (lo_flow - measured_flow_m3_h) / max(flow_range, 1e-12)
            if frac_below < 0.15:
                proximity = "moderate_left"
                reliability_risk = "Moderately left of BEP — watch for recirculation, internal heating on prolonged operation, and possible vibration."
            else:
                proximity = "far_left"
                reliability_risk = "Far left of BEP — high risk of suction/discharge recirculation, temperature rise, vibration, and mechanical-seal damage on sustained operation."

    notes = [
        f"Estimated BEP from curve: {bep_flow:.1f} m3/h @ {bep_head:.1f} m (screening estimate; replace with vendor BEP if available).",
        f"Measured operating point: {measured_flow_m3_h:.1f} m3/h @ {measured_head_m:.1f} m.",
        f"Flow offset from BEP: {flow_offset:+.1%}  |  Head offset from BEP: {head_offset:+.1%}.",
    ]

    # Add preferred zone info
    notes.append(
        f"Preferred operating band: {lo_flow:.1f} – {hi_flow:.1f} m3/h ({lo_frac:.0%}–{hi_frac:.0%} of curve range)."
    )

    if proximity in ("at_bep",):
        notes.append("Operating at BEP — ideal for reliability, energy efficiency, and seal/bearing life.")
    elif proximity == "within_preferred":
        if flow_offset > 0:
            notes.append("Within preferred band but slightly right of BEP — monitor NPSH margin if flow drifts higher.")
        else:
            notes.append("Within preferred band but slightly left of BEP — acceptable for most services.")
    elif reliability_risk:
        notes.append(reliability_risk)

    notes.extend(bep_estimate.notes)

    return BEPProximityResult(
        measured_flow_m3_h=measured_flow_m3_h,
        measured_head_m=measured_head_m,
        bep_flow_m3_h=bep_flow,
        bep_head_m=bep_head,
        flow_offset_fraction=flow_offset,
        head_offset_fraction=head_offset,
        inside_preferred_zone=inside_zone,
        proximity_status=proximity,
        reliability_risk=reliability_risk,
        notes=notes,
    )


def screen_instrument_bias(
    measured_flow_m3_h: float,
    measured_head_m: float,
    expected_flow_m3_h: float,
    expected_head_m: float,
    flow_gauge_accuracy_pct: float = 2.0,
    pressure_gauge_accuracy_pct: float = 2.0,
) -> InstrumentBiasScreen:
    """Check whether instrument gauge accuracy could explain a deviation between measured and expected values."""
    flow_disc = measured_flow_m3_h - expected_flow_m3_h
    head_disc = measured_head_m - expected_head_m

    flow_bias_pct = abs(flow_disc) / max(abs(measured_flow_m3_h), 1e-12) * 100.0
    head_bias_pct = abs(head_disc) / max(abs(measured_head_m), 1e-12) * 100.0

    flow_ok_2 = flow_bias_pct <= flow_gauge_accuracy_pct
    head_ok_2 = head_bias_pct <= pressure_gauge_accuracy_pct
    flow_ok_5 = flow_bias_pct <= 5.0
    head_ok_5 = head_bias_pct <= 5.0

    likely = flow_ok_2 or head_ok_2 or flow_ok_5 or head_ok_5

    notes = [
        f"Discrepancy: flow = {flow_disc:+.2f} m3/h ({flow_bias_pct:.1f}% of measured), "
        f"head = {head_disc:+.2f} m ({head_bias_pct:.1f}% of measured).",
        f"If the flow gauge is rated ±{flow_gauge_accuracy_pct}% of reading, "
        f"the {'entire flow discrepancy fits within gauge error.' if flow_ok_2 else f'flow discrepancy exceeds gauge error (±{flow_gauge_accuracy_pct}%).'}",
        f"If the pressure gauges are rated ±{pressure_gauge_accuracy_pct}% of reading, "
        f"the {'entire head discrepancy fits within gauge error.' if head_ok_2 else f'head discrepancy exceeds gauge error (±{pressure_gauge_accuracy_pct}%).'}",
    ]

    if not flow_ok_2 and not flow_ok_5:
        notes.append(
            f"Flow discrepancy ({flow_bias_pct:.1f}%) exceeds even a ±5% gauge band, suggesting a real process deviation "
            f"or systematic calibration drift rather than normal measurement scatter."
        )
    if not head_ok_2 and not head_ok_5:
        notes.append(
            f"Head discrepancy ({head_bias_pct:.1f}%) exceeds both ±2% and ±5% gauge bands. "
            f"Verify tap blockages, gauge zero, and elevation corrections before concluding pump performance loss."
        )
    if likely and (flow_ok_2 or head_ok_2):
        notes.append(
            "At least one discrepancy fits within standard instrument accuracy; "
            "the deviation may be attributable to normal measurement uncertainty rather than true pump degradation."
        )

    return InstrumentBiasScreen(
        measured_flow_m3_h=measured_flow_m3_h,
        measured_head_m=measured_head_m,
        expected_flow_m3_h=expected_flow_m3_h,
        expected_head_m=expected_head_m,
        flow_discrepancy_m3_h=flow_disc,
        head_discrepancy_m=head_disc,
        flow_bias_pct=flow_bias_pct,
        head_bias_pct=head_bias_pct,
        flow_explainable_with_2pct_gauge=flow_ok_2,
        head_explainable_with_2pct_gauge=head_ok_2,
        flow_explainable_with_5pct_gauge=flow_ok_5,
        head_explainable_with_5pct_gauge=head_ok_5,
        likely_explainable=likely,
        notes=notes,
    )


def compare_measured_point_to_curve(
    curve: PumpCurveModel,
    measured_flow_m3_h: float,
    measured_head_m: float,
    head_tolerance_fraction: float = 0.05,
    minimum_head_tolerance_m: float = 1.0,
) -> PumpCurveMeasuredPointComparison:
    if measured_flow_m3_h < 0.0:
        raise ValueError("Measured flow must be zero or greater.")
    if head_tolerance_fraction < 0.0:
        raise ValueError("Head tolerance fraction must be zero or greater.")
    if minimum_head_tolerance_m < 0.0:
        raise ValueError("Minimum head tolerance must be zero or greater.")

    min_flow = curve.points[0].flow_m3_h
    max_flow = curve.points[-1].flow_m3_h
    curve_head_m = interpolate_pump_head(curve, measured_flow_m3_h)
    flow_fraction = measured_flow_m3_h / max(max_flow, 1.0e-12)
    notes: list[str] = [
        "Measured-point diagnosis compares the field flow/head pair against the selected pump curve at the same flow.",
        "Treat curve mismatch as a troubleshooting screen until instrument calibration, liquid properties, and vendor test basis are confirmed.",
    ]

    if curve_head_m is None:
        if measured_flow_m3_h < min_flow:
            status = "below_curve_flow_range"
            notes.append("Measured flow sits below the first curve point; compare against a lower-flow/shutoff region before diagnosing wear or suction issues.")
        else:
            status = "above_curve_flow_range"
            notes.append("Measured flow sits above the last curve point; extend the curve or confirm the actual operating point before drawing conclusions.")
        return PumpCurveMeasuredPointComparison(
            measured_flow_m3_h=measured_flow_m3_h,
            measured_head_m=measured_head_m,
            curve_head_m=None,
            head_delta_m=None,
            head_delta_pct_of_curve=None,
            flow_fraction_of_curve_max=flow_fraction,
            status=status,
            notes=notes,
        )

    head_delta_m = measured_head_m - curve_head_m
    tolerance_m = max(abs(curve_head_m) * head_tolerance_fraction, minimum_head_tolerance_m)
    head_delta_pct = head_delta_m / max(abs(curve_head_m), 1.0e-9)
    if abs(head_delta_m) <= tolerance_m:
        status = "near_curve"
        notes.append(
            f"Measured head is within ±{tolerance_m:.2f} m of the selected curve at this flow, which is a reasonable first-pass match."
        )
    elif head_delta_m < 0.0:
        status = "below_curve"
        notes.append(
            "Measured head falls below the selected curve at this flow; practical causes can include lower actual speed, worn/trimmed impeller, suction starvation, entrained gas, reverse rotation, or pressure-basis/instrument error."
        )
    else:
        status = "above_curve"
        notes.append(
            "Measured head sits above the selected curve at this flow; recheck gauge basis, curve selection, throttling/system resistance assumptions, and whether the installed impeller or speed differs from the curve basis."
        )

    if flow_fraction > 1.0:
        notes.append("Measured flow is beyond 100% of the selected curve max flow; mismatch diagnosis is weak until the curve range is extended.")
    elif flow_fraction > 0.9:
        notes.append("Measured flow is near the far right end of the selected curve, where small flow-measurement error can swing the expected head materially.")

    return PumpCurveMeasuredPointComparison(
        measured_flow_m3_h=measured_flow_m3_h,
        measured_head_m=measured_head_m,
        curve_head_m=curve_head_m,
        head_delta_m=head_delta_m,
        head_delta_pct_of_curve=head_delta_pct,
        flow_fraction_of_curve_max=flow_fraction,
        status=status,
        notes=notes,
    )
