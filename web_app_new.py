from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

# ---------------------------------------------------------------------------
# Bootstrap: make 'engineering_app' package importable regardless of the
# directory name used by the host (local dev, PyInstaller, Streamlit Cloud).
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_PARENT_DIR = _THIS_DIR.parent

if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

# Streamlit Cloud may clone the repo under an arbitrary directory name.
# If the folder isn't literally called "engineering_app", register this
# directory as the engineering_app package so absolute imports still resolve.
if _THIS_DIR.name != "engineering_app":
    import types as _types
    _pkg = _types.ModuleType("engineering_app")
    _pkg.__path__ = [str(_THIS_DIR)]
    _pkg.__file__ = str(_THIS_DIR / "__init__.py")
    sys.modules.setdefault("engineering_app", _pkg)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from engineering_app.core.cases import CaseStore
from engineering_app.core.citric_bpe import estimate_capacity_impact_from_bpe, estimate_citric_bpe
from engineering_app.core.crystallizers import (
    CrystallizerInputs,
    estimate_citric_solubility_wt_pct,
    estimate_crystallizer,
    estimate_multi_body_crystallizer,
    MultiBodyCrystallizerInputs,
)
from engineering_app.core.solubility_curve import (
    estimate_metastable_zone,
    fit_solubility_polynomial,
    generate_solubility_curve,
    predict_crystallizer_yield_sweep,
    solubility_table_points,
)
from engineering_app.core.curves import (
    build_curve_library_from_table,
    compare_curves_at_point,
    evaluate_operating_point,
    make_curve_from_xy_rows,
)
from engineering_app.core.evaporators import (
    BodyByBodyEffectInput,
    BodyByBodyFeedConfig,
    EvaporatorDesignCalibrationInputs,
    EvaporatorInputs,
    FoulingAllowanceInputs,
    estimate_body_by_body_evaporation,
    estimate_design_calibrated_evaporation,
    estimate_evaporation,
    estimate_multi_effect_evaporation,
    evaluate_fouling_and_ncg_allowance,
)
from engineering_app.core.hydraulics import (
    PipeSegment,
    analyze_parallel_branches,
    analyze_pump_field_check,
    build_system_curve,
    calculate_hydraulics_with_units,
    calculate_pump_power,
    calculate_segmented_system,
    calculate_vessel_static_head,
    compare_pump_field_cases,
    compare_schedule_10s_sizes,
    estimate_npsha,
    find_pump_system_intersection,
    screen_suction_vessel_npsha,
    fitting_k_from_counts,
    recommend_schedule_10s_size,
    size_branch_balancing_device,
    size_control_valve,
)

from engineering_app.core.pipe_data import COMMON_FITTINGS, SCHEDULE_10S_STAINLESS
from engineering_app.core.pump_curves import (
    available_builtin_curve_options,
    assess_bep_proximity,
    build_curve_from_xy_rows as build_pump_curve_from_xy_rows,
    compare_measured_point_to_curve,
    estimate_bep_from_curve,
    find_curve_system_intersection,
    get_builtin_curve,
    screen_affinity_rerate,
    screen_instrument_bias,
)
from engineering_app.core.quicktools import (
    brix_reconciliation,
    dilution_water,
    electricity_cost,
    electricity_cost_comparison,
    flash_fraction,
    pressure_conversion,
    ratio_target_blend,
    solution_properties,
    steam_cost,
    steam_cost_comparison,
    steam_for_duty,
    tank_inventory,
    temperature_conversion,
    thermal_point,
    two_stream_blend,
)
from engineering_app.core.solutions import PRODUCT_PROFILES
from engineering_app.core.steam import duty_from_steam_flow, evaluate_steam_header_pressure_change, thermo_compressor_balance
from engineering_app.core.units import (
    AREA_UNITS,
    DELTA_TEMPERATURE_UNITS,
    DENSITY_UNITS,
    ML_DENSITY_UNITS,
    HTC_UNITS,
    LENGTH_UNITS,
    MASS_FLOW_UNITS,
    PERCENT_UNITS,
    POWER_UNITS,
    PRESSURE_UNITS,
    SPECIFIC_ENERGY_UNITS,
    TEMPERATURE_UNITS,
    TIME_UNITS,
    VELOCITY_UNITS,
    VISCOSITY_UNITS,
    VOLUME_UNITS,
    VOLUMETRIC_FLOW_UNITS,
    area_to_m2,
    c_to_delta_temperature,
    c_to_temperature,
    cp_to_viscosity,
    htc_to_w_m2k,
    kg_h_to_mass_flow,
    kg_m3_to_density,
    kj_kg_to_specific_energy,
    ml_density_to_kg_m3,
    kpa_abs_to_pressure,
    kw_to_power,
    m2_to_area,
    m3_h_to_volumetric_flow,
    m3_to_volume,
    m_s_to_velocity,
    m_to_length,
    mass_flow_to_kg_h,
    pressure_to_kpa_abs,
    seconds_to_time,
    specific_energy_to_kj_kg,
    temperature_to_c,
    volume_to_m3,
    volumetric_flow_to_m3_h,
    w_m2k_to_htc,
    length_to_m,
    density_to_kg_m3,
    viscosity_to_cp,
    delta_temperature_to_c,
    power_to_kw,
)
from engineering_app.core.heat_exchangers import (
    compare_pass_arrangements,
    size_heat_exchanger,
    calculate_lmtd,
    calculate_f_factor,
)
from engineering_app.core.motors import (
    assess_motor_loading,
    calculate_motor_size,
    calculate_pump_motor,
    estimate_vfd_savings,
)
from engineering_app.io.normalizers import normalize_curve_workbook, normalize_inspection
from engineering_app.io.workbook_inspector import inspect_workbook

st.set_page_config(page_title="Engineering App", page_icon="⚙️", layout="wide")


def _clean_input_label(label: str) -> tuple[str, str | None]:
    text = str(label).strip()
    unit = None
    if "(" in text and ")" in text and text.rfind("(") < text.rfind(")"):
        start = text.rfind("(")
        end = text.rfind(")")
        unit = text[start + 1 : end].strip() or None
        text = (text[:start] + text[end + 1 :]).strip()
    text = " ".join(text.split())
    return text, unit


def _default_input_help(widget: str, label: object) -> str | None:
    if not isinstance(label, str):
        return None
    clean_label, unit = _clean_input_label(label)
    if not clean_label:
        return None

    if widget == "number_input":
        return f"Enter {clean_label} in {unit}." if unit else f"Enter {clean_label}."
    if widget == "text_input":
        return f"Type {clean_label}."
    if widget == "text_area":
        return f"Enter details for {clean_label}."
    if widget == "selectbox":
        return f"Select the option for {clean_label}."
    if widget == "multiselect":
        return f"Select one or more options for {clean_label}."
    if widget == "radio":
        return f"Choose one option for {clean_label}."
    if widget == "slider":
        return f"Adjust {clean_label}."
    if widget == "checkbox":
        return f"Enable or disable {clean_label}."
    if widget == "file_uploader":
        return f"Upload a file for {clean_label}."
    return f"Provide {clean_label}."


def _wrap_streamlit_input(widget_name: str) -> None:
    original = getattr(st, widget_name, None)
    if original is None:
        return

    def wrapped(*args, **kwargs):
        label = kwargs.get("label")
        if label is None and args:
            label = args[0]
        if "help" not in kwargs:
            generated = _default_input_help(widget_name, label)
            if generated:
                kwargs["help"] = generated
        return original(*args, **kwargs)

    setattr(st, widget_name, wrapped)


for _widget in (
    "number_input",
    "text_input",
    "text_area",
    "selectbox",
    "multiselect",
    "radio",
    "slider",
    "checkbox",
    "file_uploader",
):
    _wrap_streamlit_input(_widget)

PROJECT_ROOT = Path(__file__).resolve().parent
CASE_STORE = CaseStore(PROJECT_ROOT / "data" / "cases")
GENERIC_CURVE_UNITS = MASS_FLOW_UNITS + VOLUMETRIC_FLOW_UNITS + PRESSURE_UNITS + TEMPERATURE_UNITS + POWER_UNITS


def _show_notes(notes: list[str]) -> None:
    for note in notes:
        st.caption(f"- {note}")


def _title_case_status(status: str) -> str:
    """Convert underscore-separated status to title case for display."""
    return status.replace("_", " ").title()


def _remember_case(page: str, inputs: dict, result: dict) -> None:
    st.session_state["last_case_payload"] = {
        "page": page,
        "inputs": inputs,
        "result": result,
    }



