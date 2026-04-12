from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile

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
)
from engineering_app.core.curves import (
    build_curve_library_from_table,
    compare_curves_at_point,
    evaluate_operating_point,
    make_curve_from_xy_rows,
)
from engineering_app.core.evaporators import (
    EvaporatorDesignCalibrationInputs,
    EvaporatorInputs,
    estimate_design_calibrated_evaporation,
    estimate_evaporation,
)
from engineering_app.core.hydraulics import (
    PipeSegment,
    analyze_parallel_branches,
    build_system_curve,
    calculate_hydraulics_with_units,
    calculate_pump_power,
    calculate_segmented_system,
    calculate_vessel_static_head,
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
    build_curve_from_xy_rows as build_pump_curve_from_xy_rows,
    find_curve_system_intersection,
    get_builtin_curve,
    screen_affinity_rerate,
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
    DELTA_TEMPERATURE_UNITS,
    DENSITY_UNITS,
    LENGTH_UNITS,
    MASS_FLOW_UNITS,
    PERCENT_UNITS,
    POWER_UNITS,
    PRESSURE_UNITS,
    TEMPERATURE_UNITS,
    TIME_UNITS,
    VELOCITY_UNITS,
    VISCOSITY_UNITS,
    VOLUME_UNITS,
    VOLUMETRIC_FLOW_UNITS,
    c_to_delta_temperature,
    c_to_temperature,
    cp_to_viscosity,
    kg_h_to_mass_flow,
    kg_m3_to_density,
    kpa_abs_to_pressure,
    kw_to_power,
    m3_h_to_volumetric_flow,
    pressure_to_kpa_abs,
    volumetric_flow_to_m3_h,
    temperature_to_c,
    m3_to_volume,
    m_s_to_velocity,
    m_to_length,
    length_to_m,
    seconds_to_time,
)
from engineering_app.io.normalizers import normalize_inspection
from engineering_app.io.workbook_inspector import inspect_workbook

