"""Pipe-dimension presets and fitting K-value libraries for practical plant hydraulics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipeSpec:
    schedule_label: str
    nps_in: float
    display_name: str
    outside_diameter_in: float
    inside_diameter_in: float
    wall_thickness_in: float


@dataclass(frozen=True)
class FittingSpec:
    key: str
    display_name: str
    k_value: float
    notes: str = ""


SCHEDULE_10S_STAINLESS: tuple[PipeSpec, ...] = (
    PipeSpec("10S", 0.5, '1/2"', 0.840, 0.674, 0.083),
    PipeSpec("10S", 0.75, '3/4"', 1.050, 0.884, 0.083),
    PipeSpec("10S", 1.0, '1"', 1.315, 1.097, 0.109),
    PipeSpec("10S", 1.25, '1-1/4"', 1.660, 1.442, 0.109),
    PipeSpec("10S", 1.5, '1-1/2"', 1.900, 1.682, 0.109),
    PipeSpec("10S", 2.0, '2"', 2.375, 2.157, 0.109),
    PipeSpec("10S", 2.5, '2-1/2"', 2.875, 2.635, 0.120),
    PipeSpec("10S", 3.0, '3"', 3.500, 3.260, 0.120),
    PipeSpec("10S", 4.0, '4"', 4.500, 4.260, 0.120),
    PipeSpec("10S", 5.0, '5"', 5.563, 5.295, 0.134),
    PipeSpec("10S", 6.0, '6"', 6.625, 6.357, 0.134),
    PipeSpec("10S", 8.0, '8"', 8.625, 8.329, 0.148),
    PipeSpec("10S", 10.0, '10"', 10.750, 10.420, 0.165),
    PipeSpec("10S", 12.0, '12"', 12.750, 12.390, 0.180),
)

COMMON_FITTINGS: tuple[FittingSpec, ...] = (
    FittingSpec("90_elbow", "90° elbow", 0.90, "Standard-radius elbow screening value."),
    FittingSpec("45_elbow", "45° elbow", 0.40, "Standard fitting screening value."),
    FittingSpec("tee_through", "Straight-through tee", 0.60, "Through-run tee estimate."),
    FittingSpec("tee_branch", "Branch tee", 1.80, "Branch-flow tee estimate."),
    FittingSpec("gate_valve", "Gate valve (open)", 0.15, "Fully open gate valve."),
    FittingSpec("ball_valve", "Ball valve (open)", 0.05, "Full-port ball valve screening value."),
    FittingSpec("globe_valve", "Globe valve (open)", 10.0, "Very high-loss control/isolation valve."),
    FittingSpec("swing_check", "Swing check valve", 2.0, "Quick screening value for swing checks."),
    FittingSpec("lift_check", "Lift check valve", 10.0, "Higher-loss check style screening value."),
    FittingSpec("butterfly_valve", "Butterfly valve (open)", 0.80, "Typical open butterfly screening value."),
)


def get_schedule_10s_map() -> dict[str, PipeSpec]:
    return {spec.display_name: spec for spec in SCHEDULE_10S_STAINLESS}


def get_common_fittings_map() -> dict[str, FittingSpec]:
    return {spec.key: spec for spec in COMMON_FITTINGS}
