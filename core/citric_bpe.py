"""Citric-acid boiling-point elevation helpers.

This module uses the workbook-derived 15-60 wt% table from Stephen's
`citric_bpe.xlsx` and exposes a provisional high-solids estimate above 60 wt%.
The >60 wt% method is intentionally flagged as a workbook-derived estimate that
should be treated cautiously until validated further.
"""

from __future__ import annotations

from dataclasses import dataclass

from engineering_app.core.thermal import build_thermal_point
from engineering_app.core.units import pressure_to_kpa_abs

CITRIC_BPE_TABLE_F: tuple[tuple[float, float], ...] = (
    (15.0, 0.60), (16.0, 0.81), (17.0, 1.01), (18.0, 1.22), (19.0, 1.43),
    (20.0, 1.64), (21.0, 1.84), (22.0, 2.05), (23.0, 2.26), (24.0, 2.46),
    (25.0, 2.67), (26.0, 2.88), (27.0, 3.08), (28.0, 3.29), (29.0, 3.50),
    (30.0, 3.70), (31.0, 3.91), (32.0, 4.12), (33.0, 4.32), (34.0, 4.53),
    (35.0, 4.74), (36.0, 4.94), (37.0, 5.15), (38.0, 5.36), (39.0, 5.56),
    (40.0, 5.77), (41.0, 5.98), (42.0, 6.18), (43.0, 6.39), (44.0, 6.60),
    (45.0, 6.80), (46.0, 7.01), (47.0, 7.22), (48.0, 7.42), (49.0, 7.63),
    (50.0, 7.84), (51.0, 8.04), (52.0, 8.25), (53.0, 8.47), (54.0, 8.68),
    (55.0, 8.89), (56.0, 9.09), (57.0, 9.30), (58.0, 9.51), (59.0, 9.71),
    (60.0, 9.92),
)


@dataclass
class CitricBPEResult:
    ds_wt_pct: float
    pressure_kpa_abs: float
    saturation_temperature_c: float
    boiling_temperature_c: float
    bpe_c: float
    bpe_f: float
    method: str
    notes: list[str]


@dataclass
class CitricCapacityImpactResult:
    steam_temperature_c: float
    saturation_temperature_c: float
    current_bpe_c: float
    new_bpe_c: float
    current_delta_t_c: float
    new_delta_t_c: float
    relative_capacity_change_pct: float
    notes: list[str]


TABLE_MIN_DS = CITRIC_BPE_TABLE_F[0][0]
TABLE_MAX_DS = CITRIC_BPE_TABLE_F[-1][0]
TABLE_MAX_BPE_F = CITRIC_BPE_TABLE_F[-1][1]


def _f_to_c(delta_f: float) -> float:
    return delta_f * 5.0 / 9.0


def _c_to_f(delta_c: float) -> float:
    return delta_c * 9.0 / 5.0


def interpolate_table_bpe_f(ds_wt_pct: float) -> float:
    ds = float(ds_wt_pct)
    table = CITRIC_BPE_TABLE_F
    if ds <= table[0][0]:
        x1, y1 = table[0]
        x2, y2 = table[1]
    elif ds >= table[-1][0]:
        x1, y1 = table[-2]
        x2, y2 = table[-1]
    else:
        x1 = y1 = x2 = y2 = 0.0
        for left, right in zip(table, table[1:]):
            if left[0] <= ds <= right[0]:
                x1, y1 = left
                x2, y2 = right
                break
    if x2 == x1:
        return y1
    return y1 + (y2 - y1) * (ds - x1) / (x2 - x1)


def workbook_high_solids_bpe_f(ds_wt_pct: float) -> float:
    ds = float(ds_wt_pct)
    return 0.85 * ds - 17.0


def estimate_citric_bpe(
    ds_wt_pct: float,
    pressure_value: float,
    pressure_unit: str,
    method: str = "auto",
) -> CitricBPEResult:
    ds = float(ds_wt_pct)
    pressure_kpa_abs = pressure_to_kpa_abs(pressure_value, pressure_unit)

    notes: list[str] = []
    if method == "table" or (method == "auto" and ds <= TABLE_MAX_DS):
        bpe_f = interpolate_table_bpe_f(ds)
        result_method = "table_interpolated"
        if ds < TABLE_MIN_DS or ds > TABLE_MAX_DS:
            notes.append("DS is outside the workbook table range; table value is extrapolated.")
    elif method in {"high_solids", "auto"}:
        bpe_f = workbook_high_solids_bpe_f(ds)
        result_method = "workbook_high_solids_estimate"
        notes.append("Above 60 wt% uses the workbook's provisional high-solids estimate.")
        notes.append("The workbook explicitly advises caution beyond the cited 15-59.9 wt% range.")
        notes.append("This high-solids equation is discontinuous with the 60 wt% table value and should be treated as a screening estimate, not validated design data.")
    else:
        raise ValueError(f"Unsupported citric BPE method: {method}")

    bpe_c = _f_to_c(bpe_f)
    thermal_point = build_thermal_point(pressure_value, pressure_unit, bpe_c)
    if ds >= 60.0:
        notes.append("Citric acid behavior above about 60 wt% may steepen due to strong non-ideal / bound-water effects.")

    return CitricBPEResult(
        ds_wt_pct=ds,
        pressure_kpa_abs=pressure_kpa_abs,
        saturation_temperature_c=thermal_point.saturation_temperature_c,
        boiling_temperature_c=thermal_point.boiling_temperature_c,
        bpe_c=bpe_c,
        bpe_f=bpe_f,
        method=result_method,
        notes=notes,
    )


def estimate_capacity_impact_from_bpe(
    steam_temperature_c: float,
    pressure_value: float,
    pressure_unit: str,
    current_bpe_c: float,
    new_bpe_c: float,
) -> CitricCapacityImpactResult:
    thermal_point = build_thermal_point(pressure_value, pressure_unit, 0.0)
    sat_temp = thermal_point.saturation_temperature_c
    current_delta_t = steam_temperature_c - (sat_temp + current_bpe_c)
    new_delta_t = steam_temperature_c - (sat_temp + new_bpe_c)
    relative_capacity_change_pct = 100.0 * (new_delta_t / max(current_delta_t, 1e-9) - 1.0)
    notes = [
        "Capacity impact is screened from available delta-T only.",
        "This does not independently adjust U, viscosity, or fouling behavior.",
    ]
    if new_bpe_c > current_bpe_c:
        notes.append("Higher BPE reduces available driving force and generally reduces evaporation capacity.")
    return CitricCapacityImpactResult(
        steam_temperature_c=steam_temperature_c,
        saturation_temperature_c=sat_temp,
        current_bpe_c=current_bpe_c,
        new_bpe_c=new_bpe_c,
        current_delta_t_c=current_delta_t,
        new_delta_t_c=new_delta_t,
        relative_capacity_change_pct=relative_capacity_change_pct,
        notes=notes,
    )