st.set_page_config(page_title="Engineering App", page_icon="⚙️", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parent
CASE_STORE = CaseStore(PROJECT_ROOT / "data" / "cases")
GENERIC_CURVE_UNITS = MASS_FLOW_UNITS + VOLUMETRIC_FLOW_UNITS + PRESSURE_UNITS + TEMPERATURE_UNITS + POWER_UNITS


def _show_notes(notes: list[str]) -> None:
    for note in notes:
        st.caption(f"- {note}")



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



def _display_percent(value_fraction: float, unit: str) -> float:
    return value_fraction * 100.0 if unit == "%" else value_fraction



def _display_temperature(value_c: float, unit: str) -> float:
    return c_to_temperature(value_c, unit)



def _display_delta_t(value_c: float, unit: str) -> float:
    return c_to_delta_temperature(value_c, unit)



def _render_status_lines(items: list[tuple[str, str]]) -> None:
    for status, text in items:
        if status == "done":
            st.markdown(f"- ~~{text}~~")
        elif status == "active":
            st.markdown(f"- **IN PROGRESS:** {text}")
        else:
            st.markdown(f"- {text}")



def render_dashboard() -> None:
    st.title("Engineering App")
    st.write("Practical plant engineering tools for steam, hydraulics, evaporation, crystallization, solution properties, and workbook inspection.")
    cols = st.columns(6)
    cards = [
        ("Quick tools", "Conversions, flash steam, blending, tank inventory, Brix reconciliation, and utility cost"),
        ("Solution BPE", "Citric, fructose, dextrose, and sucrose BPE screening"),
        ("Hydraulics", "Line sizing, TDH, branches, vessels, valves, pump power, and NPSHa"),
        ("Steam jets", "Curve comparison and operating-point screening"),
        ("Evaporators", "Duty, steam demand, ΔT, and design-calibrated U·A·ΔT capacity screening"),
        ("Crystallizers", "Citric solubility-based mother liquor, crystal vol% slurry, yield, circulation ratio, and residence time"),
    ]
    for col, (title, desc) in zip(cols, cards):
        with col:
            st.metric(title, "Ready")
            st.caption(desc)

    left, right = st.columns(2)
    with left:
        st.subheader("Currently being advanced")
        _render_status_lines([
            ("active", "Steam-jet workbook-driven model-family import and side-by-side comparison"),
            ("active", "Steam jets: add vendor-layout normalization and motive-basis filtering for imported curve families"),
            ("active", "Hydraulics refinement: extend suction/discharge vessel scenarios into broader pump troubleshooting workflows"),
            ("todo", "Evaporators: refine calibrated mode with fouling / non-condensable allowances or body-by-body staging"),
        ])
    with right:
        st.subheader("Recently completed")
        _render_status_lines([
            ("done", "Solution BPE for citric, fructose, dextrose, and sucrose"),
            ("done", "Schedule 10S stainless hydraulics sizing from 1/2 in to 12 in"),
            ("done", "Valve/fitting K-factor counting and TDH breakdown"),
            ("done", "Pump/system curve overlay"),
            ("done", "Hydraulics pump curve library/upload matched against system curves"),
            ("done", "Pump rerate / affinity screening from speed or impeller changes"),
            ("done", "Suction vessel + NPSHa scenario with optional NPSHr margin screening"),
            ("done", "Parallel branch balancing-device Cv/Kv and orifice sizing screen"),
            ("done", "Citric crystallizer slurry basis plus supersaturation / metastable-band screening"),
            ("done", "Parallel branch and vessel/static-head screens"),
            ("done", "Evaporator design-calibrated U·A·ΔT capacity mode"),
            ("done", "Quick utility cost screens plus current-vs-proposed savings deltas for steam and electricity"),
        ])



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
        from engineering_app.core.units import mass_flow_to_kg_h
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

    with tabs[9]:
        st.caption("Estimate direct steam and motor/electric operating cost, then compare current vs proposed cases so troubleshooters can rank leaks, rerates, throttling losses, and optimization opportunities.")
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
            }.get(key, key),
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

    from engineering_app.core.units import density_to_kg_m3, viscosity_to_cp

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
        liquid_temp = n4.number_input("Liquid temperature (°C)", value=35.0, key="hyd_npsh_temp")
        suction_loss = st.number_input("Suction-line loss (head, m)", value=min(max(result.head_loss_m * 0.3, 0.1), 5.0), key="hyd_npsh_loss")
        npsha = estimate_npsha(surface_pressure, surface_pressure_unit, static_head_m, suction_loss, liquid_temp, result.velocity_m_s, density_kg_m3)
        st.metric("NPSHa", f"{npsha.npsha_m:,.2f} m")
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
            liquid_temperature_c=liquid_temp,
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

    with tabs[3]:
        st.caption("Enter up to three sequential piping sections to estimate total system TDH and pressure drop.")
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
            seg_id = s2.number_input("ID (mm)", value=default_id_mm, key=f"seg_id_{idx}")
            seg_len = s3.number_input("Length (m)", value=default_len, key=f"seg_len_{idx}")
            seg_elev = s4.number_input("Elevation change (m)", value=0.0 if idx != 3 else 8.0, key=f"seg_elev_{idx}")
            seg_k = s5.number_input("Total K", value=default_k, key=f"seg_k_{idx}")
            segments.append(PipeSegment(seg_name, seg_id, seg_len, default_rough, seg_elev, seg_k))
        seg_result = calculate_segmented_system(volumetric_flow_to_m3_h(flow_value, flow_unit), density_kg_m3, viscosity_cp, segments)
        st.metric("Segmented system TDH", f"{seg_result.total_dynamic_head_m:,.2f} m")
        st.metric("Segmented system ΔP", f"{seg_result.total_pressure_drop_kpa:,.2f} kPa")
        st.dataframe(pd.DataFrame([asdict(segment) for segment in seg_result.segments]), use_container_width=True)
        _show_notes(seg_result.notes)
    with tabs[4]:
        st.caption("Check whether a parallel network will naturally self-balance or whether the entered split requires throttling/orifice loss to hold the intended branch flows.")
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
            branch_id = b2.number_input("ID (mm)", value=id_mm, key=f"hyd_branch_id_{idx}")
            branch_len = b3.number_input("Length (m)", value=length_m, key=f"hyd_branch_len_{idx}")
            branch_elev = b4.number_input("Elevation change (m)", value=elev_m, key=f"hyd_branch_elev_{idx}")
            branch_k = b5.number_input("Total K", value=k_total, key=f"hyd_branch_k_{idx}")
            branch_split = b6.number_input(
                "Flow split fraction",
                min_value=0.0,
                value=split,
                key=f"hyd_branch_split_{idx}",
                disabled=branch_mode == "self_balancing",
            )
            branches.append(PipeSegment(branch_name, branch_id, branch_len, roughness_mm, branch_elev, branch_k))
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
        st.metric("Branch head spread", f"{branch_result.head_spread_m:,.4f} m")
        if branch_result.common_branch_head_m is not None:
            st.metric("Common balanced head", f"{branch_result.common_branch_head_m:,.3f} m")
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
        head_unit = st.selectbox("Vessel head output unit", LENGTH_UNITS, index=0, key="hyd_vessel_head_out")
        volume_unit = st.selectbox("Vessel volume output unit", VOLUME_UNITS, index=0, key="hyd_vessel_vol_out")
        vessel = calculate_vessel_static_head(
            liquid_height_m=length_to_m(vessel_height, vessel_height_unit),
            vessel_diameter_m=length_to_m(vessel_diameter, vessel_diameter_unit),
            density_kg_m3=density_kg_m3,
            level_fraction=level_fraction,
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Static head", f"{m_to_length(vessel.static_head_m, head_unit):,.2f} {head_unit}")
        m2.metric("Bottom pressure", f"{vessel.bottom_pressure_kpa_g:,.2f} kPag")
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
        other_losses_kpa = c5.number_input("Installed other losses excl. valve (kPa)", min_value=0.0, value=max(result.pressure_drop_kpa, 0.0), key="hyd_cv_other_losses")

        st.markdown("**Cavitation / flashing screen**")
        q1, q2, q3, q4 = st.columns(4)
        inlet_pressure_value = q1.number_input("Valve inlet pressure", min_value=0.01, value=max(pressure_to_kpa_abs(35.0, "psig"), valve_dp_kpa + 50.0), key="hyd_cv_inlet_pressure")
        inlet_pressure_unit = q2.selectbox("Inlet pressure unit", PRESSURE_UNITS, index=0, key="hyd_cv_inlet_pressure_unit")
        liquid_temp_value = q3.number_input("Liquid temperature", value=80.0, key="hyd_cv_liquid_temp")
        liquid_temp_unit = q4.selectbox("Liquid temperature unit", TEMPERATURE_UNITS, index=0, key="hyd_cv_liquid_temp_unit")
        q5, q6 = st.columns(2)
        pressure_recovery_factor_fl = q5.number_input("Valve FL (pressure recovery factor)", min_value=0.10, max_value=1.00, value=0.90, step=0.01, key="hyd_cv_fl")
        q6.caption("Typical screening starting points: globe ~0.9, rotary/high-recovery trims lower. Confirm with the vendor for the actual trim.")
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
        if rated_cv_enabled and valve.opening_fraction_linear is not None and valve.opening_fraction_equal_percentage is not None:
            o1, o2, o3 = st.columns(3)
            o1.metric("Rated Cv loading", f"{valve.required_cv / valve.rated_cv * 100.0:,.1f}%")
            o2.metric("Linear trim opening", f"{valve.opening_fraction_linear * 100.0:,.1f}%")
            o3.metric("Equal-% opening", f"{valve.opening_fraction_equal_percentage * 100.0:,.1f}%")

        cstat1, cstat2, cstat3, cstat4 = st.columns(4)
        cstat1.metric("Outlet pressure", f"{kpa_abs_to_pressure(valve.outlet_pressure_kpa_abs, inlet_pressure_unit):,.2f} {inlet_pressure_unit}" if valve.outlet_pressure_kpa_abs is not None else "n/a")
        cstat2.metric("Vapor pressure", f"{kpa_abs_to_pressure(valve.vapor_pressure_kpa_abs, 'kPa'):,.2f} kPa" if valve.vapor_pressure_kpa_abs is not None else "n/a")
        cstat3.metric("Cavitation index σ", f"{valve.cavitation_index_sigma:,.2f}" if valve.cavitation_index_sigma is not None else "n/a")
        cstat4.metric("Status", (valve.cavitation_status or "n/a").replace("_", " ").title())
        if valve.liquid_critical_pressure_drop_kpa is not None:
            d1, d2 = st.columns(2)
            d1.metric("FL-based critical ΔP", f"{_pressure_delta_from_kpa(valve.liquid_critical_pressure_drop_kpa, valve_dp_unit):,.2f} {valve_dp_unit}")
            d2.metric("Predicted vena-contracta pressure", f"{valve.predicted_vena_contracta_pressure_kpa_abs:,.2f} kPa abs" if valve.predicted_vena_contracta_pressure_kpa_abs is not None else "n/a")
        _show_notes(valve.notes)
        st.json(asdict(valve))

    with tabs[7]:
        st.caption("Overlay a simple pump curve or a library/uploaded pump curve against the estimated system curve to visualize the operating point.")
        curve_tabs = st.tabs(["Simple line", "Library / upload"])
        current_flow_m3_h = volumetric_flow_to_m3_h(flow_value, flow_unit)

        with curve_tabs[0]:
            p1, p2, p3 = st.columns(3)
            shutoff_head = p1.number_input("Pump shutoff head (m)", min_value=0.1, value=max(result.total_dynamic_head_m * 1.6, 20.0), key="hyd_curve_shutoff")
            max_flow_curve = p2.number_input("Pump max flow (m3/h)", min_value=1.0, value=max(current_flow_m3_h * 1.5, 10.0), key="hyd_curve_max_flow")
            head_at_max_flow = p3.number_input("Pump head at max flow (m)", min_value=0.0, value=max(result.total_dynamic_head_m * 0.5, 1.0), key="hyd_curve_head_at_max")
            static_curve_head = st.number_input("System static head (m)", value=max(elevation_change if elevation_change > 0 else 0.0, 0.0), key="hyd_curve_static_head")
            k_factor = max((result.total_dynamic_head_m - static_curve_head) / max(current_flow_m3_h ** 2, 1e-9), 0.0)
            curve_points = build_system_curve(static_curve_head, k_factor, max_flow_curve)
            intersection = find_pump_system_intersection(shutoff_head, head_at_max_flow, max_flow_curve, static_curve_head, k_factor)
            xs = [point.flow_m3_h for point in curve_points]
            system_heads = [point.total_dynamic_head_m for point in curve_points]
            pump_heads = [shutoff_head + (head_at_max_flow - shutoff_head) * (x / max_flow_curve) for x in xs]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xs, y=system_heads, mode="lines", name="System curve"))
            fig.add_trace(go.Scatter(x=xs, y=pump_heads, mode="lines", name="Pump curve"))
            if intersection is not None:
                fig.add_trace(go.Scatter(x=[intersection.flow_m3_h], y=[intersection.total_dynamic_head_m], mode="markers", marker=dict(size=12), name="Estimated operating point"))
                m1, m2 = st.columns(2)
                m1.metric("Estimated operating flow", f"{intersection.flow_m3_h:,.1f} m3/h")
                m2.metric("Estimated operating head", f"{intersection.total_dynamic_head_m:,.2f} m")
            fig.update_layout(title="Pump vs System Curve", xaxis_title="Flow (m3/h)", yaxis_title="Head (m)")
            st.plotly_chart(fig, use_container_width=True)

        with curve_tabs[1]:
            st.caption("Use a built-in pump curve or upload vendor flow-head points from CSV/Excel, then compare that curve against the estimated system curve.")
            static_curve_head = st.number_input("System static head (m)", value=max(elevation_change if elevation_change > 0 else 0.0, 0.0), key="hyd_curve_static_head_adv")
            k_factor = max((result.total_dynamic_head_m - static_curve_head) / max(current_flow_m3_h ** 2, 1e-9), 0.0)
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
                        head_col = st.selectbox("Head column", columns, index=1 if len(columns) > 1 else 0, key="hyd_curve_upload_head_col")
                        curve_name = st.text_input("Curve name", value=Path(uploaded_curve.name).stem, key="hyd_curve_upload_name")
                        curve_family = st.text_input("Curve family / pump tag", value="Uploaded vendor curve", key="hyd_curve_upload_family")
                        selected_curve = build_pump_curve_from_xy_rows(curve_name, uploaded_df.to_dict(orient="records"), flow_col, head_col, family=curve_family)
            else:
                manual_curve = pd.DataFrame([
                    {"flow_m3_h": 0.0, "head_m": max(result.total_dynamic_head_m * 1.7, 25.0)},
                    {"flow_m3_h": max(current_flow_m3_h * 0.5, 10.0), "head_m": max(result.total_dynamic_head_m * 1.2, 15.0)},
                    {"flow_m3_h": max(current_flow_m3_h, 20.0), "head_m": max(result.total_dynamic_head_m * 0.95, 8.0)},
                    {"flow_m3_h": max(current_flow_m3_h * 1.35, 30.0), "head_m": max(result.total_dynamic_head_m * 0.65, 3.0)},
                ])
                edited_curve = st.data_editor(manual_curve, num_rows="dynamic", use_container_width=True, key="hyd_curve_manual_editor")
                curve_name = st.text_input("Curve name", value="Manual pump curve", key="hyd_curve_manual_name")
                curve_family = st.text_input("Curve family / pump tag", value="Manual entry", key="hyd_curve_manual_family")
                selected_curve = build_pump_curve_from_xy_rows(curve_name, edited_curve.to_dict(orient="records"), "flow_m3_h", "head_m", family=curve_family)

            if selected_curve is not None:
                max_curve_flow = selected_curve.points[-1].flow_m3_h
                system_curve_points = build_system_curve(static_curve_head, k_factor, max_curve_flow)
                library_intersection = find_curve_system_intersection(selected_curve, static_curve_head, k_factor)
                curve_df = pd.DataFrame([
                    {"Flow (m3/h)": point.flow_m3_h, "Pump head (m)": point.head_m}
                    for point in selected_curve.points
                ])
                st.dataframe(curve_df, use_container_width=True)
                xs = [point.flow_m3_h for point in system_curve_points]
                system_heads = [point.total_dynamic_head_m for point in system_curve_points]
                pump_xs = [point.flow_m3_h for point in selected_curve.points]
                pump_heads = [point.head_m for point in selected_curve.points]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xs, y=system_heads, mode="lines", name="System curve"))
                fig.add_trace(go.Scatter(x=pump_xs, y=pump_heads, mode="lines+markers", name=selected_curve.name))
                if library_intersection is not None:
                    fig.add_trace(go.Scatter(x=[library_intersection.flow_m3_h], y=[library_intersection.head_m], mode="markers", marker=dict(size=12), name="Estimated operating point"))
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Estimated operating flow", f"{library_intersection.flow_m3_h:,.1f} m3/h")
                    c2.metric("Estimated operating head", f"{library_intersection.head_m:,.2f} m")
                    c3.metric("% of curve max flow", f"{library_intersection.fraction_of_curve_max_flow * 100.0:,.1f}%")
                    if library_intersection.head_error_m > 1.0:
                        st.warning("Pump/system intersection error is still noticeable on the sampled points. Add more curve points for better accuracy.")
                fig.update_layout(title=f"{selected_curve.name} vs System Curve", xaxis_title="Flow (m3/h)", yaxis_title="Head (m)")
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
                    static_head_m=static_curve_head,
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
        family = c4.text_input("Family / motive basis", value="Motive 3.5 barg", key="sj_family")
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
        uploaded_family = st.file_uploader("Upload steam-jet model-family table", type=["csv", "xlsx", "xlsm"], key="sj_family_upload")
        family_df = None
        source_sheet = None
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
            if suffix == ".csv":
                family_df = pd.read_csv(uploaded_family)
                source_sheet = uploaded_family.name
            else:
                workbook = pd.ExcelFile(uploaded_family)
                source_sheet = st.selectbox("Workbook sheet", workbook.sheet_names, key="sj_family_sheet")
                family_df = pd.read_excel(workbook, sheet_name=source_sheet)
            st.dataframe(family_df.head(20), use_container_width=True)

        if family_df is not None and not family_df.empty:
            columns = list(family_df.columns)
            family_options = ["(none)"] + columns
            default_name_index = next((idx for idx, col in enumerate(columns) if str(col).lower() in {"model", "curve", "curve_name", "model_name", "tag", "name"}), 0)
            default_family_index = next((idx + 1 for idx, col in enumerate(columns) if "family" in str(col).lower() or "basis" in str(col).lower()), 0)
            default_x_index = next((idx for idx, col in enumerate(columns) if any(token in str(col).lower() for token in ["load", "suction", "capacity", "flow"])), 0)
            default_y_index = next((idx for idx, col in enumerate(columns) if any(token in str(col).lower() for token in ["steam", "motive", "consumption", "head", "duty"])), min(1, len(columns) - 1))
            c1, c2, c3, c4 = st.columns(4)
            curve_name_col = c1.selectbox("Curve/model name column", columns, index=default_name_index, key="sj_family_curve_name_col")
            family_col = c2.selectbox("Family column", family_options, index=default_family_index, key="sj_family_family_col")
            x_col = c3.selectbox("X column", columns, index=default_x_index, key="sj_family_x_col")
            y_col = c4.selectbox("Y column", columns, index=default_y_index, key="sj_family_y_col")
            family_label = None if family_col == "(none)" else family_col
            library = build_curve_library_from_table(
                family_df.to_dict(orient="records"),
                x_label=x_col,
                y_label=y_col,
                curve_name_label=curve_name_col,
                family_label=family_label,
                source_sheet=source_sheet,
            )
            st.metric("Imported curves", f"{len(library.curves)}")
            if library.curves:
                curve_labels = [f"{curve.name} ({curve.family or 'no family'})" for curve in library.curves]
                selected_labels = st.multiselect("Curves to compare", curve_labels, default=curve_labels[: min(3, len(curve_labels))], key="sj_family_selected")
                selected_curves = [curve for curve in library.curves if f"{curve.name} ({curve.family or 'no family'})" in selected_labels]
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
                            "operating_x": operating_x,
                            "actual_y": actual_y,
                            "selected_curves": [curve.name for curve in selected_curves],
                        },
                        {"comparison_rows": compare_df.to_dict(orient="records")},
                    )
            else:
                st.warning("No valid curves could be built from the selected columns. Check that each model has at least two numeric x/y rows.")

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

    from engineering_app.core.units import delta_temperature_to_c, power_to_kw

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

    c9, c10, c11, c12 = st.columns(4)
    passes = int(c9.number_input("Passes", min_value=1, value=2, step=1, key="ev_passes"))
    recirc = c10.number_input("Recirculation ratio", value=4.0, key="ev_recirc")
    evaporator_product = c11.selectbox(
        "Product / liquor",
        ["citric_acid", "fructose", "dextrose", "sucrose"],
        format_func=lambda key: PRODUCT_PROFILES[key].display_name,
        key="ev_product",
    )
    duty_per_kg = c12.number_input("Specific evaporation duty (kJ/kg)", value=2250.0, key="ev_spec_duty")

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

    tabs = st.tabs(["Target duty", "Design-calibrated mode"])

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
                estimated_specific_evaporation_duty_kj_kg=duty_per_kg,
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
        d1, d2, d3 = st.columns(3)
        overall_u = d1.number_input("Overall U (W/m²·K)", min_value=0.0, value=1800.0, key="ev_cal_u")
        installed_area = d2.number_input("Installed area (m²)", min_value=0.0, value=250.0, key="ev_cal_area")
        availability_pct = d3.number_input("Availability / cleanliness (%)", min_value=0.0, value=85.0, key="ev_cal_availability")

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
                estimated_specific_evaporation_duty_kj_kg=duty_per_kg,
                overall_u_w_m2_k=overall_u,
                installed_area_m2=installed_area,
                availability_factor=availability_pct / 100.0,
            )
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Target evaporation", f"{kg_h_to_mass_flow(calibrated.target_evaporation_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m2.metric("Achievable evaporation", f"{kg_h_to_mass_flow(calibrated.achievable_evaporation_rate_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
        m3.metric("Required duty", f"{kw_to_power(calibrated.required_duty_kw, duty_output_unit):,.1f} {duty_output_unit}")
        m4.metric("Available duty", f"{kw_to_power(calibrated.available_duty_kw, duty_output_unit):,.1f} {duty_output_unit}")

        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Required area", f"{calibrated.required_area_m2:,.1f} m²")
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



def render_crystallizers() -> None:
    st.header("Crystallizers")
    st.caption("For citric acid, slurry can now be based on crystal volume percent while mother liquor is auto-set from temperature-dependent solubility and screened for supersaturation / metastable-band risk.")
    c0, c1, c2, c3 = st.columns(4)
    product = c0.selectbox("Product", ["citric_acid", "generic"], format_func=lambda value: "Citric acid" if value == "citric_acid" else "Generic liquor", key="cr_product")
    feed_rate = c1.number_input("Feed rate", value=12000.0, key="cr_feed_rate")
    feed_rate_unit = c2.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="cr_feed_rate_unit")
    feed_solids = c3.number_input("Feed solids (wt%)", value=55.0, key="cr_feed_solids")

    c4, c5, c6, c7 = st.columns(4)
    basis_mode = c4.radio("Slurry basis", ["Crystal vol%", "Crystal wt%"], horizontal=True, key="cr_basis_mode")
    operating_temp = c5.number_input("Operating temperature", value=45.0, key="cr_temp")
    operating_temp_unit = c6.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="cr_temp_unit")
    circulation = c7.number_input("Circulation rate", value=72000.0, key="cr_circulation")

    c8, c9, c10, c11 = st.columns(4)
    circulation_unit = c8.selectbox("Circulation unit", MASS_FLOW_UNITS, index=0, key="cr_circulation_unit")
    slurry_withdrawal = c9.number_input("Slurry withdrawal rate", min_value=0.0, value=12000.0, key="cr_slurry_withdrawal")
    slurry_withdrawal_unit = c10.selectbox("Slurry withdrawal unit", MASS_FLOW_UNITS, index=0, key="cr_slurry_withdrawal_unit")
    output_flow_unit = c11.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="cr_flow_out")

    c12, c13 = st.columns(2)
    working_volume = c12.number_input("Working volume", value=18.0, key="cr_working_volume")
    working_volume_unit = c13.selectbox("Working volume unit", VOLUME_UNITS, index=0, key="cr_working_volume_unit")

    temp_c = operating_temp if operating_temp_unit == "C" else (operating_temp - 32.0) * 5.0 / 9.0
    auto_mother_liquor_solids = estimate_citric_solubility_wt_pct(temp_c) if product == "citric_acid" else None

    d1, d2, d3, d4 = st.columns(4)
    if basis_mode == "Crystal vol%":
        target_crystal_volume_pct = d1.number_input("Target crystals in slurry (vol%)", value=18.0, key="cr_target_vol_pct")
        slurry_solids = d2.number_input("Displayed slurry crystals (wt%)", value=25.0, key="cr_slurry_solids_display")
    else:
        slurry_solids = d1.number_input("Target slurry crystals (wt%)", value=25.0, key="cr_slurry_solids")
        target_crystal_volume_pct = None
        d2.caption("Weight-percent basis keeps the older quick-screen approach.")
    mother_liquor_solids = d3.number_input(
        "Mother liquor solids (wt%)",
        value=auto_mother_liquor_solids if auto_mother_liquor_solids is not None else 45.0,
        key="cr_mother_solids",
        disabled=product == "citric_acid",
    )
    yield_unit = d4.selectbox("Yield output unit", PERCENT_UNITS, index=0, key="cr_yield_out")

    e1, e2 = st.columns(2)
    crystal_density = e1.number_input("Crystal density (kg/m3)", value=1660.0, key="cr_crystal_density")
    mother_liquor_density = e2.number_input("Mother liquor density (kg/m3)", value=1280.0, key="cr_ml_density")

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
            crystal_density_kg_m3=crystal_density,
            mother_liquor_density_kg_m3=mother_liquor_density,
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
        st.json(CASE_STORE.load(selected_name))
    else:
        st.info("No saved cases yet.")