def _pressure_delta_from_kpa(value_kpa: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "kpa":
        return value_kpa
    if u in {"psi", "psid", "psig"}:
        return value_kpa / 6.894757293168361
    if u in {"bar", "barg", "bara"}:
        return value_kpa / 100.0
    raise ValueError(f"Unsupported differential pressure unit: {unit}")


def _pressure_delta_to_kpa(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "kpa":
        return value
    if u in {"psi", "psid", "psig"}:
        return value * 6.894757293168361
    if u in {"bar", "barg", "bara"}:
        return value * 100.0
    raise ValueError(f"Unsupported differential pressure unit: {unit}")


def _head_m_to_delta_kpa(head_m: float, density_kg_m3: float) -> float:
    return density_kg_m3 * 9.80665 * head_m / 1000.0


def _delta_kpa_to_head_m(delta_kpa: float, density_kg_m3: float) -> float:
    return delta_kpa * 1000.0 / max(density_kg_m3 * 9.80665, 1.0e-12)



def _display_percent(value_fraction: float, unit: str) -> float:
    return value_fraction * 100.0 if unit == "%" else value_fraction



def _display_temperature(value_c: float, unit: str) -> float:
    return c_to_temperature(value_c, unit)



def _display_delta_t(value_c: float, unit: str) -> float:
    return c_to_delta_temperature(value_c, unit)


def render_quick_tools() -> None:
    st.header("Quick Tools")
    tabs = st.tabs(["Pressure", "Temperature", "Thermal Point", "Steam Flash", "Solution Properties", "Brix Reconciliation", "Dilution", "Two-Stream Blend", "Ratio-Target Blend", "Tank Inventory", "Utility Cost"])
    product_options = list(PRODUCT_PROFILES.keys())
    product_labels = {key: PRODUCT_PROFILES[key].display_name for key in product_options}

    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        value = c1.number_input("Pressure value", value=15.0, key="qt_pressure_value")
        from_unit = c2.selectbox("From unit", PRESSURE_UNITS, index=5, key="qt_pressure_from")
        to_unit = c3.selectbox("To unit", PRESSURE_UNITS, index=0, key="qt_pressure_to")
        result = pressure_conversion(value, from_unit, to_unit)
        st.metric("Converted pressure", f"{result:,.3f} {to_unit}")
        _remember_case("quick-tools-pressure", {"value": value, "from_unit": from_unit, "to_unit": to_unit}, {"converted_pressure": result, "output_unit": to_unit})

    with tabs[1]:
        c1, c2, c3 = st.columns(3)
        value = c1.number_input("Temperature value", value=212.0, key="qt_temp_value")
        from_unit = c2.selectbox("From unit", TEMPERATURE_UNITS, index=1, key="qt_temp_from")
        to_unit = c3.selectbox("To unit", TEMPERATURE_UNITS, index=0, key="qt_temp_to")
        result = temperature_conversion(value, from_unit, to_unit)
        st.metric("Converted temperature", f"{result:,.2f} °{to_unit}")
        _remember_case("quick-tools-temperature", {"value": value, "from_unit": from_unit, "to_unit": to_unit}, {"converted_temperature": result, "output_unit": to_unit})

    with tabs[2]:
        c1, c2, c3, c4 = st.columns(4)
        pressure_value = c1.number_input("Operating pressure", value=25.0, key="qt_tp_pressure")
        pressure_unit = c2.selectbox("Pressure basis", PRESSURE_UNITS, index=0, key="qt_tp_pressure_unit")
        bpe_value = c3.number_input("BPE", value=3.0, key="qt_tp_bpe")
        bpe_unit = c4.selectbox("BPE unit", DELTA_TEMPERATURE_UNITS, index=0, key="qt_tp_bpe_unit")
        output_temp_unit = st.selectbox("Output temperature unit", TEMPERATURE_UNITS, index=0, key="qt_tp_temp_out")
        point = thermal_point(pressure_value, pressure_unit, bpe_value if bpe_unit == "C" else bpe_value * 5.0 / 9.0)
        st.json(
            {
                "pressure": f"{kpa_abs_to_pressure(point.pressure_kpa_abs, pressure_unit):,.3f} {pressure_unit}",
                "saturation_temperature": f"{_display_temperature(point.saturation_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}",
                "boiling_temperature": f"{_display_temperature(point.boiling_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}",
                "condensing_temperature": f"{_display_temperature(point.condensing_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}",
                "bpe": f"{_display_delta_t(point.bpe_c, bpe_unit):,.2f} °{bpe_unit}",
            }
        )

    with tabs[3]:
        c1, c2, c3, c4 = st.columns(4)
        condensate_temp = c1.number_input("Condensate temperature", value=120.0, key="qt_flash_temp")
        temp_unit = c2.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="qt_flash_temp_unit")
        flash_pressure_value = c3.number_input("Flash pressure", value=10.0, key="qt_flash_pressure")
        flash_pressure_unit = c4.selectbox("Flash pressure unit", PRESSURE_UNITS, index=0, key="qt_flash_pressure_unit")
        c5, c6, c7 = st.columns(3)
        condensate_flow = c5.number_input("Condensate flow", value=10000.0, key="qt_flash_flow")
        condensate_flow_unit = c6.selectbox("Flow unit", MASS_FLOW_UNITS, index=0, key="qt_flash_flow_unit")
        output_flow_unit = c7.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="qt_flash_flow_out")
        temp_c = condensate_temp if temp_unit == "C" else (condensate_temp - 32.0) * 5.0 / 9.0
        condensate_flow_kg_h = condensate_flow if condensate_flow_unit == "kg/h" else None
        result = flash_fraction(temp_c, flash_pressure_value, flash_pressure_unit, mass_flow_to_kg_h(condensate_flow, condensate_flow_unit))
        m1, m2, m3 = st.columns(3)
        m1.metric("Flash fraction", f"{result.flash_fraction:.3f}")
        m2.metric("Flash steam", f"{kg_h_to_mass_flow(result.flash_steam_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m3.metric("Remaining liquid", f"{kg_h_to_mass_flow(result.remaining_liquid_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        _show_notes(result.notes)

    with tabs[4]:
        c1, c2, c3 = st.columns(3)
        product = c1.selectbox("Product", product_options, format_func=lambda key: product_labels[key], key="qt_solution_product")
        solids_wt_pct = c2.number_input("Solids concentration (wt%)", min_value=0.0, max_value=95.0, value=55.0, key="qt_solution_solids")
        temperature_value = c3.number_input("Solution temperature", value=45.0, key="qt_solution_temp")
        c4, c5, c6, c7 = st.columns(4)
        temperature_unit = c4.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="qt_solution_temp_unit")
        pressure_value = c5.number_input("Operating pressure", value=20.0, key="qt_solution_pressure")
        pressure_unit = c6.selectbox("Pressure unit", PRESSURE_UNITS, index=0, key="qt_solution_pressure_unit")
        flow_value = c7.number_input("Optional solution flow", min_value=0.0, value=12000.0, key="qt_solution_flow")
        c8, c9, c10, c11 = st.columns(4)
        flow_unit = c8.selectbox("Flow unit", MASS_FLOW_UNITS, index=0, key="qt_solution_flow_unit")
        density_unit = c9.selectbox("Density output unit", DENSITY_UNITS, index=0, key="qt_solution_density_out")
        bpe_unit = c10.selectbox("BPE output unit", DELTA_TEMPERATURE_UNITS, index=0, key="qt_solution_bpe_out")
        viscosity_unit = c11.selectbox("Viscosity output unit", VISCOSITY_UNITS, index=0, key="qt_solution_visc_out")
        output_temp_unit = st.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="qt_solution_temp_out")

        temperature_c = temperature_value if temperature_unit == "C" else (temperature_value - 32.0) * 5.0 / 9.0
        result = solution_properties(product, solids_wt_pct, temperature_c, pressure_value, pressure_unit, flow_value if flow_value > 0 else None, flow_unit)
        result_dict = asdict(result)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Estimated density", f"{kg_m3_to_density(result.estimated_density_kg_m3, density_unit):,.2f} {density_unit}")
        m2.metric("Estimated BPE", f"{_display_delta_t(result.estimated_bpe_c, bpe_unit):,.2f} °{bpe_unit}")
        m3.metric("Estimated viscosity", f"{cp_to_viscosity(result.estimated_viscosity_cp, viscosity_unit):,.3f} {viscosity_unit}")
        m4.metric("Boiling point", f"{_display_temperature(result.boiling_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}")
        st.json(result_dict)
        _show_notes(result.notes)

    with tabs[5]:
        st.caption("Reconcile field refractometer °Bx against lab solids and/or density so dilution, evaporator, and inventory screens use a product-calibrated dissolved-solids basis.")
        c1, c2, c3, c4 = st.columns(4)
        product = c1.selectbox("Product", product_options, format_func=lambda key: product_labels[key], key="qt_brix_product")
        observed_brix = c2.number_input("Observed refractometer reading (°Bx)", min_value=0.0, max_value=95.0, value=62.5, key="qt_brix_observed")
        temperature_value = c3.number_input("Sample temperature", value=25.0, key="qt_brix_temp")
        temperature_unit = c4.selectbox("Sample temperature unit", TEMPERATURE_UNITS, index=0, key="qt_brix_temp_unit")

        d1, d2, d3, d4 = st.columns(4)
        pressure_value = d1.number_input("Screen pressure", value=20.0, key="qt_brix_pressure")
        pressure_unit = d2.selectbox("Pressure unit", PRESSURE_UNITS, index=0, key="qt_brix_pressure_unit")
        flow_value = d3.number_input("Optional process flow", min_value=0.0, value=12000.0, key="qt_brix_flow")
        flow_unit = d4.selectbox("Flow unit", MASS_FLOW_UNITS, index=0, key="qt_brix_flow_unit")

        e1, e2, e3, e4 = st.columns(4)
        use_lab_reference = e1.checkbox("Use lab solids reference", value=True, key="qt_brix_use_lab")
        lab_solids_wt_pct = e2.number_input("Lab dissolved solids (wt%)", min_value=0.0, max_value=95.0, value=60.8, disabled=not use_lab_reference, key="qt_brix_lab_solids")
        use_density_reference = e3.checkbox("Use density reference", value=True, key="qt_brix_use_density")
        density_value = e4.number_input("Measured density", min_value=0.0, value=1305.0, disabled=not use_density_reference, key="qt_brix_density")

        f1, f2, f3, f4, f5 = st.columns(5)
        density_input_unit = f1.selectbox("Density input unit", DENSITY_UNITS, index=0, key="qt_brix_density_unit")
        solids_output_unit = f2.selectbox("Solids output unit", PERCENT_UNITS, index=0, key="qt_brix_solids_out")
        density_output_unit = f3.selectbox("Density output unit", DENSITY_UNITS, index=0, key="qt_brix_density_out")
        bpe_output_unit = f4.selectbox("BPE output unit", DELTA_TEMPERATURE_UNITS, index=0, key="qt_brix_bpe_out")
        viscosity_output_unit = f5.selectbox("Viscosity output unit", VISCOSITY_UNITS, index=0, key="qt_brix_visc_out")
        output_temp_unit = st.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="qt_brix_temp_out")

        mb_result = None
        try:
            temperature_c = temperature_to_c(temperature_value, temperature_unit)
            result = brix_reconciliation(
                product=product,
                observed_brix=observed_brix,
                temperature_c=temperature_c,
                pressure_value=pressure_value,
                pressure_unit=pressure_unit,
                lab_solids_wt_pct=lab_solids_wt_pct if use_lab_reference else None,
                measured_density_value=density_value if use_density_reference else None,
                measured_density_unit=density_input_unit,
                flow_value=flow_value if flow_value > 0 else None,
                flow_unit=flow_unit,
            )
            m1, m2, m3, m4 = st.columns(4)
            corrected_display = _display_percent(result.corrected_solids_wt_pct / 100.0, solids_output_unit)
            reference_display = (
                _display_percent(result.reference_solids_wt_pct / 100.0, solids_output_unit)
                if result.reference_solids_wt_pct is not None
                else None
            )
            density_implied_display = (
                _display_percent(result.density_implied_solids_wt_pct / 100.0, solids_output_unit)
                if result.density_implied_solids_wt_pct is not None
                else None
            )
            solids_unit_label = "wt%" if solids_output_unit == "%" else "fraction"
            m1.metric("Corrected solids", f"{corrected_display:,.3f} {solids_unit_label}")
            m2.metric("Reference solids", f"{reference_display:,.3f} {solids_unit_label}" if reference_display is not None else "Not entered")
            m3.metric("Brix offset", f"{result.brix_offset_deg_bx:+.3f} °Bx" if result.brix_offset_deg_bx is not None else "No correction")
            m4.metric("Brix factor", f"{result.brix_factor:,.4f}" if result.brix_factor is not None else "No correction")

            n1, n2, n3, n4 = st.columns(4)
            n1.metric("Density-implied solids", f"{density_implied_display:,.3f} {solids_unit_label}" if density_implied_display is not None else "Not entered")
            n2.metric("Expected density", f"{kg_m3_to_density(result.expected_density_kg_m3, density_output_unit):,.3f} {density_output_unit}")
            n3.metric("Estimated BPE", f"{_display_delta_t(result.estimated_bpe_c, bpe_output_unit):,.2f} °{bpe_output_unit}")
            n4.metric("Estimated viscosity", f"{cp_to_viscosity(result.estimated_viscosity_cp, viscosity_output_unit):,.3f} {viscosity_output_unit}")

            p1, p2, p3 = st.columns(3)
            p1.metric("Observed minus reference", f"{result.solids_error_wt_pct:+.2f} wt%" if result.solids_error_wt_pct is not None else "No correction")
            p2.metric("Boiling point", f"{_display_temperature(result.boiling_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}")
            if result.dissolved_solids_kg_h is not None and result.water_kg_h is not None:
                p3.metric("Dissolved solids flow", f"{kg_h_to_mass_flow(result.dissolved_solids_kg_h, flow_unit):,.1f} {flow_unit}")
                st.metric("Water flow", f"{kg_h_to_mass_flow(result.water_kg_h, flow_unit):,.1f} {flow_unit}")
            else:
                p3.metric("Dissolved solids flow", "Flow not entered")

            st.json(asdict(result))
            _show_notes(result.notes)
            _remember_case(
                "quick-tools-brix-reconciliation",
                {
                    "product": product,
                    "observed_brix": observed_brix,
                    "temperature_value": temperature_value,
                    "temperature_unit": temperature_unit,
                    "pressure_value": pressure_value,
                    "pressure_unit": pressure_unit,
                    "flow_value": flow_value,
                    "flow_unit": flow_unit,
                    "use_lab_reference": use_lab_reference,
                    "lab_solids_wt_pct": lab_solids_wt_pct if use_lab_reference else None,
                    "use_density_reference": use_density_reference,
                    "density_value": density_value if use_density_reference else None,
                    "density_unit": density_input_unit,
                },
                asdict(result),
            )
        except ValueError as exc:
            st.error(str(exc))

    with tabs[6]:
        c1, c2, c3 = st.columns(3)
        product = c1.selectbox("Product", product_options, format_func=lambda key: product_labels[key], key="qt_dilution_product")
        feed_rate_value = c2.number_input("Feed flow", min_value=0.0, value=10000.0, key="qt_dilution_flow")
        feed_rate_unit = c3.selectbox("Feed flow unit", MASS_FLOW_UNITS, index=0, key="qt_dilution_flow_unit")
        c4, c5, c6 = st.columns(3)
        feed_solids_wt_pct = c4.number_input("Feed solids (wt%)", min_value=0.0, max_value=95.0, value=70.0, key="qt_dilution_feed_solids")
        target_solids_wt_pct = c5.number_input("Target solids after dilution (wt%)", min_value=0.1, max_value=95.0, value=55.0, key="qt_dilution_target_solids")
        output_flow_unit = c6.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="qt_dilution_flow_out")
        try:
            result = dilution_water(product, feed_rate_value, feed_rate_unit, feed_solids_wt_pct, target_solids_wt_pct)
            m1, m2, m3 = st.columns(3)
            m1.metric("Water to add", f"{kg_h_to_mass_flow(result.required_water_addition_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            m2.metric("Final flow", f"{kg_h_to_mass_flow(result.final_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            m3.metric("Solids held constant", f"{kg_h_to_mass_flow(result.solids_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            st.json(asdict(result))
            _show_notes(result.notes)
        except ValueError as exc:
            st.error(str(exc))

    with tabs[7]:
        st.caption("Blend two liquor, syrup, water, or condensate streams on a dissolved-solids basis and screen the resulting mixed properties.")
        c1, c2 = st.columns(2)
        product = c1.selectbox("Product", product_options, format_func=lambda key: product_labels[key], key="qt_blend_product")
        output_flow_unit = c2.selectbox("Blend flow output unit", MASS_FLOW_UNITS, index=0, key="qt_blend_flow_out")

        st.markdown("**Stream A**")
        a1, a2, a3, a4 = st.columns(4)
        stream_a_rate_value = a1.number_input("Stream A flow", min_value=0.0, value=8000.0, key="qt_blend_a_flow")
        stream_a_rate_unit = a2.selectbox("Stream A flow unit", MASS_FLOW_UNITS, index=0, key="qt_blend_a_flow_unit")
        stream_a_solids_wt_pct = a3.number_input("Stream A solids (wt%)", min_value=0.0, max_value=100.0, value=68.0, key="qt_blend_a_solids")
        stream_a_temperature_value = a4.number_input("Stream A temperature", value=65.0, key="qt_blend_a_temp")
        a5, a6 = st.columns(2)
        stream_a_temperature_unit = a5.selectbox("Stream A temperature unit", TEMPERATURE_UNITS, index=0, key="qt_blend_a_temp_unit")
        temp_output_unit = a6.selectbox("Blend temperature output unit", TEMPERATURE_UNITS, index=0, key="qt_blend_temp_out")

        st.markdown("**Stream B**")
        b1, b2, b3, b4 = st.columns(4)
        stream_b_rate_value = b1.number_input("Stream B flow", min_value=0.0, value=2500.0, key="qt_blend_b_flow")
        stream_b_rate_unit = b2.selectbox("Stream B flow unit", MASS_FLOW_UNITS, index=0, key="qt_blend_b_flow_unit")
        stream_b_solids_wt_pct = b3.number_input("Stream B solids (wt%)", min_value=0.0, max_value=100.0, value=0.0, key="qt_blend_b_solids")
        stream_b_temperature_value = b4.number_input("Stream B temperature", value=25.0, key="qt_blend_b_temp")
        b5, b6, b7, b8 = st.columns(4)
        stream_b_temperature_unit = b5.selectbox("Stream B temperature unit", TEMPERATURE_UNITS, index=0, key="qt_blend_b_temp_unit")
        pressure_value = b6.number_input("Property-screen pressure", value=20.0, key="qt_blend_pressure")
        pressure_unit = b7.selectbox("Pressure unit", PRESSURE_UNITS, index=0, key="qt_blend_pressure_unit")
        density_unit = b8.selectbox("Density output unit", DENSITY_UNITS, index=0, key="qt_blend_density_out")
        c3, c4 = st.columns(2)
        bpe_unit = c3.selectbox("BPE output unit", DELTA_TEMPERATURE_UNITS, index=0, key="qt_blend_bpe_out")
        viscosity_unit = c4.selectbox("Viscosity output unit", VISCOSITY_UNITS, index=0, key="qt_blend_visc_out")

        try:
            stream_a_temperature_c = temperature_to_c(stream_a_temperature_value, stream_a_temperature_unit)
            stream_b_temperature_c = temperature_to_c(stream_b_temperature_value, stream_b_temperature_unit)
            blend = two_stream_blend(
                product=product,
                stream_a_rate_value=stream_a_rate_value,
                stream_a_rate_unit=stream_a_rate_unit,
                stream_a_solids_wt_pct=stream_a_solids_wt_pct,
                stream_b_rate_value=stream_b_rate_value,
                stream_b_rate_unit=stream_b_rate_unit,
                stream_b_solids_wt_pct=stream_b_solids_wt_pct,
                stream_a_temperature_c=stream_a_temperature_c,
                stream_b_temperature_c=stream_b_temperature_c,
            )
            property_temp_c = blend.blended_temperature_c if blend.blended_temperature_c is not None else stream_a_temperature_c
            properties = solution_properties(
                product,
                blend.blended_solids_wt_pct,
                property_temp_c,
                pressure_value,
                pressure_unit,
                blend.total_rate_kg_h,
                "kg/h",
            )
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Blended flow", f"{kg_h_to_mass_flow(blend.total_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            m2.metric("Blended solids", f"{blend.blended_solids_wt_pct:,.2f} wt%")
            m3.metric("Dissolved solids", f"{kg_h_to_mass_flow(blend.blended_solids_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            blend_temp_display = (
                f"{_display_temperature(blend.blended_temperature_c, temp_output_unit):,.2f} °{temp_output_unit}"
                if blend.blended_temperature_c is not None
                else "Not calculated"
            )
            m4.metric("Blended temperature", blend_temp_display)
            n1, n2, n3 = st.columns(3)
            n1.metric("Estimated density", f"{kg_m3_to_density(properties.estimated_density_kg_m3, density_unit):,.2f} {density_unit}")
            n2.metric("Estimated BPE", f"{_display_delta_t(properties.estimated_bpe_c, bpe_unit):,.2f} °{bpe_unit}")
            n3.metric("Estimated viscosity", f"{cp_to_viscosity(properties.estimated_viscosity_cp, viscosity_unit):,.3f} {viscosity_unit}")
            st.json({"blend": asdict(blend), "properties": asdict(properties)})
            _show_notes(blend.notes + properties.notes)
            _remember_case(
                "quick-tools-two-stream-blend",
                {
                    "product": product,
                    "stream_a_rate_value": stream_a_rate_value,
                    "stream_a_rate_unit": stream_a_rate_unit,
                    "stream_a_solids_wt_pct": stream_a_solids_wt_pct,
                    "stream_a_temperature_value": stream_a_temperature_value,
                    "stream_a_temperature_unit": stream_a_temperature_unit,
                    "stream_b_rate_value": stream_b_rate_value,
                    "stream_b_rate_unit": stream_b_rate_unit,
                    "stream_b_solids_wt_pct": stream_b_solids_wt_pct,
                    "stream_b_temperature_value": stream_b_temperature_value,
                    "stream_b_temperature_unit": stream_b_temperature_unit,
                    "pressure_value": pressure_value,
                    "pressure_unit": pressure_unit,
                },
                {"blend": asdict(blend), "properties": asdict(properties)},
            )
        except ValueError as exc:
            st.error(str(exc))

    with tabs[8]:
        st.caption("Solve how much of a second stream is required to hit a target blend solids level while holding one known stream fixed.")
        c1, c2, c3 = st.columns(3)
        product = c1.selectbox("Product", product_options, format_func=lambda key: product_labels[key], key="qt_ratio_product")
        output_flow_unit = c2.selectbox("Solved flow output unit", MASS_FLOW_UNITS, index=0, key="qt_ratio_flow_out")
        solids_output_unit = c3.selectbox("Solids output unit", PERCENT_UNITS, index=0, key="qt_ratio_solids_out")

        d1, d2 = st.columns(2)
        known_stream_label = d1.text_input("Fixed stream label", value="Base liquor", key="qt_ratio_known_label")
        target_stream_label = d2.text_input("Adjusted stream label", value="Water / dilution stream", key="qt_ratio_target_label")

        st.markdown("**Fixed stream**")
        a1, a2, a3, a4 = st.columns(4)
        known_stream_rate_value = a1.number_input("Fixed stream flow", min_value=0.0, value=8000.0, key="qt_ratio_known_flow")
        known_stream_rate_unit = a2.selectbox("Fixed stream flow unit", MASS_FLOW_UNITS, index=0, key="qt_ratio_known_flow_unit")
        known_stream_solids_wt_pct = a3.number_input("Fixed stream solids (wt%)", min_value=0.0, max_value=100.0, value=68.0, key="qt_ratio_known_solids")
        known_stream_temperature_value = a4.number_input("Fixed stream temperature", value=65.0, key="qt_ratio_known_temp")
        a5, a6, a7 = st.columns(3)
        known_stream_temperature_unit = a5.selectbox("Fixed stream temperature unit", TEMPERATURE_UNITS, index=0, key="qt_ratio_known_temp_unit")
        target_stream_solids_wt_pct = a6.number_input("Adjusted stream solids (wt%)", min_value=0.0, max_value=100.0, value=0.0, key="qt_ratio_target_stream_solids")
        target_blend_solids_wt_pct = a7.number_input("Target blend solids (wt%)", min_value=0.0, max_value=100.0, value=55.0, key="qt_ratio_target_blend_solids")

        st.markdown("**Adjusted stream and property screen**")
        b1, b2, b3, b4 = st.columns(4)
        target_stream_temperature_value = b1.number_input("Adjusted stream temperature", value=25.0, key="qt_ratio_target_temp")
        target_stream_temperature_unit = b2.selectbox("Adjusted stream temperature unit", TEMPERATURE_UNITS, index=0, key="qt_ratio_target_temp_unit")
        pressure_value = b3.number_input("Property-screen pressure", value=20.0, key="qt_ratio_pressure")
        pressure_unit = b4.selectbox("Pressure unit", PRESSURE_UNITS, index=0, key="qt_ratio_pressure_unit")
        c4, c5, c6, c7 = st.columns(4)
        density_unit = c4.selectbox("Density output unit", DENSITY_UNITS, index=0, key="qt_ratio_density_out")
        bpe_unit = c5.selectbox("BPE output unit", DELTA_TEMPERATURE_UNITS, index=0, key="qt_ratio_bpe_out")
        viscosity_unit = c6.selectbox("Viscosity output unit", VISCOSITY_UNITS, index=0, key="qt_ratio_visc_out")
        temp_output_unit = c7.selectbox("Blend temperature output unit", TEMPERATURE_UNITS, index=0, key="qt_ratio_temp_out")

        try:
            known_stream_temperature_c = temperature_to_c(known_stream_temperature_value, known_stream_temperature_unit)
            target_stream_temperature_c = temperature_to_c(target_stream_temperature_value, target_stream_temperature_unit)
            blend = ratio_target_blend(
                product=product,
                known_stream_rate_value=known_stream_rate_value,
                known_stream_rate_unit=known_stream_rate_unit,
                known_stream_solids_wt_pct=known_stream_solids_wt_pct,
                target_stream_solids_wt_pct=target_stream_solids_wt_pct,
                target_blend_solids_wt_pct=target_blend_solids_wt_pct,
                known_stream_temperature_c=known_stream_temperature_c,
                target_stream_temperature_c=target_stream_temperature_c,
                known_stream_label=known_stream_label,
                target_stream_label=target_stream_label,
            )
            property_temp_c = blend.blended_temperature_c if blend.blended_temperature_c is not None else known_stream_temperature_c
            properties = solution_properties(
                product,
                blend.target_blend_solids_wt_pct,
                property_temp_c,
                pressure_value,
                pressure_unit,
                blend.total_rate_kg_h,
                "kg/h",
            )
            solved_solids_display = _display_percent(blend.target_blend_solids_wt_pct / 100.0, solids_output_unit)
            solids_unit_label = "wt%" if solids_output_unit == "%" else "fraction"
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(f"Required {target_stream_label}", f"{kg_h_to_mass_flow(blend.required_target_stream_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            m2.metric("Target-to-fixed ratio", f"{blend.target_to_known_ratio:,.3f}")
            m3.metric("Final blend flow", f"{kg_h_to_mass_flow(blend.total_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            m4.metric("Target blend solids", f"{solved_solids_display:,.3f} {solids_unit_label}")

            n1, n2, n3, n4 = st.columns(4)
            n1.metric("Blended dissolved solids", f"{kg_h_to_mass_flow(blend.blended_solids_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            n2.metric("Blended water", f"{kg_h_to_mass_flow(blend.blended_water_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
            blend_temp_display = (
                f"{_display_temperature(blend.blended_temperature_c, temp_output_unit):,.2f} °{temp_output_unit}"
                if blend.blended_temperature_c is not None
                else "Not calculated"
            )
            n3.metric("Blended temperature", blend_temp_display)
            n4.metric("Estimated density", f"{kg_m3_to_density(properties.estimated_density_kg_m3, density_unit):,.2f} {density_unit}")

            p1, p2, p3 = st.columns(3)
            p1.metric("Estimated BPE", f"{_display_delta_t(properties.estimated_bpe_c, bpe_unit):,.2f} °{bpe_unit}")
            p2.metric("Estimated viscosity", f"{cp_to_viscosity(properties.estimated_viscosity_cp, viscosity_unit):,.3f} {viscosity_unit}")
            p3.metric("Boiling point", f"{_display_temperature(properties.boiling_temperature_c, temp_output_unit):,.2f} °{temp_output_unit}")
            st.json({"blend": asdict(blend), "properties": asdict(properties)})
            _show_notes(blend.notes + properties.notes)
            _remember_case(
                "quick-tools-ratio-target-blend",
                {
                    "product": product,
                    "known_stream_label": known_stream_label,
                    "target_stream_label": target_stream_label,
                    "known_stream_rate_value": known_stream_rate_value,
                    "known_stream_rate_unit": known_stream_rate_unit,
                    "known_stream_solids_wt_pct": known_stream_solids_wt_pct,
                    "known_stream_temperature_value": known_stream_temperature_value,
                    "known_stream_temperature_unit": known_stream_temperature_unit,
                    "target_stream_solids_wt_pct": target_stream_solids_wt_pct,
                    "target_blend_solids_wt_pct": target_blend_solids_wt_pct,
                    "target_stream_temperature_value": target_stream_temperature_value,
                    "target_stream_temperature_unit": target_stream_temperature_unit,
                    "pressure_value": pressure_value,
                    "pressure_unit": pressure_unit,
                },
                {"blend": asdict(blend), "properties": asdict(properties)},
            )
        except ValueError as exc:
            st.error(str(exc))

    with tabs[9]:
        c1, c2, c3 = st.columns(3)
        tank_type = c1.selectbox(
            "Tank type",
            ["vertical_cylindrical", "horizontal_cylindrical", "rectangular"],
            format_func=lambda key: {
                "vertical_cylindrical": "Vertical cylindrical tank",
                "horizontal_cylindrical": "Horizontal cylindrical tank",
                "rectangular": "Rectangular tank / basin",
            }[key],
            key="qt_tank_type",
        )
        level_value = c2.number_input("Liquid level", min_value=0.0, value=2.4, key="qt_tank_level")
        level_unit = c3.selectbox("Liquid level unit", LENGTH_UNITS, index=0, key="qt_tank_level_unit")

        density_col, density_unit_col, volume_unit_col, time_unit_col = st.columns(4)
        density_value = density_col.number_input("Optional liquid density", min_value=0.0, value=1000.0, key="qt_tank_density")
        density_unit = density_unit_col.selectbox("Density unit", DENSITY_UNITS, index=0, key="qt_tank_density_unit")
        output_volume_unit = volume_unit_col.selectbox("Volume output unit", VOLUME_UNITS, index=0, key="qt_tank_volume_out")
        output_time_unit = time_unit_col.selectbox("Time output unit", TIME_UNITS, index=2, key="qt_tank_time_out")

        transfer_col, transfer_unit_col = st.columns(2)
        transfer_rate_value = transfer_col.number_input("Optional transfer rate", min_value=0.0, value=25.0, key="qt_tank_transfer_rate")
        transfer_rate_unit = transfer_unit_col.selectbox("Transfer-rate unit", VOLUMETRIC_FLOW_UNITS, index=0, key="qt_tank_transfer_unit")

        dimension_values: dict[str, float]
        dimension_units: dict[str, str]
        if tank_type == "vertical_cylindrical":
            d1, d2, d3, d4 = st.columns(4)
            diameter_value = d1.number_input("Tank diameter", min_value=0.01, value=3.2, key="qt_tank_vert_diameter")
            diameter_unit = d2.selectbox("Diameter unit", LENGTH_UNITS, index=0, key="qt_tank_vert_diameter_unit")
            height_value = d3.number_input("Straight-side height", min_value=0.01, value=6.0, key="qt_tank_vert_height")
            height_unit = d4.selectbox("Height unit", LENGTH_UNITS, index=0, key="qt_tank_vert_height_unit")
            dimension_values = {"diameter": diameter_value, "height": height_value}
            dimension_units = {"diameter": diameter_unit, "height": height_unit}
        elif tank_type == "horizontal_cylindrical":
            d1, d2, d3, d4 = st.columns(4)
            diameter_value = d1.number_input("Shell diameter", min_value=0.01, value=2.4, key="qt_tank_horiz_diameter")
            diameter_unit = d2.selectbox("Diameter unit", LENGTH_UNITS, index=0, key="qt_tank_horiz_diameter_unit")
            length_value = d3.number_input("Straight-shell length", min_value=0.01, value=8.0, key="qt_tank_horiz_length")
            length_unit = d4.selectbox("Length unit", LENGTH_UNITS, index=0, key="qt_tank_horiz_length_unit")
            dimension_values = {"diameter": diameter_value, "length": length_value}
            dimension_units = {"diameter": diameter_unit, "length": length_unit}
        else:
            d1, d2, d3, d4, d5, d6 = st.columns(6)
            length_value = d1.number_input("Tank length", min_value=0.01, value=5.0, key="qt_tank_rect_length")
            length_unit = d2.selectbox("Length unit", LENGTH_UNITS, index=0, key="qt_tank_rect_length_unit")
            width_value = d3.number_input("Tank width", min_value=0.01, value=3.0, key="qt_tank_rect_width")
            width_unit = d4.selectbox("Width unit", LENGTH_UNITS, index=0, key="qt_tank_rect_width_unit")
            height_value = d5.number_input("Straight-side height", min_value=0.01, value=2.5, key="qt_tank_rect_height")
            height_unit = d6.selectbox("Height unit", LENGTH_UNITS, index=0, key="qt_tank_rect_height_unit")
            dimension_values = {"length": length_value, "width": width_value, "height": height_value}
            dimension_units = {"length": length_unit, "width": width_unit, "height": height_unit}

        try:
            density_arg = density_value if density_value > 0.0 else None
            transfer_arg = transfer_rate_value if transfer_rate_value > 0.0 else None
            result = tank_inventory(
                tank_type=tank_type,
                dimensions=dimension_values,
                dimension_units=dimension_units,
                liquid_level_value=level_value,
                liquid_level_unit=level_unit,
                density_value=density_arg,
                density_unit=density_unit,
                transfer_rate_value=transfer_arg,
                transfer_rate_unit=transfer_rate_unit,
            )
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Liquid volume", f"{m3_to_volume(result.liquid_volume_m3, output_volume_unit):,.2f} {output_volume_unit}")
            m2.metric("Tank total volume", f"{m3_to_volume(result.total_volume_m3, output_volume_unit):,.2f} {output_volume_unit}")
            m3.metric("Free ullage", f"{m3_to_volume(result.available_ullage_m3, output_volume_unit):,.2f} {output_volume_unit}")
            m4.metric("Fill level", f"{result.fill_fraction * 100.0:,.1f} %")
            n1, n2, n3 = st.columns(3)
            n1.metric("Clamped liquid level", f"{m_to_length(result.liquid_level_m, level_unit):,.2f} {level_unit}")
            n2.metric(
                "Liquid mass",
                f"{result.liquid_mass_kg:,.0f} kg" if result.liquid_mass_kg is not None else "Not entered",
            )
            residence_display = (
                f"{seconds_to_time(result.residence_time_h * 3600.0, output_time_unit):,.2f} {output_time_unit}"
                if result.residence_time_h is not None
                else "Not entered"
            )
            n3.metric("Residence / pump-out time", residence_display)
            st.json(asdict(result))
            _show_notes(result.notes)
            _remember_case(
                "quick-tools-tank-inventory",
                {
                    "tank_type": tank_type,
                    "dimensions": dimension_values,
                    "dimension_units": dimension_units,
                    "liquid_level_value": level_value,
                    "liquid_level_unit": level_unit,
                    "density_value": density_arg,
                    "density_unit": density_unit,
                    "transfer_rate_value": transfer_arg,
                    "transfer_rate_unit": transfer_rate_unit,
                },
                asdict(result),
            )
        except ValueError as exc:
            st.error(str(exc))

    with tabs[10]:
        st.caption("Estimate direct steam and utility cost, then compare current vs proposed cases so troubleshooters can rank leaks, rerates, throttling losses, and optimization opportunities.")
        utility_tabs = st.tabs(["Steam", "Electricity"])
        steam_cost_basis_options = ["$/kg", "$/1000 kg", "$/lb", "$/1000 lb", "$/metric ton"]
        motor_power_units = ["kW", "hp"]

        with utility_tabs[0]:
            steam_tabs = st.tabs(["Single case", "Current vs proposed"])

            with steam_tabs[0]:
                c1, c2, c3 = st.columns(3)
                steam_flow_value = c1.number_input("Steam flow", min_value=0.0, value=8000.0, key="qt_utility_steam_flow")
                steam_flow_unit = c2.selectbox("Steam flow unit", MASS_FLOW_UNITS, index=0, key="qt_utility_steam_flow_unit")
                steam_cost_value = c3.number_input("Steam unit cost", min_value=0.0, value=18.0, key="qt_utility_steam_cost")
                c4, c5, c6 = st.columns(3)
                steam_cost_basis = c4.selectbox("Steam cost basis", steam_cost_basis_options, index=4, key="qt_utility_steam_cost_basis")
                steam_hours_per_day = c5.number_input("Operating hours per day", min_value=0.0, max_value=24.0, value=24.0, key="qt_utility_steam_hours")
                steam_days_per_year = c6.number_input("Operating days per year", min_value=0.0, max_value=366.0, value=350.0, key="qt_utility_steam_days")
                output_flow_unit = st.selectbox("Steam flow output unit", MASS_FLOW_UNITS, index=0, key="qt_utility_steam_flow_out")
                try:
                    result = steam_cost(
                        steam_flow_value=steam_flow_value,
                        steam_flow_unit=steam_flow_unit,
                        steam_cost_value=steam_cost_value,
                        steam_cost_basis=steam_cost_basis,
                        operating_hours_per_day=steam_hours_per_day,
                        operating_days_per_year=steam_days_per_year,
                    )
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Hourly steam cost", f"${result.hourly_cost:,.2f}/h")
                    m2.metric("Daily steam cost", f"${result.daily_cost:,.2f}/day")
                    m3.metric("Annual steam cost", f"${result.annual_cost:,.0f}/yr")
                    m4.metric("Annual steam use", f"{result.annual_steam_consumption_kg / 1000.0:,.1f} metric ton/yr")
                    n1, n2, n3 = st.columns(3)
                    n1.metric("Steam flow basis", f"{kg_h_to_mass_flow(result.steam_flow_kg_h, output_flow_unit):,.2f} {output_flow_unit}")
                    n2.metric("Daily steam use", f"{result.daily_steam_consumption_kg / 1000.0:,.1f} metric ton/day")
                    n3.metric("Unit steam cost", f"${result.steam_unit_cost_per_kg * 1000.0:,.2f}/metric ton")
                    st.json(asdict(result))
                    _show_notes(result.notes)
                    _remember_case(
                        "quick-tools-utility-cost-steam",
                        {
                            "steam_flow_value": steam_flow_value,
                            "steam_flow_unit": steam_flow_unit,
                            "steam_cost_value": steam_cost_value,
                            "steam_cost_basis": steam_cost_basis,
                            "operating_hours_per_day": steam_hours_per_day,
                            "operating_days_per_year": steam_days_per_year,
                        },
                        asdict(result),
                    )
                except ValueError as exc:
                    st.error(str(exc))

            with steam_tabs[1]:
                st.caption("Use the same steam cost and operating schedule for current and proposed cases to estimate savings from leaks fixed, pressure optimization, or process improvements.")
                s1, s2, s3 = st.columns(3)
                current_steam_flow_value = s1.number_input("Current steam flow", min_value=0.0, value=8000.0, key="qt_utility_steam_cmp_current_flow")
                proposed_steam_flow_value = s2.number_input("Proposed steam flow", min_value=0.0, value=6800.0, key="qt_utility_steam_cmp_proposed_flow")
                steam_cmp_flow_unit = s3.selectbox("Steam flow unit", MASS_FLOW_UNITS, index=0, key="qt_utility_steam_cmp_flow_unit")
                s4, s5, s6 = st.columns(3)
                steam_cmp_cost_value = s4.number_input("Steam unit cost", min_value=0.0, value=18.0, key="qt_utility_steam_cmp_cost")
                steam_cmp_cost_basis = s5.selectbox("Steam cost basis", steam_cost_basis_options, index=4, key="qt_utility_steam_cmp_cost_basis")
                steam_cmp_output_flow_unit = s6.selectbox("Steam delta output unit", MASS_FLOW_UNITS, index=0, key="qt_utility_steam_cmp_flow_out")
                s7, s8 = st.columns(2)
                steam_cmp_hours = s7.number_input("Operating hours per day", min_value=0.0, max_value=24.0, value=24.0, key="qt_utility_steam_cmp_hours")
                steam_cmp_days = s8.number_input("Operating days per year", min_value=0.0, max_value=366.0, value=350.0, key="qt_utility_steam_cmp_days")
                try:
                    result = steam_cost_comparison(
                        current_steam_flow_value=current_steam_flow_value,
                        proposed_steam_flow_value=proposed_steam_flow_value,
                        steam_flow_unit=steam_cmp_flow_unit,
                        steam_cost_value=steam_cmp_cost_value,
                        steam_cost_basis=steam_cmp_cost_basis,
                        operating_hours_per_day=steam_cmp_hours,
                        operating_days_per_year=steam_cmp_days,
                    )
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Annual savings", f"${result.annual_cost_savings:,.0f}/yr")
                    m2.metric("Hourly savings", f"${result.hourly_cost_savings:,.2f}/h")
                    m3.metric("Annual steam reduction", f"{kg_h_to_mass_flow(result.annual_steam_savings_kg / max(steam_cmp_hours * steam_cmp_days, 1e-9), steam_cmp_output_flow_unit):,.2f} {steam_cmp_output_flow_unit} eqv")
                    m4.metric("Annual steam saved", f"{result.annual_steam_savings_kg / 1000.0:,.1f} metric ton/yr")
                    n1, n2, n3 = st.columns(3)
                    n1.metric("Current annual cost", f"${result.current.annual_cost:,.0f}/yr")
                    n2.metric("Proposed annual cost", f"${result.proposed.annual_cost:,.0f}/yr")
                    n3.metric("Annual cost delta", f"${result.annual_cost_delta:,.0f}/yr")
                    p1, p2, p3 = st.columns(3)
                    p1.metric("Current steam flow", f"{kg_h_to_mass_flow(result.current.steam_flow_kg_h, steam_cmp_output_flow_unit):,.2f} {steam_cmp_output_flow_unit}")
                    p2.metric("Proposed steam flow", f"{kg_h_to_mass_flow(result.proposed.steam_flow_kg_h, steam_cmp_output_flow_unit):,.2f} {steam_cmp_output_flow_unit}")
                    p3.metric("Flow delta", f"{kg_h_to_mass_flow(result.proposed.steam_flow_kg_h - result.current.steam_flow_kg_h, steam_cmp_output_flow_unit):,.2f} {steam_cmp_output_flow_unit}")
                    st.json(asdict(result))
                    _show_notes(result.notes + result.current.notes + result.proposed.notes)
                    _remember_case(
                        "quick-tools-utility-cost-steam-comparison",
                        {
                            "current_steam_flow_value": current_steam_flow_value,
                            "proposed_steam_flow_value": proposed_steam_flow_value,
                            "steam_flow_unit": steam_cmp_flow_unit,
                            "steam_cost_value": steam_cmp_cost_value,
                            "steam_cost_basis": steam_cmp_cost_basis,
                            "operating_hours_per_day": steam_cmp_hours,
                            "operating_days_per_year": steam_cmp_days,
                        },
                        asdict(result),
                    )
                except ValueError as exc:
                    st.error(str(exc))

        with utility_tabs[1]:
            elec_tabs = st.tabs(["Single case", "Current vs proposed"])

            with elec_tabs[0]:
                e1, e2, e3 = st.columns(3)
                shaft_power_value = e1.number_input("Motor shaft / rated power", min_value=0.0, value=75.0, key="qt_utility_elec_power")
                shaft_power_unit = e2.selectbox("Power unit", motor_power_units, index=0, key="qt_utility_elec_power_unit")
                electricity_rate = e3.number_input("Electricity rate ($/kWh)", min_value=0.0, value=0.09, format="%.4f", key="qt_utility_elec_rate")
                e4, e5, e6, e7 = st.columns(4)
                load_pct = e4.number_input("Motor load (%)", min_value=0.0, max_value=100.0, value=85.0, key="qt_utility_elec_load")
                motor_efficiency_pct = e5.number_input("Motor efficiency (%)", min_value=1.0, max_value=100.0, value=92.0, key="qt_utility_elec_eff")
                elec_hours_per_day = e6.number_input("Operating hours per day", min_value=0.0, max_value=24.0, value=24.0, key="qt_utility_elec_hours")
                elec_days_per_year = e7.number_input("Operating days per year", min_value=0.0, max_value=366.0, value=350.0, key="qt_utility_elec_days")
                try:
                    result = electricity_cost(
                        shaft_power_value=shaft_power_value,
                        shaft_power_unit=shaft_power_unit,
                        electricity_rate_per_kwh=electricity_rate,
                        load_pct=load_pct,
                        motor_efficiency_pct=motor_efficiency_pct,
                        operating_hours_per_day=elec_hours_per_day,
                        operating_days_per_year=elec_days_per_year,
                    )
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Electrical input", f"{result.electric_input_kw:,.2f} kW")
                    m2.metric("Hourly electricity cost", f"${result.hourly_cost:,.2f}/h")
                    m3.metric("Daily electricity cost", f"${result.daily_cost:,.2f}/day")
                    m4.metric("Annual electricity cost", f"${result.annual_cost:,.0f}/yr")
                    n1, n2, n3 = st.columns(3)
                    n1.metric("Shaft load basis", f"{result.shaft_power_kw * result.load_fraction:,.2f} kW")
                    n2.metric("Daily energy", f"{result.daily_energy_kwh:,.1f} kWh/day")
                    n3.metric("Annual energy", f"{result.annual_energy_kwh:,.0f} kWh/yr")
                    st.json(asdict(result))
                    _show_notes(result.notes)
                    _remember_case(
                        "quick-tools-utility-cost-electricity",
                        {
                            "shaft_power_value": shaft_power_value,
                            "shaft_power_unit": shaft_power_unit,
                            "electricity_rate_per_kwh": electricity_rate,
                            "load_pct": load_pct,
                            "motor_efficiency_pct": motor_efficiency_pct,
                            "operating_hours_per_day": elec_hours_per_day,
                            "operating_days_per_year": elec_days_per_year,
                        },
                        asdict(result),
                    )
                except ValueError as exc:
                    st.error(str(exc))

            with elec_tabs[1]:
                st.caption("Compare current and proposed motor/pump operating points at one electricity rate to estimate savings from trims, VFD changes, right-sizing, or efficiency upgrades.")
                q1, q2, q3 = st.columns(3)
                current_shaft_power_value = q1.number_input("Current shaft / rated power", min_value=0.0, value=75.0, key="qt_utility_elec_cmp_current_power")
                proposed_shaft_power_value = q2.number_input("Proposed shaft / rated power", min_value=0.0, value=60.0, key="qt_utility_elec_cmp_proposed_power")
                elec_cmp_power_unit = q3.selectbox("Power unit", motor_power_units, index=0, key="qt_utility_elec_cmp_power_unit")
                q4, q5, q6 = st.columns(3)
                electricity_cmp_rate = q4.number_input("Electricity rate ($/kWh)", min_value=0.0, value=0.09, format="%.4f", key="qt_utility_elec_cmp_rate")
                elec_cmp_hours = q5.number_input("Operating hours per day", min_value=0.0, max_value=24.0, value=24.0, key="qt_utility_elec_cmp_hours")
                elec_cmp_days = q6.number_input("Operating days per year", min_value=0.0, max_value=366.0, value=350.0, key="qt_utility_elec_cmp_days")
                q7, q8, q9, q10 = st.columns(4)
                current_load_pct = q7.number_input("Current motor load (%)", min_value=0.0, max_value=100.0, value=85.0, key="qt_utility_elec_cmp_current_load")
                proposed_load_pct = q8.number_input("Proposed motor load (%)", min_value=0.0, max_value=100.0, value=78.0, key="qt_utility_elec_cmp_proposed_load")
                current_motor_efficiency_pct = q9.number_input("Current motor efficiency (%)", min_value=1.0, max_value=100.0, value=92.0, key="qt_utility_elec_cmp_current_eff")
                proposed_motor_efficiency_pct = q10.number_input("Proposed motor efficiency (%)", min_value=1.0, max_value=100.0, value=94.0, key="qt_utility_elec_cmp_proposed_eff")
                try:
                    result = electricity_cost_comparison(
                        current_shaft_power_value=current_shaft_power_value,
                        proposed_shaft_power_value=proposed_shaft_power_value,
                        shaft_power_unit=elec_cmp_power_unit,
                        electricity_rate_per_kwh=electricity_cmp_rate,
                        current_load_pct=current_load_pct,
                        proposed_load_pct=proposed_load_pct,
                        current_motor_efficiency_pct=current_motor_efficiency_pct,
                        proposed_motor_efficiency_pct=proposed_motor_efficiency_pct,
                        operating_hours_per_day=elec_cmp_hours,
                        operating_days_per_year=elec_cmp_days,
                    )
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Annual savings", f"${result.annual_cost_savings:,.0f}/yr")
                    m2.metric("Hourly savings", f"${result.hourly_cost_savings:,.2f}/h")
                    m3.metric("Annual energy saved", f"{result.annual_energy_savings_kwh:,.0f} kWh/yr")
                    m4.metric("Input power delta", f"{result.electric_input_kw_delta:,.2f} kW")
                    n1, n2, n3 = st.columns(3)
                    n1.metric("Current annual cost", f"${result.current.annual_cost:,.0f}/yr")
                    n2.metric("Proposed annual cost", f"${result.proposed.annual_cost:,.0f}/yr")
                    n3.metric("Annual cost delta", f"${result.annual_cost_delta:,.0f}/yr")
                    p1, p2, p3 = st.columns(3)
                    p1.metric("Current electrical input", f"{result.current.electric_input_kw:,.2f} kW")
                    p2.metric("Proposed electrical input", f"{result.proposed.electric_input_kw:,.2f} kW")
                    p3.metric("Annual energy delta", f"{result.annual_energy_delta_kwh:,.0f} kWh/yr")
                    st.json(asdict(result))
                    _show_notes(result.notes + result.current.notes + result.proposed.notes)
                    _remember_case(
                        "quick-tools-utility-cost-electricity-comparison",
                        {
                            "current_shaft_power_value": current_shaft_power_value,
                            "proposed_shaft_power_value": proposed_shaft_power_value,
                            "shaft_power_unit": elec_cmp_power_unit,
                            "electricity_rate_per_kwh": electricity_cmp_rate,
                            "current_load_pct": current_load_pct,
                            "proposed_load_pct": proposed_load_pct,
                            "current_motor_efficiency_pct": current_motor_efficiency_pct,
                            "proposed_motor_efficiency_pct": proposed_motor_efficiency_pct,
                            "operating_hours_per_day": elec_cmp_hours,
                            "operating_days_per_year": elec_cmp_days,
                        },
                        asdict(result),
                    )
                except ValueError as exc:
                    st.error(str(exc))



def render_solution_bpe() -> None:
    st.header("Solution BPE")
    tabs = st.tabs(["BPE estimate", "Capacity impact"])
    bpe_products = ["citric_acid", "fructose", "dextrose", "sucrose"]

    with tabs[0]:
        c1, c2, c3, c4 = st.columns(4)
        product = c1.selectbox("Product", bpe_products, format_func=lambda key: PRODUCT_PROFILES[key].display_name, key="bpe_product")
        solids = c2.number_input("Solids / DS (wt%)", min_value=0.0, max_value=90.0, value=62.0, key="bpe_solids")
        pressure_value = c3.number_input("Operating pressure", value=20.0, key="bpe_pressure")
        pressure_unit = c4.selectbox("Pressure unit", PRESSURE_UNITS, index=0, key="bpe_pressure_unit")
        c5, c6, c7 = st.columns(3)
        method = c5.selectbox(
            "Method",
            ["auto", "table", "high_solids"] if product == "citric_acid" else ["auto"],
            format_func=lambda key: {
                "auto": "Auto",
                "table": "Workbook table / interpolation",
                "high_solids": "Workbook >60 DS estimate",
            }.get(key, str(key)),
            key="bpe_method",
        )
        bpe_unit = c6.selectbox("BPE output unit", DELTA_TEMPERATURE_UNITS, index=0, key="bpe_out_unit")
        temp_unit = c7.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="bpe_temp_out")

        if product == "citric_acid":
            result_payload = asdict(estimate_citric_bpe(solids, pressure_value, pressure_unit, method=method))
            notes = result_payload["notes"]
            bpe_c = result_payload["bpe_c"]
            sat_c = result_payload["saturation_temperature_c"]
            boil_c = result_payload["boiling_temperature_c"]
            method_label = result_payload["method"]
        else:
            solution = solution_properties(product, solids, 45.0, pressure_value, pressure_unit)
            result_payload = asdict(solution)
            notes = solution.notes
            bpe_c = solution.estimated_bpe_c
            sat_c = solution.saturation_temperature_c
            boil_c = solution.boiling_temperature_c
            method_label = "product_screening_estimate"
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("BPE", f"{_display_delta_t(bpe_c, bpe_unit):,.2f} °{bpe_unit}")
        m2.metric("Saturation temp", f"{_display_temperature(sat_c, temp_unit):,.2f} °{temp_unit}")
        m3.metric("Boiling temp", f"{_display_temperature(boil_c, temp_unit):,.2f} °{temp_unit}")
        m4.metric("Method", method_label)
        st.json(result_payload)
        _show_notes(notes)

    with tabs[1]:
        c1, c2, c3, c4 = st.columns(4)
        steam_temp = c1.number_input("Steam temperature", value=180.0, key="bpe_cap_steam_temp")
        steam_temp_unit = c2.selectbox("Steam temperature unit", TEMPERATURE_UNITS, index=0, key="bpe_cap_steam_temp_unit")
        pressure_value = c3.number_input("Operating pressure", value=20.0, key="bpe_cap_pressure")
        pressure_unit = c4.selectbox("Pressure unit", PRESSURE_UNITS, index=0, key="bpe_cap_pressure_unit")
        c5, c6, c7, c8 = st.columns(4)
        current_bpe = c5.number_input("Current BPE", value=6.0, key="bpe_cap_current_bpe")
        new_bpe = c6.number_input("New BPE", value=10.0, key="bpe_cap_new_bpe")
        bpe_unit = c7.selectbox("BPE unit", DELTA_TEMPERATURE_UNITS, index=0, key="bpe_cap_bpe_unit")
        dt_unit = c8.selectbox("ΔT output unit", DELTA_TEMPERATURE_UNITS, index=0, key="bpe_cap_dt_out")
        temp_unit_out = st.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="bpe_cap_temp_out")
        steam_temp_c = steam_temp if steam_temp_unit == "C" else (steam_temp - 32.0) * 5.0 / 9.0
        current_bpe_c = current_bpe if bpe_unit == "C" else current_bpe * 5.0 / 9.0
        new_bpe_c = new_bpe if bpe_unit == "C" else new_bpe * 5.0 / 9.0
        impact = estimate_capacity_impact_from_bpe(steam_temp_c, pressure_value, pressure_unit, current_bpe_c, new_bpe_c)
        m1, m2, m3 = st.columns(3)
        m1.metric("Current ΔT", f"{_display_delta_t(impact.current_delta_t_c, dt_unit):,.2f} °{dt_unit}")
        m2.metric("New ΔT", f"{_display_delta_t(impact.new_delta_t_c, dt_unit):,.2f} °{dt_unit}")
        m3.metric("Relative capacity change", f"{impact.relative_capacity_change_pct:,.1f} %")
        st.json({**asdict(impact), "steam_temperature_display": f"{_display_temperature(impact.steam_temperature_c, temp_unit_out):,.2f} °{temp_unit_out}", "saturation_temperature_display": f"{_display_temperature(impact.saturation_temperature_c, temp_unit_out):,.2f} °{temp_unit_out}"})
        _show_notes(impact.notes)



def render_hydraulics() -> None:
    st.header("Hydraulics")
    st.caption("Sized for plant line studies with stainless schedule 10S presets, fittings, TDH, pump power, NPSHa, segmented systems, and control-valve sizing.")
    tabs = st.tabs(["Single line", "Size comparison", "Pump & NPSHa", "Segmented system", "Parallel branches", "Vessel/static head", "Control valve", "Pump/System curve"])


    base1, base2, base3, base4 = st.columns(4)
    flow_value = base1.number_input("Flow", value=100.0, key="hyd_flow")
    flow_unit = base2.selectbox("Flow unit", VOLUMETRIC_FLOW_UNITS, index=0, key="hyd_flow_unit")
    density = base3.number_input("Density", value=998.0, key="hyd_density")
    density_unit = base4.selectbox("Density unit", DENSITY_UNITS, index=0, key="hyd_density_unit")
    base5, base6, base7, base8 = st.columns(4)
    viscosity = base5.number_input("Viscosity", value=1.0, key="hyd_viscosity")
    viscosity_unit = base6.selectbox("Viscosity unit", VISCOSITY_UNITS, index=0, key="hyd_viscosity_unit")
    pipe_basis = base7.selectbox("Pipe basis", ["schedule_10s_stainless", "custom_id"], format_func=lambda key: {"schedule_10s_stainless": "Schedule 10S stainless preset", "custom_id": "Custom inside diameter"}[key], key="hyd_pipe_basis")
    roughness_mm = base8.number_input("Roughness (mm)", value=0.045, key="hyd_roughness")

    if pipe_basis == "schedule_10s_stainless":
        selected_pipe = st.selectbox("Pipe size", [spec.display_name for spec in SCHEDULE_10S_STAINLESS], index=5, key="hyd_pipe_preset")
        pipe_lookup = {spec.display_name: spec for spec in SCHEDULE_10S_STAINLESS}
        pipe_spec = pipe_lookup[selected_pipe]
        pipe_id = pipe_spec.inside_diameter_in * 25.4
        pipe_id_unit = "mm"
        st.caption(f"Selected {selected_pipe} Sch {pipe_spec.schedule_label} stainless, ID = {pipe_id:.2f} mm")
    else:
        custom1, custom2 = st.columns(2)
        pipe_id = custom1.number_input("Pipe ID", value=52.5, key="hyd_pipe_id")
        pipe_id_unit = custom2.selectbox("Pipe ID unit", LENGTH_UNITS, index=2, key="hyd_pipe_id_unit")

    geom1, geom2, geom3 = st.columns(3)
    pipe_length = geom1.number_input("Pipe length", value=120.0, key="hyd_pipe_len")
    pipe_length_unit = geom2.selectbox("Pipe length unit", LENGTH_UNITS, index=0, key="hyd_pipe_len_unit")
    elevation_change = geom3.number_input("Elevation change", value=12.0, key="hyd_elev")
    elevation_unit = st.selectbox("Elevation unit", LENGTH_UNITS, index=0, key="hyd_elev_unit")

    st.subheader("Fittings and valves")
    fitting_cols = st.columns(5)
    fitting_counts = {}
    for idx, fitting in enumerate(COMMON_FITTINGS):
        fitting_counts[fitting.key] = fitting_cols[idx % 5].number_input(fitting.display_name, min_value=0, value=0, step=1, key=f"fit_{fitting.key}")
    additional_k = st.number_input("Additional user-entered K", value=0.0, key="hyd_additional_k")
    fitting_k_total, fitting_notes = fitting_k_from_counts(fitting_counts)
    fitting_k_total += additional_k
    st.caption(f"Computed fitting K total: {fitting_k_total:.2f}")

    density_kg_m3 = density_to_kg_m3(density, density_unit)
    viscosity_cp = viscosity_to_cp(viscosity, viscosity_unit)
    result = calculate_hydraulics_with_units(
        volumetric_flow_value=flow_value,
        volumetric_flow_unit=flow_unit,
        density_kg_m3=density_kg_m3,
        viscosity_cp=viscosity_cp,
        pipe_id_value=pipe_id,
        pipe_id_unit=pipe_id_unit,
        pipe_length_value=pipe_length,
        pipe_length_unit=pipe_length_unit,
        roughness_mm=roughness_mm,
        elevation_change_value=elevation_change,
        elevation_change_unit=elevation_unit,
        fitting_k_total=fitting_k_total,
    )

    with tabs[0]:
        c1, c2, c3, c4 = st.columns(4)
        velocity_unit = c1.selectbox("Velocity output unit", VELOCITY_UNITS, index=0, key="hyd_vel_out")
        head_unit = c2.selectbox("Head output unit", LENGTH_UNITS, index=0, key="hyd_head_out")
        dp_unit = c3.selectbox("Pressure-drop output unit", ("kPa", "psi", "bar"), index=0, key="hyd_dp_out")
        residence_unit = c4.selectbox("Residence-time output unit", TIME_UNITS, index=0, key="hyd_time_out")
        volume_unit = st.selectbox("Line-volume output unit", VOLUME_UNITS, index=0, key="hyd_vol_out")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Velocity", f"{m_s_to_velocity(result.velocity_m_s, velocity_unit):,.2f} {velocity_unit}")
        m2.metric("Pressure drop", f"{_pressure_delta_from_kpa(result.pressure_drop_kpa, dp_unit):,.2f} {dp_unit}")
        m3.metric("Straight-pipe loss", f"{m_to_length(result.straight_loss_m, head_unit):,.2f} {head_unit}")
        m4.metric("Fitting loss", f"{m_to_length(result.fitting_loss_m, head_unit):,.2f} {head_unit}")
        m5.metric("TDH", f"{m_to_length(result.total_dynamic_head_m, head_unit):,.2f} {head_unit}")
        c5, c6 = st.columns(2)
        c5.metric("Residence time", f"{seconds_to_time(result.residence_time_s, residence_unit):,.2f} {residence_unit}")
        c6.metric("Line volume", f"{m3_to_volume(result.line_volume_m3, volume_unit):,.3f} {volume_unit}")
        _show_notes(result.notes + fitting_notes)
        st.json(asdict(result))

    with tabs[1]:
        velocity_unit = st.selectbox("Comparison velocity unit", VELOCITY_UNITS, index=0, key="hyd_cmp_vel_out")
        head_unit = st.selectbox("Comparison head unit", LENGTH_UNITS, index=0, key="hyd_cmp_head_out")
        dp_unit = st.selectbox("Comparison ΔP unit", ("kPa", "psi", "bar"), index=0, key="hyd_cmp_dp_out")
        residence_unit = st.selectbox("Comparison residence unit", TIME_UNITS, index=0, key="hyd_cmp_time_out")
        rows = compare_schedule_10s_sizes(
            volumetric_flow_value=flow_value,
            volumetric_flow_unit=flow_unit,
            density_kg_m3=density_kg_m3,
            viscosity_cp=viscosity_cp,
            pipe_length_value=pipe_length,
            pipe_length_unit=pipe_length_unit,
            roughness_mm=roughness_mm,
            elevation_change_value=elevation_change,
            elevation_change_unit=elevation_unit,
            fitting_k_total=fitting_k_total,
        )
        rec = recommend_schedule_10s_size(rows)
        if rec is not None:
            st.success(f"Recommended size: {rec.pipe_label} — {rec.reason}")
        df = pd.DataFrame([
            {
                "Pipe": row.pipe_label,
                "ID (mm)": row.pipe_id_mm,
                f"Velocity ({velocity_unit})": m_s_to_velocity(row.velocity_m_s, velocity_unit),
                f"ΔP ({dp_unit})": _pressure_delta_from_kpa(row.pressure_drop_kpa, dp_unit),
                f"TDH ({head_unit})": m_to_length(row.total_dynamic_head_m, head_unit),
                f"Residence ({residence_unit})": seconds_to_time(row.residence_time_s, residence_unit),
                "Preferred velocity band": "Yes" if row.acceptable_velocity else "No",
            }
            for row in rows
        ])
        st.dataframe(df, use_container_width=True)

    with tabs[2]:
        c1, c2, c3 = st.columns(3)
        efficiency = c1.number_input("Pump efficiency (fraction)", min_value=0.05, max_value=1.0, value=0.70, key="hyd_pump_eff")
        power_unit = c2.selectbox("Pump power output unit", POWER_UNITS, index=0, key="hyd_power_out")
        pump_power = calculate_pump_power(volumetric_flow_to_m3_h(flow_value, flow_unit), result.total_dynamic_head_m, density_kg_m3, efficiency)
        c1.metric("Hydraulic power", f"{kw_to_power(pump_power.hydraulic_power_kw, power_unit):,.2f} {power_unit}")
        c2.metric("Brake power", f"{kw_to_power(pump_power.brake_power_kw, power_unit):,.2f} {power_unit}")
        c3.metric("Brake horsepower", f"{pump_power.brake_horsepower_hp:,.2f} hp")
        _show_notes(pump_power.notes)

        st.subheader("NPSHa screen")
        n1, n2, n3, n4 = st.columns(4)
        surface_pressure = n1.number_input("Tank / surface pressure", value=0.0, key="hyd_npsh_surface_pressure")
        surface_pressure_unit = n2.selectbox("Surface pressure unit", PRESSURE_UNITS, index=6, key="hyd_npsh_surface_unit")
        static_head_m = n3.number_input("Static suction head (+ flooded / - lift)", value=2.0, key="hyd_npsh_static_head")
        liquid_temp = n4.number_input("Liquid temperature", value=35.0, key="hyd_npsh_temp")
        n5, n6, n7 = st.columns(3)
        npsh_head_unit = n5.selectbox("NPSH head unit", LENGTH_UNITS, index=0, key="hyd_npsh_head_unit")
        npsh_temp_unit = n6.selectbox("NPSH temperature unit", TEMPERATURE_UNITS, index=0, key="hyd_npsh_temp_unit")
        npsh_dp_unit = n7.selectbox("NPSH pressure-delta unit", ("kPa", "psi", "bar"), index=0, key="hyd_npsh_dp_unit")
        static_head_m = length_to_m(static_head_m, npsh_head_unit)
        liquid_temp_c = temperature_to_c(liquid_temp, npsh_temp_unit)
        suction_loss = st.number_input(
            f"Suction-line loss (head, {npsh_head_unit})",
            value=m_to_length(min(max(result.head_loss_m * 0.3, 0.1), 5.0), npsh_head_unit),
            key="hyd_npsh_loss",
        )
        suction_loss_m = length_to_m(suction_loss, npsh_head_unit)
        npsha = estimate_npsha(surface_pressure, surface_pressure_unit, static_head_m, suction_loss_m, liquid_temp_c, result.velocity_m_s, density_kg_m3)
        st.metric("NPSHa", f"{m_to_length(npsha.npsha_m, npsh_head_unit):,.2f} {npsh_head_unit}")
        _show_notes(npsha.notes)
        st.json(asdict(npsha))

        st.divider()
        st.subheader("Suction vessel + NPSHa scenario")
        st.caption("Turn vessel level into suction head at the pump centerline, then compare the resulting NPSHa against an entered NPSHr when troubleshooting suction limitations.")
        sv1, sv2, sv3, sv4 = st.columns(4)
        vessel_height_for_npsh = sv1.number_input("Suction vessel straight-side height", min_value=0.1, value=6.0, key="hyd_npsh_vessel_height")
        vessel_height_unit_for_npsh = sv2.selectbox("Vessel height unit", LENGTH_UNITS, index=0, key="hyd_npsh_vessel_height_unit")
        vessel_diameter_for_npsh = sv3.number_input("Suction vessel diameter", min_value=0.1, value=2.5, key="hyd_npsh_vessel_diameter")
        vessel_diameter_unit_for_npsh = sv4.selectbox("Vessel diameter unit", LENGTH_UNITS, index=0, key="hyd_npsh_vessel_diameter_unit")
        sv5, sv6, sv7, sv8 = st.columns(4)
        vessel_level_fraction_for_npsh = sv5.number_input("Liquid level fraction", min_value=0.0, value=0.65, key="hyd_npsh_vessel_level_fraction")
        pump_centerline_elevation = sv6.number_input("Pump centerline elevation above vessel bottom", value=1.0, key="hyd_npsh_pump_centerline")
        pump_centerline_unit = sv7.selectbox("Pump elevation unit", LENGTH_UNITS, index=0, key="hyd_npsh_pump_centerline_unit")
        required_npshr_enabled = sv8.checkbox("Compare against required NPSHr", value=True, key="hyd_npsh_required_enabled")
        sv9, sv10, sv11 = st.columns(3)
        required_npshr_value = sv9.number_input("Required NPSHr", min_value=0.01, value=4.5, key="hyd_npsh_required_value", disabled=not required_npshr_enabled)
        required_npshr_unit = sv10.selectbox("Required NPSHr unit", LENGTH_UNITS, index=0, key="hyd_npsh_required_unit", disabled=not required_npshr_enabled)
        vessel_head_output_unit = sv11.selectbox("Scenario head output unit", LENGTH_UNITS, index=0, key="hyd_npsh_scenario_head_out")
        suction_vessel_screen = screen_suction_vessel_npsha(
            vessel_height_m=length_to_m(vessel_height_for_npsh, vessel_height_unit_for_npsh),
            vessel_diameter_m=length_to_m(vessel_diameter_for_npsh, vessel_diameter_unit_for_npsh),
            level_fraction=vessel_level_fraction_for_npsh,
            pump_centerline_elevation_m=length_to_m(pump_centerline_elevation, pump_centerline_unit),
            surface_pressure_value=surface_pressure,
            surface_pressure_unit=surface_pressure_unit,
            suction_line_loss_m=suction_loss,
            liquid_temperature_c=liquid_temp_c,
            velocity_m_s=result.velocity_m_s,
            density_kg_m3=density_kg_m3,
            required_npshr_m=length_to_m(required_npshr_value, required_npshr_unit) if required_npshr_enabled else None,
        )
        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("Liquid level", f"{m_to_length(suction_vessel_screen.vessel.liquid_level_m, vessel_head_output_unit):,.2f} {vessel_head_output_unit}")
        sm2.metric("Static head to pump", f"{m_to_length(suction_vessel_screen.static_head_to_pump_m, vessel_head_output_unit):,.2f} {vessel_head_output_unit}")
        sm3.metric("Scenario NPSHa", f"{m_to_length(suction_vessel_screen.npsha.npsha_m, vessel_head_output_unit):,.2f} {vessel_head_output_unit}")
        if suction_vessel_screen.npsh_margin_m is not None and suction_vessel_screen.npsh_margin_ratio is not None:
            sm4.metric(
                "NPSH margin",
                f"{m_to_length(suction_vessel_screen.npsh_margin_m, vessel_head_output_unit):,.2f} {vessel_head_output_unit}",
                delta=f"{suction_vessel_screen.npsh_margin_ratio:,.2f}x NPSHr",
            )
        else:
            sm4.metric("NPSH margin", "Enter NPSHr")
        _show_notes(suction_vessel_screen.notes)
        st.json(asdict(suction_vessel_screen))

        st.divider()
        st.subheader("Pump field troubleshooting check")
        st.caption("Convert field suction/discharge pressure readings into developed head and hydraulic power, then compare against the expected system TDH to screen for suction starvation, wear, throttling, or instrument-basis issues.")
        pf1, pf2, pf3, pf4 = st.columns(4)
        suction_pressure_value = pf1.number_input("Measured suction pressure", value=5.0, key="hyd_field_suction_pressure")
        suction_pressure_unit = pf2.selectbox("Suction pressure unit", PRESSURE_UNITS, index=6, key="hyd_field_suction_pressure_unit")
        discharge_pressure_value = pf3.number_input("Measured discharge pressure", value=32.0, key="hyd_field_discharge_pressure")
        discharge_pressure_unit = pf4.selectbox("Discharge pressure unit", PRESSURE_UNITS, index=6, key="hyd_field_discharge_pressure_unit")
        pf5, pf6, pf7, pf8 = st.columns(4)
        suction_pipe_id_value = pf5.number_input("Suction line/nozzle ID", min_value=0.01, value=pipe_id, key="hyd_field_suction_id")
        suction_pipe_id_unit = pf6.selectbox("Suction ID unit", LENGTH_UNITS, index=LENGTH_UNITS.index(pipe_id_unit) if pipe_id_unit in LENGTH_UNITS else 0, key="hyd_field_suction_id_unit")
        discharge_pipe_id_value = pf7.number_input("Discharge line/nozzle ID", min_value=0.01, value=pipe_id, key="hyd_field_discharge_id")
        discharge_pipe_id_unit = pf8.selectbox("Discharge ID unit", LENGTH_UNITS, index=LENGTH_UNITS.index(pipe_id_unit) if pipe_id_unit in LENGTH_UNITS else 0, key="hyd_field_discharge_id_unit")
        pf9, pf10, pf11, pf12 = st.columns(4)
        suction_gauge_elevation = pf9.number_input("Suction gauge elevation", value=0.0, key="hyd_field_suction_elev")
        suction_gauge_elevation_unit = pf10.selectbox("Suction elevation unit", LENGTH_UNITS, index=0, key="hyd_field_suction_elev_unit")
        discharge_gauge_elevation = pf11.number_input("Discharge gauge elevation", value=0.0, key="hyd_field_discharge_elev")
        discharge_gauge_elevation_unit = pf12.selectbox("Discharge elevation unit", LENGTH_UNITS, index=0, key="hyd_field_discharge_elev_unit")
        pf13, pf14, pf15, pf16 = st.columns(4)
        field_efficiency = pf13.number_input("Field pump efficiency (fraction)", min_value=0.05, max_value=1.0, value=efficiency, key="hyd_field_efficiency")
        compare_expected_head = pf14.checkbox("Compare against expected system TDH", value=True, key="hyd_field_compare_expected")
        expected_head_value = pf15.number_input("Expected system TDH", min_value=0.0, value=result.total_dynamic_head_m, key="hyd_field_expected_head", disabled=not compare_expected_head)
        expected_head_unit = pf16.selectbox("Expected TDH unit", LENGTH_UNITS, index=0, key="hyd_field_expected_head_unit", disabled=not compare_expected_head)
        field_head_output_unit = st.selectbox("Field-check head output unit", LENGTH_UNITS, index=0, key="hyd_field_head_out")
        field_check = analyze_pump_field_check(
            flow_m3_h=volumetric_flow_to_m3_h(flow_value, flow_unit),
            density_kg_m3=density_kg_m3,
            suction_pressure_value=suction_pressure_value,
            suction_pressure_unit=suction_pressure_unit,
            discharge_pressure_value=discharge_pressure_value,
            discharge_pressure_unit=discharge_pressure_unit,
            suction_pipe_id_mm=length_to_m(suction_pipe_id_value, suction_pipe_id_unit) * 1000.0,
            discharge_pipe_id_mm=length_to_m(discharge_pipe_id_value, discharge_pipe_id_unit) * 1000.0,
            suction_gauge_elevation_m=length_to_m(suction_gauge_elevation, suction_gauge_elevation_unit),
            discharge_gauge_elevation_m=length_to_m(discharge_gauge_elevation, discharge_gauge_elevation_unit),
            pump_efficiency_fraction=field_efficiency,
            expected_system_head_m=length_to_m(expected_head_value, expected_head_unit) if compare_expected_head else None,
            liquid_temperature_c=liquid_temp_c,
        )
        fm1, fm2, fm3, fm4 = st.columns(4)
        fm1.metric("Developed head", f"{m_to_length(field_check.developed_head_m, field_head_output_unit):,.2f} {field_head_output_unit}")
        fm2.metric("Pressure head rise", f"{m_to_length(field_check.differential_pressure_head_m, field_head_output_unit):,.2f} {field_head_output_unit}")
        fm3.metric("Velocity correction", f"{m_to_length(field_check.velocity_head_change_m, field_head_output_unit):,.2f} {field_head_output_unit}")
        fm4.metric("Elevation correction", f"{m_to_length(field_check.elevation_head_change_m, field_head_output_unit):,.2f} {field_head_output_unit}")
        fn1, fn2, fn3, fn4 = st.columns(4)
        fn1.metric("Hydraulic power", f"{kw_to_power(field_check.hydraulic_power_kw, power_unit):,.2f} {power_unit}")
        fn2.metric("Brake power", f"{kw_to_power(field_check.brake_power_kw, power_unit):,.2f} {power_unit}" if field_check.brake_power_kw is not None else "n/a")
        fn3.metric("Brake horsepower", f"{field_check.brake_horsepower_hp:,.2f} hp" if field_check.brake_horsepower_hp is not None else "n/a")
        if field_check.head_margin_to_expected_m is not None:
            expected_head_display_m = field_check.expected_system_head_m if field_check.expected_system_head_m is not None else 0.0
            fn4.metric(
                "Head margin vs expected",
                f"{m_to_length(field_check.head_margin_to_expected_m, field_head_output_unit):,.2f} {field_head_output_unit}",
                delta=f"vs {m_to_length(expected_head_display_m, field_head_output_unit):,.2f} {field_head_output_unit}",
            )
        else:
            fn4.metric("Head margin vs expected", "Not enabled")
        fv1, fv2, fv3, fv4 = st.columns(4)
        fv1.metric("Suction velocity", f"{m_s_to_velocity(field_check.suction_velocity_m_s, velocity_unit):,.2f} {velocity_unit}")
        fv2.metric("Discharge velocity", f"{m_s_to_velocity(field_check.discharge_velocity_m_s, velocity_unit):,.2f} {velocity_unit}")
        fv3.metric("Suction pressure", f"{kpa_abs_to_pressure(field_check.suction_pressure_kpa_abs, suction_pressure_unit):,.2f} {suction_pressure_unit}")
        if field_check.suction_pressure_margin_to_vapor_kpa is not None:
            fv4.metric("Suction margin over vapor", f"{_pressure_delta_from_kpa(field_check.suction_pressure_margin_to_vapor_kpa, npsh_dp_unit):,.2f} {npsh_dp_unit}")
        else:
            fv4.metric("Suction margin over vapor", "Add temperature")
        _show_notes(field_check.notes)

        st.divider()
        st.subheader("Baseline comparison & curve diagnosis")
        st.caption("Compare the current measured case against a known-good baseline and, when available, check both cases against a selected pump curve at the same measured flow.")
        baseline_flow_value = flow_value
        baseline_flow_unit = flow_unit
        baseline_check = None
        baseline_curve_diag = None
        baseline_enabled = st.checkbox("Enable baseline/reference comparison", value=True, key="hyd_field_baseline_enabled")
        if baseline_enabled:
            base1, base2, base3, base4 = st.columns(4)
            baseline_flow_value = base1.number_input("Baseline flow", min_value=0.0, value=flow_value, key="hyd_field_baseline_flow")
            baseline_flow_unit = base2.selectbox("Baseline flow unit", VOLUMETRIC_FLOW_UNITS, index=VOLUMETRIC_FLOW_UNITS.index(flow_unit) if flow_unit in VOLUMETRIC_FLOW_UNITS else 0, key="hyd_field_baseline_flow_unit")
            baseline_suction_pressure_value = base3.number_input("Baseline suction pressure", value=suction_pressure_value, key="hyd_field_baseline_suction_pressure")
            baseline_suction_pressure_unit = base4.selectbox("Baseline suction pressure unit", PRESSURE_UNITS, index=PRESSURE_UNITS.index(suction_pressure_unit) if suction_pressure_unit in PRESSURE_UNITS else 0, key="hyd_field_baseline_suction_pressure_unit")
            base5, base6, base7, base8 = st.columns(4)
            baseline_discharge_pressure_value = base5.number_input("Baseline discharge pressure", value=discharge_pressure_value, key="hyd_field_baseline_discharge_pressure")
            baseline_discharge_pressure_unit = base6.selectbox("Baseline discharge pressure unit", PRESSURE_UNITS, index=PRESSURE_UNITS.index(discharge_pressure_unit) if discharge_pressure_unit in PRESSURE_UNITS else 0, key="hyd_field_baseline_discharge_pressure_unit")
            baseline_suction_pipe_id_value = base7.number_input("Baseline suction ID", min_value=0.01, value=suction_pipe_id_value, key="hyd_field_baseline_suction_id")
            baseline_suction_pipe_id_unit = base8.selectbox("Baseline suction ID unit", LENGTH_UNITS, index=LENGTH_UNITS.index(suction_pipe_id_unit) if suction_pipe_id_unit in LENGTH_UNITS else 0, key="hyd_field_baseline_suction_id_unit")
            base9, base10, base11, base12 = st.columns(4)
            baseline_discharge_pipe_id_value = base9.number_input("Baseline discharge ID", min_value=0.01, value=discharge_pipe_id_value, key="hyd_field_baseline_discharge_id")
            baseline_discharge_pipe_id_unit = base10.selectbox("Baseline discharge ID unit", LENGTH_UNITS, index=LENGTH_UNITS.index(discharge_pipe_id_unit) if discharge_pipe_id_unit in LENGTH_UNITS else 0, key="hyd_field_baseline_discharge_id_unit")
            baseline_suction_elevation = base11.number_input("Baseline suction gauge elevation", value=suction_gauge_elevation, key="hyd_field_baseline_suction_elev")
            baseline_suction_elevation_unit = base12.selectbox("Baseline suction elevation unit", LENGTH_UNITS, index=LENGTH_UNITS.index(suction_gauge_elevation_unit) if suction_gauge_elevation_unit in LENGTH_UNITS else 0, key="hyd_field_baseline_suction_elev_unit")
            base13, base14, base15, base16 = st.columns(4)
            baseline_discharge_elevation = base13.number_input("Baseline discharge gauge elevation", value=discharge_gauge_elevation, key="hyd_field_baseline_discharge_elev")
            baseline_discharge_elevation_unit = base14.selectbox("Baseline discharge elevation unit", LENGTH_UNITS, index=LENGTH_UNITS.index(discharge_gauge_elevation_unit) if discharge_gauge_elevation_unit in LENGTH_UNITS else 0, key="hyd_field_baseline_discharge_elev_unit")
            baseline_efficiency = base15.number_input("Baseline pump efficiency (fraction)", min_value=0.05, max_value=1.0, value=field_efficiency, key="hyd_field_baseline_efficiency")
            baseline_expected_head_value = base16.number_input("Baseline expected TDH", min_value=0.0, value=expected_head_value if compare_expected_head else result.total_dynamic_head_m, key="hyd_field_baseline_expected_head")
            baseline_expected_head_unit = st.selectbox("Baseline expected TDH unit", LENGTH_UNITS, index=LENGTH_UNITS.index(expected_head_unit) if compare_expected_head and expected_head_unit in LENGTH_UNITS else 0, key="hyd_field_baseline_expected_head_unit")

            baseline_check = analyze_pump_field_check(
                flow_m3_h=volumetric_flow_to_m3_h(baseline_flow_value, baseline_flow_unit),
                density_kg_m3=density_kg_m3,
                suction_pressure_value=baseline_suction_pressure_value,
                suction_pressure_unit=baseline_suction_pressure_unit,
                discharge_pressure_value=baseline_discharge_pressure_value,
                discharge_pressure_unit=baseline_discharge_pressure_unit,
                suction_pipe_id_mm=length_to_m(baseline_suction_pipe_id_value, baseline_suction_pipe_id_unit) * 1000.0,
                discharge_pipe_id_mm=length_to_m(baseline_discharge_pipe_id_value, baseline_discharge_pipe_id_unit) * 1000.0,
                suction_gauge_elevation_m=length_to_m(baseline_suction_elevation, baseline_suction_elevation_unit),
                discharge_gauge_elevation_m=length_to_m(baseline_discharge_elevation, baseline_discharge_elevation_unit),
                pump_efficiency_fraction=baseline_efficiency,
                expected_system_head_m=length_to_m(baseline_expected_head_value, baseline_expected_head_unit) if compare_expected_head else None,
                liquid_temperature_c=liquid_temp_c,
            )
            baseline_comparison = compare_pump_field_cases(
                baseline_flow_m3_h=volumetric_flow_to_m3_h(baseline_flow_value, baseline_flow_unit),
                baseline=baseline_check,
                current_flow_m3_h=volumetric_flow_to_m3_h(flow_value, flow_unit),
                current=field_check,
            )
            bc1, bc2, bc3, bc4 = st.columns(4)
            bc1.metric("Flow change", f"{m3_h_to_volumetric_flow(baseline_comparison.flow_delta_m3_h, flow_unit):,.2f} {flow_unit}", delta=f"{baseline_comparison.flow_delta_fraction * 100.0:+.1f}%" if baseline_comparison.flow_delta_fraction is not None else None)
            bc2.metric("Developed-head change", f"{m_to_length(baseline_comparison.developed_head_delta_m, field_head_output_unit):,.2f} {field_head_output_unit}")
            bc3.metric("Hydraulic-power change", f"{kw_to_power(baseline_comparison.hydraulic_power_delta_kw, power_unit):,.2f} {power_unit}")
            if baseline_comparison.brake_power_delta_kw is not None:
                bc4.metric("Brake-power change", f"{kw_to_power(baseline_comparison.brake_power_delta_kw, power_unit):,.2f} {power_unit}")
            else:
                bc4.metric("Brake-power change", "n/a")
            bd1, bd2, bd3, bd4 = st.columns(4)
            bd1.metric("Suction-pressure change", f"{_pressure_delta_from_kpa(baseline_comparison.suction_pressure_delta_kpa, npsh_dp_unit):,.2f} {npsh_dp_unit}")
            bd2.metric("Discharge-pressure change", f"{_pressure_delta_from_kpa(baseline_comparison.discharge_pressure_delta_kpa, npsh_dp_unit):,.2f} {npsh_dp_unit}")
            if baseline_comparison.suction_margin_to_vapor_delta_kpa is not None:
                bd3.metric("Suction-margin change", f"{_pressure_delta_from_kpa(baseline_comparison.suction_margin_to_vapor_delta_kpa, npsh_dp_unit):,.2f} {npsh_dp_unit}")
            else:
                bd3.metric("Suction-margin change", "n/a")
            if baseline_comparison.expected_head_margin_delta_m is not None:
                bd4.metric("Expected-TDH margin change", f"{m_to_length(baseline_comparison.expected_head_margin_delta_m, field_head_output_unit):,.2f} {field_head_output_unit}")
            else:
                bd4.metric("Expected-TDH margin change", "n/a")
            _show_notes(baseline_comparison.notes)
            with st.expander("Baseline case JSON"):
                st.json(asdict(baseline_check))
            with st.expander("Baseline comparison JSON"):
                st.json(asdict(baseline_comparison))

        curve_diag_enabled = st.checkbox("Enable measured-vs-curve diagnosis", value=False, key="hyd_field_curve_diag_enabled")
        if curve_diag_enabled:
            curve_diag_source = st.radio("Curve source for diagnosis", ["Built-in library", "Manual table"], horizontal=True, key="hyd_field_curve_diag_source")
            curve_diag = None
            if curve_diag_source == "Built-in library":
                curve_diag_key = st.selectbox("Diagnosis curve", available_builtin_curve_options(), format_func=lambda key: get_builtin_curve(key).name, key="hyd_field_curve_diag_builtin")
                curve_diag = get_builtin_curve(curve_diag_key)
            else:
                diag_table = pd.DataFrame([
                    {"flow_m3_h": 0.0, "head_m": max(field_check.developed_head_m * 1.25, 10.0)},
                    {"flow_m3_h": max(volumetric_flow_to_m3_h(flow_value, flow_unit) * 0.6, 5.0), "head_m": max(field_check.developed_head_m * 1.1, 8.0)},
                    {"flow_m3_h": max(volumetric_flow_to_m3_h(flow_value, flow_unit), 10.0), "head_m": max(field_check.developed_head_m, 5.0)},
                    {"flow_m3_h": max(volumetric_flow_to_m3_h(flow_value, flow_unit) * 1.35, 15.0), "head_m": max(field_check.developed_head_m * 0.7, 2.0)},
                ])
                edited_diag_table = st.data_editor(diag_table, num_rows="dynamic", use_container_width=True, key="hyd_field_curve_diag_manual")
                curve_diag_name = st.text_input("Diagnosis curve name", value="Field reference curve", key="hyd_field_curve_diag_name")
                curve_diag_family = st.text_input("Diagnosis curve family", value="Field troubleshooting", key="hyd_field_curve_diag_family")
                curve_diag = build_pump_curve_from_xy_rows(curve_diag_name, edited_diag_table.to_dict(orient="records"), "flow_m3_h", "head_m", family=curve_diag_family)
            if curve_diag is not None:
                current_curve_diag = compare_measured_point_to_curve(
                    curve_diag,
                    measured_flow_m3_h=volumetric_flow_to_m3_h(flow_value, flow_unit),
                    measured_head_m=field_check.developed_head_m,
                )
                curve_diag_rows = [{
                    "Case": "Current",
                    f"Measured flow ({flow_unit})": m3_h_to_volumetric_flow(current_curve_diag.measured_flow_m3_h, flow_unit),
                    f"Measured head ({field_head_output_unit})": m_to_length(current_curve_diag.measured_head_m, field_head_output_unit),
                    f"Curve head at same flow ({field_head_output_unit})": m_to_length(current_curve_diag.curve_head_m, field_head_output_unit) if current_curve_diag.curve_head_m is not None else None,
                    f"Head delta vs curve ({field_head_output_unit})": m_to_length(current_curve_diag.head_delta_m, field_head_output_unit) if current_curve_diag.head_delta_m is not None else None,
                    "Status": current_curve_diag.status,
                }]
                if baseline_enabled and baseline_check is not None:
                    baseline_curve_diag = compare_measured_point_to_curve(
                        curve_diag,
                        measured_flow_m3_h=volumetric_flow_to_m3_h(baseline_flow_value, baseline_flow_unit),
                        measured_head_m=baseline_check.developed_head_m,
                    )
                    curve_diag_rows.append({
                        "Case": "Baseline",
                        f"Measured flow ({flow_unit})": m3_h_to_volumetric_flow(baseline_curve_diag.measured_flow_m3_h, flow_unit),
                        f"Measured head ({field_head_output_unit})": m_to_length(baseline_curve_diag.measured_head_m, field_head_output_unit),
                        f"Curve head at same flow ({field_head_output_unit})": m_to_length(baseline_curve_diag.curve_head_m, field_head_output_unit) if baseline_curve_diag.curve_head_m is not None else None,
                        f"Head delta vs curve ({field_head_output_unit})": m_to_length(baseline_curve_diag.head_delta_m, field_head_output_unit) if baseline_curve_diag.head_delta_m is not None else None,
                        "Status": baseline_curve_diag.status,
                    })
                st.dataframe(pd.DataFrame(curve_diag_rows), use_container_width=True)
                curve_fig = go.Figure()
                curve_fig.add_trace(go.Scatter(
                    x=[m3_h_to_volumetric_flow(point.flow_m3_h, flow_unit) for point in curve_diag.points],
                    y=[m_to_length(point.head_m, field_head_output_unit) for point in curve_diag.points],
                    mode="lines+markers",
                    name=curve_diag.name,
                ))
                curve_fig.add_trace(go.Scatter(
                    x=[m3_h_to_volumetric_flow(current_curve_diag.measured_flow_m3_h, flow_unit)],
                    y=[m_to_length(current_curve_diag.measured_head_m, field_head_output_unit)],
                    mode="markers",
                    marker=dict(size=12),
                    name="Current measured case",
                ))
                if baseline_enabled and baseline_curve_diag is not None:
                    curve_fig.add_trace(go.Scatter(
                        x=[m3_h_to_volumetric_flow(baseline_curve_diag.measured_flow_m3_h, flow_unit)],
                        y=[m_to_length(baseline_curve_diag.measured_head_m, field_head_output_unit)],
                        mode="markers",
                        marker=dict(size=12, symbol="diamond"),
                        name="Baseline measured case",
                    ))
                curve_fig.update_layout(title="Measured cases vs selected pump curve", xaxis_title=f"Flow ({flow_unit})", yaxis_title=f"Head ({field_head_output_unit})")
                st.plotly_chart(curve_fig, use_container_width=True)
                _show_notes(current_curve_diag.notes)
                if baseline_enabled and baseline_curve_diag is not None:
                    _show_notes([f"Baseline: {note}" for note in baseline_curve_diag.notes])
                with st.expander("Current field-check JSON"):
                    st.json(asdict(field_check))
                with st.expander("Curve diagnosis JSON"):
                    st.json({
                        "current": asdict(current_curve_diag),
                        "baseline": asdict(baseline_curve_diag) if baseline_enabled and baseline_curve_diag is not None else None,
                    })
        else:
            with st.expander("Current field-check JSON"):
                st.json(asdict(field_check))

        # ── BEP Proximity & Instrument Bias ────────────────────────────
        st.divider()
        st.subheader("BEP proximity & instrument-bias screen")
        st.caption("Estimate how close the current operating point sits to the pump's best-efficiency point and whether standard gauge accuracy could explain any flow/head deviation from expected values.")

        bep_enabled = st.checkbox("Enable BEP proximity assessment", value=True, key="hyd_bep_enabled")
        if bep_enabled:
            bep_curve_source = st.radio(
                "Curve for BEP estimate",
                ["Built-in library", "Manual table"],
                horizontal=True,
                key="hyd_bep_curve_source",
            )
            bep_curve_used = None
            if bep_curve_source == "Built-in library":
                bep_curve_key = st.selectbox(
                    "BEP curve",
                    available_builtin_curve_options(),
                    format_func=lambda key: get_builtin_curve(key).name,
                    key="hyd_bep_builtin",
                )
                bep_curve_used = get_builtin_curve(bep_curve_key)
            else:
                st.caption("Enter enough flow/head points to estimate a BEP (2 minimum).")
                bep_table = pd.DataFrame([
                    { "flow_m3_h": 0.0, "head_m": max(field_check.developed_head_m * 1.3, 15.0)},
                    { "flow_m3_h": max(volumetric_flow_to_m3_h(flow_value, flow_unit) * 0.5, 5.0), "head_m": max(field_check.developed_head_m * 1.15, 10.0)},
                    { "flow_m3_h": max(volumetric_flow_to_m3_h(flow_value, flow_unit), 10.0), "head_m": max(field_check.developed_head_m * 1.0, 5.0)},
                    { "flow_m3_h": max(volumetric_flow_to_m3_h(flow_value, flow_unit) * 1.4, 15.0), "head_m": max(field_check.developed_head_m * 0.65, 2.0)},
                ])
                edited_bep_table = st.data_editor(bep_table, num_rows="dynamic", use_container_width=True, key="hyd_bep_manual_table")
                bep_curve_name = st.text_input("BEP curve name", value="BEP reference curve", key="hyd_bep_manual_name")
                bep_curve_family = st.text_input("BEP curve family", value="BEP screening", key="hyd_bep_manual_family")
                try:
                    bep_curve_used = build_pump_curve_from_xy_rows(
                        bep_curve_name, edited_bep_table.to_dict(orient="records"), "flow_m3_h", "head_m", family=bep_curve_family,
                    )
                except Exception:
                    st.warning("Manual BEP curve needs at least two valid points for estimation.")

            if bep_curve_used is not None:
                cur_flow_m3_h = volumetric_flow_to_m3_h(flow_value, flow_unit)
                cur_head_m = field_check.developed_head_m

                # Preferred zone controls
                bz1, bz2 = st.columns(2)
                pref_zone_lo = bz1.slider("Preferred zone lower bound (fraction of curve range)", min_value=0.4, max_value=0.9, value=0.70, step=0.05, key="hyd_bep_zone_lo")
                pref_zone_hi = bz2.slider("Preferred zone upper bound (fraction of curve range)", min_value=0.6, max_value=1.0, value=0.95, step=0.05, key="hyd_bep_zone_hi")
                if pref_zone_lo >= pref_zone_hi:
                    pref_zone_hi = pref_zone_lo + 0.05

                bep_est = estimate_bep_from_curve(bep_curve_used, preferred_zone=(pref_zone_lo, pref_zone_hi))
                bep_result = assess_bep_proximity(
                    bep_curve_used,
                    measured_flow_m3_h=cur_flow_m3_h,
                    measured_head_m=cur_head_m,
                    preferred_zone=(pref_zone_lo, pref_zone_hi),
                    bep_estimate=bep_est,
                )

                bp1, bp2, bp3, bp4 = st.columns(4)
                bp1.metric("Estimated BEP flow", f"{m3_h_to_volumetric_flow(bep_result.bep_flow_m3_h, flow_unit):,.1f} {flow_unit}", help=f"~{bep_est.flow_fraction_of_max:.0%} of curve range")
                bp2.metric("Estimated BEP head", f"{m_to_length(bep_result.bep_head_m, field_head_output_unit):,.1f} {field_head_output_unit}")
                bp3.metric(
                    "BEP proximity status",
                    _title_case_status(bep_result.proximity_status),
                    delta=f"Flow offset {bep_result.flow_offset_fraction:+.1%}"
                )
                bp4.metric(
                    "Inside preferred zone",
                    "Yes" if bep_result.inside_preferred_zone else "No",
                )

                if bep_result.reliability_risk:
                    st.warning(bep_result.reliability_risk)

                b_fig = go.Figure()
                b_fig.add_trace(go.Scatter(
                    x=[m3_h_to_volumetric_flow(pt.flow_m3_h, flow_unit) for pt in bep_curve_used.points],
                    y=[m_to_length(pt.head_m, field_head_output_unit) for pt in bep_curve_used.points],
                    mode="lines+markers",
                    name=bep_curve_used.name,
                    line=dict(dash="solid"),
                ))
                # Mark BEP point
                b_fig.add_trace(go.Scatter(
                    x=[m3_h_to_volumetric_flow(bep_result.bep_flow_m3_h, flow_unit)],
                    y=[m_to_length(bep_result.bep_head_m, field_head_output_unit)],
                    mode="markers",
                    marker=dict(size=14, symbol="star", color="green"),
                    name=f"Estimated BEP ({m3_h_to_volumetric_flow(bep_result.bep_flow_m3_h, flow_unit):.1f} {flow_unit}, {m_to_length(bep_result.bep_head_m, field_head_output_unit):.1f} {field_head_output_unit})",
                ))
                # Mark measured current point
                b_fig.add_trace(go.Scatter(
                    x=[m3_h_to_volumetric_flow(cur_flow_m3_h, flow_unit)],
                    y=[m_to_length(cur_head_m, field_head_output_unit)],
                    mode="markers",
                    marker=dict(size=12, symbol="circle", color="red"),
                    name=f"Current measured ({m3_h_to_volumetric_flow(cur_flow_m3_h, flow_unit):.1f} {flow_unit}, {m_to_length(cur_head_m, field_head_output_unit):.1f} {field_head_output_unit})",
                ))
                # Mark preferred zone band
                flow_range = bep_curve_used.points[-1].flow_m3_h - bep_curve_used.points[0].flow_m3_h
                lo_f = m3_h_to_volumetric_flow(bep_curve_used.points[0].flow_m3_h + pref_zone_lo * flow_range, flow_unit)
                hi_f = m3_h_to_volumetric_flow(bep_curve_used.points[0].flow_m3_h + pref_zone_hi * flow_range, flow_unit)
                b_fig.add_vrect(
                    x0=lo_f, x1=hi_f,
                    fillcolor="green", opacity=0.08,
                    line_width=0,
                    annotation_text=f"Preferred zone ({pref_zone_lo:.0%}–{pref_zone_hi:.0%})",
                    annotation_position="top",
                )
                # Mark baseline if available
                if baseline_enabled and baseline_curve_diag is not None and baseline_check is not None:
                    bl_flow = volumetric_flow_to_m3_h(baseline_flow_value, baseline_flow_unit)
                    b_fig.add_trace(go.Scatter(
                        x=[m3_h_to_volumetric_flow(bl_flow, flow_unit)],
                        y=[m_to_length(baseline_check.developed_head_m, field_head_output_unit)],
                        mode="markers",
                        marker=dict(size=12, symbol="diamond", color="blue"),
                        name=f"Baseline ({m3_h_to_volumetric_flow(bl_flow, flow_unit):.1f} {flow_unit}, {m_to_length(baseline_check.developed_head_m, field_head_output_unit):.1f} {field_head_output_unit})",
                    ))
                b_fig.update_layout(
                    title=f"BEP proximity on {bep_curve_used.name}",
                    xaxis_title=f"Flow ({flow_unit})",
                    yaxis_title=f"Head ({field_head_output_unit})",
                )
                st.plotly_chart(b_fig, use_container_width=True)
                _show_notes(bep_result.notes)

        instrument_enabled = st.checkbox("Enable instrument-bias screen", value=True, key="hyd_instr_bias_enabled")
        if instrument_enabled:
            expected_flow_displaying = field_check.expected_system_head_m if field_check.expected_system_head_m is not None else field_check.developed_head_m
            ib1, ib2, ib3, ib4 = st.columns(4)
            ib_flow_expected_value = ib1.number_input(
                "Expected/reference flow",
                min_value=0.0,
                value=flow_value,
                key="hyd_instr_exp_flow",
            )
            ib_flow_expected_unit = ib2.selectbox(
                "Expected flow unit",
                VOLUMETRIC_FLOW_UNITS,
                index=VOLUMETRIC_FLOW_UNITS.index(flow_unit) if flow_unit in VOLUMETRIC_FLOW_UNITS else 0,
                key="hyd_instr_exp_flow_unit",
            )
            ib_head_expected_value = ib3.number_input(
                f"Expected/reference head ({field_head_output_unit})",
                min_value=0.0,
                value=m_to_length(field_check.developed_head_m, field_head_output_unit),
                key="hyd_instr_exp_head",
            )
            ib_gauge_accuracy = ib4.selectbox(
                "Gauge accuracy assumption",
                ["2%", "3%", "5%"],
                index=0,
                key="hyd_instr_gauge_acc",
            )
            gauge_acc_num = float(ib_gauge_accuracy.rstrip("%"))

            ib_bias = screen_instrument_bias(
                measured_flow_m3_h=volumetric_flow_to_m3_h(flow_value, flow_unit),
                measured_head_m=field_check.developed_head_m,
                expected_flow_m3_h=volumetric_flow_to_m3_h(ib_flow_expected_value, ib_flow_expected_unit),
                expected_head_m=length_to_m(ib_head_expected_value, field_head_output_unit),
                flow_gauge_accuracy_pct=gauge_acc_num,
                pressure_gauge_accuracy_pct=gauge_acc_num,
            )

            bias1, bias2, bias3, bias4 = st.columns(4)
            bias1.metric(
                "Flow discrepancy",
                f"{m3_h_to_volumetric_flow(ib_bias.flow_discrepancy_m3_h, flow_unit):+.2f} {flow_unit}",
                delta=f"{ib_bias.flow_bias_pct:.1f}% of reading",
            )
            bias2.metric(
                "Head discrepancy",
                f"{m_to_length(ib_bias.head_discrepancy_m, field_head_output_unit):+.2f} {field_head_output_unit}",
                delta=f"{ib_bias.head_bias_pct:.1f}% of reading",
            )
            bias3.metric(
                "Flow explainable by gauge error",
                f"{ib_gauge_accuracy}" if ib_bias.flow_explainable_with_2pct_gauge or (gauge_acc_num == 5 and ib_bias.flow_explainable_with_5pct_gauge) else f"No — exceeds {ib_gauge_accuracy}",
            )
            bias4.metric(
                "Head explainable by gauge error",
                f"{ib_gauge_accuracy}" if ib_bias.head_explainable_with_2pct_gauge or (gauge_acc_num == 5 and ib_bias.head_explainable_with_5pct_gauge) else f"No — exceeds {ib_gauge_accuracy}",
            )

            if ib_bias.likely_explainable:
                st.info("This deviation may be attributable to normal instrument measurement uncertainty rather than actual pump degradation or system change.")
            else:
                st.warning("Discrepancy exceeds the assumed gauge accuracy band on both flow and head — investigate process changes, calibration drift, or true pump performance loss before attributing readings to normal scatter.")

            _show_notes(ib_bias.notes)

    with tabs[3]:
        st.caption("Enter up to three sequential piping sections to estimate total system TDH and pressure drop.")
        sg1, sg2, sg3, sg4, sg5 = st.columns(5)
        seg_id_unit = sg1.selectbox("Segment ID unit", LENGTH_UNITS, index=LENGTH_UNITS.index("mm") if "mm" in LENGTH_UNITS else 0, key="hyd_seg_id_unit")
        seg_len_unit = sg2.selectbox("Segment length unit", LENGTH_UNITS, index=LENGTH_UNITS.index("m") if "m" in LENGTH_UNITS else 0, key="hyd_seg_len_unit")
        seg_elev_unit = sg3.selectbox("Segment elevation unit", LENGTH_UNITS, index=LENGTH_UNITS.index("m") if "m" in LENGTH_UNITS else 0, key="hyd_seg_elev_unit")
        seg_head_out_unit = sg4.selectbox("Segment head output unit", LENGTH_UNITS, index=LENGTH_UNITS.index("m") if "m" in LENGTH_UNITS else 0, key="hyd_seg_head_out")
        seg_dp_out_unit = sg5.selectbox("Segment ΔP output unit", ("kPa", "psi", "bar"), index=0, key="hyd_seg_dp_out")
        default_segments = [
            ("Suction", 2.157 * 25.4, 12.0, 0.5, 1.5),
            ("Discharge main", 2.157 * 25.4, 90.0, 0.045, 8.0),
            ("Final rise", 2.157 * 25.4, 18.0, 0.045, 4.0),
        ]
        segments = []
        for idx, (name, default_id_mm, default_len, default_rough, default_k) in enumerate(default_segments, start=1):
            st.markdown(f"Section {idx}: {name}")
            s1, s2, s3, s4, s5 = st.columns(5)
            seg_name = s1.text_input("Name", value=name, key=f"seg_name_{idx}")
            seg_id = s2.number_input(f"ID ({seg_id_unit})", value=m_to_length(default_id_mm / 1000.0, seg_id_unit), key=f"seg_id_{idx}")
            seg_len = s3.number_input(f"Length ({seg_len_unit})", value=m_to_length(default_len, seg_len_unit), key=f"seg_len_{idx}")
            seg_elev = s4.number_input(f"Elevation change ({seg_elev_unit})", value=m_to_length(0.0 if idx != 3 else 8.0, seg_elev_unit), key=f"seg_elev_{idx}")
            seg_k = s5.number_input("Total K", value=default_k, key=f"seg_k_{idx}")
            segments.append(PipeSegment(seg_name, length_to_m(seg_id, seg_id_unit) * 1000.0, length_to_m(seg_len, seg_len_unit), default_rough, length_to_m(seg_elev, seg_elev_unit), seg_k))
        seg_result = calculate_segmented_system(volumetric_flow_to_m3_h(flow_value, flow_unit), density_kg_m3, viscosity_cp, segments)
        st.metric("Segmented system TDH", f"{m_to_length(seg_result.total_dynamic_head_m, seg_head_out_unit):,.2f} {seg_head_out_unit}")
        st.metric("Segmented system ΔP", f"{_pressure_delta_from_kpa(seg_result.total_pressure_drop_kpa, seg_dp_out_unit):,.2f} {seg_dp_out_unit}")
        st.dataframe(pd.DataFrame([asdict(segment) for segment in seg_result.segments]), use_container_width=True)
        _show_notes(seg_result.notes)
    with tabs[4]:
        st.caption("Check whether a parallel network will naturally self-balance or whether the entered split requires throttling/orifice loss to hold the intended branch flows.")
        pb1, pb2, pb3 = st.columns(3)
        parallel_id_unit = pb1.selectbox("Branch ID unit", LENGTH_UNITS, index=LENGTH_UNITS.index("mm") if "mm" in LENGTH_UNITS else 0, key="hyd_parallel_id_unit")
        parallel_len_unit = pb2.selectbox("Branch length unit", LENGTH_UNITS, index=LENGTH_UNITS.index("m") if "m" in LENGTH_UNITS else 0, key="hyd_parallel_len_unit")
        parallel_elev_unit = pb3.selectbox("Branch elevation unit", LENGTH_UNITS, index=LENGTH_UNITS.index("m") if "m" in LENGTH_UNITS else 0, key="hyd_parallel_elev_unit")
        branch_mode = st.radio(
            "Parallel branch mode",
            ("entered_split", "self_balancing"),
            format_func=lambda mode: "Entered split check" if mode == "entered_split" else "Self-balancing estimate",
            horizontal=True,
            key="hyd_parallel_mode",
        )
        branch_defaults = [
            ("Branch A", 54.8, 30.0, 0.0, 4.0, 0.40),
            ("Branch B", 54.8, 45.0, 2.0, 6.0, 0.35),
            ("Branch C", 54.8, 25.0, -1.0, 3.0, 0.25),
        ]
        branches = []
        fractions = []
        for idx, (name, id_mm, length_m, elev_m, k_total, split) in enumerate(branch_defaults, start=1):
            st.markdown(f"Parallel branch {idx}")
            b1, b2, b3, b4, b5, b6 = st.columns(6)
            branch_name = b1.text_input("Name", value=name, key=f"hyd_branch_name_{idx}")
            branch_id = b2.number_input(f"ID ({parallel_id_unit})", value=m_to_length(id_mm / 1000.0, parallel_id_unit), key=f"hyd_branch_id_{idx}")
            branch_len = b3.number_input(f"Length ({parallel_len_unit})", value=m_to_length(length_m, parallel_len_unit), key=f"hyd_branch_len_{idx}")
            branch_elev = b4.number_input(f"Elevation change ({parallel_elev_unit})", value=m_to_length(elev_m, parallel_elev_unit), key=f"hyd_branch_elev_{idx}")
            branch_k = b5.number_input("Total K", value=k_total, key=f"hyd_branch_k_{idx}")
            branch_split = b6.number_input(
                "Flow split fraction",
                min_value=0.0,
                value=split,
                key=f"hyd_branch_split_{idx}",
                disabled=branch_mode == "self_balancing",
            )
            branches.append(PipeSegment(branch_name, length_to_m(branch_id, parallel_id_unit) * 1000.0, length_to_m(branch_len, parallel_len_unit), roughness_mm, length_to_m(branch_elev, parallel_elev_unit), branch_k))
            fractions.append(branch_split)
        total_flow_m3_h = volumetric_flow_to_m3_h(flow_value, flow_unit)
        branch_result = analyze_parallel_branches(
            total_flow_m3_h=total_flow_m3_h,
            density_kg_m3=density_kg_m3,
            viscosity_cp=viscosity_cp,
            branches=branches,
            branch_split_fractions=fractions,
            mode=branch_mode,
        )
        st.metric("Branch head spread", f"{m_to_length(branch_result.head_spread_m, head_unit):,.4f} {head_unit}")
        if branch_result.common_branch_head_m is not None:
            st.metric("Common balanced head", f"{m_to_length(branch_result.common_branch_head_m, head_unit):,.3f} {head_unit}")
        branch_df = pd.DataFrame([
            {
                "Branch": branch.name,
                f"Flow ({flow_unit})": m3_h_to_volumetric_flow(branch.flow_m3_h, flow_unit),
                "% of total flow": branch.percent_of_total_flow,
                f"ΔP ({dp_unit})": _pressure_delta_from_kpa(branch.pressure_drop_kpa, dp_unit),
                f"TDH ({head_unit})": m_to_length(branch.total_dynamic_head_m, head_unit),
                f"Velocity ({velocity_unit})": m_s_to_velocity(branch.velocity_m_s, velocity_unit),
                f"Head error ({head_unit})": m_to_length(branch.head_error_m, head_unit) if branch.head_error_m is not None else None,
                f"Needed extra loss ({head_unit})": m_to_length(branch.balancing_loss_m, head_unit) if branch.balancing_loss_m is not None else None,
            }
            for branch in branch_result.branches
        ])
        st.dataframe(branch_df, use_container_width=True)
        if branch_mode == "entered_split":
            self_balancing_result = analyze_parallel_branches(
                total_flow_m3_h=total_flow_m3_h,
                density_kg_m3=density_kg_m3,
                viscosity_cp=viscosity_cp,
                branches=branches,
                mode="self_balancing",
            )
            st.caption("Natural self-balancing comparison for the same hardware and total flow")
            self_balancing_df = pd.DataFrame([
                {
                    "Branch": branch.name,
                    f"Balanced flow ({flow_unit})": m3_h_to_volumetric_flow(branch.flow_m3_h, flow_unit),
                    "% of total flow": branch.percent_of_total_flow,
                    f"TDH ({head_unit})": m_to_length(branch.total_dynamic_head_m, head_unit),
                }
                for branch in self_balancing_result.branches
            ])
            st.dataframe(self_balancing_df, use_container_width=True)

            balance_device_rows = []
            cd_col, orifice_unit_col = st.columns(2)
            balancing_cd = cd_col.number_input(
                "Balancing-orifice discharge coefficient Cd",
                min_value=0.10,
                max_value=1.00,
                value=0.62,
                step=0.01,
                key="hyd_parallel_balance_cd",
            )
            orifice_output_unit = orifice_unit_col.selectbox(
                "Balancing device diameter unit",
                LENGTH_UNITS,
                index=LENGTH_UNITS.index("mm") if "mm" in LENGTH_UNITS else 0,
                key="hyd_parallel_balance_orifice_unit",
            )
            for segment, branch in zip(branches, branch_result.branches):
                if branch.balancing_loss_m is None or branch.balancing_loss_m <= 0.05 or branch.flow_m3_h <= 0.0:
                    continue
                device = size_branch_balancing_device(
                    branch=segment,
                    branch_flow_m3_h=branch.flow_m3_h,
                    density_kg_m3=density_kg_m3,
                    required_additional_head_m=branch.balancing_loss_m,
                    discharge_coefficient=balancing_cd,
                )
                balance_device_rows.append(
                    {
                        "Branch": device.branch_name,
                        f"Needed extra loss ({head_unit})": m_to_length(device.required_additional_head_m, head_unit),
                        f"Needed extra ΔP ({dp_unit})": _pressure_delta_from_kpa(device.required_additional_pressure_drop_kpa, dp_unit),
                        "Required Kv": device.required_kv,
                        "Required Cv": device.required_cv,
                        f"Equivalent orifice ({orifice_output_unit})": m_to_length(device.equivalent_orifice_diameter_mm / 1000.0, orifice_output_unit) if device.equivalent_orifice_diameter_mm is not None else None,
                        "Beta ratio": device.equivalent_orifice_beta_ratio,
                        "Notes": " ".join(device.notes),
                    }
                )
            if balance_device_rows:
                st.caption("Balancing-device screen for branches that need extra throttling to hold the entered split")
                st.dataframe(pd.DataFrame(balance_device_rows), use_container_width=True)
            _show_notes(self_balancing_result.notes)
        _show_notes(branch_result.notes)

    with tabs[5]:
        st.caption("Estimate vessel-derived static head from liquid level for tanks, feed vessels, or suction/discharge receivers.")
        v1, v2, v3, v4, v5 = st.columns(5)
        vessel_height = v1.number_input("Vessel straight-side height", min_value=0.1, value=6.0, key="hyd_vessel_height")
        vessel_height_unit = v2.selectbox("Height unit", LENGTH_UNITS, index=0, key="hyd_vessel_height_unit")
        vessel_diameter = v3.number_input("Vessel diameter", min_value=0.1, value=2.5, key="hyd_vessel_diameter")
        vessel_diameter_unit = v4.selectbox("Diameter unit", LENGTH_UNITS, index=0, key="hyd_vessel_diameter_unit")
        level_fraction = v5.number_input("Liquid level fraction", min_value=0.0, value=0.65, key="hyd_vessel_level_fraction")
        vh1, vh2, vh3 = st.columns(3)
        head_unit = vh1.selectbox("Vessel head output unit", LENGTH_UNITS, index=0, key="hyd_vessel_head_out")
        volume_unit = vh2.selectbox("Vessel volume output unit", VOLUME_UNITS, index=0, key="hyd_vessel_vol_out")
        vessel_pressure_out_unit = vh3.selectbox("Vessel pressure output unit", PRESSURE_UNITS, index=6, key="hyd_vessel_pressure_out")
        vessel = calculate_vessel_static_head(
            liquid_height_m=length_to_m(vessel_height, vessel_height_unit),
            vessel_diameter_m=length_to_m(vessel_diameter, vessel_diameter_unit),
            density_kg_m3=density_kg_m3,
            level_fraction=level_fraction,
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Static head", f"{m_to_length(vessel.static_head_m, head_unit):,.2f} {head_unit}")
        m2.metric("Bottom pressure", f"{kpa_abs_to_pressure(vessel.bottom_pressure_kpa_g + 101.325, vessel_pressure_out_unit):,.2f} {vessel_pressure_out_unit}")
        m3.metric("Liquid volume", f"{m3_to_volume(vessel.volume_m3, volume_unit):,.2f} {volume_unit}")
        _show_notes(vessel.notes)
        st.json(asdict(vessel))

    with tabs[6]:
        st.caption("Screen liquid control-valve sizing from line flow, density, and target valve pressure drop, then add cavitation/flashing checks from inlet pressure, liquid temperature, and FL.")
        c1, c2, c3 = st.columns(3)
        valve_dp = c1.number_input("Target valve ΔP", min_value=0.01, value=max(result.pressure_drop_kpa * 0.35, 20.0), key="hyd_cv_dp")
        valve_dp_unit = c2.selectbox("Valve ΔP unit", ("kPa", "psi", "bar"), index=0, key="hyd_cv_dp_unit")
        rated_cv_enabled = c3.checkbox("Compare against rated Cv", value=True, key="hyd_cv_has_rated")
        valve_dp_kpa = valve_dp if valve_dp_unit == "kPa" else (valve_dp / 0.1450377377 if valve_dp_unit == "psi" else valve_dp * 100.0)
        c4, c5 = st.columns(2)
        rated_cv = c4.number_input("Rated Cv", min_value=0.01, value=90.0, key="hyd_cv_rated", disabled=not rated_cv_enabled)
        other_losses_unit = c5.selectbox("Installed-loss unit", ("kPa", "psi", "bar"), index=0, key="hyd_cv_other_losses_unit")
        other_losses_value = st.number_input(f"Installed other losses excl. valve ({other_losses_unit})", min_value=0.0, value=_pressure_delta_from_kpa(max(result.pressure_drop_kpa, 0.0), other_losses_unit), key="hyd_cv_other_losses")
        other_losses_kpa = _pressure_delta_to_kpa(other_losses_value, other_losses_unit)

        st.markdown("**Cavitation / flashing screen**")
        q1, q2, q3, q4 = st.columns(4)
        inlet_pressure_value = q1.number_input("Valve inlet pressure", min_value=0.01, value=max(pressure_to_kpa_abs(35.0, "psig"), valve_dp_kpa + 50.0), key="hyd_cv_inlet_pressure")
        inlet_pressure_unit = q2.selectbox("Inlet pressure unit", PRESSURE_UNITS, index=0, key="hyd_cv_inlet_pressure_unit")
        liquid_temp_value = q3.number_input("Liquid temperature", value=80.0, key="hyd_cv_liquid_temp")
        liquid_temp_unit = q4.selectbox("Liquid temperature unit", TEMPERATURE_UNITS, index=0, key="hyd_cv_liquid_temp_unit")
        q5, q6 = st.columns(2)
        pressure_recovery_factor_fl = q5.number_input("Valve FL (pressure recovery factor)", min_value=0.10, max_value=1.00, value=0.90, step=0.01, key="hyd_cv_fl")
        q6.caption("Typical screening starting points: globe ~0.9, rotary/high-recovery trims lower. Confirm with the vendor for the actual trim.")
        valve_pressure_out_unit = st.selectbox("Valve pressure output unit", PRESSURE_UNITS, index=0, key="hyd_cv_pressure_out_unit")
        liquid_temp_c = temperature_to_c(liquid_temp_value, liquid_temp_unit)

        valve = size_control_valve(
            flow_m3_h=volumetric_flow_to_m3_h(flow_value, flow_unit),
            differential_pressure_kpa=valve_dp_kpa,
            density_kg_m3=density_kg_m3,
            installed_pressure_drop_kpa=other_losses_kpa,
            rated_cv=rated_cv if rated_cv_enabled else None,
            inlet_pressure_value=inlet_pressure_value,
            inlet_pressure_unit=inlet_pressure_unit,
            liquid_temperature_c=liquid_temp_c,
            pressure_recovery_factor_fl=pressure_recovery_factor_fl,
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Required Cv", f"{valve.required_cv:,.1f}")
        m2.metric("Required Kv", f"{valve.required_kv:,.1f}")
        m3.metric("Specific gravity", f"{valve.specific_gravity:,.3f}")
        authority_display = f"{valve.valve_authority:,.2f}" if valve.valve_authority is not None else "n/a"
        m4.metric("Valve authority", authority_display)
        if rated_cv_enabled and valve.rated_cv is not None and valve.rated_cv > 0 and valve.opening_fraction_linear is not None and valve.opening_fraction_equal_percentage is not None:
            o1, o2, o3 = st.columns(3)
            o1.metric("Rated Cv loading", f"{valve.required_cv / valve.rated_cv * 100.0:,.1f}%")
            o2.metric("Linear trim opening", f"{valve.opening_fraction_linear * 100.0:,.1f}%")
            o3.metric("Equal-% opening", f"{valve.opening_fraction_equal_percentage * 100.0:,.1f}%")

        cstat1, cstat2, cstat3, cstat4 = st.columns(4)
        cstat1.metric("Outlet pressure", f"{kpa_abs_to_pressure(valve.outlet_pressure_kpa_abs, valve_pressure_out_unit):,.2f} {valve_pressure_out_unit}" if valve.outlet_pressure_kpa_abs is not None else "n/a")
        cstat2.metric("Vapor pressure", f"{kpa_abs_to_pressure(valve.vapor_pressure_kpa_abs, valve_pressure_out_unit):,.2f} {valve_pressure_out_unit}" if valve.vapor_pressure_kpa_abs is not None else "n/a")
        cstat3.metric("Cavitation index σ", f"{valve.cavitation_index_sigma:,.2f}" if valve.cavitation_index_sigma is not None else "n/a")
        cstat4.metric("Status", (valve.cavitation_status or "n/a").replace("_", " ").title())
        if valve.liquid_critical_pressure_drop_kpa is not None:
            d1, d2 = st.columns(2)
            d1.metric("FL-based critical ΔP", f"{_pressure_delta_from_kpa(valve.liquid_critical_pressure_drop_kpa, valve_dp_unit):,.2f} {valve_dp_unit}")
            d2.metric("Predicted vena-contracta pressure", f"{kpa_abs_to_pressure(valve.predicted_vena_contracta_pressure_kpa_abs, valve_pressure_out_unit):,.2f} {valve_pressure_out_unit}" if valve.predicted_vena_contracta_pressure_kpa_abs is not None else "n/a")
        _show_notes(valve.notes)
        st.json(asdict(valve))

    with tabs[7]:
        st.caption("Overlay a simple pump curve or a library/uploaded pump curve against the estimated system curve to visualize the operating point.")
        curve_tabs = st.tabs(["Simple line", "Library / upload"])
        current_flow_m3_h = volumetric_flow_to_m3_h(flow_value, flow_unit)
        psc_col1, psc_col2 = st.columns(2)
        psc_flow_unit = psc_col1.selectbox("Flow unit", VOLUMETRIC_FLOW_UNITS, index=VOLUMETRIC_FLOW_UNITS.index(flow_unit) if flow_unit in VOLUMETRIC_FLOW_UNITS else 0, key="hyd_psc_flow_unit")
        psc_pressure_unit = psc_col2.selectbox("Pressure unit", ("kPa", "psi", "bar"), index=0, key="hyd_psc_pressure_unit")

        with curve_tabs[0]:
            p1, p2, p3 = st.columns(3)
            _default_shutoff = _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(result.total_dynamic_head_m * 1.6, 20.0), density_kg_m3), psc_pressure_unit)
            _default_max_flow = m3_h_to_volumetric_flow(max(current_flow_m3_h * 1.5, 10.0), psc_flow_unit)
            _default_head_at_max = _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(result.total_dynamic_head_m * 0.5, 1.0), density_kg_m3), psc_pressure_unit)
            _default_static_head = _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(length_to_m(elevation_change, elevation_unit) if elevation_change > 0 else 0.0, 0.0), density_kg_m3), psc_pressure_unit)
            shutoff_head = p1.number_input(f"Pump shutoff pressure rise ({psc_pressure_unit})", min_value=0.0, value=_default_shutoff, key="hyd_curve_shutoff")
            max_flow_curve = p2.number_input(f"Pump max flow ({psc_flow_unit})", min_value=0.0, value=_default_max_flow, key="hyd_curve_max_flow")
            head_at_max_flow = p3.number_input(f"Pump pressure at max flow ({psc_pressure_unit})", min_value=0.0, value=_default_head_at_max, key="hyd_curve_head_at_max")
            static_curve_head = st.number_input(f"System static pressure rise ({psc_pressure_unit})", value=_default_static_head, key="hyd_curve_static_head")
            shutoff_head_m = _delta_kpa_to_head_m(_pressure_delta_to_kpa(shutoff_head, psc_pressure_unit), density_kg_m3)
            max_flow_curve_m3_h = volumetric_flow_to_m3_h(max_flow_curve, psc_flow_unit)
            head_at_max_flow_m = _delta_kpa_to_head_m(_pressure_delta_to_kpa(head_at_max_flow, psc_pressure_unit), density_kg_m3)
            static_curve_head_m = _delta_kpa_to_head_m(_pressure_delta_to_kpa(static_curve_head, psc_pressure_unit), density_kg_m3)
            k_factor = max((result.total_dynamic_head_m - static_curve_head_m) / max(current_flow_m3_h ** 2, 1e-9), 0.0)
            curve_points = build_system_curve(static_curve_head_m, k_factor, max_flow_curve_m3_h)
            intersection = find_pump_system_intersection(shutoff_head_m, head_at_max_flow_m, max_flow_curve_m3_h, static_curve_head_m, k_factor)
            xs = [m3_h_to_volumetric_flow(point.flow_m3_h, psc_flow_unit) for point in curve_points]
            system_heads = [_pressure_delta_from_kpa(_head_m_to_delta_kpa(point.total_dynamic_head_m, density_kg_m3), psc_pressure_unit) for point in curve_points]
            pump_heads = [_pressure_delta_from_kpa(_head_m_to_delta_kpa(shutoff_head_m + (head_at_max_flow_m - shutoff_head_m) * (point.flow_m3_h / max(max_flow_curve_m3_h, 1e-9)), density_kg_m3), psc_pressure_unit) for point in curve_points]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xs, y=system_heads, mode="lines", name="System curve"))
            fig.add_trace(go.Scatter(x=xs, y=pump_heads, mode="lines", name="Pump curve"))
            if intersection is not None:
                fig.add_trace(go.Scatter(x=[m3_h_to_volumetric_flow(intersection.flow_m3_h, psc_flow_unit)], y=[_pressure_delta_from_kpa(_head_m_to_delta_kpa(intersection.total_dynamic_head_m, density_kg_m3), psc_pressure_unit)], mode="markers", marker=dict(size=12), name="Estimated operating point"))
                m1, m2 = st.columns(2)
                m1.metric("Estimated operating flow", f"{m3_h_to_volumetric_flow(intersection.flow_m3_h, psc_flow_unit):,.1f} {psc_flow_unit}")
                m2.metric("Estimated operating pressure", f"{_pressure_delta_from_kpa(_head_m_to_delta_kpa(intersection.total_dynamic_head_m, density_kg_m3), psc_pressure_unit):,.2f} {psc_pressure_unit}")
            fig.update_layout(title="Pump vs System Curve", xaxis_title=f"Flow ({psc_flow_unit})", yaxis_title=f"Pressure ({psc_pressure_unit})")
            st.plotly_chart(fig, use_container_width=True)

        with curve_tabs[1]:
            st.caption("Use a built-in pump curve or upload vendor flow-head points from CSV/Excel, then compare that curve against the estimated system curve.")
            _adv_default_static = _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(length_to_m(elevation_change, elevation_unit) if elevation_change > 0 else 0.0, 0.0), density_kg_m3), psc_pressure_unit)
            static_curve_head = st.number_input(f"System static pressure rise ({psc_pressure_unit})", value=_adv_default_static, key="hyd_curve_static_head_adv")
            static_curve_head_m = _delta_kpa_to_head_m(_pressure_delta_to_kpa(static_curve_head, psc_pressure_unit), density_kg_m3)
            k_factor = max((result.total_dynamic_head_m - static_curve_head_m) / max(current_flow_m3_h ** 2, 1e-9), 0.0)
            curve_source = st.radio("Pump curve source", ["Built-in library", "Upload CSV/Excel", "Manual table"], horizontal=True, key="hyd_curve_source")

            selected_curve = None
            uploaded_df = None

            if curve_source == "Built-in library":
                curve_key = st.selectbox("Built-in pump curve", available_builtin_curve_options(), format_func=lambda key: get_builtin_curve(key).name, key="hyd_curve_builtin")
                selected_curve = get_builtin_curve(curve_key)
                st.write(f"Family: {selected_curve.family}")
                for note in selected_curve.notes:
                    st.caption(note)
            elif curve_source == "Upload CSV/Excel":
                uploaded_curve = st.file_uploader("Upload pump curve table", type=["csv", "xlsx", "xlsm"], key="hyd_curve_upload")
                if uploaded_curve is not None:
                    suffix = Path(uploaded_curve.name).suffix.lower()
                    if suffix == ".csv":
                        uploaded_df = pd.read_csv(uploaded_curve)
                    else:
                        workbook = pd.ExcelFile(uploaded_curve)
                        sheet_name = st.selectbox("Workbook sheet", workbook.sheet_names, key="hyd_curve_sheet")
                        uploaded_df = pd.read_excel(workbook, sheet_name=sheet_name)
                    if uploaded_df is not None and not uploaded_df.empty:
                        st.dataframe(uploaded_df.head(15), use_container_width=True)
                        columns = list(uploaded_df.columns)
                        flow_col = st.selectbox("Flow column", columns, index=0, key="hyd_curve_upload_flow_col")
                        head_col = st.selectbox("Pressure column", columns, index=1 if len(columns) > 1 else 0, key="hyd_curve_upload_head_col")
                        curve_name = st.text_input("Curve name", value=Path(uploaded_curve.name).stem, key="hyd_curve_upload_name")
                        curve_family = st.text_input("Curve family / pump tag", value="Uploaded vendor curve", key="hyd_curve_upload_family")
                        uploaded_rows_si = [
                            {
                                "flow_m3_h": volumetric_flow_to_m3_h(row.get(flow_col) or 0.0, psc_flow_unit),
                                "head_m": _delta_kpa_to_head_m(_pressure_delta_to_kpa(row.get(head_col) or 0.0, psc_pressure_unit), density_kg_m3),
                            }
                            for row in uploaded_df.to_dict(orient="records")
                        ]
                        selected_curve = build_pump_curve_from_xy_rows(curve_name, uploaded_rows_si, "flow_m3_h", "head_m", family=curve_family)
            else:
                _mc_flow_col = f"flow ({psc_flow_unit})"
                _mc_head_col = f"pressure ({psc_pressure_unit})"
                manual_curve = pd.DataFrame([
                    {_mc_flow_col: m3_h_to_volumetric_flow(0.0, psc_flow_unit), _mc_head_col: _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(result.total_dynamic_head_m * 1.7, 25.0), density_kg_m3), psc_pressure_unit)},
                    {_mc_flow_col: m3_h_to_volumetric_flow(max(current_flow_m3_h * 0.5, 10.0), psc_flow_unit), _mc_head_col: _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(result.total_dynamic_head_m * 1.2, 15.0), density_kg_m3), psc_pressure_unit)},
                    {_mc_flow_col: m3_h_to_volumetric_flow(max(current_flow_m3_h, 20.0), psc_flow_unit), _mc_head_col: _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(result.total_dynamic_head_m * 0.95, 8.0), density_kg_m3), psc_pressure_unit)},
                    {_mc_flow_col: m3_h_to_volumetric_flow(max(current_flow_m3_h * 1.35, 30.0), psc_flow_unit), _mc_head_col: _pressure_delta_from_kpa(_head_m_to_delta_kpa(max(result.total_dynamic_head_m * 0.65, 3.0), density_kg_m3), psc_pressure_unit)},
                ])
                edited_curve = st.data_editor(manual_curve, num_rows="dynamic", use_container_width=True, key="hyd_curve_manual_editor")
                curve_name = st.text_input("Curve name", value="Manual pump curve", key="hyd_curve_manual_name")
                curve_family = st.text_input("Curve family / pump tag", value="Manual entry", key="hyd_curve_manual_family")
                _mc_si_rows = [{"flow_m3_h": volumetric_flow_to_m3_h(row.get(_mc_flow_col) or 0.0, psc_flow_unit), "head_m": _delta_kpa_to_head_m(_pressure_delta_to_kpa(row.get(_mc_head_col) or 0.0, psc_pressure_unit), density_kg_m3)} for row in edited_curve.to_dict(orient="records")]
                selected_curve = build_pump_curve_from_xy_rows(curve_name, _mc_si_rows, "flow_m3_h", "head_m", family=curve_family)

            if selected_curve is not None:
                max_curve_flow = selected_curve.points[-1].flow_m3_h
                system_curve_points = build_system_curve(static_curve_head_m, k_factor, max_curve_flow)
                library_intersection = find_curve_system_intersection(selected_curve, static_curve_head_m, k_factor)
                curve_df = pd.DataFrame([
                    {f"Flow ({psc_flow_unit})": m3_h_to_volumetric_flow(point.flow_m3_h, psc_flow_unit), f"Pump pressure ({psc_pressure_unit})": _pressure_delta_from_kpa(_head_m_to_delta_kpa(point.head_m, density_kg_m3), psc_pressure_unit)}
                    for point in selected_curve.points
                ])
                st.dataframe(curve_df, use_container_width=True)
                xs = [m3_h_to_volumetric_flow(point.flow_m3_h, psc_flow_unit) for point in system_curve_points]
                system_heads = [_pressure_delta_from_kpa(_head_m_to_delta_kpa(point.total_dynamic_head_m, density_kg_m3), psc_pressure_unit) for point in system_curve_points]
                pump_xs = [m3_h_to_volumetric_flow(point.flow_m3_h, psc_flow_unit) for point in selected_curve.points]
                pump_heads = [_pressure_delta_from_kpa(_head_m_to_delta_kpa(point.head_m, density_kg_m3), psc_pressure_unit) for point in selected_curve.points]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xs, y=system_heads, mode="lines", name="System curve"))
                fig.add_trace(go.Scatter(x=pump_xs, y=pump_heads, mode="lines+markers", name=selected_curve.name))
                if library_intersection is not None:
                    fig.add_trace(go.Scatter(x=[m3_h_to_volumetric_flow(library_intersection.flow_m3_h, psc_flow_unit)], y=[_pressure_delta_from_kpa(_head_m_to_delta_kpa(library_intersection.head_m, density_kg_m3), psc_pressure_unit)], mode="markers", marker=dict(size=12), name="Estimated operating point"))
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Estimated operating flow", f"{m3_h_to_volumetric_flow(library_intersection.flow_m3_h, psc_flow_unit):,.1f} {psc_flow_unit}")
                    c2.metric("Estimated operating pressure", f"{_pressure_delta_from_kpa(_head_m_to_delta_kpa(library_intersection.head_m, density_kg_m3), psc_pressure_unit):,.2f} {psc_pressure_unit}")
                    c3.metric("% of curve max flow", f"{library_intersection.fraction_of_curve_max_flow * 100.0:,.1f}%")
                    if library_intersection.head_error_m > 1.0:
                        st.warning("Pump/system intersection error is still noticeable on the sampled points. Add more curve points for better accuracy.")
                fig.update_layout(title=f"{selected_curve.name} vs System Curve", xaxis_title=f"Flow ({psc_flow_unit})", yaxis_title=f"Pressure ({psc_pressure_unit})")
                st.plotly_chart(fig, use_container_width=True)
                _show_notes(selected_curve.notes)

                st.divider()
                st.subheader("Pump rerate / affinity screening")
                st.caption("Screen speed or impeller changes against the same system curve before ordering a rerate. Outputs are unit-selectable; confirm final NPSHr and power with vendor data.")
                unit_col1, unit_col2 = st.columns(2)
                affinity_flow_unit = unit_col1.selectbox("Rerate output flow unit", VOLUMETRIC_FLOW_UNITS, index=0, key="hyd_curve_affinity_flow_unit")
                affinity_head_unit = unit_col2.selectbox("Rerate output head unit", LENGTH_UNITS, index=0, key="hyd_curve_affinity_head_unit")
                speed_col1, speed_col2 = st.columns(2)
                base_speed_rpm = speed_col1.number_input("Base speed (rpm)", min_value=1.0, value=1780.0, key="hyd_curve_affinity_base_speed")
                rerated_speed_rpm = speed_col2.number_input("Rerated speed (rpm)", min_value=1.0, value=1780.0, key="hyd_curve_affinity_new_speed")
                imp_col1, imp_col2, imp_col3 = st.columns(3)
                impeller_unit = imp_col3.selectbox("Impeller diameter unit", LENGTH_UNITS, index=3, key="hyd_curve_affinity_impeller_unit")
                base_impeller = imp_col1.number_input("Base impeller diameter", min_value=0.01, value=10.0, key="hyd_curve_affinity_base_impeller")
                rerated_impeller = imp_col2.number_input("Rerated impeller diameter", min_value=0.01, value=10.0, key="hyd_curve_affinity_new_impeller")
                speed_ratio = rerated_speed_rpm / max(base_speed_rpm, 1.0e-9)
                impeller_ratio = length_to_m(rerated_impeller, impeller_unit) / max(length_to_m(base_impeller, impeller_unit), 1.0e-12)
                rerate = screen_affinity_rerate(
                    selected_curve,
                    static_head_m=static_curve_head_m,
                    k_factor_m_per_m3h2=k_factor,
                    speed_ratio=speed_ratio,
                    impeller_ratio=impeller_ratio,
                )
                base_curve_flow_display = [m3_h_to_volumetric_flow(point.flow_m3_h, affinity_flow_unit) for point in rerate.base_curve.points]
                base_curve_head_display = [m_to_length(point.head_m, affinity_head_unit) for point in rerate.base_curve.points]
                scaled_curve_flow_display = [m3_h_to_volumetric_flow(point.flow_m3_h, affinity_flow_unit) for point in rerate.scaled_curve.points]
                scaled_curve_head_display = [m_to_length(point.head_m, affinity_head_unit) for point in rerate.scaled_curve.points]
                system_curve_flow_display = [m3_h_to_volumetric_flow(point.flow_m3_h, affinity_flow_unit) for point in system_curve_points]
                system_curve_head_display = [m_to_length(point.total_dynamic_head_m, affinity_head_unit) for point in system_curve_points]

                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Speed ratio", f"{rerate.speed_ratio:,.3f}x")
                r2.metric("Impeller ratio", f"{rerate.impeller_ratio:,.3f}x")
                r3.metric("Relative power", f"{rerate.relative_power_factor * 100.0:,.1f}%")
                r4.metric("Relative NPSHr", f"{rerate.relative_npshr_factor * 100.0:,.1f}%")
                if rerate.base_intersection is not None and rerate.scaled_intersection is not None:
                    base_flow_display = m3_h_to_volumetric_flow(rerate.base_intersection.flow_m3_h, affinity_flow_unit)
                    scaled_flow_display = m3_h_to_volumetric_flow(rerate.scaled_intersection.flow_m3_h, affinity_flow_unit)
                    base_head_display = m_to_length(rerate.base_intersection.head_m, affinity_head_unit)
                    scaled_head_display = m_to_length(rerate.scaled_intersection.head_m, affinity_head_unit)
                    delta_flow_pct = (rerate.scaled_intersection.flow_m3_h - rerate.base_intersection.flow_m3_h) / max(rerate.base_intersection.flow_m3_h, 1.0e-9) * 100.0
                    delta_head_pct = (rerate.scaled_intersection.head_m - rerate.base_intersection.head_m) / max(rerate.base_intersection.head_m, 1.0e-9) * 100.0
                    op1, op2, op3, op4 = st.columns(4)
                    op1.metric("Base operating flow", f"{base_flow_display:,.1f} {affinity_flow_unit}")
                    op2.metric("Rerated operating flow", f"{scaled_flow_display:,.1f} {affinity_flow_unit}", delta=f"{delta_flow_pct:+.1f}%")
                    op3.metric("Base operating head", f"{base_head_display:,.2f} {affinity_head_unit}")
                    op4.metric("Rerated operating head", f"{scaled_head_display:,.2f} {affinity_head_unit}", delta=f"{delta_head_pct:+.1f}%")

                affinity_fig = go.Figure()
                affinity_fig.add_trace(go.Scatter(x=system_curve_flow_display, y=system_curve_head_display, mode="lines", name="System curve"))
                affinity_fig.add_trace(go.Scatter(x=base_curve_flow_display, y=base_curve_head_display, mode="lines+markers", name=f"Base curve: {rerate.base_curve.name}"))
                affinity_fig.add_trace(go.Scatter(x=scaled_curve_flow_display, y=scaled_curve_head_display, mode="lines+markers", name="Rerated curve"))
                if rerate.base_intersection is not None:
                    affinity_fig.add_trace(go.Scatter(
                        x=[m3_h_to_volumetric_flow(rerate.base_intersection.flow_m3_h, affinity_flow_unit)],
                        y=[m_to_length(rerate.base_intersection.head_m, affinity_head_unit)],
                        mode="markers",
                        marker=dict(size=11),
                        name="Base operating point",
                    ))
                if rerate.scaled_intersection is not None:
                    affinity_fig.add_trace(go.Scatter(
                        x=[m3_h_to_volumetric_flow(rerate.scaled_intersection.flow_m3_h, affinity_flow_unit)],
                        y=[m_to_length(rerate.scaled_intersection.head_m, affinity_head_unit)],
                        mode="markers",
                        marker=dict(size=11, symbol="diamond"),
                        name="Rerated operating point",
                    ))
                affinity_fig.update_layout(
                    title=f"{selected_curve.name} rerate screen",
                    xaxis_title=f"Flow ({affinity_flow_unit})",
                    yaxis_title=f"Head ({affinity_head_unit})",
                )
                st.plotly_chart(affinity_fig, use_container_width=True)
                rerate_df = pd.DataFrame([
                    {
                        "Case": "Base",
                        f"Operating flow ({affinity_flow_unit})": m3_h_to_volumetric_flow(rerate.base_intersection.flow_m3_h, affinity_flow_unit) if rerate.base_intersection is not None else None,
                        f"Operating head ({affinity_head_unit})": m_to_length(rerate.base_intersection.head_m, affinity_head_unit) if rerate.base_intersection is not None else None,
                        "% of curve max flow": rerate.base_intersection.fraction_of_curve_max_flow * 100.0 if rerate.base_intersection is not None else None,
                    },
                    {
                        "Case": "Rerated",
                        f"Operating flow ({affinity_flow_unit})": m3_h_to_volumetric_flow(rerate.scaled_intersection.flow_m3_h, affinity_flow_unit) if rerate.scaled_intersection is not None else None,
                        f"Operating head ({affinity_head_unit})": m_to_length(rerate.scaled_intersection.head_m, affinity_head_unit) if rerate.scaled_intersection is not None else None,
                        "% of curve max flow": rerate.scaled_intersection.fraction_of_curve_max_flow * 100.0 if rerate.scaled_intersection is not None else None,
                    },
                ])
                st.dataframe(rerate_df, use_container_width=True)
                _show_notes(rerate.notes)

    _remember_case(
        "hydraulics",
        {
            "flow_value": flow_value,
            "flow_unit": flow_unit,
            "density": density,
            "density_unit": density_unit,
            "viscosity": viscosity,
            "viscosity_unit": viscosity_unit,
            "pipe_basis": pipe_basis,
            "pipe_id": pipe_id,
            "pipe_id_unit": pipe_id_unit,
            "pipe_length": pipe_length,
            "pipe_length_unit": pipe_length_unit,
            "elevation_change": elevation_change,
            "elevation_unit": elevation_unit,
            "fitting_k_total": fitting_k_total,
        },
        {
            "single_line": asdict(result),
            "size_recommendation": asdict(rec) if rec is not None else None,
            "pump_power": asdict(pump_power),
            "npsha": asdict(npsha),
            "segmented_system": asdict(seg_result),
            "control_valve": asdict(valve),
        },
    )



