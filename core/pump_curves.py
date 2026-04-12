from __future__ import annotations

from dataclasses import dataclass


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