def render_roadmap() -> None:
    st.header("Roadmap")
    st.caption("Completed lines are struck through. Active items are marked in progress.")

    st.subheader("Completed foundations")
    _render_status_lines([
        ("done", "Fresh engineering_app project scaffolded and placed under Documents/projects"),
        ("done", "Streamlit browser shell established"),
        ("done", "Per-input and per-output unit handling added across engineering pages"),
        ("done", "Workbook upload and inspection workflow added"),
        ("done", "Case manager added"),
        ("done", "Solution BPE tools added for citric, fructose, dextrose, and sucrose"),
        ("done", "Hydraulics core expanded with schedule 10S sizing, valves/fittings, TDH, pump power, NPSHa, segmented systems, control valves, pump/system curve, branch screens, and vessel head tools"),
        ("done", "Hydraulics pump curve library/upload added for system-curve matching"),
        ("done", "Citric crystallizer slurry basis updated to use crystal vol% plus solubility-based mother liquor and supersaturation screening"),
        ("done", "Quick tools expanded with blending, Brix reconciliation, tank inventory, utility cost screens, and current-vs-proposed utility deltas"),
    ])

    st.subheader("Active work")
    _render_status_lines([
        ("active", "Steam jets: import workbook-derived curve families and compare multiple models side-by-side"),
        ("active", "Steam jets: add vendor-layout normalization and motive-basis filtering for imported curve families"),
        ("active", "Hydraulics: extend suction/discharge vessel scenarios into broader pump troubleshooting workflows"),
    ])

    st.subheader("Next queued additions")
    _render_status_lines([
        ("todo", "Solution BPE: refine >60 DS citric estimation with stronger literature-backed correlation"),
        ("todo", "Evaporators: refine calibrated mode with fouling / non-condensable allowances or body-by-body staging"),
        ("done", "Hydraulics: add pump curve affinity / rerate screening from speed or impeller changes"),
        ("done", "Hydraulics: add suction vessel + NPSHa scenario with optional NPSHr margin screening"),
        ("done", "Crystallizers: add metastable-zone and supersaturation screening on top of citric solubility-based slurry"),
        ("done", "Hydraulics: add balancing-valve/orifice coefficient sizing from parallel branch split checks"),
        ("done", "Evaporators: add design-calibrated U·A·ΔT capacity mode for existing bodies"),
        ("done", "Quick tools: add ratio-target blend solving for operator-driven stream targeting"),
    ])

    st.info("The hourly review job is set up to keep pushing this roadmap forward with practical improvements and internet research when useful.")


PAGES = {
    "Dashboard": render_dashboard,
    "Roadmap": render_roadmap,
    "Quick Tools": render_quick_tools,
    "Solution BPE": render_solution_bpe,
    "Hydraulics": render_hydraulics,
    "Steam Jets": render_steam_jets,
    "Steam & Utilities": render_steam,
    "Evaporators": render_evaporators,
    "Crystallizers": render_crystallizers,
    "Workbook Import": render_workbook_import,
    "Case Manager": render_case_manager,
}

with st.sidebar:
    st.title("Engineering App")
    page = st.radio("Section", list(PAGES.keys()))
    st.caption("Browser shell for plant engineering workflows.")

PAGES[page]()