def render_steam_jets() -> None:
    st.header("Steam Jets / Thermo-Compressors")
    tabs = st.tabs(["Curve check", "Workbook family import", "Thermo-compressor balance"])

    with tabs[0]:
        st.write("Enter a performance curve and compare one operating point against it. Units are selectable and apply to the editor and displayed results.")
        c0, c00 = st.columns(2)
        x_unit = c0.selectbox("X-axis unit", GENERIC_CURVE_UNITS, index=0, key="sj_x_unit")
        y_unit = c00.selectbox("Y-axis unit", GENERIC_CURVE_UNITS, index=0, key="sj_y_unit")
        default_curve = pd.DataFrame(
            [
                {"suction_load": 2000.0, "motive_steam": 3200.0},
                {"suction_load": 4000.0, "motive_steam": 5000.0},
                {"suction_load": 6000.0, "motive_steam": 7100.0},
                {"suction_load": 8000.0, "motive_steam": 9500.0},
            ]
        )
        edited = st.data_editor(default_curve, num_rows="dynamic", use_container_width=True, key="sj_editor")
        c1, c2, c3, c4 = st.columns(4)
        curve_name = c1.text_input("Curve name", value="Thermo-compressor A", key="sj_curve_name")
        x_col = c2.selectbox("X column", list(edited.columns), index=0, key="sj_xcol")
        y_col = c3.selectbox("Y column", list(edited.columns), index=1 if len(edited.columns) > 1 else 0, key="sj_ycol")
        family = c4.text_input(
            "Curve label (optional)",
            value="",
            key="sj_family",
            help="Optional tag for this curve, e.g. the motive-steam pressure the vendor curve is based on. Used only for labelling saved cases — does not affect calculations.",
        )
        operating_x = st.number_input("Operating x-value", value=5000.0, key="sj_x")
        actual_y = st.number_input("Actual y-value", value=6200.0, key="sj_y")
        rows = edited.to_dict(orient="records")
        curve = make_curve_from_xy_rows(curve_name, x_col, y_col, rows, family=family)
        result = evaluate_operating_point(curve, operating_x, actual_y)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=edited[x_col], y=edited[y_col], mode="lines+markers", name="Curve"))
        fig.add_trace(go.Scatter(x=[operating_x], y=[result.predicted_y], mode="markers", marker=dict(size=12), name="Predicted point"))
        fig.add_trace(go.Scatter(x=[operating_x], y=[actual_y], mode="markers", marker=dict(size=12, symbol="diamond"), name="Actual point"))
        fig.update_layout(xaxis_title=f"{x_col} ({x_unit})", yaxis_title=f"{y_col} ({y_unit})", title="Steam-Jet Operating Point vs Curve")
        st.plotly_chart(fig, use_container_width=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Predicted y", f"{result.predicted_y:,.1f} {y_unit}")
        m2.metric("Actual y", f"{result.actual_y:,.1f} {y_unit}")
        m3.metric("% of curve", f"{result.percent_of_curve:,.1f}%")
        m4.metric("Deviation", f"{result.deviation_pct:,.1f}%")
        _show_notes(result.notes)
        _remember_case(
            "steam-jets-curve-check",
            {
                "curve_name": curve_name,
                "x_column": x_col,
                "y_column": y_col,
                "family": family,
                "x_unit": x_unit,
                "y_unit": y_unit,
                "operating_x": operating_x,
                "actual_y": actual_y,
                "rows": rows,
            },
            asdict(result),
        )

    with tabs[1]:
        st.write("Import a workbook or CSV that contains multiple steam-jet or thermo-compressor model curves, group them into curve families, and compare candidate models side-by-side at one operating point.")
        f1, f2 = st.columns(2)
        x_unit = f1.selectbox("Imported x-axis unit", GENERIC_CURVE_UNITS, index=0, key="sj_family_x_unit")
        y_unit = f2.selectbox("Imported y-axis unit", GENERIC_CURVE_UNITS, index=0, key="sj_family_y_unit")
        from engineering_app.io.vendor_presets import VENDOR_NAMES, GENERIC_AUTO_DETECT, suggest_mapping_from_vendor_preset, VENDOR_PRESETS
        vendor_choice = st.selectbox(
            "Vendor preset",
            [GENERIC_AUTO_DETECT] + VENDOR_NAMES,
            index=0,
            key="sj_vendor_preset",
        )
        vendor_hint = GENERIC_AUTO_DETECT if vendor_choice == GENERIC_AUTO_DETECT else vendor_choice

        # Vendor preset reference cards (always visible, above upload)
        with st.expander("Vendor preset reference — click to see what each vendor format looks like"):
            for vp in VENDOR_PRESETS:
                st.markdown(f"**{vp.vendor}** — {vp.notes}")
                st.caption(f"Name tokens: {', '.join(sorted(vp.name_tokens))}")
                st.caption(f"X tokens: {', '.join(sorted(vp.x_tokens))} | Y tokens: {', '.join(sorted(vp.y_tokens))}")
                st.caption(f"Family patterns: {', '.join(vp.family_column_patterns)} | Unit hints: X={vp.x_unit_hint}, Y={vp.y_unit_hint}")
                st.divider()

        st.caption(
            "Vendor presets auto-detect column layouts for known steam-jet vendors. "
            "Auto-detect infers format from sheet/column names. "
            "Select a specific vendor to force that vendor's mapping rules."
        )
        uploaded_family = st.file_uploader("Upload steam-jet model-family table", type=["csv", "xlsx", "xlsm"], key="sj_family_upload")
        family_df = None
        source_sheet = None
        normalized_library = None
        normalized_notes: list[str] = []
        preferred_library_mode = "manual"
        vendor_suggestion = None
        if uploaded_family is None:
            default_family_df = pd.DataFrame([
                {"model": "TC-A", "family": "Motive 3.5 barg", "suction_load": 2000.0, "motive_steam": 3200.0},
                {"model": "TC-A", "family": "Motive 3.5 barg", "suction_load": 4000.0, "motive_steam": 5000.0},
                {"model": "TC-A", "family": "Motive 3.5 barg", "suction_load": 6000.0, "motive_steam": 7100.0},
                {"model": "TC-B", "family": "Motive 3.5 barg", "suction_load": 2000.0, "motive_steam": 3000.0},
                {"model": "TC-B", "family": "Motive 3.5 barg", "suction_load": 4000.0, "motive_steam": 4700.0},
                {"model": "TC-B", "family": "Motive 3.5 barg", "suction_load": 6000.0, "motive_steam": 6800.0},
                {"model": "TC-C", "family": "Motive 5.0 barg", "suction_load": 2000.0, "motive_steam": 2800.0},
                {"model": "TC-C", "family": "Motive 5.0 barg", "suction_load": 4000.0, "motive_steam": 4450.0},
                {"model": "TC-C", "family": "Motive 5.0 barg", "suction_load": 6000.0, "motive_steam": 6500.0},
            ])
            st.caption("No file uploaded yet, so a built-in multi-model example table is shown below.")
            family_df = st.data_editor(default_family_df, num_rows="dynamic", use_container_width=True, key="sj_family_default_editor")
            source_sheet = "manual-family-table"
        else:
            suffix = Path(uploaded_family.name).suffix.lower()
            upload_bytes = uploaded_family.getvalue()
            if suffix == ".csv":
                family_df = pd.read_csv(uploaded_family)
                source_sheet = uploaded_family.name
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                    handle.write(upload_bytes)
                    temp_path = Path(handle.name)
                try:
                    inspection = inspect_workbook(temp_path)
                    vendor_preset_arg = None if vendor_hint == GENERIC_AUTO_DETECT else vendor_choice
                    normalized_library = normalize_curve_workbook(inspection, vendor_preset=vendor_preset_arg)
                    normalized_notes = normalized_library.notes
                    preferred_library_mode = "normalized" if normalized_library.curves else "manual"
                finally:
                    temp_path.unlink(missing_ok=True)
                workbook = pd.ExcelFile(uploaded_family)
                source_sheet = st.selectbox("Workbook sheet", workbook.sheet_names, key="sj_family_sheet")
                family_df = pd.read_excel(workbook, sheet_name=source_sheet)
            st.dataframe(family_df.head(20), use_container_width=True)

        # Vendor mapping suggestion panel — runs against whatever columns are now available
        if family_df is not None and not family_df.empty:
            columns = list(family_df.columns)
            vp_arg = None if vendor_hint == GENERIC_AUTO_DETECT else vendor_hint
            vendor_suggestion = suggest_mapping_from_vendor_preset(columns, vp_arg)

            confidence_icons = {"high": "green", "medium": "orange", "low": "red", "none": "red"}
            color = confidence_icons.get(vendor_suggestion.confidence, "gray")
            with st.container():
                st.markdown(f"**Vendor Mapping Preview** — *confidence: :{color}[{vendor_suggestion.confidence}]*")
                if vendor_suggestion.vendor:
                    st.caption(f"Detected: **{vendor_suggestion.vendor}**")
                else:
                    st.caption("No vendor-specific pattern matched; using generic heuristics.")
                if vendor_suggestion.notes:
                    st.caption(vendor_suggestion.notes)
                map_cols = st.columns(4)
                map_cols[0].metric("Name column", vendor_suggestion.name_col or "(not detected)")
                map_cols[1].metric("X column", vendor_suggestion.x_col or "(not detected)")
                map_cols[2].metric("Y column", vendor_suggestion.y_col or "(not detected)")
                map_cols[3].metric("Family column", vendor_suggestion.family_col or "(not detected)")

        if family_df is not None and not family_df.empty:
            columns = list(family_df.columns)
            family_options = ["(none)"] + columns
            # Derive default column indices from vendor preset suggestion when available
            if vendor_suggestion and vendor_suggestion.confidence in ("high", "medium"):
                name_index = columns.index(vendor_suggestion.name_col) if isinstance(vendor_suggestion.name_col, str) and vendor_suggestion.name_col in columns else 0
                x_index = columns.index(vendor_suggestion.x_col) if isinstance(vendor_suggestion.x_col, str) and vendor_suggestion.x_col in columns else 0
                y_index = columns.index(vendor_suggestion.y_col) if isinstance(vendor_suggestion.y_col, str) and vendor_suggestion.y_col in columns else min(1, len(columns) - 1)
                fam_index = columns.index(vendor_suggestion.family_col) + 1 if vendor_suggestion.family_col and vendor_suggestion.family_col in columns else 0
            else:
                # Fallback to generic heuristics
                name_index = next((idx for idx, col in enumerate(columns) if str(col).lower() in {"model", "curve", "curve_name", "model_name", "tag", "name"}), 0)
                x_index = next((idx for idx, col in enumerate(columns) if any(token in str(col).lower() for token in ["load", "suction", "capacity", "flow"])), 0)
                y_index = next((idx for idx, col in enumerate(columns) if any(token in str(col).lower() for token in ["steam", "consumption", "head", "duty", "ratio"]) and "pressure" not in str(col).lower()), min(1, len(columns) - 1))
                fam_index = next((idx + 1 for idx, col in enumerate(columns) if "family" in str(col).lower() or "basis" in str(col).lower()), 0)
            c1, c2, c3, c4 = st.columns(4)
            curve_name_col = c1.selectbox("Curve/model name column", columns, index=name_index, key="sj_family_curve_name_col")
            family_col = c2.selectbox("Family column", family_options, index=fam_index, key="sj_family_family_col")
            x_col = c3.selectbox("X column", columns, index=x_index, key="sj_family_x_col")
            y_col = c4.selectbox("Y column", columns, index=y_index, key="sj_family_y_col")
            family_label = None if family_col == "(none)" else family_col
            manual_library = build_curve_library_from_table(
                family_df.to_dict(orient="records"),
                x_label=x_col,
                y_label=y_col,
                curve_name_label=curve_name_col,
                family_label=family_label,
                source_sheet=str(source_sheet) if source_sheet is not None else None,
            )
            library_mode_options = ["Manual column mapping"]
            if normalized_library and normalized_library.curves:
                library_mode_options.insert(0, "Workbook preview auto-normalization")
            library_mode = st.radio(
                "Curve-library build mode",
                library_mode_options,
                index=0 if preferred_library_mode == "normalized" and len(library_mode_options) > 1 else len(library_mode_options) - 1,
                horizontal=True,
                key="sj_family_build_mode",
            )
            library = normalized_library if library_mode.startswith("Workbook") and normalized_library is not None else manual_library
            st.metric("Imported curves", f"{len(library.curves)}")
            if normalized_notes and library_mode.startswith("Workbook"):
                st.caption("Workbook preview normalization notes:")
                _show_notes(normalized_notes)
            if library.curves:
                family_values = sorted({curve.family for curve in library.curves if curve.family})
                if family_values:
                    selected_families = st.multiselect(
                        "Family / motive basis filter",
                        family_values,
                        default=family_values,
                        key="sj_family_filter",
                    )
                    filtered_curves = [curve for curve in library.curves if curve.family in selected_families]
                else:
                    selected_families = []
                    filtered_curves = list(library.curves)
                curve_labels = [f"{curve.name} ({curve.family or 'no family'})" for curve in filtered_curves]
                selected_labels = st.multiselect(
                    "Curves to compare",
                    curve_labels,
                    default=curve_labels[: min(3, len(curve_labels))],
                    key="sj_family_selected",
                )
                selected_curves = [curve for curve in filtered_curves if f"{curve.name} ({curve.family or 'no family'})" in selected_labels]
                operating_x = st.number_input("Comparison x-value", value=5000.0, key="sj_family_operating_x")
                actual_y = st.number_input("Actual y-value for comparison", value=6200.0, key="sj_family_actual_y")
                if selected_curves:
                    comparison_rows = compare_curves_at_point(selected_curves, operating_x, actual_y)
                    compare_df = pd.DataFrame([
                        {
                            "Curve": row.curve_name,
                            "Family": row.family or "",
                            f"Predicted y ({y_unit})": row.predicted_y,
                            f"Actual y ({y_unit})": row.actual_y,
                            "% of curve": row.percent_of_curve,
                            "Deviation %": row.deviation_pct,
                            "In envelope": row.in_envelope,
                        }
                        for row in comparison_rows
                    ])
                    st.dataframe(compare_df, use_container_width=True)
                    fig = go.Figure()
                    for curve in selected_curves:
                        xs = [point.x for point in curve.points]
                        ys = [point.y for point in curve.points]
                        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=f"{curve.name} ({curve.family or 'no family'})"))
                    fig.add_trace(go.Scatter(x=[operating_x] * len(comparison_rows), y=[row.predicted_y for row in comparison_rows], mode="markers", marker=dict(size=11), name="Predicted points"))
                    fig.add_trace(go.Scatter(x=[operating_x], y=[actual_y], mode="markers", marker=dict(size=12, symbol="diamond"), name="Actual point"))
                    fig.update_layout(title="Steam-jet model-family comparison", xaxis_title=f"{x_col} ({x_unit})", yaxis_title=f"{y_col} ({y_unit})")
                    st.plotly_chart(fig, use_container_width=True)
                    best_match = comparison_rows[0]
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Closest curve", best_match.curve_name)
                    m2.metric("Closest family", best_match.family or "n/a")
                    m3.metric("Closest deviation", f"{best_match.deviation_pct:,.1f}%")
                    _remember_case(
                        "steam-jets-model-family-compare",
                        {
                            "source_sheet": source_sheet,
                            "curve_name_col": curve_name_col,
                            "family_col": family_label,
                            "x_col": x_col,
                            "y_col": y_col,
                            "library_mode": library_mode,
                            "family_filter": selected_families,
                            "operating_x": operating_x,
                            "actual_y": actual_y,
                            "selected_curves": [curve.name for curve in selected_curves],
                        },
                        {"comparison_rows": compare_df.to_dict(orient="records")},
                    )
                elif filtered_curves:
                    st.info("Select at least one curve to run the side-by-side comparison.")
                else:
                    st.warning("No curves remain after the current family / motive-basis filter.")
            else:
                st.warning("No valid curves could be built from the selected workbook preview or manual column mapping. Check that each model has at least two numeric x/y rows.")

    with tabs[2]:
        st.write("Screen a thermo-compressor from suction vapor load and pressure lift using a simple adiabatic steam-mixing balance. Use vendor curves before equipment selection.")
        b1, b2, b3, b4 = st.columns(4)
        suction_flow_value = b1.number_input("Suction vapor flow", min_value=0.1, value=5000.0, key="sj_balance_suction_flow")
        suction_flow_unit = b2.selectbox("Suction flow unit", MASS_FLOW_UNITS, index=0, key="sj_balance_suction_flow_unit")
        suction_pressure_value = b3.number_input("Suction pressure", value=150.0, key="sj_balance_suction_pressure")
        suction_pressure_unit = b4.selectbox("Suction pressure unit", PRESSURE_UNITS, index=0, key="sj_balance_suction_pressure_unit")
        b5, b6, b7, b8 = st.columns(4)
        motive_pressure_value = b5.number_input("Motive steam pressure", value=3.5, key="sj_balance_motive_pressure")
        motive_pressure_unit = b6.selectbox("Motive steam pressure unit", PRESSURE_UNITS, index=4, key="sj_balance_motive_pressure_unit")
        discharge_pressure_value = b7.number_input("Discharge pressure", value=1.2, key="sj_balance_discharge_pressure")
        discharge_pressure_unit = b8.selectbox("Discharge pressure unit", PRESSURE_UNITS, index=4, key="sj_balance_discharge_pressure_unit")
        b9, b10, b11, b12 = st.columns(4)
        suction_superheat = b9.number_input("Suction superheat", min_value=0.0, value=0.0, key="sj_balance_suction_superheat")
        suction_superheat_unit = b10.selectbox("Suction superheat unit", DELTA_TEMPERATURE_UNITS, index=0, key="sj_balance_suction_superheat_unit")
        motive_superheat = b11.number_input("Motive superheat", min_value=0.0, value=0.0, key="sj_balance_motive_superheat")
        motive_superheat_unit = b12.selectbox("Motive superheat unit", DELTA_TEMPERATURE_UNITS, index=0, key="sj_balance_motive_superheat_unit")
        c13, c14, c15 = st.columns(3)
        flow_output_unit = c13.selectbox("Flow output unit", MASS_FLOW_UNITS, index=0, key="sj_balance_flow_out_unit")
        pressure_output_unit = c14.selectbox("Pressure output unit", PRESSURE_UNITS, index=4, key="sj_balance_pressure_out_unit")
        temp_output_unit = c15.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="sj_balance_temp_out_unit")

        suction_superheat_c = suction_superheat if suction_superheat_unit == "C" else suction_superheat * 5.0 / 9.0
        motive_superheat_c = motive_superheat if motive_superheat_unit == "C" else motive_superheat * 5.0 / 9.0
        try:
            balance = thermo_compressor_balance(
                suction_flow_value=suction_flow_value,
                suction_flow_unit=suction_flow_unit,
                suction_pressure_value=suction_pressure_value,
                suction_pressure_unit=suction_pressure_unit,
                motive_pressure_value=motive_pressure_value,
                motive_pressure_unit=motive_pressure_unit,
                discharge_pressure_value=discharge_pressure_value,
                discharge_pressure_unit=discharge_pressure_unit,
                suction_superheat_c=suction_superheat_c,
                motive_superheat_c=motive_superheat_c,
            )
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Required motive steam", f"{kg_h_to_mass_flow(balance.motive_flow_kg_h, flow_output_unit):,.1f} {flow_output_unit}")
            m2.metric("Discharge flow", f"{kg_h_to_mass_flow(balance.discharge_flow_kg_h, flow_output_unit):,.1f} {flow_output_unit}")
            m3.metric("Entrainment ratio", f"{balance.entrainment_ratio:,.2f}")
            m4.metric("Compression ratio", f"{balance.compression_ratio:,.2f}")
            n1, n2, n3 = st.columns(3)
            n1.metric("Motive/suction ratio", f"{balance.motive_to_suction_ratio:,.2f}")
            n2.metric("Motive expansion ratio", f"{balance.motive_expansion_ratio:,.2f}")
            n3.metric("Discharge saturation temp", f"{_display_temperature(balance.discharge_temperature_c, temp_output_unit):,.2f} °{temp_output_unit}")
            st.json(
                {
                    "suction_flow": f"{kg_h_to_mass_flow(balance.suction_flow_kg_h, flow_output_unit):,.2f} {flow_output_unit}",
                    "required_motive_steam": f"{kg_h_to_mass_flow(balance.motive_flow_kg_h, flow_output_unit):,.2f} {flow_output_unit}",
                    "discharge_flow": f"{kg_h_to_mass_flow(balance.discharge_flow_kg_h, flow_output_unit):,.2f} {flow_output_unit}",
                    "suction_pressure": f"{kpa_abs_to_pressure(balance.suction_pressure_kpa_abs, pressure_output_unit):,.3f} {pressure_output_unit}",
                    "motive_pressure": f"{kpa_abs_to_pressure(balance.motive_pressure_kpa_abs, pressure_output_unit):,.3f} {pressure_output_unit}",
                    "discharge_pressure": f"{kpa_abs_to_pressure(balance.discharge_pressure_kpa_abs, pressure_output_unit):,.3f} {pressure_output_unit}",
                    "suction_vapor_temperature": f"{_display_temperature(balance.suction_temperature_c, temp_output_unit):,.2f} °{temp_output_unit}",
                    "motive_vapor_temperature": f"{_display_temperature(balance.motive_temperature_c, temp_output_unit):,.2f} °{temp_output_unit}",
                    "discharge_temperature": f"{_display_temperature(balance.discharge_temperature_c, temp_output_unit):,.2f} °{temp_output_unit}",
                    "suction_vapor_enthalpy_kj_kg": round(balance.suction_vapor_enthalpy_kj_kg, 2),
                    "motive_vapor_enthalpy_kj_kg": round(balance.motive_vapor_enthalpy_kj_kg, 2),
                    "discharge_vapor_enthalpy_kj_kg": round(balance.discharge_vapor_enthalpy_kj_kg, 2),
                    "entrainment_ratio": round(balance.entrainment_ratio, 4),
                    "compression_ratio": round(balance.compression_ratio, 4),
                    "motive_expansion_ratio": round(balance.motive_expansion_ratio, 4),
                }
            )
            _show_notes(balance.notes)
            _remember_case(
                "steam-jets-thermo-compressor-balance",
                {
                    "suction_flow_value": suction_flow_value,
                    "suction_flow_unit": suction_flow_unit,
                    "suction_pressure_value": suction_pressure_value,
                    "suction_pressure_unit": suction_pressure_unit,
                    "motive_pressure_value": motive_pressure_value,
                    "motive_pressure_unit": motive_pressure_unit,
                    "discharge_pressure_value": discharge_pressure_value,
                    "discharge_pressure_unit": discharge_pressure_unit,
                    "suction_superheat": suction_superheat,
                    "suction_superheat_unit": suction_superheat_unit,
                    "motive_superheat": motive_superheat,
                    "motive_superheat_unit": motive_superheat_unit,
                },
                asdict(balance),
            )
        except ValueError as exc:
            st.error(str(exc))



