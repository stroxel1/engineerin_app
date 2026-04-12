"""Curve ingestion and interpolation helpers for steam-jet and thermo-compressor work."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CurvePoint:
    x: float
    y: float
    meta: Dict[str, float] = field(default_factory=dict)


@dataclass
class PerformanceCurve:
    name: str
    x_label: str
    y_label: str
    points: List[CurvePoint]
    family: Optional[str] = None
    source_sheet: Optional[str] = None


@dataclass
class CurveLibrary:
    curves: List[PerformanceCurve] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def list_names(self) -> List[str]:
        return [curve.name for curve in self.curves]


@dataclass
class CurveOperatingPointResult:
    x_value: float
    predicted_y: float
    actual_y: float
    percent_of_curve: float
    deviation_pct: float
    in_envelope: bool
    notes: list[str]


@dataclass
class CurveComparisonRow:
    curve_name: str
    family: Optional[str]
    source_sheet: Optional[str]
    predicted_y: float
    actual_y: float
    percent_of_curve: float
    deviation_pct: float
    in_envelope: bool


def sort_curve_points(points: List[CurvePoint]) -> List[CurvePoint]:
    return sorted(points, key=lambda point: point.x)


def interpolate_y(curve: PerformanceCurve, x_value: float) -> float:
    points = sort_curve_points(curve.points)
    if len(points) < 2:
        raise ValueError("At least two curve points are required for interpolation")

    if x_value <= points[0].x:
        p1, p2 = points[0], points[1]
    elif x_value >= points[-1].x:
        p1, p2 = points[-2], points[-1]
    else:
        p1, p2 = points[0], points[1]
        for left, right in zip(points, points[1:]):
            if left.x <= x_value <= right.x:
                p1, p2 = left, right
                break

    if p2.x == p1.x:
        return p1.y
    slope = (p2.y - p1.y) / (p2.x - p1.x)
    return p1.y + slope * (x_value - p1.x)


def evaluate_operating_point(curve: PerformanceCurve, x_value: float, actual_y: float) -> CurveOperatingPointResult:
    points = sort_curve_points(curve.points)
    predicted_y = interpolate_y(curve, x_value)
    x_min = points[0].x
    x_max = points[-1].x
    in_envelope = x_min <= x_value <= x_max
    percent_of_curve = 100.0 * actual_y / max(predicted_y, 1e-9)
    deviation_pct = 100.0 * (actual_y - predicted_y) / max(predicted_y, 1e-9)

    notes: list[str] = []
    if not in_envelope:
        notes.append("Operating x-value is outside the available curve envelope; result is extrapolated.")
    if percent_of_curve < 90.0:
        notes.append("Actual performance is materially below the curve estimate.")
    elif percent_of_curve > 110.0:
        notes.append("Actual performance is materially above the curve estimate; check basis and units.")
    else:
        notes.append("Actual performance is reasonably close to the curve estimate.")

    return CurveOperatingPointResult(
        x_value=x_value,
        predicted_y=predicted_y,
        actual_y=actual_y,
        percent_of_curve=percent_of_curve,
        deviation_pct=deviation_pct,
        in_envelope=in_envelope,
        notes=notes,
    )


def make_curve_from_xy_rows(
    name: str,
    x_label: str,
    y_label: str,
    rows: List[dict],
    family: Optional[str] = None,
    source_sheet: Optional[str] = None,
) -> PerformanceCurve:
    points: List[CurvePoint] = []
    for row in rows:
        try:
            x_value = float(row[x_label])
            y_value = float(row[y_label])
        except (KeyError, TypeError, ValueError):
            continue
        meta = {k: v for k, v in row.items() if k not in {x_label, y_label}}
        points.append(CurvePoint(x=x_value, y=y_value, meta=meta))

    if len(points) < 2:
        raise ValueError("At least two numeric x/y rows are required to build a performance curve")

    return PerformanceCurve(
        name=name,
        x_label=x_label,
        y_label=y_label,
        points=sort_curve_points(points),
        family=family,
        source_sheet=source_sheet,
    )


def build_curve_library_from_table(
    rows: List[dict],
    x_label: str,
    y_label: str,
    curve_name_label: str,
    family_label: Optional[str] = None,
    source_sheet: Optional[str] = None,
) -> CurveLibrary:
    grouped_rows: Dict[tuple[str, Optional[str]], List[dict]] = {}
    for row in rows:
        curve_name = row.get(curve_name_label)
        if curve_name in (None, ""):
            continue
        family = row.get(family_label) if family_label else None
        key = (str(curve_name), None if family in (None, "") else str(family))
        grouped_rows.setdefault(key, []).append(row)

    curves: List[PerformanceCurve] = []
    for (curve_name, family), curve_rows in grouped_rows.items():
        try:
            curves.append(
                make_curve_from_xy_rows(
                    name=curve_name,
                    x_label=x_label,
                    y_label=y_label,
                    rows=curve_rows,
                    family=family,
                    source_sheet=source_sheet,
                )
            )
        except ValueError:
            continue

    return CurveLibrary(curves=curves)


def compare_curves_at_point(curves: List[PerformanceCurve], x_value: float, actual_y: float) -> List[CurveComparisonRow]:
    comparison: List[CurveComparisonRow] = []
    for curve in curves:
        result = evaluate_operating_point(curve, x_value, actual_y)
        comparison.append(
            CurveComparisonRow(
                curve_name=curve.name,
                family=curve.family,
                source_sheet=curve.source_sheet,
                predicted_y=result.predicted_y,
                actual_y=result.actual_y,
                percent_of_curve=result.percent_of_curve,
                deviation_pct=result.deviation_pct,
                in_envelope=result.in_envelope,
            )
        )
    comparison.sort(key=lambda row: abs(row.deviation_pct))
    return comparison
