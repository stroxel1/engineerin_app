"""Heat exchanger screening helpers — LMTD, F-factor, duty, and UA sizing.

These are lightweight field approximations suitable for quick plant
troubleshooting.  They are not intended for detailed mechanical design
or TEMA specification work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Simple data containers
# ---------------------------------------------------------------------------

@dataclass
class LMTDResult:
    """Log-mean temperature difference for a single-pass counter-current HX."""
    thot_in: float       # °C, hot inlet
    thot_out: float      # °C, hot outlet
    tcold_in: float      # °C, cold inlet
    tcold_out: float     # °C, cold outlet
    dt1: float           # °C, temperature difference at one end
    dt2: float           # °C, temperature difference at the other end
    lmtd: float          # °C, log-mean temperature difference
    approach_warn: bool  # True if approach < 3 °C
    cross_warn: bool     # True if temperature cross detected
    notes: list[str]


@dataclass
class FFactorResult:
    """Correction factor F for multi-pass shell-and-tube exchangers."""
    p: float             # Temperature effectiveness (0-1)
    r: float             # Heat capacity rate ratio
    f_factor: float      # Correction factor (typically 0.75-1.0)
    shell_passes: int
    tube_passes: int
    f_low_warn: bool     # True if F < 0.75 (poor design)
    notes: list[str]


@dataclass
class HXDutyResult:
    """Known UA and LMTD → duty, or known duty → required UA."""
    duty_kw: float
    ua_kw_per_k: float
    lmtd_c: float
    f_factor: float
    corrected_lmtd_c: float
    notes: list[str]


@dataclass
class HXSizingResult:
    """Required area and UA for a duty with screening LMTD and F-factor."""
    duty_kw: float
    lmtd_c: float
    f_factor: float
    corrected_lmtd_c: float
    assumed_u_w_m2k: float
    required_area_m2: float
    required_u_w_m2k: float   # If area is fixed, what U is needed?
    installed_area_m2: float | None
    area_utilization_fraction: float | None  # required / installed
    notes: list[str]


@dataclass
class HXPassComparisonResult:
    """Compare LMTD and F for multiple pass arrangements."""
    shell_passes: int
    tube_passes: int
    p: float
    r: float
    f_factor: float
    corrected_lmtd_c: float
    required_area_m2: float
    notes: list[str]


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

def calculate_lmtd(
    thot_in: float,
    thot_out: float,
    tcold_in: float,
    tcold_out: float,
    flow_arrangement: str = "counter",
) -> LMTDResult:
    """Compute LMTD for counter-current or co-current (parallel) flow."""
    if flow_arrangement.lower() in ("counter", "counter-current"):
        dt1 = thot_in - tcold_out
        dt2 = thot_out - tcold_in
    else:
        dt1 = thot_in - tcold_in
        dt2 = thot_out - tcold_out

    notes: list[str] = []
    cross_warn = False
    approach_warn = False

    if dt1 <= 0 or dt2 <= 0:
        cross_warn = True
        notes.append("Temperature cross detected — the chosen outlet temperatures may not be achievable in this flow arrangement.")
        lmtd = 0.0
    elif abs(dt1 - dt2) < 0.01:
        lmtd = dt1  # Avoid division by zero in log
    else:
        lmtd = (dt1 - dt2) / math.log(dt1 / dt2)

    approach = min(dt1, dt2) if dt1 > 0 and dt2 > 0 else min(dt1, dt2)
    if approach < 3.0 and not cross_warn:
        approach_warn = True
        notes.append(f"Approach temperature ({approach:.1f} °C) is very small — this may require excessive area or be impractical.")

    if not cross_warn and not approach_warn:
        notes.append("Counter-current flow gives the largest possible LMTD for the terminal temperatures.")
    if cross_warn:
        notes.append("A temperature cross makes LMTD undefined for single-pass arrangements. Consider a multi-pass or multipass shell-and-tube configuration.")

    return LMTDResult(
        thot_in=thot_in,
        thot_out=thot_out,
        tcold_in=tcold_in,
        tcold_out=tcold_out,
        dt1=dt1,
        dt2=dt2,
        lmtd=lmtd,
        approach_warn=approach_warn,
        cross_warn=cross_warn,
        notes=notes,
    )


def calculate_f_factor(
    p: float,
    r: float,
    shell_passes: int = 1,
    tube_passes: int = 2,
) -> FFactorResult:
    """F-factor correction for N-shell-pass, M-tube-pass exchangers (Bowman chart).

    Standard 1-2 formula (Kern / Bowman):
    W = sqrt(R^2 + 1)
    F = (W/(R-1)) * ln((1-P)/(1-P*R)) / ln((2/P - 1 - R + W) / (2/P - 1 - R - W))

    For multiple shell passes: F_N ≈ 1 - (1 - F_1)/N (Underwood approximation).
    """
    notes: list[str] = []
    f_low_warn = False

    if not (0.0 <= p <= 1.0):
        raise ValueError("Temperature effectiveness P must be between 0 and 1.")
    if r < 0:
        raise ValueError("Heat capacity ratio R cannot be negative.")

    if abs(p) < 1e-9:
        return FFactorResult(p=p, r=r, f_factor=1.0, shell_passes=shell_passes,
                            tube_passes=tube_passes, f_low_warn=False,
                            notes=["F = 1.0 — trivial case with negligible temperature effectiveness."])

    w = math.sqrt(r * r + 1.0)

    # Handle R = 1 as limit
    if abs(r - 1.0) < 1e-6:
        # Limit R → 1 gives F = P / ((1-P) * ln(2/(2-P) + ...))
        # Use R=1+eps for numerical stability
        r_use = 1.0 + 1e-6
        w = math.sqrt(r_use ** 2 + 1.0)
    else:
        r_use = r

    try:
        num_ratio = (1.0 - p) / (1.0 - p * r_use)
        if num_ratio <= 0:
            f1 = 0.5
            notes.append("F-factor: temperature cross prevents exact calculation — using approximation.")
        else:
            denom_top = 2.0 / p - 1.0 - r_use + w
            denom_bot = 2.0 / p - 1.0 - r_use - w
            if denom_top * denom_bot <= 0:
                f1 = 0.5
                notes.append("F-factor: log argument invalid — using approximation.")
            else:
                ln_num = math.log(num_ratio)
                ln_den = math.log(denom_top / denom_bot)
                if abs(ln_den) < 1e-12 or r_use == 1.0:
                    # R ≈ 1 special case
                    f1 = p / ((1.0 - p) * math.log(2 / (2.0 - p))) if abs(1.0 - p) > 1e-9 else 1.0
                else:
                    f1 = (w / (r_use - 1.0)) * ln_num / ln_den
    except (ValueError, ZeroDivisionError):
        f1 = 0.5
        notes.append("F-factor: numerical error — using approximation.")

    # Multiple shell pass correction
    if shell_passes > 1:
        f_use = 1.0 - (1.0 - max(f1, 0.0)) / shell_passes
    else:
        f_use = f1

    f_use = max(0.0, min(f_use, 1.0))

    if f_use < 0.75:
        f_low_warn = True
        notes.append(f"F-factor ({f_use:.3f}) is below 0.75 — not recommended. Consider adding shell passes or changing temperatures.")
    elif f_use < 0.85:
        notes.append(f"F-factor ({f_use:.3f}) is marginal but acceptable for screening.")
    else:
        notes.append(f"F-factor ({f_use:.3f}) is good for {shell_passes}-{tube_passes} arrangement.")

    return FFactorResult(
        p=p, r=r, f_factor=round(f_use, 4),
        shell_passes=shell_passes, tube_passes=tube_passes,
        f_low_warn=f_low_warn, notes=notes,
    )


def calculate_hx_duty(
    duty_kw: float | None = None,
    ua_kw_per_k: float | None = None,
    lmtd_c: float | None = None,
    f_factor: float = 1.0,
) -> HXDutyResult:
    """Compute the missing piece of Q = U·A·LMTD·F.

    Provide any two of (duty_kw, ua_kw_per_k, lmtd_c) and the third is solved.
    """
    notes: list[str] = []
    provided = sum(x is not None for x in [duty_kw, ua_kw_per_k, lmtd_c])
    if provided != 2:
        raise ValueError("Exactly two of duty_kw, ua_kw_per_k, and lmtd_c must be provided.")

    if duty_kw is None:
        lmtd_val = lmtd_c if lmtd_c is not None else 0.0
        ua_val = ua_kw_per_k if ua_kw_per_k is not None else 0.0
        duty_kw = ua_val * lmtd_val * f_factor
        notes.append(f"Duty calculated from U·A ({ua_val:.2f} kW/K) × corrected LMTD: {duty_kw:.1f} kW.")
    elif ua_kw_per_k is None:
        if duty_kw <= 0:
            raise ValueError("Duty must be positive when solving for U·A.")
        lmtd_val = lmtd_c if lmtd_c is not None else 0.0
        if lmtd_val * f_factor <= 0:
            raise ValueError("Corrected LMTD must be positive when solving for U·A.")
        ua_kw_per_k = duty_kw / (lmtd_val * f_factor)
        notes.append(f"Required U·A: {ua_kw_per_k:.2f} kW/K for duty {duty_kw:.1f} kW.")
    else:
        if ua_kw_per_k <= 0:
            raise ValueError("U·A must be positive.")
        ua_val = ua_kw_per_k
        ua_val = max(ua_val, 1e-9)
        lmtd_val = duty_kw / (ua_val * f_factor)
        lmtd_c = lmtd_val
        notes.append(f"Required LMTD: {lmtd_val:.2f} °C for duty {duty_kw:.1f} kW with U·A {ua_val:.2f} kW/K.")

    corrected_lmtd = (lmtd_c if lmtd_c is not None else 0.0) * f_factor

    return HXDutyResult(
        duty_kw=duty_kw,
        ua_kw_per_k=ua_kw_per_k if ua_kw_per_k is not None else 0.0,
        lmtd_c=lmtd_c if lmtd_c is not None else 0.0,
        f_factor=f_factor,
        corrected_lmtd_c=corrected_lmtd,
        notes=notes,
    )


def size_heat_exchanger(
    thot_in: float,
    thot_out: float,
    tcold_in: float,
    tcold_out: float,
    duty_kw: float,
    assumed_u_w_m2k: float = 800.0,
    shell_passes: int = 1,
    tube_passes: int = 2,
    installed_area_m2: float | None = None,
) -> HXSizingResult:
    """Screen a heat exchanger area and U given terminal temperatures and duty.

    Steps:
    1. Compute LMTD from terminal temperatures (counter-current).
    2. Compute F-factor for the specified pass arrangement.
    3. Solve for required area: A = Q / (U · LMTD · F).
    4. Optionally check against installed area and report utilization.
    """
    notes: list[str] = []

    lmtd_result = calculate_lmtd(thot_in, thot_out, tcold_in, tcold_out)
    notes.extend(lmtd_result.notes)

    if lmtd_result.cross_warn:
        raise ValueError(
            "Temperature cross detected — cannot size a heat exchanger for these terminal temperatures "
            "in a single-pass arrangement. Adjust outlet temperatures or change flow arrangement."
        )

    # Temperature effectiveness P and heat capacity ratio R
    dt_max = thot_in - tcold_in if thot_in > tcold_in else tcold_in - thot_in
    if dt_max <= 0:
        raise ValueError("No temperature difference available to drive heat transfer.")

    p = (tcold_out - tcold_in) / dt_max
    r = (thot_in - thot_out) / (tcold_out - tcold_in) if abs(tcold_out - tcold_in) > 1e-9 else 0.0
    r = max(r, 0.0)

    f_result = calculate_f_factor(p, r, shell_passes, tube_passes)
    notes.extend(f_result.notes)

    lmtd_c = lmtd_result.lmtd
    f_factor = f_result.f_factor
    corrected_lmtd = lmtd_c * f_factor

    if corrected_lmtd <= 0:
        raise ValueError("Corrected LMTD is zero or negative — exchanger cannot meet the specified duty.")
    if duty_kw <= 0:
        raise ValueError("Heat duty must be positive.")
    if assumed_u_w_m2k <= 0:
        assumed_u_w_m2k = 500.0
        notes.append("Invalid U value entered, defaulting to 500 W/m²·K for screening.")

    u_w_m2k = assumed_u_w_m2k
    duty_w = duty_kw * 1000.0
    required_area = duty_w / (u_w_m2k * corrected_lmtd)

    area_util = None
    if installed_area_m2 is not None and installed_area_m2 > 0:
        area_util = required_area / installed_area_m2
        if area_util > 1.0:
            notes.append(
                f"Required area ({required_area:.1f} m²) exceeds installed ({installed_area_m2:.1f} m²) — the existing exchanger may not reach the target duty."
            )
        elif area_util < 0.7:
            notes.append(
                f"Installed area is significantly oversized ({installed_area_m2:.1f} m² vs {required_area:.1f} m² required) — check whether the exchanger is being operated at reduced capacity."
            )
        else:
            notes.append(f"Area utilization: {area_util*100:.1f}% of installed ({installed_area_m2:.1f} m²).")

    required_u = (duty_w / (installed_area_m2 * corrected_lmtd)) if installed_area_m2 and installed_area_m2 > 0 else 0.0

    return HXSizingResult(
        duty_kw=duty_kw,
        lmtd_c=lmtd_c,
        f_factor=f_factor,
        corrected_lmtd_c=corrected_lmtd,
        assumed_u_w_m2k=u_w_m2k,
        required_area_m2=required_area,
        required_u_w_m2k=required_u,
        installed_area_m2=installed_area_m2,
        area_utilization_fraction=area_util,
        notes=notes,
    )


def compare_pass_arrangements(
    thot_in: float,
    thot_out: float,
    tcold_in: float,
    tcold_out: float,
    duty_kw: float,
    u_w_m2k: float = 800.0,
) -> list[HXPassComparisonResult]:
    """Compare 1-2, 2-4, and 3-6 pass arrangements for a given duty."""
    lmtd_result = calculate_lmtd(thot_in, thot_out, tcold_in, tcold_out)
    lmtd_c = lmtd_result.lmtd

    dt_max = thot_in - tcold_in if thot_in > tcold_in else tcold_in - thot_in
    p = (tcold_out - tcold_in) / dt_max if dt_max > 0 else 0.0
    r = (thot_in - thot_out) / (tcold_out - tcold_in) if abs(tcold_out - tcold_in) > 1e-9 else 0.0
    r = max(r, 0.0)

    arrangements = [(1, 2), (2, 4), (3, 6)]
    results = []
    for n_shell, n_tube in arrangements:
        f_res = calculate_f_factor(p, r, n_shell, n_tube)
        corrected_lmtd = lmtd_c * f_res.f_factor
        duty_w = duty_kw * 1000.0
        area = duty_w / (u_w_m2k * corrected_lmtd) if corrected_lmtd > 0 else float('inf')
        notes = f_res.notes.copy()
        if corrected_lmtd > 0:
            notes.append(f"Required area: {area:.1f} m² at U={u_w_m2k:.0f} W/m²·K, LMTD={lmtd_c:.1f}°C, F={f_res.f_factor:.3f}.")
        results.append(
            HXPassComparisonResult(
                shell_passes=n_shell,
                tube_passes=n_tube,
                p=p,
                r=r,
                f_factor=f_res.f_factor,
                corrected_lmtd_c=corrected_lmtd,
                required_area_m2=area,
                notes=notes,
            )
        )
    return results