def render_steam() -> None:
    st.header("Steam & Utilities")
    st.caption("Quick utility screens for steam demand, duty back-calculation, and steam-header pressure-change impacts on capacity.")
    tab1, tab2, tab3 = st.tabs(["Steam for duty", "Duty from steam", "Header pressure change"])


    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        duty_value = c1.number_input("Duty", value=2500.0, key="steam_duty_value")
        duty_unit = c2.selectbox("Duty unit", POWER_UNITS, index=0, key="steam_duty_unit")
        pressure_value = c3.number_input("Steam pressure", value=3.5, key="steam_pressure_value")
        pressure_unit = c4.selectbox("Pressure unit", PRESSURE_UNITS, index=4, key="steam_pressure_unit")
        steam_flow_out_unit = st.selectbox("Steam-flow output unit", MASS_FLOW_UNITS, index=0, key="steam_flow_out_unit")
        temp_out_unit = st.selectbox("Condensing-temperature output unit", TEMPERATURE_UNITS, index=0, key="steam_temp_out_unit")
        result = steam_for_duty(power_to_kw(duty_value, duty_unit), pressure_value, pressure_unit)
        m1, m2, m3 = st.columns(3)
        m1.metric("Steam required", f"{kg_h_to_mass_flow(result.steam_flow_kg_h, steam_flow_out_unit):,.1f} {steam_flow_out_unit}")
        m2.metric("Condensate", f"{kg_h_to_mass_flow(result.condensate_flow_kg_h, steam_flow_out_unit):,.1f} {steam_flow_out_unit}")
        m3.metric("Condensing temperature", f"{_display_temperature(result.condensing_temperature_c, temp_out_unit):,.2f} °{temp_out_unit}")
        _remember_case(
            "steam-for-duty",
            {"duty_value": duty_value, "duty_unit": duty_unit, "pressure_value": pressure_value, "pressure_unit": pressure_unit},
            {"steam_flow_kg_h": result.steam_flow_kg_h, "condensate_flow_kg_h": result.condensate_flow_kg_h, "condensing_temperature_c": result.condensing_temperature_c},
        )
        _show_notes(result.notes)

    with tab2:
        c1, c2, c3, c4, c5 = st.columns(5)
        steam_flow = c1.number_input("Steam flow", value=4000.0, key="steam_flow_value")
        steam_flow_unit = c2.selectbox("Steam flow unit", MASS_FLOW_UNITS, index=0, key="steam_flow_unit")
        pressure_value = c3.number_input("Steam pressure", value=3.5, key="steam_pressure_value_2")
        pressure_unit = c4.selectbox("Pressure unit", PRESSURE_UNITS, index=4, key="steam_pressure_unit_2")
        duty_out_unit = c5.selectbox("Duty output unit", POWER_UNITS, index=0, key="steam_duty_out_unit")
        temp_out_unit = st.selectbox("Condensing-temperature output unit", TEMPERATURE_UNITS, index=0, key="steam_duty_temp_out")
        result = duty_from_steam_flow(steam_flow, steam_flow_unit, pressure_value, pressure_unit)
        m1, m2 = st.columns(2)
        m1.metric("Available duty", f"{kw_to_power(result.duty_kw, duty_out_unit):,.1f} {duty_out_unit}")
        m2.metric("Condensing temperature", f"{_display_temperature(result.condensing_temperature_c, temp_out_unit):,.2f} °{temp_out_unit}")
        _remember_case(
            "duty-from-steam",
            {"steam_flow": steam_flow, "steam_flow_unit": steam_flow_unit, "pressure_value": pressure_value, "pressure_unit": pressure_unit},
            {"duty_kw": result.duty_kw, "condensing_temperature_c": result.condensing_temperature_c, "latent_heat_kj_kg": result.latent_heat_kj_kg},
        )
        _show_notes(result.notes)

    with tab3:
        st.subheader("Steam header pressure-change screen")
        st.caption("Compare current vs reduced header pressure for the same duty, and optionally evaluate lost condensing ΔT against a process boiling condition.")
        c1, c2, c3, c4 = st.columns(4)
        duty_value = c1.number_input("Target duty", min_value=0.1, value=2500.0, key="steam_hdr_duty")
        duty_unit = c2.selectbox("Duty unit", POWER_UNITS, index=0, key="steam_hdr_duty_unit")
        current_pressure_value = c3.number_input("Current header pressure", value=4.5, key="steam_hdr_current_pressure")
        current_pressure_unit = c4.selectbox("Current pressure unit", PRESSURE_UNITS, index=4, key="steam_hdr_current_pressure_unit")
        c5, c6 = st.columns(2)
        reduced_pressure_value = c5.number_input("Reduced / upset header pressure", value=3.0, key="steam_hdr_reduced_pressure")
        reduced_pressure_unit = c6.selectbox("Reduced pressure unit", PRESSURE_UNITS, index=4, key="steam_hdr_reduced_pressure_unit")

        st.markdown("**Optional process-side boiling context**")
        p1, p2, p3, p4 = st.columns(4)
        include_process_context = p1.checkbox("Include process boiling check", value=True, key="steam_hdr_include_process")
        process_pressure_value = p2.number_input("Process pressure", value=20.0, key="steam_hdr_process_pressure", disabled=not include_process_context)
        process_pressure_unit = p3.selectbox("Process pressure unit", PRESSURE_UNITS, index=0, key="steam_hdr_process_pressure_unit", disabled=not include_process_context)
        bpe_value = p4.number_input("Process BPE", value=6.0, key="steam_hdr_bpe", disabled=not include_process_context)
        bpe_unit = st.selectbox("Process BPE unit", DELTA_TEMPERATURE_UNITS, index=0, key="steam_hdr_bpe_unit", disabled=not include_process_context)

        out1, out2, out3, out4 = st.columns(4)
        steam_flow_out_unit = out1.selectbox("Steam-flow output unit", MASS_FLOW_UNITS, index=0, key="steam_hdr_flow_out")
        duty_out_unit = out2.selectbox("Duty output unit", POWER_UNITS, index=0, key="steam_hdr_duty_out")
        temp_out_unit = out3.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="steam_hdr_temp_out")
        dt_out_unit = out4.selectbox("ΔT output unit", DELTA_TEMPERATURE_UNITS, index=0, key="steam_hdr_dt_out")

        result = evaluate_steam_header_pressure_change(
            duty_kw=power_to_kw(duty_value, duty_unit),
            current_pressure_value=current_pressure_value,
            current_pressure_unit=current_pressure_unit,
            reduced_pressure_value=reduced_pressure_value,
            reduced_pressure_unit=reduced_pressure_unit,
            process_pressure_value=process_pressure_value if include_process_context else None,
            process_pressure_unit=process_pressure_unit,
            process_bpe_c=delta_temperature_to_c(bpe_value, bpe_unit),
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current steam required", f"{kg_h_to_mass_flow(result.current_steam_flow_kg_h, steam_flow_out_unit):,.1f} {steam_flow_out_unit}")
        m2.metric("Reduced-pressure steam required", f"{kg_h_to_mass_flow(result.reduced_steam_flow_kg_h, steam_flow_out_unit):,.1f} {steam_flow_out_unit}")
        m3.metric("Extra steam required", f"{kg_h_to_mass_flow(result.additional_steam_required_kg_h, steam_flow_out_unit):,.1f} {steam_flow_out_unit}", delta=f"{result.additional_steam_required_pct:,.1f}%")
        m4.metric("Duty shortfall at same steam flow", f"{kw_to_power(result.duty_shortfall_kw, duty_out_unit):,.1f} {duty_out_unit}", delta=f"{result.duty_shortfall_pct:,.1f}% shortfall")

        t1, t2, t3 = st.columns(3)
        t1.metric("Current condensing temp", f"{_display_temperature(result.current_condensing_temperature_c, temp_out_unit):,.2f} °{temp_out_unit}")
        t2.metric("Reduced condensing temp", f"{_display_temperature(result.reduced_condensing_temperature_c, temp_out_unit):,.2f} °{temp_out_unit}")
        t3.metric("Same-flow available duty", f"{kw_to_power(result.reduced_available_duty_kw, duty_out_unit):,.1f} {duty_out_unit}")

        if result.process_boiling_temperature_c is not None:
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Process boiling temp", f"{_display_temperature(result.process_boiling_temperature_c, temp_out_unit):,.2f} °{temp_out_unit}")
            d2.metric("Current available ΔT", f"{_display_delta_t(result.current_available_delta_t_c or 0.0, dt_out_unit):,.2f} °{dt_out_unit}")
            d3.metric("Reduced available ΔT", f"{_display_delta_t(result.reduced_available_delta_t_c or 0.0, dt_out_unit):,.2f} °{dt_out_unit}")
            d4.metric("ΔT change", f"{_display_delta_t(result.delta_t_change_c or 0.0, dt_out_unit):,.2f} °{dt_out_unit}")

        comparison_df = pd.DataFrame(
            [
                {"case": "Current header", "steam_required": kg_h_to_mass_flow(result.current_steam_flow_kg_h, steam_flow_out_unit), "available_duty": kw_to_power(result.current_available_duty_kw, duty_out_unit)},
                {"case": "Reduced header", "steam_required": kg_h_to_mass_flow(result.reduced_steam_flow_kg_h, steam_flow_out_unit), "available_duty": kw_to_power(result.reduced_available_duty_kw, duty_out_unit)},
            ]
        )
        st.plotly_chart(
            px.bar(
                comparison_df,
                x="case",
                y=["steam_required", "available_duty"],
                barmode="group",
                title=f"Header pressure comparison ({steam_flow_out_unit} and {duty_out_unit})",
            ),
            use_container_width=True,
        )
        _remember_case(
            "steam-header-pressure-change",
            {
                "duty_value": duty_value,
                "duty_unit": duty_unit,
                "current_pressure_value": current_pressure_value,
                "current_pressure_unit": current_pressure_unit,
                "reduced_pressure_value": reduced_pressure_value,
                "reduced_pressure_unit": reduced_pressure_unit,
                "include_process_context": include_process_context,
                "process_pressure_value": process_pressure_value if include_process_context else None,
                "process_pressure_unit": process_pressure_unit if include_process_context else None,
                "bpe_value": bpe_value if include_process_context else None,
                "bpe_unit": bpe_unit if include_process_context else None,
            },
            asdict(result),
        )
        st.json(asdict(result))
        _show_notes(result.notes)



def render_evaporators() -> None:
    st.header("Evaporators")
    st.caption("Screen target evaporation duty or estimate achievable performance from installed U·A·ΔT for an existing body.")

    c1, c2, c3, c4 = st.columns(4)
    feed_rate = c1.number_input("Feed rate", value=25000.0, key="ev_feed_rate")
    feed_rate_unit = c2.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="ev_feed_rate_unit")
    feed_solids = c3.number_input("Feed solids (wt%)", value=12.0, key="ev_feed_solids")
    product_solids = c4.number_input("Product solids (wt%)", value=50.0, key="ev_prod_solids")

    c5, c6, c7, c8 = st.columns(4)
    steam_pressure = c5.number_input("Steam pressure", value=3.5, key="ev_steam_pressure")
    steam_pressure_unit = c6.selectbox("Steam pressure unit", PRESSURE_UNITS, index=4, key="ev_steam_pressure_unit")
    operating_pressure = c7.number_input("Operating pressure", value=20.0, key="ev_operating_pressure")
    operating_pressure_unit = c8.selectbox("Operating pressure unit", PRESSURE_UNITS, index=0, key="ev_operating_pressure_unit")

    c9, c10, c11, c12, c13 = st.columns(5)
    passes = int(c9.number_input("Passes", min_value=1, value=2, step=1, key="ev_passes"))
    recirc = c10.number_input("Recirculation ratio", value=4.0, key="ev_recirc")
    evaporator_product = c11.selectbox(
        "Product / liquor",
        ["citric_acid", "fructose", "dextrose", "sucrose"],
        format_func=lambda key: PRODUCT_PROFILES[key].display_name,
        key="ev_product",
    )
    duty_per_kg = c12.number_input("Specific evaporation duty", value=2250.0, key="ev_spec_duty")
    spec_duty_unit = c13.selectbox("Specific duty unit", SPECIFIC_ENERGY_UNITS, index=0, key="ev_spec_duty_unit")

    output1, output2, output3, output4 = st.columns(4)
    output_flow_unit = output1.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="ev_flow_out")
    output_temp_unit = output2.selectbox("Output temperature unit", TEMPERATURE_UNITS, index=0, key="ev_temp_out")
    delta_t_unit = output3.selectbox("ΔT output unit", DELTA_TEMPERATURE_UNITS, index=0, key="ev_dt_out")
    duty_output_unit = output4.selectbox("Duty output unit", POWER_UNITS, index=0, key="ev_duty_out")
    bpe_unit = st.selectbox("Displayed BPE unit", DELTA_TEMPERATURE_UNITS, index=0, key="ev_bpe_unit")

    if evaporator_product == "citric_acid":
        citric = estimate_citric_bpe(product_solids, operating_pressure, operating_pressure_unit, method="auto")
        bpe_c = citric.bpe_c
        st.caption(f"Auto-estimated citric BPE at {product_solids:.1f} wt%: {_display_delta_t(bpe_c, bpe_unit):,.2f} °{bpe_unit}")
        _show_notes(citric.notes)
    else:
        auto_props = solution_properties(evaporator_product, product_solids, 45.0, operating_pressure, operating_pressure_unit)
        bpe_c = auto_props.estimated_bpe_c
        st.caption(f"Auto-estimated BPE for {PRODUCT_PROFILES[evaporator_product].display_name}: {_display_delta_t(bpe_c, bpe_unit):,.2f} °{bpe_unit}")

    tabs = st.tabs(["Target duty", "Design-calibrated mode", "Fouling & NCG", "Multi-effect staging", "Body-by-body staging"])

    with tabs[0]:
        result = estimate_evaporation(
            EvaporatorInputs(
                feed_rate_value=feed_rate,
                feed_rate_unit=feed_rate_unit,
                feed_solids_wt_pct=feed_solids,
                product_solids_wt_pct=product_solids,
                steam_pressure_value=steam_pressure,
                steam_pressure_unit=steam_pressure_unit,
                operating_pressure_value=operating_pressure,
                operating_pressure_unit=operating_pressure_unit,
                passes=passes,
                recirculation_ratio=recirc,
                bpe_c=bpe_c,
                estimated_specific_evaporation_duty_kj_kg=specific_energy_to_kj_kg(duty_per_kg, spec_duty_unit),
            )
        )
        df = pd.DataFrame(
            [
                {"Stream": "Feed", "value": kg_h_to_mass_flow(result.feed_rate_kg_h, output_flow_unit)},
                {"Stream": "Product", "value": kg_h_to_mass_flow(result.product_rate_kg_h, output_flow_unit)},
                {"Stream": "Evaporation", "value": kg_h_to_mass_flow(result.evaporation_rate_kg_h, output_flow_unit)},
                {"Stream": "Steam", "value": kg_h_to_mass_flow(result.estimated_steam_flow_kg_h, output_flow_unit)},
            ]
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Evaporation", f"{kg_h_to_mass_flow(result.evaporation_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m2.metric("Steam flow", f"{kg_h_to_mass_flow(result.estimated_steam_flow_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m3.metric("Boiling temp", f"{_display_temperature(result.boiling_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}")
        m4.metric("ΔT", f"{_display_delta_t(result.delta_t_c, delta_t_unit):,.2f} °{delta_t_unit}")
        n1, n2 = st.columns(2)
        n1.metric("Duty", f"{kw_to_power(result.estimated_duty_kw, duty_output_unit):,.1f} {duty_output_unit}")
        n2.metric("Steam economy", f"{result.steam_economy_kg_evap_per_kg_steam:,.2f} kg/kg")
        st.plotly_chart(px.bar(df, x="Stream", y="value", title=f"Evaporator Streams ({output_flow_unit})"), use_container_width=True)
        _show_notes(result.notes)
        _remember_case("evaporators-target-duty", {
            "feed_rate": feed_rate,
            "feed_rate_unit": feed_rate_unit,
            "feed_solids": feed_solids,
            "product_solids": product_solids,
            "steam_pressure": steam_pressure,
            "steam_pressure_unit": steam_pressure_unit,
            "operating_pressure": operating_pressure,
            "operating_pressure_unit": operating_pressure_unit,
            "passes": passes,
            "recirc": recirc,
            "product": evaporator_product,
            "specific_evaporation_duty_kj_kg": duty_per_kg,
            "bpe_c": bpe_c,
        }, asdict(result))

    with tabs[1]:
        st.caption("Estimate whether the installed evaporator body can actually reach the entered target concentration at the current pressure basis.")
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        overall_u = d1.number_input("Overall U", min_value=0.0, value=1800.0, key="ev_cal_u")
        ev_u_unit = d2.selectbox("U unit", HTC_UNITS, index=0, key="ev_cal_u_unit")
        installed_area = d3.number_input("Installed area", min_value=0.0, value=250.0, key="ev_cal_area")
        ev_area_unit = d4.selectbox("Area unit", AREA_UNITS, index=0, key="ev_cal_area_unit")
        availability_pct = d5.number_input("Availability (%)", min_value=0.0, value=85.0, key="ev_cal_availability")

        calibrated = estimate_design_calibrated_evaporation(
            EvaporatorDesignCalibrationInputs(
                feed_rate_value=feed_rate,
                feed_rate_unit=feed_rate_unit,
                feed_solids_wt_pct=feed_solids,
                target_product_solids_wt_pct=product_solids,
                steam_pressure_value=steam_pressure,
                steam_pressure_unit=steam_pressure_unit,
                operating_pressure_value=operating_pressure,
                operating_pressure_unit=operating_pressure_unit,
                bpe_c=bpe_c,
                estimated_specific_evaporation_duty_kj_kg=specific_energy_to_kj_kg(duty_per_kg, spec_duty_unit),
                overall_u_w_m2_k=htc_to_w_m2k(overall_u, ev_u_unit),
                installed_area_m2=area_to_m2(installed_area, ev_area_unit),
                availability_factor=availability_pct / 100.0,
            )
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Target evaporation", f"{kg_h_to_mass_flow(calibrated.target_evaporation_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m2.metric("Achievable evaporation", f"{kg_h_to_mass_flow(calibrated.achievable_evaporation_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m3.metric("Required duty", f"{kw_to_power(calibrated.required_duty_kw, duty_output_unit):,.1f} {duty_output_unit}")
        m4.metric("Available duty", f"{kw_to_power(calibrated.available_duty_kw, duty_output_unit):,.1f} {duty_output_unit}")

        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Required area", f"{m2_to_area(calibrated.required_area_m2, ev_area_unit):,.1f} {ev_area_unit}")
        n2.metric("Area utilization", f"{calibrated.area_utilization_fraction * 100.0:,.1f} %")
        n3.metric("Achievable product rate", f"{kg_h_to_mass_flow(calibrated.achievable_product_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        achievable_product_solids = calibrated.dissolved_solids_kg_h / max(calibrated.achievable_product_rate_kg_h, 1e-9) * 100.0
        n4.metric("Achievable product solids", f"{achievable_product_solids:,.2f} wt%")

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Boiling temp", f"{_display_temperature(calibrated.boiling_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}")
        p2.metric("Condensing temp", f"{_display_temperature(calibrated.condensing_temperature_c, output_temp_unit):,.2f} °{output_temp_unit}")
        p3.metric("Available ΔT", f"{_display_delta_t(calibrated.delta_t_c, delta_t_unit):,.2f} °{delta_t_unit}")
        p4.metric("Available steam flow", f"{kg_h_to_mass_flow(calibrated.available_steam_flow_kg_h, output_flow_unit):,.1f} {output_flow_unit}")

        compare_df = pd.DataFrame([
            {"Case": "Target", f"Evaporation ({output_flow_unit})": kg_h_to_mass_flow(calibrated.target_evaporation_rate_kg_h, output_flow_unit), f"Duty ({duty_output_unit})": kw_to_power(calibrated.required_duty_kw, duty_output_unit), "Product solids (wt%)": product_solids},
            {"Case": "Achievable", f"Evaporation ({output_flow_unit})": kg_h_to_mass_flow(calibrated.achievable_evaporation_rate_kg_h, output_flow_unit), f"Duty ({duty_output_unit})": kw_to_power(calibrated.available_duty_kw, duty_output_unit), "Product solids (wt%)": achievable_product_solids},
        ])
        st.dataframe(compare_df, use_container_width=True)
        _show_notes(calibrated.notes)
        _remember_case("evaporators-design-calibrated", {
            "feed_rate": feed_rate,
            "feed_rate_unit": feed_rate_unit,
            "feed_solids": feed_solids,
            "product_solids": product_solids,
            "steam_pressure": steam_pressure,
            "steam_pressure_unit": steam_pressure_unit,
            "operating_pressure": operating_pressure,
            "operating_pressure_unit": operating_pressure_unit,
            "product": evaporator_product,
            "specific_evaporation_duty_kj_kg": duty_per_kg,
            "bpe_c": bpe_c,
            "overall_u_w_m2_k": overall_u,
            "installed_area_m2": installed_area,
            "availability_pct": availability_pct,
        }, asdict(calibrated))

    with tabs[2]:
        st.caption("Estimate how fouling resistances and non-condensable gases degrade an evaporator's effective U and driving ΔT. Enter clean U and fouling factors typical for your service; treat outputs as screening-level allowances, not design margins.")
        f0, f1, f2, f0u = st.columns(4)
        clean_u_val = f0.number_input("Clean overall U", min_value=100.0, value=2000.0, key="ev_fouling_clean_u")
        fouling_u_unit = f0u.selectbox("U unit", HTC_UNITS, index=0, key="ev_fouling_u_unit")
        tube_fouling = f1.number_input("Tube-side fouling (m²·K/W)", min_value=0.0, value=0.00035, format="%.5f", key="ev_fouling_tube")
        steam_fouling = f2.number_input("Steam-side fouling (m²·K/W)", min_value=0.0, value=0.00010, format="%.5f", key="ev_fouling_steam")

        f3, f4, f5, f6 = st.columns(4)
        ncg_fraction = f3.number_input("NCG mole fraction in steam space", min_value=0.0, max_value=0.15, value=0.02, step=0.005, key="ev_fouling_ncg")
        fouling_steam_pressure = f4.number_input(
            "Steam supply pressure", value=steam_pressure, key="ev_fouling_steam_pressure",
        )
        fouling_steam_pressure_unit = f5.selectbox("Steam pressure unit", PRESSURE_UNITS, index=PRESSURE_UNITS.index(steam_pressure_unit) if steam_pressure_unit in PRESSURE_UNITS else 4, key="ev_fouling_steam_pressure_unit")
        fouling_operating_pressure = f6.number_input(
            "Vapor body operating pressure", value=operating_pressure, key="ev_fouling_operating_pressure",
        )
        f7, f8, f9 = st.columns(3)
        fouling_operating_pressure_unit = f7.selectbox("Operating pressure unit", PRESSURE_UNITS, index=PRESSURE_UNITS.index(operating_pressure_unit) if operating_pressure_unit in PRESSURE_UNITS else 0, key="ev_fouling_operating_pressure_unit")
        fouling_bpe = f8.number_input("BPE", value=bpe_c if bpe_unit == "C" else bpe_c, key="ev_fouling_bpe_c")
        fouling_bpe_unit = f9.selectbox("BPE unit", DELTA_TEMPERATURE_UNITS, index=0, key="ev_fouling_bpe_unit")

        fouling_inputs = FoulingAllowanceInputs(
            clean_u_w_m2_k=htc_to_w_m2k(clean_u_val, fouling_u_unit),
            tube_side_fouling_m2_k_w=tube_fouling,
            steam_side_fouling_m2_k_w=steam_fouling,
            ncg_mole_fraction=ncg_fraction,
            steam_pressure_value=fouling_steam_pressure,
            steam_pressure_unit=fouling_steam_pressure_unit,
            operating_pressure_value=fouling_operating_pressure,
            operating_pressure_unit=fouling_operating_pressure_unit,
            bpe_c=delta_temperature_to_c(fouling_bpe, fouling_bpe_unit),
        )
        fouling_result = evaluate_fouling_and_ncg_allowance(fouling_inputs)

        u1, u2, u3, u4 = st.columns(4)
        u1.metric("Clean U", f"{w_m2k_to_htc(fouling_result.clean_u_w_m2_k, fouling_u_unit):,.0f} {fouling_u_unit}")
        u2.metric("Fouled U", f"{w_m2k_to_htc(fouling_result.dirty_u_w_m2_k, fouling_u_unit):,.0f} {fouling_u_unit}", delta=f"{fouling_result.u_degradation_pct:.1f}% degradation")
        u3.metric("Clean condensing temp", f"{_display_temperature(fouling_result.clean_condensing_temp_c, output_temp_unit):,.1f} °{output_temp_unit}")
        u4.metric("Effective condensing (w/ NCG)", f"{_display_temperature(fouling_result.effective_condensing_temp_c, output_temp_unit):,.1f} °{output_temp_unit}")

        v1, v2, v3, v4 = st.columns(4)
        v1.metric("Condensing temp penalty", f"{_display_delta_t(fouling_result.condensing_temp_penalty_c, delta_t_unit):+.2f} °{delta_t_unit}")
        v2.metric("Clean ΔT", f"{_display_delta_t(fouling_result.clean_delta_t_c, delta_t_unit):,.2f} °{delta_t_unit}")
        v3.metric("Fouled ΔT", f"{_display_delta_t(fouling_result.dirty_delta_t_c, delta_t_unit):,.2f} °{delta_t_unit}")
        v4.metric("ΔT penalty", f"{_display_delta_t(fouling_result.delta_t_penalty_c, delta_t_unit):+.2f} °{delta_t_unit}")

        w1, w2, w3 = st.columns(3)
        w1.metric(
            "Clean duty (per m²)", f"{fouling_result.clean_capacity_kw:,.2f} kW/m²",
        )
        w2.metric(
            "Fouled duty (per m²)", f"{fouling_result.dirty_capacity_kw:,.2f} kW/m²",
            delta=f"{fouling_result.capacity_penalty_pct:.1f}% loss",
        )
        w3.metric(
            "Combined allowance factor", f"{fouling_result.combined_allowance:.3f}x",
            help=f"Dirty case is {fouling_result.combined_allowance:.3f} × the clean U·ΔT capacity",
        )

        if installed_area > 0:
            x1, x2, x3 = st.columns(3)
            x1.metric("Total clean capacity", f"{fouling_result.clean_capacity_kw * installed_area:,.1f} kW")
            x2.metric("Total fouled capacity", f"{fouling_result.dirty_capacity_kw * installed_area:,.1f} kW")
            total_loss = (fouling_result.clean_capacity_kw - fouling_result.dirty_capacity_kw) * installed_area
            x3.metric("Total capacity loss", f"{total_loss:,.1f} kW", delta=f"{fouling_result.capacity_penalty_pct:.1f}%")

        _show_notes(fouling_result.notes)
        _remember_case(
            "evaporators-fouling-ncg",
            {
                "clean_u_w_m2_k": clean_u_val,
                "tube_fouling": tube_fouling,
                "steam_fouling": steam_fouling,
                "ncg_fraction": ncg_fraction,
                "steam_pressure_value": fouling_steam_pressure,
                "steam_pressure_unit": fouling_steam_pressure_unit,
                "operating_pressure_value": fouling_operating_pressure,
                "operating_pressure_unit": fouling_operating_pressure_unit,
                "bpe_c": fouling_bpe,
            },
            {k: v for k, v in asdict(fouling_result).items() if k != "notes"},
        )

    with tabs[3]:
        st.caption("Screen a multi-effect evaporator train by distributing available ΔT across effects, estimating per-effect BPE, and computing forward-feed temperature/pressure profiles and overall steam economy.")

        d1, d2, d3 = st.columns(3)
        me_n_effects = d1.number_input("Number of effects", min_value=1, max_value=6, value=3, step=1, key="ev_me_n_effects")
        me_feed_rate = d2.number_input("Feed rate", value=25000.0, key="ev_me_feed_rate")
        me_feed_rate_unit = d3.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="ev_me_feed_rate_unit")

        d4, d5 = st.columns(2)
        me_feed_solids = d4.number_input("Feed solids (wt%)", value=12.0, key="ev_me_feed_solids")
        me_product_solids = d5.number_input("Product solids (wt%)", value=50.0, key="ev_me_product_solids")

        e1, e2, e3, e4 = st.columns(4)
        me_steam_pressure = e1.number_input("Steam pressure", value=3.5, key="ev_me_steam_pressure")
        me_steam_pressure_unit = e2.selectbox("Steam pressure unit", PRESSURE_UNITS, index=4, key="ev_me_steam_pressure_unit")
        me_last_effect_pressure = e3.number_input("Last-effect pressure", value=12.0, key="ev_me_last_pressure")
        me_last_effect_pressure_unit = e4.selectbox("Last-effect pressure unit", PRESSURE_UNITS, index=0, key="ev_me_last_pressure_unit")

        e5, e6, e7 = st.columns(3)
        me_duty_per_kg = e5.number_input("Specific evaporation duty", value=2250.0, key="ev_me_spec_duty")
        me_spec_duty_unit = e6.selectbox("Specific duty unit", SPECIFIC_ENERGY_UNITS, index=0, key="ev_me_spec_duty_unit")
        me_temp_out_unit = e7.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="ev_me_temp_out")

        me_bpe_u1, me_bpe_u2 = st.columns([1, 3])
        me_bpe_unit = me_bpe_u1.selectbox("BPE unit", DELTA_TEMPERATURE_UNITS, index=0, key="ev_me_bpe_unit")
        st.caption(f"Enter BPE for each effect ({me_bpe_unit}). The app will pad with the last entered value if fewer than the number of effects.")
        bpe_cols = st.columns(min(me_n_effects, 6))
        me_bpe_list = []
        for i in range(me_n_effects):
            bpe_val = bpe_cols[i].number_input(
                f"Effect {i+1} BPE",
                value=6.0 + i * 3.0,
                min_value=0.0,
                key=f"ev_me_bpe_{i}",
            )
            me_bpe_list.append(bpe_val)

        try:
            me_result = estimate_multi_effect_evaporation(
                feed_rate_kg_h=me_feed_rate if me_feed_rate_unit == "kg/h" else mass_flow_to_kg_h(me_feed_rate, me_feed_rate_unit),
                feed_solids_wt_pct=me_feed_solids,
                product_solids_wt_pct=me_product_solids,
                n_effects=me_n_effects,
                steam_pressure_value=me_steam_pressure,
                steam_pressure_unit=me_steam_pressure_unit,
                last_effect_pressure_value=me_last_effect_pressure,
                last_effect_pressure_unit=me_last_effect_pressure_unit,
                bpe_c_per_effect=[delta_temperature_to_c(b, me_bpe_unit) for b in me_bpe_list],
                estimated_specific_evaporation_duty_kj_kg=specific_energy_to_kj_kg(me_duty_per_kg, me_spec_duty_unit),
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Number of effects", str(me_result.n_effects))
            m2.metric("Total evaporation", f"{kg_h_to_mass_flow(me_result.total_evaporation_kg_h, me_feed_rate_unit):,.1f} {me_feed_rate_unit}")
            m3.metric("Steam required", f"{kg_h_to_mass_flow(me_result.steam_flow_kg_h, me_feed_rate_unit):,.1f} {me_feed_rate_unit}")
            m4.metric("Steam economy", f"{me_result.overall_steam_economy:.2f} kg/kg")

            s1, s2, s3 = st.columns(3)
            s1.metric("Steam temperature", f"{_display_temperature(me_result.steam_temperature_c, me_temp_out_unit):,.1f} °{me_temp_out_unit}")
            s2.metric("Last-effect boiling temp", f"{_display_temperature(me_result.last_effect_boiling_temperature_c, me_temp_out_unit):,.1f} °{me_temp_out_unit}")
            s3.metric("Overall ΔT", f"{me_result.overall_delta_t_c * (1.8 if me_temp_out_unit == 'F' else 1.0):.1f} °{me_temp_out_unit}")

            st.subheader("Effect-by-effect profile")
            effect_df = pd.DataFrame([
                {
                    "Effect": f"{eff.effect_number}",
                    f"Steam temp (°{me_temp_out_unit})": _display_temperature(eff.steam_temperature_c, me_temp_out_unit),
                    f"Boiling temp (°{me_temp_out_unit})": _display_temperature(eff.boiling_temperature_c, me_temp_out_unit),
                    f"BPE (°{me_bpe_unit})": c_to_delta_temperature(eff.bpe_c, me_bpe_unit),
                    f"Net ΔT (°{me_temp_out_unit})": eff.delta_t_c * (1.8 if me_temp_out_unit == 'F' else 1.0),
                    "Pressure (kPa abs)": eff.pressure_kpa_abs,
                    f"Evaporation ({me_feed_rate_unit})": kg_h_to_mass_flow(eff.evaporation_kg_h, me_feed_rate_unit),
                    "Cumulative evap (kg/h)": eff.cumulative_evaporation_kg_h,
                    "Liquor solids (wt%)": eff.liquor_solids_wt_pct,
                }
                for eff in me_result.effects
            ])
            st.dataframe(effect_df, use_container_width=True)

            # Temperature profile plot
            effect_nums = [eff.effect_number for eff in me_result.effects]
            steam_temps = [_display_temperature(eff.steam_temperature_c, me_temp_out_unit) for eff in me_result.effects]
            boil_temps = [_display_temperature(eff.boiling_temperature_c, me_temp_out_unit) for eff in me_result.effects]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=effect_nums, y=steam_temps, mode="lines+markers", name="Steam temp", line=dict(dash="dash")))
            fig.add_trace(go.Scatter(x=effect_nums, y=boil_temps, mode="lines+markers", name="Boiling temp"))
            fig.update_layout(
                title="Multi-effect temperature profile",
                xaxis_title="Effect number",
                yaxis_title=f"Temperature (°{me_temp_out_unit})",
                xaxis=dict(tickmode="linear", dtick=1),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Solids profile plot
            liquor_solids = [eff.liquor_solids_wt_pct for eff in me_result.effects]
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=effect_nums, y=liquor_solids, name="Liquor solids (wt%)"))
            fig2.update_layout(
                title="Liquor solids concentration by effect",
                xaxis_title="Effect number",
                yaxis_title="Solids (wt%)",
                xaxis=dict(tickmode="linear", dtick=1),
            )
            st.plotly_chart(fig2, use_container_width=True)

            _show_notes(me_result.notes)
            _remember_case(
                "evaporators-multi-effect",
                {
                    "n_effects": me_n_effects,
                    "feed_rate": me_feed_rate,
                    "feed_rate_unit": me_feed_rate_unit,
                    "feed_solids": me_feed_solids,
                    "product_solids": me_product_solids,
                    "steam_pressure": me_steam_pressure,
                    "steam_pressure_unit": me_steam_pressure_unit,
                    "last_effect_pressure": me_last_effect_pressure,
                    "last_effect_pressure_unit": me_last_effect_pressure_unit,
                    "bpe_list": me_bpe_list,
                    "specific_duty": me_duty_per_kg,
                },
                {
                    "n_effects": me_result.n_effects,
                    "total_evaporation_kg_h": me_result.total_evaporation_kg_h,
                    "steam_flow_kg_h": me_result.steam_flow_kg_h,
                    "steam_economy": me_result.overall_steam_economy,
                    "effects": [
                        {
                            "effect_number": eff.effect_number,
                            "steam_temp_c": eff.steam_temperature_c,
                            "boiling_temp_c": eff.boiling_temperature_c,
                            "bpe_c": eff.bpe_c,
                            "delta_t_c": eff.delta_t_c,
                            "pressure_kpa_abs": eff.pressure_kpa_abs,
                            "evaporation_kg_h": eff.evaporation_kg_h,
                            "liquor_solids_wt_pct": eff.liquor_solids_wt_pct,
                        }
                        for eff in me_result.effects
                    ],
                },
            )
        except ValueError as exc:
            st.error(str(exc))

    with tabs[4]:
        st.caption("Screen a multi-effect evaporator train with per-effect U values, installed areas, feed preheat, and flow direction. Unlike the simplified equal-ΔT mode, each body can have different heat-transfer coefficients and areas, and sensible-heat effects are explicitly tracked.")

        bb1, bb2, bb3 = st.columns(3)
        bb_n_effects = bb1.number_input("Number of effects", min_value=1, max_value=8, value=3, step=1, key="ev_bb_n_effects")
        bb_feed_rate = bb2.number_input("Feed rate", value=25000.0, key="ev_bb_feed_rate")
        bb_feed_rate_unit = bb3.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="ev_bb_feed_rate_unit")

        bb4, bb5, bb6, bb7 = st.columns(4)
        bb_feed_solids = bb4.number_input("Feed solids (wt%)", value=12.0, key="ev_bb_feed_solids")
        bb_feed_temp = bb5.number_input("Feed temperature", value=85.0, key="ev_bb_feed_temp")
        bb_feed_temp_unit = bb6.selectbox("Feed temp unit", TEMPERATURE_UNITS, index=0, key="ev_bb_feed_temp_unit")
        bb_flow_dir = bb7.selectbox("Flow direction", ["forward", "backward"], key="ev_bb_dir")

        bb8, bb9, bb10 = st.columns(3)
        bb_feed_effect = bb8.number_input("Feed entry effect (1-" + str(bb_n_effects) + ")", min_value=1, max_value=max(bb_n_effects, 1), value=1 if bb_flow_dir == "forward" else bb_n_effects, step=1, key="ev_bb_feed_eff")
        bb_steam_pressure = bb9.number_input("Steam pressure", value=3.5, key="ev_bb_steam_pressure")
        bb_steam_pressure_unit = bb10.selectbox("Steam pressure unit", PRESSURE_UNITS, index=4, key="ev_bb_steam_pressure_unit")

        bb11, bb12 = st.columns(2)
        bb_last_effect_pressure = bb11.number_input("Last-effect pressure", value=12.0, key="ev_bb_last_pressure")
        bb_last_effect_pressure_unit = bb12.selectbox("Last-effect pressure unit", PRESSURE_UNITS, index=0, key="ev_bb_last_pressure_unit")

        bb13, bb14, bb15, bb16 = st.columns(4)
        bb_duty_per_kg = bb13.number_input("Specific evaporation duty", value=2250.0, key="ev_bb_spec_duty")
        bb_spec_duty_unit = bb14.selectbox("Specific duty unit", SPECIFIC_ENERGY_UNITS, index=0, key="ev_bb_spec_duty_unit")
        bb_temp_out_unit = bb15.selectbox("Temperature output unit", TEMPERATURE_UNITS, index=0, key="ev_bb_temp_out")
        bb_flow_out_unit = bb16.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="ev_bb_flow_out")

        bb_u1, bb_u2, bb_u3 = st.columns(3)
        bb_u_unit = bb_u1.selectbox("U unit", HTC_UNITS, index=0, key="ev_bb_u_unit")
        bb_area_unit = bb_u2.selectbox("Area unit", AREA_UNITS, index=0, key="ev_bb_area_unit")
        bb_bpe_unit = bb_u3.selectbox("BPE unit", DELTA_TEMPERATURE_UNITS, index=0, key="ev_bb_bpe_unit")

        st.markdown("**Per-effect configuration**")
        st.caption("Enter U and installed area for each body. U typically drops in later effects as liquor concentration and viscosity increase.")
        effect_cols = st.columns(min(bb_n_effects, 8))
        bb_effect_configs: list[BodyByBodyEffectInput] = []
        for i in range(bb_n_effects):
            with effect_cols[i]:
                st.markdown(f"**Effect {i+1}**")
                eff_u = st.number_input(
                    f"Overall U ({bb_u_unit})", value=2500.0 - i * 400.0, min_value=200.0, key=f"ev_bb_u_{i}"
                )
                eff_a = st.number_input(
                    f"Installed area ({bb_area_unit})", value=200.0 + i * 20.0, min_value=10.0, key=f"ev_bb_area_{i}"
                )
                eff_bpe = st.number_input(
                    f"BPE (°{bb_bpe_unit})", value=3.0 + i * 3.0, min_value=0.0, key=f"ev_bb_bpe_{i}"
                )
                bb_effect_configs.append(BodyByBodyEffectInput(
                    effect_number=i + 1,
                    u_w_m2_k=htc_to_w_m2k(eff_u, bb_u_unit),
                    area_m2=area_to_m2(eff_a, bb_area_unit),
                    bpe_c=delta_temperature_to_c(eff_bpe, bb_bpe_unit),
                ))

        bb_feed_temp_c = temperature_to_c(bb_feed_temp, bb_feed_temp_unit)
        feed_config = BodyByBodyFeedConfig(
            feed_rate_kg_h=bb_feed_rate if bb_feed_rate_unit == "kg/h" else mass_flow_to_kg_h(bb_feed_rate, bb_feed_rate_unit),
            feed_solids_wt_pct=bb_feed_solids,
            feed_temperature_c=bb_feed_temp_c,
            feed_effect=bb_feed_effect,
            flow_direction=bb_flow_dir,
        )

        try:
            bb_result = estimate_body_by_body_evaporation(
                feed_config=feed_config,
                effect_configs=bb_effect_configs,
                steam_pressure_value=bb_steam_pressure,
                steam_pressure_unit=bb_steam_pressure_unit,
                last_effect_pressure_value=bb_last_effect_pressure,
                last_effect_pressure_unit=bb_last_effect_pressure_unit,
                estimated_specific_evaporation_duty_kj_kg=specific_energy_to_kj_kg(bb_duty_per_kg, bb_spec_duty_unit),
            )

            x1, x2, x3, x4 = st.columns(4)
            x1.metric("Number of effects", str(bb_result.n_effects))
            x2.metric("Total evaporation", f"{kg_h_to_mass_flow(bb_result.total_evaporation_kg_h, bb_feed_rate_unit):,.1f} {bb_feed_rate_unit}")
            x3.metric("Steam required", f"{kg_h_to_mass_flow(bb_result.steam_flow_kg_h, bb_feed_rate_unit):,.1f} {bb_feed_rate_unit}")
            x4.metric("Steam economy", f"{bb_result.overall_steam_economy:.2f} kg/kg")

            y1, y2 = st.columns(2)
            y1.metric("Product rate", f"{kg_h_to_mass_flow(bb_result.product_rate_kg_h, bb_feed_rate_unit):,.1f} {bb_feed_rate_unit}")
            y2.metric("Feed rate", f"{kg_h_to_mass_flow(bb_result.feed_rate_kg_h, bb_feed_rate_unit):,.1f} {bb_feed_rate_unit}")

            st.subheader("Body-by-body detail")
            bb_df = pd.DataFrame([
                {
                    "Effect": f"{eff.effect_number}",
                    f"Steam temp ({bb_temp_out_unit})": _display_temperature(eff.steam_temperature_c, bb_temp_out_unit),
                    f"Boiling temp ({bb_temp_out_unit})": _display_temperature(eff.boiling_temperature_c, bb_temp_out_unit),
                    f"BPE (°{bb_bpe_unit})": c_to_delta_temperature(eff.bpe_c, bb_bpe_unit),
                    f"Net ΔT (°{bb_temp_out_unit})": eff.net_delta_t_c * (1.8 if bb_temp_out_unit == 'F' else 1.0),
                    "Pressure (kPa abs)": eff.effect_pressure_kpa_abs,
                    f"Evap ({bb_feed_rate_unit})": kg_h_to_mass_flow(eff.evaporation_kg_h, bb_feed_rate_unit),
                    f"Cum. evap (kg/h)": eff.cumulative_evaporation_kg_h,
                    "Liquor solids (wt%)": eff.liquor_solids_wt_pct,
                    f"Liquor flow ({bb_feed_rate_unit})": kg_h_to_mass_flow(eff.liquor_flow_kg_h, bb_feed_rate_unit),
                    f"Steam ({bb_feed_rate_unit})": kg_h_to_mass_flow(eff.steam_flow_kg_h, bb_feed_rate_unit),
                    "Sensible heat (kW)": eff.sensible_heat_kw,
                    "Duty (kW)": eff.duty_kw,
                    f"U ({bb_u_unit})": w_m2k_to_htc(eff.u_w_m2_k, bb_u_unit),
                    f"Req. area ({bb_area_unit})": m2_to_area(eff.required_area_m2, bb_area_unit),
                    f"Inst. area ({bb_area_unit})": m2_to_area(bb_effect_configs[eff.effect_number - 1].area_m2, bb_area_unit),
                    "Area util.": eff.area_utilization,
                    f"Feed in ({bb_temp_out_unit})": _display_temperature(eff.feed_in_temperature_c, bb_temp_out_unit),
                }
                for eff in bb_result.effects
            ])
            st.dataframe(bb_df, use_container_width=True)

            # Temperature profile
            eff_nums = [eff.effect_number for eff in bb_result.effects]
            steam_temps = [_display_temperature(eff.steam_temperature_c, bb_temp_out_unit) for eff in bb_result.effects]
            boil_temps = [_display_temperature(eff.boiling_temperature_c, bb_temp_out_unit) for eff in bb_result.effects]
            feed_in_temps = [_display_temperature(eff.feed_in_temperature_c, bb_temp_out_unit) for eff in bb_result.effects]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=eff_nums, y=steam_temps, mode="lines+markers", name="Steam temp", line=dict(dash="dash")))
            fig.add_trace(go.Scatter(x=eff_nums, y=boil_temps, mode="lines+markers", name="Boiling temp"))
            fig.add_trace(go.Scatter(x=eff_nums, y=feed_in_temps, mode="lines+markers", name="Feed in temp", line=dict(dash="dot")))
            fig.update_layout(
                title="Body-by-body temperature profile",
                xaxis_title="Effect number",
                yaxis_title=f"Temperature (°{bb_temp_out_unit})",
                xaxis=dict(tickmode="linear", dtick=1),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Duty and area utilization
            z1, z2 = st.columns(2)
            with z1:
                fig_duty = go.Figure()
                fig_duty.add_trace(go.Bar(x=eff_nums, y=[eff.duty_kw for eff in bb_result.effects], name="Duty (kW)"))
                fig_duty.add_trace(go.Bar(x=eff_nums, y=[eff.sensible_heat_kw for eff in bb_result.effects], name="Sensible heat (kW)"))
                fig_duty.update_layout(
                    title="Duty breakdown by effect",
                    xaxis_title="Effect number",
                    yaxis_title="Duty (kW)",
                    xaxis=dict(tickmode="linear", dtick=1),
                    barmode="stack",
                )
                st.plotly_chart(fig_duty, use_container_width=True)

            with z2:
                fig_area = go.Figure()
                inst_areas = [m2_to_area(bb_effect_configs[eff.effect_number - 1].area_m2, bb_area_unit) for eff in bb_result.effects]
                fig_area.add_trace(go.Bar(x=eff_nums, y=inst_areas, name=f"Installed area ({bb_area_unit})", width=0.3, offset=-0.25))
                fig_area.add_trace(go.Bar(x=eff_nums, y=[m2_to_area(eff.required_area_m2, bb_area_unit) for eff in bb_result.effects], name=f"Required area ({bb_area_unit})", width=0.3, offset=0.15))
                fig_area.add_trace(go.Scatter(x=eff_nums, y=[eff.area_utilization for eff in bb_result.effects], mode="lines+markers", name="Area utilization", yaxis="y2"))
                fig_area.update_layout(
                    title="Area comparison and utilization",
                    xaxis_title="Effect number",
                    yaxis_title=f"Area ({bb_area_unit})",
                    xaxis=dict(tickmode="linear", dtick=1),
                )
                st.plotly_chart(fig_area, use_container_width=True)

            _show_notes(bb_result.notes)
            _remember_case(
                "evaporators-body-by-body",
                {
                    "n_effects": bb_n_effects,
                    "feed_rate": bb_feed_rate,
                    "feed_rate_unit": bb_feed_rate_unit,
                    "feed_solids": bb_feed_solids,
                    "feed_temp_c": bb_feed_temp_c,
                    "flow_direction": bb_flow_dir,
                    "feed_effect": bb_feed_effect,
                    "steam_pressure": bb_steam_pressure,
                    "steam_pressure_unit": bb_steam_pressure_unit,
                    "last_effect_pressure": bb_last_effect_pressure,
                    "last_effect_pressure_unit": bb_last_effect_pressure_unit,
                    "effects": [{"u": c.u_w_m2_k, "area": c.area_m2, "bpe": c.bpe_c, "effect": c.effect_number} for c in bb_effect_configs],
                },
                {
                    "n_effects": bb_result.n_effects,
                    "total_evaporation_kg_h": bb_result.total_evaporation_kg_h,
                    "product_rate_kg_h": bb_result.product_rate_kg_h,
                    "steam_flow_kg_h": bb_result.steam_flow_kg_h,
                    "steam_economy": bb_result.overall_steam_economy,
                    "effects": [
                        {
                            "effect_number": eff.effect_number,
                            "steam_temp_c": eff.steam_temperature_c,
                            "boiling_temp_c": eff.boiling_temperature_c,
                            "pressure_kpa_abs": eff.effect_pressure_kpa_abs,
                            "evaporation_kg_h": eff.evaporation_kg_h,
                            "liquor_solids_wt_pct": eff.liquor_solids_wt_pct,
                            "area_utilization": eff.area_utilization,
                        }
                        for eff in bb_result.effects
                    ],
                },
            )
        except ValueError as exc:
            st.error(str(exc))



def render_crystallizers() -> None:
    st.header("Crystallizers")
    st.caption("For citric acid, slurry can now be based on crystal volume percent while mother liquor is auto-set from temperature-dependent solubility and screened for supersaturation / metastable-band risk.")
    tabs = st.tabs(["Single-body screen", "Multi-body train"])

    with tabs[0]:
        c0, c1, c2, c3 = st.columns(4)
        product = c0.selectbox("Product", ["citric_acid", "generic"], format_func=lambda value: "Citric acid" if value == "citric_acid" else "Generic liquor", key="cr_product")
        feed_rate = c1.number_input("Feed rate", value=12000.0, key="cr_feed_rate")
        feed_rate_unit = c2.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="cr_feed_rate_unit")
        feed_solids = c3.number_input("Feed solids (wt%)", value=55.0, key="cr_feed_solids")

        c4, c5, c6, c7 = st.columns(4)
        operating_temp = c4.number_input("Operating temperature", value=45.0, key="cr_temp")
        operating_temp_unit = c5.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="cr_temp_unit")
        circulation = c6.number_input("Circulation rate", value=72000.0, key="cr_circulation")
        circulation_unit = c7.selectbox("Circulation unit", MASS_FLOW_UNITS, index=0, key="cr_circulation_unit")

        c8, c9, c10, c11 = st.columns(4)
        slurry_withdrawal = c8.number_input("Slurry withdrawal rate", min_value=0.0, value=12000.0, key="cr_slurry_withdrawal")
        slurry_withdrawal_unit = c9.selectbox("Slurry withdrawal unit", MASS_FLOW_UNITS, index=0, key="cr_slurry_withdrawal_unit")
        output_flow_unit = c10.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="cr_flow_out")
        yield_unit = c11.selectbox("Yield output unit", PERCENT_UNITS, index=0, key="cr_yield_out")

        c12, c13 = st.columns(2)
        working_volume = c12.number_input("Working volume", value=18.0, key="cr_working_volume")
        working_volume_unit = c13.selectbox("Working volume unit", VOLUME_UNITS, index=0, key="cr_working_volume_unit")

        temp_c = operating_temp if operating_temp_unit == "C" else (operating_temp - 32.0) * 5.0 / 9.0
        auto_mother_liquor_solids = estimate_citric_solubility_wt_pct(temp_c) if product == "citric_acid" else None

        d1, d2, d3 = st.columns(3)
        target_crystal_volume_pct = d1.number_input("Target crystals in slurry (vol%)", value=18.0, key="cr_target_vol_pct",
            help="Crystal volume percent as measured in the crystallizer (sight glass, sampler, or centrifuge reading).")
        basis_mode = "Crystal vol%"
        slurry_solids = 25.0  # placeholder; engine recalculates from vol% + densities
        mother_liquor_solids = d2.number_input(
            "Mother liquor solids (wt%)",
            value=auto_mother_liquor_solids if auto_mother_liquor_solids is not None else 45.0,
            key="cr_mother_solids",
            disabled=product == "citric_acid",
            help="Dissolved solids in the liquid phase. For citric acid this is auto-set from temperature-dependent solubility data.",
        )
        _ = d3.empty()

        e1, e2, e3, e4 = st.columns(4)
        crystal_density = e1.number_input("Crystal density", value=1660.0, key="cr_crystal_density",
            help="Density of the solid crystals. Used to convert your vol% reading to a mass balance. Citric acid monohydrate ≈ 1,540–1,660 kg/m³.")
        cr_density_unit = e2.selectbox("Crystal density unit", DENSITY_UNITS, index=0, key="cr_density_unit")
        cr_ml_density_unit = e3.selectbox("ML density unit", ML_DENSITY_UNITS, index=0, key="cr_ml_density_unit")
        _ml_default = 1280.0 if cr_ml_density_unit != "DS%" else 45.0
        mother_liquor_density = e4.number_input(
            "Mother liquor density" if cr_ml_density_unit != "DS%" else "ML dissolved solids (wt%)",
            value=_ml_default, key="cr_ml_density",
            help="Density of the liquid phase. Choose DS% to enter dissolved-solids wt% and auto-estimate density from the citric-acid correlation.")

        f1, f2 = st.columns(2)
        supersat_screen_band_pct = f1.number_input(
            "Controllable supersaturation band upper limit (%)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="cr_supersat_band_pct",
            help="User-entered screening band for relative supersaturation = (feed solids - equilibrium solids) / equilibrium solids.",
        )
        supersat_high_warning_pct = f2.number_input(
            "High supersaturation warning limit (%)",
            min_value=supersat_screen_band_pct,
            value=max(supersat_screen_band_pct + 10.0, 20.0),
            step=1.0,
            key="cr_supersat_high_pct",
            help="Above this relative supersaturation band, expect a stronger fines / spontaneous nucleation tendency unless the crystallizer and classification loop are robust.",
        )

        result = estimate_crystallizer(
            CrystallizerInputs(
                feed_rate_value=feed_rate,
                feed_rate_unit=feed_rate_unit,
                feed_solids_wt_pct=feed_solids,
                mother_liquor_solids_wt_pct=mother_liquor_solids,
                target_slurry_solids_wt_pct=slurry_solids,
                circulation_rate_value=circulation,
                circulation_rate_unit=circulation_unit,
                working_volume_value=working_volume,
                working_volume_unit=working_volume_unit,
                operating_temperature_c=temp_c,
                product=product,
                crystal_density_kg_m3=density_to_kg_m3(crystal_density, cr_density_unit),
                mother_liquor_density_kg_m3=ml_density_to_kg_m3(mother_liquor_density, cr_ml_density_unit, temperature_c=temp_c),
                target_crystal_volume_pct=target_crystal_volume_pct,
                slurry_withdrawal_rate_value=slurry_withdrawal,
                slurry_withdrawal_rate_unit=slurry_withdrawal_unit,
                supersaturation_screen_band_relative=supersat_screen_band_pct / 100.0,
                supersaturation_high_warning_relative=supersat_high_warning_pct / 100.0,
            )
        )

        if product == "citric_acid":
            st.caption(f"Auto mother-liquor basis from published citric-acid water solubility data: {result.mother_liquor_solids_wt_pct:,.2f} wt% at {temp_c:,.1f} °C.")

        residence_unit = st.selectbox("Residence-time output unit", TIME_UNITS, index=2, key="cr_time_out")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Crystals", f"{kg_h_to_mass_flow(result.crystals_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m2.metric("Mother liquor", f"{kg_h_to_mass_flow(result.mother_liquor_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m3.metric("Crystal mass % in slurry", f"{result.slurry_crystal_mass_fraction * 100.0:,.2f} wt%")
        if result.slurry_crystal_volume_fraction is not None:
            m4.metric("Crystal volume % in slurry", f"{result.slurry_crystal_volume_fraction * 100.0:,.2f} vol%")
        elif result.residence_time_h is not None:
            residence_s = result.residence_time_h * 3600.0
            m4.metric("Residence time", f"{seconds_to_time(residence_s, residence_unit):,.2f} {residence_unit}")

        n1, n2, n3, n4 = st.columns(4)
        if result.residence_time_h is not None:
            residence_s = result.residence_time_h * 3600.0
            n1.metric("Residence time", f"{seconds_to_time(residence_s, residence_unit):,.2f} {residence_unit}")
        n2.metric("Slurry withdrawal", f"{kg_h_to_mass_flow(result.slurry_withdrawal_rate_kg_h if result.slurry_withdrawal_rate_kg_h is not None else result.estimated_slurry_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        n3.metric("Circulation ratio", f"{result.circulation_ratio:,.2f}")
        n4.metric("Yield", f"{_display_percent(result.yield_fraction_of_feed_solids, yield_unit):,.2f} {yield_unit}")

        st.subheader("Supersaturation screen")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Equilibrium mother liquor", f"{result.equilibrium_solids_wt_pct:,.2f} wt%")
        s2.metric("Absolute supersaturation", f"{result.absolute_supersaturation_wt_pct:,.2f} wt%")
        s3.metric("Relative supersaturation", f"{result.relative_supersaturation * 100.0:,.1f} %")
        s4.metric("Supersaturation ratio", f"{result.supersaturation_ratio:,.3f}")
        t1, t2 = st.columns(2)
        t1.metric("Solids above equilibrium", f"{kg_h_to_mass_flow(result.solids_above_equilibrium_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        t2.metric("Supersaturation zone", result.supersaturation_zone)
        st.caption(
            f"Screening bands: controllable <= {supersat_screen_band_pct:,.1f}% relative supersaturation; high-warning > {supersat_high_warning_pct:,.1f}% relative supersaturation."
        )
        _show_notes(result.notes)
        _remember_case("crystallizers", {
            "product": product,
            "feed_rate": feed_rate,
            "feed_rate_unit": feed_rate_unit,
            "feed_solids": feed_solids,
            "operating_temp": operating_temp,
            "operating_temp_unit": operating_temp_unit,
            "basis_mode": basis_mode,
            "target_crystal_volume_pct": target_crystal_volume_pct,
            "target_slurry_solids_wt_pct": slurry_solids,
            "mother_liquor_solids_wt_pct": mother_liquor_solids,
            "circulation": circulation,
            "circulation_unit": circulation_unit,
            "slurry_withdrawal": slurry_withdrawal,
            "slurry_withdrawal_unit": slurry_withdrawal_unit,
            "working_volume": working_volume,
            "working_volume_unit": working_volume_unit,
            "crystal_density_kg_m3": crystal_density,
            "mother_liquor_density_kg_m3": mother_liquor_density,
            "supersaturation_screen_band_pct": supersat_screen_band_pct,
            "supersaturation_high_warning_pct": supersat_high_warning_pct,
        }, asdict(result))

    with tabs[1]:
        st.caption("Screen a multi-body cooling crystallizer train for citric acid. Liquor flows forward through bodies at progressively lower temperatures, and solids precipitate when concentration exceeds the equilibrium solubility at each body's operating temperature.")
        mb0, mb1 = st.columns(2)
        mb_feed_rate = mb0.number_input("Feed rate", value=12000.0, key="mb_cr_feed_rate")
        mb_feed_rate_unit = mb1.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="mb_cr_feed_rate_unit")
        mb_feed_solids = mb0.number_input("Feed solids (wt%)", value=55.0, key="mb_cr_feed_solids")
        mb_n_bodies = mb1.number_input("Number of bodies", min_value=2, max_value=6, value=3, step=1, key="mb_cr_n_bodies")

        mb_temps_label = st.caption("Set body temperatures (decreasing from first to last body for a cooling crystallizer):")
        mb_temp_unit_col, _ = st.columns([1, 3])
        mb_temp_unit = mb_temp_unit_col.selectbox("Body temp unit", TEMPERATURE_UNITS, index=0, key="mb_cr_temp_unit")
        temp_cols = st.columns(min(mb_n_bodies, 6))
        default_temps = [80.0, 60.0, 45.0, 35.0, 25.0, 20.0]
        mb_body_temps = []
        for i in range(int(mb_n_bodies)):
            mb_body_temps.append(temp_cols[i].number_input(f"Body {i+1} temp", value=default_temps[i], key=f"mb_cr_body_temp_{i}"))

        mb_vol_c1, mb_vol_c2, mb_vol_c3 = st.columns(3)
        mb_working_volume = mb_vol_c1.number_input("Working volume per body", value=18.0, key="mb_cr_working_vol")
        mb_vol_unit = mb_vol_c2.selectbox("Volume unit", VOLUME_UNITS, index=0, key="mb_cr_vol_unit")
        mb_output_flow_unit = mb_vol_c3.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="mb_cr_flow_out")

        mb_d1, mb_d2, mb_d3, mb_d4 = st.columns(4)
        mb_crystal_density = mb_d1.number_input("Crystal density", value=1660.0, key="mb_cr_crystal_density")
        mb_density_unit = mb_d2.selectbox("Crystal density unit", DENSITY_UNITS, index=0, key="mb_cr_density_unit")
        mb_ml_density_unit = mb_d3.selectbox("ML density unit", ML_DENSITY_UNITS, index=0, key="mb_cr_ml_density_unit")
        _mb_ml_default = 1280.0 if mb_ml_density_unit != "DS%" else 45.0
        mb_ml_density = mb_d4.number_input(
            "Mother liquor density" if mb_ml_density_unit != "DS%" else "ML dissolved solids (wt%)",
            value=_mb_ml_default, key="mb_cr_ml_density",
            help="Choose DS% to enter dissolved-solids wt% and auto-estimate density from the citric-acid correlation.")

        mb_sec = st.checkbox("Include secondary feed points", value=False, help="Allow additional feed inlets at intermediate bodies.", key="mb_cr_sec_feed")
        if mb_sec:
            st.caption("Enter secondary feed rates for each body (enter 0.0 for bodies without secondary feed):")
            sec_rate_cols = st.columns(int(mb_n_bodies))
            mb_sec_rates = []
            for i in range(int(mb_n_bodies)):
                mb_sec_rates.append(sec_rate_cols[i].number_input(f"Body {i+1} sec feed rate", value=0.0, key=f"mb_cr_sec_rate_{i}"))

            st.caption("Secondary feed solids (wt%) per body:")
            sec_solids_cols = st.columns(int(mb_n_bodies))
            mb_sec_solids = []
            for i in range(int(mb_n_bodies)):
                mb_sec_solids.append(sec_solids_cols[i].number_input(f"Body {i+1} sec feed solids", value=mb_feed_solids, key=f"mb_cr_sec_solids_{i}"))
        else:
            mb_sec_rates = None
            mb_sec_solids = None

        mb_result_payload: dict = {}
        try:
            mb_inputs = MultiBodyCrystallizerInputs(
                feed_rate_value=mb_feed_rate,
                feed_rate_unit=mb_feed_rate_unit,
                feed_solids_wt_pct=mb_feed_solids,
                n_bodies=int(mb_n_bodies),
                body_temperatures_c=[temperature_to_c(t, mb_temp_unit) for t in mb_body_temps],
                working_volume_per_body_m3=volume_to_m3(mb_working_volume, mb_vol_unit),
                crystal_density_kg_m3=density_to_kg_m3(mb_crystal_density, mb_density_unit),
                mother_liquor_density_kg_m3=ml_density_to_kg_m3(mb_ml_density, mb_ml_density_unit, temperature_c=sum(temperature_to_c(t, mb_temp_unit) for t in mb_body_temps) / max(len(mb_body_temps), 1)),
                include_secondary_feed_points=mb_sec,
                secondary_feed_rates_value=mb_sec_rates if mb_sec and mb_sec_rates else None,
                secondary_feed_solids_wt_pct=mb_sec_solids if mb_sec and mb_sec_solids else None,
            )
            mb_result = estimate_multi_body_crystallizer(mb_inputs, product="citric_acid")
            mb_result_payload = {k: v for k, v in asdict(mb_result).items() if k != "bodies"}

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Bodies in train", str(mb_result.n_bodies))
            m2.metric("Total crystals", f"{kg_h_to_mass_flow(mb_result.total_crystals_kg_h, mb_output_flow_unit):,.1f} {mb_output_flow_unit}")
            m3.metric("Final mother liquor", f"{kg_h_to_mass_flow(mb_result.final_mother_liquor_kg_h, mb_output_flow_unit):,.1f} {mb_output_flow_unit}")
            m4.metric("Overall yield", f"{mb_result.overall_yield_fraction * 100.0:.1f}%")

            if mb_result.total_residence_time_h is not None:
                st.metric("Total residence time", f"{mb_result.total_residence_time_h:.2f} h")
            st.metric("Total working volume", f"{mb_result.total_working_volume_m3:.1f} m3")

            st.subheader("Body-by-body profile")
            body_df = pd.DataFrame([
                {
                    "Body": b.body_number,
                    "Temp (°C)": b.temperature_c,
                    "Equilibrium solubility (wt%)": b.equilibrium_solids_wt_pct,
                    "Liquor in (kg/h)": b.liquor_rate_in_kg_h,
                    "Liquor in solids (wt%)": b.liquor_solids_in_wt_pct,
                    "Crystals produced (kg/h)": b.crystals_produced_kg_h,
                    "Cumulative crystals (kg/h)": b.cumulative_crystals_kg_h,
                    "Residence (h)": b.residence_time_h or "—"
                }
                for b in mb_result.bodies
            ])
            st.dataframe(body_df, use_container_width=True)

            # Temperature profile plot
            body_nums = [b.body_number for b in mb_result.bodies]
            eq_solids = [b.equilibrium_solids_wt_pct for b in mb_result.bodies]
            liquor_in_solids = [b.liquor_solids_in_wt_pct for b in mb_result.bodies]
            temperatures = [b.temperature_c for b in mb_result.bodies]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=body_nums, y=temperatures, mode="lines+markers", name="Body temp (°C)"))
            fig.add_trace(go.Scatter(x=body_nums, y=eq_solids, mode="lines+markers", name="Eq. solubility (wt%)"))
            fig.add_trace(go.Scatter(x=body_nums, y=liquor_in_solids, mode="lines+markers", name="Liquor in solids (wt%)"))
            fig.update_layout(
                title="Multi-body crystallizer temperature and solubility profile",
                xaxis_title="Body number",
                xaxis=dict(tickmode="linear", dtick=1),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Cumulative crystals bar chart
            crystals = [b.crystals_produced_kg_h for b in mb_result.bodies]
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=body_nums, y=crystals, name="Crystals per body (kg/h)"))
            fig2.update_layout(
                title="Crystals produced per body",
                xaxis_title="Body number",
                yaxis_title=f"Crystals ({mb_output_flow_unit})",
                xaxis=dict(tickmode="linear", dtick=1),
            )
            st.plotly_chart(fig2, use_container_width=True)

            _show_notes(mb_result.notes)
            for b in mb_result.bodies:
                if b.notes:
                    with st.expander(f"Body {b.body_number} notes"):
                        _show_notes(b.notes)
        except ValueError as exc:
            st.error(str(exc))
        _remember_case("crystallizers-multi-body", {
            "feed_rate": mb_feed_rate,
            "feed_rate_unit": mb_feed_rate_unit,
            "feed_solids": mb_feed_solids,
            "n_bodies": mb_n_bodies,
            "body_temps": mb_body_temps,
            "working_volume": mb_working_volume,
            "include_secondary": mb_sec,
        }, mb_result_payload)



def render_solubility_curve() -> None:
    st.header("Citric Acid Solubility Curve & Yield Planner")
    st.caption("Interactive solubility curve with polynomial fit, yield prediction across a cooling temperature sweep, and metastable zone estimation for crystallizer operating parameter planning.")

    tabs = st.tabs(["Solubility Curve", "Yield Sweep Planner", "Metastable Zone"])

    with tabs[0]:
        st.subheader("Solubility Curve Viewer")
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        sol_temp_unit = c1.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="sol_temp_unit")
        _lo = c_to_temperature(-10.0, sol_temp_unit)
        _hi80 = c_to_temperature(80.0, sol_temp_unit)
        _hi120 = c_to_temperature(120.0, sol_temp_unit)
        _lo30 = c_to_temperature(30.0, sol_temp_unit)
        temp_min = c2.number_input(f"Min temp (°{sol_temp_unit})", min_value=_lo, max_value=_hi80, value=c_to_temperature(0.0, sol_temp_unit), key="sol_temp_min")
        temp_max = c3.number_input(f"Max temp (°{sol_temp_unit})", min_value=_lo30, max_value=_hi120, value=c_to_temperature(100.0, sol_temp_unit), key="sol_temp_max")
        num_pts = c4.slider("Number of curve points", min_value=10, max_value=200, value=50, key="sol_num_pts")

        d1, d2 = st.columns(2)
        fit_degree = d1.selectbox("Polynomial degree", [2, 3, 4, 5], index=2, key="sol_deg")
        y_unit = d2.selectbox("Y-axis unit", ["wt% solids", "g/100g water"], index=0, key="sol_yunit")

        temp_min_c = temperature_to_c(temp_min, sol_temp_unit)
        temp_max_c = temperature_to_c(temp_max, sol_temp_unit)
        fit = fit_solubility_polynomial(degree=fit_degree)
        curve = generate_solubility_curve(temp_min=temp_min_c, temp_max=temp_max_c, num_points=num_pts, use_polynomial=True, include_raw_data=True)

        col_r1, col_r2 = st.columns([1, 1])
        col_r1.metric(f"Polynomial fit (degree {fit_degree})", f"R\u00b2 = {fit.r_squared:.6f}")
        col_r2.metric(f"Fitting accuracy", f"Max error: {fit.max_error_wt_pct:.4f} wt%", help=f"Mean error: {fit.mean_error_wt_pct:.4f} wt%")

        disp_temps = [c_to_temperature(t, sol_temp_unit) for t in curve["temperatures"]]
        raw_disp_temps = [c_to_temperature(p.temperature_c, sol_temp_unit) for p in solubility_table_points()]
        fig = go.Figure()
        if y_unit == "wt% solids":
            fig.add_trace(go.Scatter(x=disp_temps, y=curve["solubility_wt_pct"],
                                     mode="lines", name=f"Degree {fit_degree} fit", line=dict(color="blue", width=2)))
            fig.add_trace(go.Scatter(x=raw_disp_temps,
                                     y=[p.solubility_wt_pct for p in solubility_table_points()],
                                     mode="markers", name="Published data",
                                     marker=dict(color="red", size=8, symbol="x")))
            y_label = "Citric acid solubility (wt%)"
        else:
            fig.add_trace(go.Scatter(x=disp_temps, y=curve["solubility_g_per_100g"],
                                     mode="lines", name=f"Degree {fit_degree} fit", line=dict(color="blue", width=2)))
            fig.add_trace(go.Scatter(x=raw_disp_temps,
                                     y=[p.solubility_g_per_100g_water for p in solubility_table_points()],
                                     mode="markers", name="Published data",
                                     marker=dict(color="red", size=8, symbol="x")))
            y_label = "Citric acid solubility (g/100g water)"

        fig.update_layout(
            xaxis_title=f"Temperature (°{sol_temp_unit})",
            yaxis_title=y_label,
            hovermode="x unified",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Published data from citric acid solubility tables, converted to wt% basis.")

    with tabs[1]:
        st.subheader("Cooling Crystallizer Yield Sweep")
        st.caption("Sweep crystallizer yield across a temperature range to find optimal operating parameters.")

        p1, p2, p3, p4, p5 = st.columns([1, 1, 1, 1, 1])
        feed_solids = p1.number_input("Feed solids (wt%)", min_value=1.0, max_value=85.0, value=60.0, key="ys_feed_solids")
        ys_temp_unit = p2.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="ys_temp_unit")
        _ys_lo = c_to_temperature(0.0, ys_temp_unit)
        _ys_hi100 = c_to_temperature(100.0, ys_temp_unit)
        _ys_hi80 = c_to_temperature(80.0, ys_temp_unit)
        feed_temp = p3.number_input(f"Feed temp (°{ys_temp_unit})", min_value=c_to_temperature(10.0, ys_temp_unit), max_value=_ys_hi100, value=c_to_temperature(70.0, ys_temp_unit), key="ys_feed_temp")
        feed_rate = p4.number_input("Feed rate", min_value=100.0, value=10000.0, step=100.0, key="ys_feed_rate")
        ys_flow_unit = p5.selectbox("Feed flow unit", MASS_FLOW_UNITS, index=0, key="ys_flow_unit")

        q1, q2, q3, q4 = st.columns(4)
        sweep_start = q1.number_input(f"Sweep start (°{ys_temp_unit})", min_value=_ys_lo, max_value=_ys_hi100, value=c_to_temperature(70.0, ys_temp_unit), key="ys_start")
        sweep_end = q2.number_input(f"Sweep end (°{ys_temp_unit})", min_value=_ys_lo, max_value=_ys_hi80, value=c_to_temperature(20.0, ys_temp_unit), key="ys_end")
        meta_offset = q3.number_input("Metastable zone width (wt%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5, key="ys_meta")
        num_sweep_pts = q4.slider("Sweep points", min_value=5, max_value=50, value=20, key="ys_num_pts")

        flow_out_unit = st.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="ys_flow_out")

        feed_temp_c = temperature_to_c(feed_temp, ys_temp_unit)
        feed_rate_kg_h = mass_flow_to_kg_h(feed_rate, ys_flow_unit)
        sweep_start_c = temperature_to_c(sweep_start, ys_temp_unit)
        sweep_end_c = temperature_to_c(sweep_end, ys_temp_unit)

        if sweep_end >= sweep_start:
            st.warning("Sweep end temperature must be below start temperature for a cooling crystallizer.")
        else:
            try:
                sweep_result = predict_crystallizer_yield_sweep(
                    feed_solids_wt_pct=feed_solids,
                    feed_temperature_c=feed_temp_c,
                    sweep_start_c=sweep_start_c,
                    sweep_end_c=sweep_end_c,
                    feed_rate_kg_h=feed_rate_kg_h,
                    use_polynomial=True,
                    metastable_offset_wt_pct=meta_offset,
                    num_points=num_sweep_pts,
                )

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Max theoretical yield", f"{sweep_result.max_yield_fraction * 100:.1f}%")
                m2.metric("at temperature", f"{c_to_temperature(sweep_result.optimal_temperature_c, ys_temp_unit):.1f} °{ys_temp_unit}")
                optimal_crystals = sweep_result.points[-1]["crystals_kg_h"] if sweep_result.points else 0
                m3.metric("Crystals at optimal",
                          f"{kg_h_to_mass_flow(optimal_crystals, flow_out_unit):,.0f} {flow_out_unit}")
                m4.metric("Feed solids", f"{feed_solids:.1f} wt%")

                sweep_df = pd.DataFrame(sweep_result.points)
                sweep_df["temperature_disp"] = sweep_df["temperature_c"].apply(lambda t: c_to_temperature(t, ys_temp_unit))
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=sweep_df["temperature_disp"], y=sweep_df["yield_pct"],
                                         mode="lines+markers", name="Yield %", line=dict(color="green", width=2),
                                         marker=dict(size=6)))
                fig.add_trace(go.Scatter(x=sweep_df["temperature_disp"], y=sweep_df["crystals_kg_h"],
                                         mode="lines", name=f"Crystals ({flow_out_unit})",
                                         line=dict(color="blue", dash="dash"), yaxis="y2"))
                fig.update_layout(
                    title="Crystallizer yield vs. operating temperature",
                    xaxis_title=f"Temperature (°{ys_temp_unit})",
                    yaxis=dict(title="Yield (%)", side="left"),
                    yaxis2=dict(title=f"Crystals ({flow_out_unit})", side="right", overlaying="y"),
                    hovermode="x unified",
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                )
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Yield sweep table")
                st.dataframe(sweep_df, use_container_width=True)
                _show_notes(sweep_result.notes)
            except ValueError as exc:
                st.error(str(exc))

    with tabs[2]:
        st.subheader("Metastable Zone Estimator")
        st.caption("Estimate the metastable zone boundaries for crystallizer operation planning.")

        mz1, mz2, mz3 = st.columns(3)
        mz_temp_unit = mz1.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="mz_temp_unit")
        meta_temp = mz2.number_input(f"Temperature (°{mz_temp_unit})", min_value=c_to_temperature(0.0, mz_temp_unit), max_value=c_to_temperature(100.0, mz_temp_unit), value=c_to_temperature(40.0, mz_temp_unit), key="mz_temp")
        meta_width = mz3.number_input("Metastable zone width (wt%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5, key="mz_width")

        meta_temp_c = temperature_to_c(meta_temp, mz_temp_unit)
        try:
            meta_result = estimate_metastable_zone(meta_temp_c, metastable_width_wt_pct=meta_width)

            r1, r2, r3 = st.columns(3)
            r1.metric("Equilibrium solubility", f"{meta_result.equilibrium_solids_wt_pct:.2f} wt%")
            r2.metric("Metastable zone", f"{meta_result.lower_metastable_limit_wt_pct:.2f} to {meta_result.upper_metastable_limit_wt_pct:.2f} wt%")
            r3.metric("Labile zone starts at", f"{meta_result.labile_zone_start_wt_pct:.2f} wt%")

            low = meta_result.lower_metastable_limit_wt_pct
            eq = meta_result.equilibrium_solids_wt_pct
            upper = meta_result.upper_metastable_limit_wt_pct
            labile = meta_result.labile_zone_start_wt_pct

            fig = go.Figure()
            fig.add_hrect(y0=0, y1=low, fillcolor="lightblue", opacity=0.3)
            fig.add_hrect(y0=low, y1=upper, fillcolor="lightyellow", opacity=0.3)
            fig.add_hline(y=eq, line_dash="dash", line_color="green",
                          annotation_text=f"Equilibrium ({eq:.2f} wt%)", annotation_position="top right")
            fig.add_hline(y=labile, line_dash="dot", line_color="red",
                          annotation_text=f"Labile ({labile:.2f} wt%)", annotation_position="bottom right")
            fig.update_layout(
                title=f"Metastable zone diagram at {meta_temp:.1f} °{mz_temp_unit} (width = {meta_width} wt%)",
                yaxis_title="Solids wt%",
                yaxis_range=[0, max(labile + 10, 100)],
            )
            st.plotly_chart(fig, use_container_width=True)
            _show_notes(meta_result.notes)
        except ValueError as exc:
            st.error(str(exc))



def render_heat_exchangers() -> None:
    st.header("Heat Exchangers")
    st.caption("LMTD screening, F-factor correction, and UA-based area sizing for shell-and-tube heat exchangers.  Use these results for quick plant checks — not for TEMA or mechanical design.")

    tabs = st.tabs(["LMTD & Area Sizing", "LMTD Checker", "F-Factor Explorer", "Pass Arrangement Compare"])

    with tabs[0]:
        st.caption("Enter terminal temperatures, duty, and a screening U to estimate required heat exchanger area.")
        c1, c2, c3, c4 = st.columns(4)
        thot_in = c1.number_input("Hot-side inlet", value=95.0, key="hx_thot_in")
        thot_out = c2.number_input("Hot-side outlet", value=45.0, key="hx_thot_out")
        tcold_in = c3.number_input("Cold-side inlet", value=25.0, key="hx_tcold_in")
        tcold_out = c4.number_input("Cold-side outlet", value=55.0, key="hx_tcold_out")
        d1, d2, d3, d4 = st.columns(4)
        duty_kw = d1.number_input("Heat duty", min_value=0.1, value=500.0, key="hx_duty")
        duty_unit = d2.selectbox("Duty unit", POWER_UNITS, index=0, key="hx_duty_unit")
        assumed_u = d3.number_input("Assumed overall U", min_value=50.0, value=800.0, key="hx_u")
        u_unit = d4.selectbox("U unit", HTC_UNITS, index=0, key="hx_u_unit")
        e1, e2, e3, e4, e5 = st.columns(5)
        sp = int(e1.number_input("Shell passes", min_value=1, max_value=6, value=1, step=1, key="hx_sp"))
        tp = int(e2.number_input("Tube passes", min_value=1, max_value=12, value=2, step=1, key="hx_tp"))
        inst_area = e3.number_input("Installed area (optional)", min_value=0.0, value=0.0, key="hx_inst_area")
        temp_unit = e4.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="hx_temp_unit")
        area_unit = e5.selectbox("Area unit", AREA_UNITS, index=0, key="hx_area_unit")

        try:
            t_hi = temperature_to_c(thot_in, temp_unit)
            t_ho = temperature_to_c(thot_out, temp_unit)
            t_ci = temperature_to_c(tcold_in, temp_unit)
            t_co = temperature_to_c(tcold_out, temp_unit)
            duty_canonical = power_to_kw(duty_kw, duty_unit)
            u_canonical = htc_to_w_m2k(assumed_u, u_unit)
            inst_m2 = area_to_m2(inst_area, area_unit) if inst_area > 0 else None
            sizing = size_heat_exchanger(t_hi, t_ho, t_ci, t_co, duty_canonical, u_canonical, sp, tp, inst_m2)
            lmtd_c = sizing.lmtd_c
            area_disp = m2_to_area(sizing.required_area_m2, area_unit)
            inst_disp = m2_to_area(inst_m2, area_unit) if inst_m2 else 0.0
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("LMTD", f"{lmtd_c:.2f} °C")
            m2.metric("F-factor", f"{sizing.f_factor:.4f}")
            m3.metric("Corrected LMTD", f"{sizing.corrected_lmtd_c:.2f} °C")
            m4.metric("Required area", f"{area_disp:.1f} {area_unit}")
            if inst_m2:
                util = sizing.area_utilization_fraction
                n1, n2 = st.columns(2)
                n1.metric("Installed area", f"{inst_disp:.1f} {area_unit}")
                n2.metric("Area utilization", f"{util*100:.1f}%" if util else "N/A")
                if sizing.required_u_w_m2k > 0:
                    st.metric(f"Required U if using all installed area", f"{w_m2k_to_htc(sizing.required_u_w_m2k, u_unit):,.0f} {u_unit}")
            _show_notes(sizing.notes)
            _remember_case("heat-exchangers-sizing", {
                "thot_in": thot_in, "thot_out": thot_out,
                "tcold_in": tcold_in, "tcold_out": tcold_out,
                "duty": duty_kw, "duty_unit": duty_unit,
                "assumed_u": assumed_u, "u_unit": u_unit,
                "shell_passes": sp, "tube_passes": tp,
                "installed_area": inst_area, "area_unit": area_unit,
            }, {k: v for k, v in sizing.__dict__.items() if k != "notes"})
        except ValueError as exc:
            st.error(str(exc))

    with tabs[1]:
        st.caption("Compute LMTD from any four terminal temperatures. Optionally compute the F-factor for a multi-pass arrangement.")
        l1, l2, l3, l4, l_tu = st.columns(5)
        lt_hi = l1.number_input("Hot inlet", value=95.0, key="lx_hi")
        lt_ho = l2.number_input("Hot outlet", value=45.0, key="lx_ho")
        lt_ci = l3.number_input("Cold inlet", value=25.0, key="lx_ci")
        lt_co = l4.number_input("Cold outlet", value=55.0, key="lx_co")
        lx_temp_unit = l_tu.selectbox("Temp unit", TEMPERATURE_UNITS, index=0, key="lx_temp_unit")
        l5, l6 = st.columns(2)
        l_flow = l5.selectbox("Flow arrangement", ["counter", "co-current"], index=0, key="lx_flow")
        l_sp = int(l6.number_input("Shell passes (0 = skip F-factor)", min_value=0, max_value=6, value=0, step=1, key="lx_sp"))

        lt_hi_c = temperature_to_c(lt_hi, lx_temp_unit)
        lt_ho_c = temperature_to_c(lt_ho, lx_temp_unit)
        lt_ci_c = temperature_to_c(lt_ci, lx_temp_unit)
        lt_co_c = temperature_to_c(lt_co, lx_temp_unit)
        lmtd = calculate_lmtd(lt_hi_c, lt_ho_c, lt_ci_c, lt_co_c, l_flow)
        _dt_scale = 1.8 if lx_temp_unit == "F" else 1.0
        col1, col2 = st.columns(2)
        col1.metric("ΔT₁", f"{lmtd.dt1 * _dt_scale:.2f} °{lx_temp_unit}")
        col2.metric("ΔT₂", f"{lmtd.dt2 * _dt_scale:.2f} °{lx_temp_unit}")
        st.metric("LMTD", f"{lmtd.lmtd * _dt_scale:.2f} °{lx_temp_unit}")
        if lmtd.cross_warn:
            st.warning("Temperature cross — LMTD is undefined in this single-pass arrangement.")
        if lmtd.approach_warn:
            st.warning("Very small approach — expect large area requirement.")
        _show_notes(lmtd.notes)

        if l_sp > 0 and lmtd.lmtd > 0:
            dt_max = lt_hi - lt_ci if lt_hi > lt_ci else lt_ci - lt_hi
            if dt_max > 0 and abs(lt_co - lt_ci) > 1e-9:
                p_val = (lt_co - lt_ci) / dt_max
                r_val = (lt_hi - lt_ho) / (lt_co - lt_ci)
                f = calculate_f_factor(p_val, r_val, l_sp, l_sp * 2)
                st.metric("F-factor", f"{f.f_factor:.4f}")
                st.metric("Corrected LMTD (F · LMTD)", f"{lmtd.lmtd * _dt_scale * f.f_factor:.2f} °{lx_temp_unit}")
                if f.f_low_warn:
                    st.warning("F-factor below 0.75 — this pass arrangement is not recommended; consider adding shell passes.")
                f1, f2 = st.columns(2)
                f1.metric("P (effectiveness)", f"{f.p:.4f}")
                f2.metric("R (capacity ratio)", f"{f.r:.4f}")
                _show_notes(f.notes)
            else:
                st.info("Cannot compute F-factor with current temperatures — check for zero temperature ranges.")

        _remember_case("heat-exchangers-lmtd", {
            "thot_in": lt_hi, "thot_out": lt_ho, "tcold_in": lt_ci, "tcold_out": lt_co,
            "flow": l_flow, "shell_passes": l_sp,
        }, {"lmtd": lmtd.lmtd, "dt1": lmtd.dt1, "dt2": lmtd.dt2, "cross_warn": lmtd.cross_warn})

    with tabs[2]:
        st.caption("Explore how F-factor changes with P (temperature effectiveness) and R (heat capacity ratio) for different pass arrangements.")
        f1, f2, f3 = st.columns(3)
        fp = f1.slider("P (0–1)", min_value=0.01, max_value=0.99, value=0.40, step=0.01, key="xf_p")
        fr = f2.slider("R", min_value=0.1, max_value=5.0, value=1.5, step=0.1, key="xf_r")
        fsp = int(f3.number_input("Shell passes", min_value=1, max_value=4, value=1, step=1, key="xf_sp"))

        f_res = calculate_f_factor(fp, fr, fsp, fsp * 2)
        st.metric(f"F-factor ({fsp}-{fsp*2})", f"{f_res.f_factor:.4f}")
        if f_res.f_low_warn:
            st.warning("F < 0.75 — this arrangement is generally not recommended.")
        else:
            st.success("F-factor is in the acceptable range.")
        f1, f2 = st.columns(2)
        f1.metric("P (effectiveness)", f"{f_res.p:.4f}")
        f2.metric("R (capacity ratio)", f"{f_res.r:.4f}")
        _show_notes(f_res.notes)

    with tabs[3]:
        st.caption("Compare 1-2, 2-4, and 3-6 pass arrangements for a given duty to see the trade-off in F-factor and area.")
        p1, p2, p3, p4, p5 = st.columns(5)
        pt_hi = p1.number_input("Hot inlet", value=95.0, key="xp_hi")
        pt_ho = p2.number_input("Hot outlet", value=45.0, key="xp_ho")
        pt_ci = p3.number_input("Cold inlet", value=25.0, key="xp_ci")
        pt_co = p4.number_input("Cold outlet", value=55.0, key="xp_co")
        xp_temp_unit = p5.selectbox("Temp unit", TEMPERATURE_UNITS, index=0, key="xp_temp_unit")
        q1, q2, q3, q4 = st.columns(4)
        q_duty = q1.number_input("Duty", min_value=0.1, value=500.0, key="xp_duty")
        xp_duty_unit = q2.selectbox("Duty unit", POWER_UNITS, index=0, key="xp_duty_unit")
        q_u = q3.number_input("U", min_value=50.0, value=800.0, key="xp_u")
        xp_u_unit = q4.selectbox("U unit", HTC_UNITS, index=0, key="xp_u_unit")

        try:
            xp_hi_c = temperature_to_c(pt_hi, xp_temp_unit)
            xp_ho_c = temperature_to_c(pt_ho, xp_temp_unit)
            xp_ci_c = temperature_to_c(pt_ci, xp_temp_unit)
            xp_co_c = temperature_to_c(pt_co, xp_temp_unit)
            xp_duty_kw = power_to_kw(q_duty, xp_duty_unit)
            xp_u_wm2k = htc_to_w_m2k(q_u, xp_u_unit)
            comparisons = compare_pass_arrangements(xp_hi_c, xp_ho_c, xp_ci_c, xp_co_c, xp_duty_kw, xp_u_wm2k)
            xp_dt_scale = 1.8 if xp_temp_unit == "F" else 1.0
            rows = []
            for c in comparisons:
                rows.append({
                    "Arrangement": f"{c.shell_passes}-{c.tube_passes}",
                    "F-factor": f"{c.f_factor:.4f}",
                    f"Corrected LMTD (°{xp_temp_unit})": f"{c.corrected_lmtd_c * xp_dt_scale:.2f}",
                    f"Required area (m²)": f"{c.required_area_m2:.1f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            for c in comparisons:
                with st.expander(f"{c.shell_passes}-{c.tube_passes} notes"):
                    _show_notes(c.notes)
        except ValueError as exc:
            st.error(str(exc))


def render_motors_drives() -> None:
    st.header("Motors & Drives")
    st.caption("Motor sizing, pump motor power screening, VFD savings estimates, and motor loading health checks.")

    tabs = st.tabs(["Motor Sizing", "Pump Motor Power", "VFD Savings", "Motor Loading Check"])

    with tabs[0]:
        st.caption("Select a standard motor frame size from a shaft power requirement.")
        m1, m2, m3, m4, m5 = st.columns(5)
        shaft_kw = m1.number_input("Shaft power", min_value=0.1, value=22.0, key="ms_shaft")
        ms_power_unit = m2.selectbox("Power unit", POWER_UNITS, index=0, key="ms_power_unit")
        load_pct = m3.number_input("Expected load (%)", min_value=10.0, max_value=100.0, value=80.0, key="ms_load")
        sf = m4.number_input("Service factor", min_value=1.0, max_value=1.5, value=1.15, step=0.05, key="ms_sf")
        voltage = m5.number_input("Motor voltage (V)", min_value=200.0, value=480.0, step=10.0, key="ms_voltage")
        s1, s2 = st.columns(2)
        standard = s1.selectbox("Motor standard", ["IEC", "NEMA"], index=0, key="ms_standard")
        std_lower = standard.lower()
        try:
            result = calculate_motor_size(power_to_kw(shaft_kw, ms_power_unit), load_pct, sf, voltage, std_lower)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Recommended motor", f"{kw_to_power(result.next_standard_motor_kw, ms_power_unit):.1f} {ms_power_unit}")
            c2.metric("Motor loading", f"{result.loading_pct:.1f}%")
            c3.metric("Electrical input", f"{kw_to_power(result.electrical_input_kw, ms_power_unit):.1f} {ms_power_unit}")
            c4.metric("Estimated eff.", f"{result.motor_efficiency_pct:.1f}%")
            e1, e2, e3 = st.columns(3)
            e1.metric("Power factor", f"{result.pf:.3f}")
            e2.metric("Apparent power", f"{result.apparent_power_kva:.1f} kVA")
            e3.metric("FLA (3-phase)", f"{result.full_load_current_3ph:.1f} A")
            _show_notes(result.notes)
            _remember_case("motor-sizing", {
                "shaft_kw": shaft_kw, "load_pct": load_pct,
                "service_factor": sf, "voltage": voltage, "standard": standard,
            }, {k: v for k, v in result.__dict__.items() if k != "notes"})
        except ValueError as exc:
            st.error(str(exc))

    with tabs[1]:
        st.caption("Estimate motor power from pump flow, head, and efficiency.")
        p1, p2, p3, p4, p5, p6 = st.columns(6)
        flow = p1.number_input("Flow", min_value=0.01, value=50.0, key="pm_flow")
        pm_flow_unit = p2.selectbox("Flow unit", VOLUMETRIC_FLOW_UNITS, index=0, key="pm_flow_unit")
        head = p3.number_input("Head", min_value=0.1, value=30.0, key="pm_head")
        pm_head_unit = p4.selectbox("Head unit", LENGTH_UNITS, index=0, key="pm_head_unit")
        sg = p5.number_input("Specific gravity", min_value=0.5, max_value=2.0, value=1.0, step=0.05, key="pm_sg")
        pump_eff = p6.number_input("Pump eff. (%)", min_value=30.0, max_value=95.0, value=75.0, key="pm_eff")
        motor_eff_input = st.number_input("Motor efficiency (%) — leave 0 to auto-estimate", min_value=0.0, max_value=100.0, value=0.0, key="pm_motor_eff")
        motor_eff_val = motor_eff_input if motor_eff_input > 0 else None
        try:
            result = calculate_pump_motor(volumetric_flow_to_m3_h(flow, pm_flow_unit), length_to_m(head, pm_head_unit), sg, pump_eff, motor_eff_val)
            c1, c2, c3 = st.columns(3)
            c1.metric("Hydraulic power", f"{result.hydraulic_kw:.1f} kW")
            c2.metric("Shaft power", f"{result.shaft_power_kw:.1f} kW")
            c3.metric("Electrical input", f"{result.electrical_input_kw:.1f} kW")
            _show_notes(result.notes)
            _remember_case("pump-motor", {"flow": flow, "head": head, "sg": sg, "pump_eff": pump_eff, "motor_eff": motor_eff_val}, {k: v for k, v in result.__dict__.items() if k != "notes"})
        except ValueError as exc:
            st.error(str(exc))

    with tabs[2]:
        st.caption("Estimate kWh and cost savings when replacing throttle/bypass control with a VFD at reduced speed.")
        v1, v2, v3, v4, v5 = st.columns(5)
        rated_kw = v1.number_input("Motor rated power", min_value=0.1, value=37.0, key="vfd_rated")
        vfd_power_unit = v2.selectbox("Power unit", POWER_UNITS, index=0, key="vfd_power_unit")
        speed_pct = v3.number_input("Operating speed (%)", min_value=20.0, max_value=100.0, value=70.0, key="vfd_speed")
        ctrl_method = v4.selectbox("Current control method", ["Throttle", "Bypass", "Generic"], index=0, key="vfd_ctrl")
        annual_hrs = v5.number_input("Annual hours", min_value=100.0, max_value=8760.0, value=8000.0, key="vfd_hrs")
        v5, v6 = st.columns(2)
        elec_rate = v5.number_input("Electricity rate ($/kWh)", min_value=0.01, value=0.10, step=0.01, key="vfd_rate")
        drive_eff = v6.number_input("Drive+motor combined efficiency", min_value=0.7, max_value=0.99, value=0.87, step=0.01, key="vfd_drive_eff")

        try:
            result = estimate_vfd_savings(
                power_to_kw(rated_kw, vfd_power_unit), speed_pct, ctrl_method.lower().replace(" ", "_"), annual_hrs, elec_rate
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VFD input at speed", f"{kw_to_power(result.estimated_vfd_input_kw, vfd_power_unit):.1f} {vfd_power_unit}")
            c2.metric(f"Current input ({result.current_control_method})", f"{kw_to_power(result.current_input_kw, vfd_power_unit):.1f} {vfd_power_unit}")
            c3.metric("Savings", f"{kw_to_power(result.estimated_savings_kw, vfd_power_unit):.1f} {vfd_power_unit}")
            c4.metric("Annual savings", f"{result.estimated_annual_savings_kwh:,.0f} kWh")
            s1, s2, s3 = st.columns(3)
            s1.metric("Annual cost savings", f"${result.estimated_annual_cost_savings:,.2f}")
            if result.payback_months:
                s2.metric("Est. payback", f"{result.payback_months:.1f} months")
            else:
                s2.metric("Est. payback", "N/A")
            s3.metric("Speed", f"{result.rated_speed_pct:.0f}%")
            _show_notes(result.notes)
            _remember_case("vfd-savings", {"rated_kw": rated_kw, "speed_pct": speed_pct, "ctrl": ctrl_method, "annual_hrs": annual_hrs, "elec_rate": elec_rate}, {k: v for k, v in result.__dict__.items() if k != "notes"})
        except ValueError as exc:
            st.error(str(exc))

    with tabs[3]:
        st.caption("Quick motor loading health check from nameplate rating and measured electrical input.")
        h1, h2, h3, h4, h5 = st.columns(5)
        motor_rated = h1.number_input("Motor nameplate", min_value=0.1, value=37.0, key="mh_rated")
        mh_power_unit = h2.selectbox("Power unit", POWER_UNITS, index=0, key="mh_power_unit")
        measured = h3.number_input("Measured input", min_value=0.0, value=30.0, key="mh_measured")
        mot_eff = h4.number_input("Motor eff. (%)", min_value=50.0, max_value=99.0, value=90.0, key="mh_eff")
        elec_rate = h5.number_input("Elec rate ($/kWh)", min_value=0.01, value=0.10, step=0.01, key="mh_rate")
        ahrs = st.number_input("Annual operating hours", min_value=100.0, max_value=8760.0, value=8000.0, key="mh_hrs")
        try:
            result = assess_motor_loading(power_to_kw(motor_rated, mh_power_unit), power_to_kw(measured, mh_power_unit), mot_eff, elec_rate, ahrs)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Motor nameplate", f"{kw_to_power(result.motor_rated_kw, mh_power_unit):.1f} {mh_power_unit}")
            c2.metric("Measured input", f"{kw_to_power(result.measured_input_kw, mh_power_unit):.1f} {mh_power_unit}")
            c3.metric("Est. shaft power", f"{kw_to_power(result.estimated_shaft_kw, mh_power_unit):.1f} {mh_power_unit}")
            c4.metric("Loading", f"{result.load_factor_pct:.0f}%")
            s1, s2, s3 = st.columns(3)
            status = "OVERLOADED" if result.is_undersized else ("LIGHTLY LOADED" if result.is_oversized else "OK")
            s1.metric("Status", status)
            s2.metric("Annual energy", f"{result.estimated_annual_energy_kwh:,.0f} kWh")
            s3.metric("Annual cost", f"${result.estimated_annual_cost:,.2f}")
            if result.is_undersized:
                st.error("Motor appears overloaded — check for overheating and insulation damage risk.")
            elif result.is_oversized:
                st.warning("Motor is lightly loaded — consider right-sizing or adding a VFD.")
            _show_notes(result.notes)
            _remember_case("motor-loading", {"rated": motor_rated, "measured": measured, "eff": mot_eff, "rate": elec_rate, "hrs": ahrs}, {k: v for k, v in result.__dict__.items() if k != "notes"})
        except ValueError as exc:
            st.error(str(exc))


def render_workbook_import() -> None:
    st.header("Workbook Upload & Inspection")
    uploaded = st.file_uploader("Upload an Excel workbook", type=["xlsx", "xlsm"])
    if not uploaded:
        st.info("Upload a workbook to inspect sheets, header candidates, classifications, and preview-normalized tables.")
        return
    suffix = Path(uploaded.name).suffix or ".xlsx"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(uploaded.getbuffer())
            temp_path = Path(handle.name)
        inspection = inspect_workbook(temp_path)
        normalized = normalize_inspection(inspection)
        st.subheader("Workbook source")
        st.json(inspection.get("source", {}))
        sheets_df = pd.DataFrame(
            [{
                "sheet_name": sheet.get("sheet_name"),
                "max_row": sheet.get("max_row"),
                "max_column": sheet.get("max_column"),
                "hidden": sheet.get("hidden"),
                "freeze_panes": sheet.get("freeze_panes"),
                "formula_cells": sheet.get("formula_cell_count"),
            } for sheet in inspection.get("sheet_previews", [])]
        )
        st.dataframe(sheets_df, use_container_width=True)
        for sheet in inspection.get("sheet_previews", []):
            with st.expander(sheet.get("sheet_name", "Sheet")):
                st.json(sheet)
        if normalized:
            for table in normalized:
                with st.expander(f"{table['sheet_name']} ({table['classification']})"):
                    st.json(table)
        else:
            st.info("No table-shaped normalized data was found in the sampled workbook rows.")
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()



def render_case_manager() -> None:
    st.header("Case Manager")
    latest = st.session_state.get("last_case_payload")
    if latest:
        st.subheader("Latest calculated case")
        st.json(latest)
        default_name = latest.get("page", "case")
    else:
        st.info("Run a calculator page first to populate a case payload, or save a manual JSON case below.")
        default_name = "case"
    with st.form("save_case_form"):
        case_name = st.text_input("Case name", value=default_name)
        description = st.text_input("Description", value="")
        manual_json = st.text_area("Manual JSON payload override (optional)", value=json.dumps(latest, indent=2) if latest else "{}", height=250)
        submitted = st.form_submit_button("Save case")
        if submitted:
            payload = json.loads(manual_json)
            if description:
                payload["description"] = description
            path = CASE_STORE.save(case_name, payload)
            st.success(f"Saved case to {path}")
    cases = CASE_STORE.list_cases()
    if cases:
        selected_name = st.selectbox("Select saved case", [case["name"] for case in cases])
        if selected_name is not None:
            st.json(CASE_STORE.load(str(selected_name)))
    else:
        st.info("No saved cases yet.")


def render_steam_cost_comparison() -> None:
    """Steam cost comparison for current vs proposed utility optimization."""
    st.header("Steam Cost Comparison")
    st.markdown("Compare current steam usage against proposed improvements to estimate annual savings.")
    
    # Current case inputs
    st.subheader("Current Case")
    current_steam_flow = st.number_input(
        "Current steam flow", 
        value=5000.0,
        help="Steam flow rate for current operation"
    )
    current_steam_flow_unit = st.selectbox(
        "Flow unit",
        ["kg/h", "t/h", "lb/h", "ton/h"],
        index=0
    )
    
    # Proposed case inputs
    st.subheader("Proposed Case")
    proposed_steam_flow = st.number_input(
        "Proposed steam flow", 
        value=4500.0,
        help="Steam flow rate after improvements"
    )
    proposed_steam_flow_unit = st.selectbox(
        "Flow unit",
        ["kg/h", "t/h", "lb/h", "ton/h"],
        index=0
    )
    
    # Common inputs
    st.subheader("Cost Parameters")
    steam_cost_value = st.number_input(
        "Steam cost",
        value=10.0,
        help="Cost per unit of steam"
    )
    steam_cost_basis = st.selectbox(
        "Cost basis",
        ["$/kg", "$/1000 kg", "$/lb", "$/1000 lb", "$/t", "$/metric ton"],
        index=0
    )
    operating_hours_per_day = st.number_input(
        "Operating hours per day",
        value=24.0,
        min_value=0.0,
        max_value=24.0,
        help="Hours of operation per day"
    )
    operating_days_per_year = st.number_input(
        "Operating days per year",
        value=365.0,
        min_value=0.0,
        max_value=366.0,
        help="Days of operation per year"
    )
    
    # Calculate button
    if st.button("Calculate Savings"):
        try:
            from engineering_app.core.steam import compare_steam_costs
            
            result = compare_steam_costs(
                current_steam_flow_value=current_steam_flow,
                proposed_steam_flow_value=proposed_steam_flow,
                steam_flow_unit=current_steam_flow_unit,
                steam_cost_value=steam_cost_value,
                steam_cost_basis=steam_cost_basis,
                operating_hours_per_day=operating_hours_per_day,
                operating_days_per_year=operating_days_per_year,
            )
            
            st.subheader("Results")
            
            # Current case summary
            st.markdown("## Current Case")
            st.metric("Hourly Cost", f"${result.current.hourly_cost:.2f}")
            st.metric("Daily Cost", f"${result.current.daily_cost:.2f}")
            st.metric("Annual Cost", f"${result.current.annual_cost:.2f}")
            st.metric("Daily Steam", f"{result.current.daily_steam_consumption_kg:.0f} kg")
            st.metric("Annual Steam", f"{result.current.annual_steam_consumption_kg:.0f} kg")
            
            # Proposed case summary
            st.markdown("## Proposed Case")
            st.metric("Hourly Cost", f"${result.proposed.hourly_cost:.2f}")
            st.metric("Daily Cost", f"${result.proposed.daily_cost:.2f}")
            st.metric("Annual Cost", f"${result.proposed.annual_cost:.2f}")
            st.metric("Daily Steam", f"{result.proposed.daily_steam_consumption_kg:.0f} kg")
            st.metric("Annual Steam", f"{result.proposed.annual_steam_consumption_kg:.0f} kg")
            
            # Delta summary
            st.markdown("## Savings Summary")
            st.metric("Hourly Savings", f"${result.hourly_cost_savings:.2f}")
            st.metric("Daily Savings", f"${result.daily_cost_delta:.2f}")
            st.metric("Annual Savings", f"${result.annual_cost_savings:.2f}")
            st.metric("Annual Steam Savings", f"{result.annual_steam_savings_kg:.0f} kg")
            
            # Notes
            if result.notes:
                st.markdown("## Notes")
                for note in result.notes:
                    st.info(note)
            
        except Exception as exc:
            st.error(f"Calculation error: {str(exc)}")

PAGES = {
    "Solution BPE": render_solution_bpe,
    "Quick Tools": render_quick_tools,
    "Hydraulics": render_hydraulics,
    "Heat Exchangers": render_heat_exchangers,
    "Steam Jets": render_steam_jets,
    "Steam & Utilities": render_steam,
    "Evaporators": render_evaporators,
    "Crystallizers": render_crystallizers,
    "Solubility Curve": render_solubility_curve,
    "Motors & Drives": render_motors_drives,
    "Workbook Import": render_workbook_import,
    "Steam Cost Comparison": render_steam_cost_comparison,
    "Case Manager": render_case_manager,
}

def main():
    """Main entry point for the Streamlit engineering app."""
    with st.sidebar:
        st.title("Engineering App")
        page = st.radio("Section", list(PAGES.keys()))
        st.caption("Browser shell for plant engineering workflows.")
        
    # Render the selected page
    PAGES[page]()

if __name__ == "__main__":
    main()
