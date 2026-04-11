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
from engineering_app.core.crystallizers import CrystallizerInputs, estimate_crystallizer
from engineering_app.core.curves import evaluate_operating_point, make_curve_from_xy_rows
from engineering_app.core.evaporators import EvaporatorInputs, estimate_evaporation
from engineering_app.core.hydraulics import (
    PipeSegment,
    build_system_curve,
    calculate_hydraulics_with_units,
    calculate_pump_power,
    calculate_segmented_system,
    compare_schedule_10s_sizes,
    estimate_npsha,
    find_pump_system_intersection,
    fitting_k_from_counts,
    recommend_schedule_10s_size,
    size_control_valve,
)

from engineering_app.core.pipe_data import COMMON_FITTINGS, SCHEDULE_10S_STAINLESS
from engineering_app.core.quicktools import (
    dilution_water,
    flash_fraction,
    pressure_conversion,
    solution_properties,
    steam_for_duty,
    temperature_conversion,
    thermal_point,
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
    m3_to_volume,
    m_s_to_velocity,
    m_to_length,
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



def render_dashboard() -> None:
    st.title("Engineering App")
    st.write("Practical plant engineering tools for steam, hydraulics, evaporation, crystallization, solution properties, and workbook inspection.")
    cols = st.columns(6)
    cards = [
        ("Quick tools", "Conversions, flash steam, and dilution"),
        ("Solution BPE", "Citric, fructose, dextrose, and sucrose BPE screening"),
        ("Hydraulics", "Velocity, pressure drop, TDH, and residence time"),
        ("Steam jets", "Curve comparison and operating-point screening"),
        ("Evaporators", "Duty, steam demand, and ΔT screen"),
        ("Crystallizers", "Yield, slurry rate, circulation ratio, and residence time"),
    ]
    for col, (title, desc) in zip(cols, cards):
        with col:
            st.metric(title, "Ready")
            st.caption(desc)



def render_quick_tools() -> None:
    st.header("Quick Tools")
    tabs = st.tabs(["Pressure", "Temperature", "Thermal Point", "Steam Flash", "Solution Properties", "Dilution"])
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
    tabs = st.tabs(["Single line", "Size comparison", "Pump & NPSHa", "Segmented system", "Control valve", "Pump/System curve"])

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
        suction_loss = st.number_input("Suction-line loss (head, m)", value=max(result.head_loss_m * 0.3, 0.1), key="hyd_npsh_loss")
        npsha = estimate_npsha(surface_pressure, surface_pressure_unit, static_head_m, suction_loss, liquid_temp, result.velocity_m_s, density_kg_m3)
        st.metric("NPSHa", f"{npsha.npsha_m:,.2f} m")
        _show_notes(npsha.notes)
        st.json(asdict(npsha))

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
        st.caption("Screen liquid control-valve sizing from line flow, density, and target valve pressure drop.")
        c1, c2, c3 = st.columns(3)
        valve_dp = c1.number_input("Target valve ΔP", min_value=0.01, value=max(result.pressure_drop_kpa * 0.35, 20.0), key="hyd_cv_dp")
        valve_dp_unit = c2.selectbox("Valve ΔP unit", ("kPa", "psi", "bar"), index=0, key="hyd_cv_dp_unit")
        rated_cv_enabled = c3.checkbox("Compare against rated Cv", value=True, key="hyd_cv_has_rated")
        c4, c5 = st.columns(2)
        rated_cv = c4.number_input("Rated Cv", min_value=0.01, value=90.0, key="hyd_cv_rated", disabled=not rated_cv_enabled)
        other_losses_kpa = c5.number_input("Installed total losses incl. valve (kPa)", min_value=0.01, value=max(result.pressure_drop_kpa + valve_dp, valve_dp), key="hyd_cv_other_losses")
        valve_dp_kpa = valve_dp if valve_dp_unit == "kPa" else (valve_dp / 0.1450377377 if valve_dp_unit == "psi" else valve_dp * 100.0)
        valve = size_control_valve(
            flow_m3_h=volumetric_flow_to_m3_h(flow_value, flow_unit),
            differential_pressure_kpa=valve_dp_kpa,
            density_kg_m3=density_kg_m3,
            installed_pressure_drop_kpa=other_losses_kpa,
            rated_cv=rated_cv if rated_cv_enabled else None,
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
        _show_notes(valve.notes)
        st.json(asdict(valve))

    with tabs[5]:
        st.caption("Overlay a simple pump curve against the estimated system curve to visualize the operating point.")
        p1, p2, p3 = st.columns(3)
        shutoff_head = p1.number_input("Pump shutoff head (m)", min_value=0.1, value=max(result.total_dynamic_head_m * 1.6, 20.0), key="hyd_curve_shutoff")
        max_flow_curve = p2.number_input("Pump max flow (m3/h)", min_value=1.0, value=max(volumetric_flow_to_m3_h(flow_value, flow_unit) * 1.5, 10.0), key="hyd_curve_max_flow")
        head_at_max_flow = p3.number_input("Pump head at max flow (m)", min_value=0.0, value=max(result.total_dynamic_head_m * 0.5, 1.0), key="hyd_curve_head_at_max")
        static_curve_head = st.number_input("System static head (m)", value=max(elevation_change if elevation_change > 0 else 0.0, 0.0), key="hyd_curve_static_head")
        current_flow_m3_h = volumetric_flow_to_m3_h(flow_value, flow_unit)
        k_factor = max((result.total_dynamic_head_m - static_curve_head) / max(current_flow_m3_h ** 2, 1e-9), 0.0)
        curve_points = build_system_curve(static_curve_head, k_factor, max_flow_curve)
        intersection = find_pump_system_intersection(shutoff_head, head_at_max_flow, max_flow_curve, static_curve_head, k_factor)
        import pandas as pd
        import plotly.graph_objects as go
        xs = [point.flow_m3_h for point in curve_points]
        system_heads = [point.total_dynamic_head_m for point in curve_points]
        pump_heads = [shutoff_head + (head_at_max_flow - shutoff_head) * (x / max_flow_curve) for x in xs]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=xs, y=system_heads, mode="lines", name="System curve"))
        fig.add_trace(go.Scatter(x=xs, y=pump_heads, mode="lines", name="Pump curve"))
        if intersection is not None:
            fig.add_trace(go.Scatter(x=[intersection.flow_m3_h], y=[intersection.total_dynamic_head_m], mode="markers", marker=dict(size=12), name="Estimated operating point"))
            st.metric("Estimated operating flow", f"{intersection.flow_m3_h:,.1f} m3/h")
            st.metric("Estimated operating head", f"{intersection.total_dynamic_head_m:,.2f} m")
        fig.update_layout(title="Pump vs System Curve", xaxis_title="Flow (m3/h)", yaxis_title="Head (m)")
        st.plotly_chart(fig, use_container_width=True)

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
    tabs = st.tabs(["Curve check", "Thermo-compressor balance"])

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
    output_flow_unit = st.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="ev_flow_out")
    output_temp_unit = st.selectbox("Output temperature unit", TEMPERATURE_UNITS, index=0, key="ev_temp_out")
    delta_t_unit = st.selectbox("ΔT output unit", DELTA_TEMPERATURE_UNITS, index=0, key="ev_dt_out")
    duty_output_unit = st.selectbox("Duty output unit", POWER_UNITS, index=0, key="ev_duty_out")
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
    st.metric("Duty", f"{kw_to_power(result.estimated_duty_kw, duty_output_unit):,.1f} {duty_output_unit}")
    st.plotly_chart(px.bar(df, x="Stream", y="value", title=f"Evaporator Streams ({output_flow_unit})"), use_container_width=True)
    _show_notes(result.notes)



def render_crystallizers() -> None:
    st.header("Crystallizers")
    c1, c2, c3, c4 = st.columns(4)
    feed_rate = c1.number_input("Feed rate", value=12000.0, key="cr_feed_rate")
    feed_rate_unit = c2.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="cr_feed_rate_unit")
    feed_solids = c3.number_input("Feed solids (wt%)", value=55.0, key="cr_feed_solids")
    mother_liquor_solids = c4.number_input("Mother liquor solids (wt%)", value=45.0, key="cr_mother_solids")
    c5, c6, c7, c8 = st.columns(4)
    slurry_solids = c5.number_input("Target slurry solids (wt%)", value=25.0, key="cr_slurry_solids")
    circulation = c6.number_input("Circulation rate", value=72000.0, key="cr_circulation")
    circulation_unit = c7.selectbox("Circulation unit", MASS_FLOW_UNITS, index=0, key="cr_circulation_unit")
    operating_temp = c8.number_input("Operating temperature", value=45.0, key="cr_temp")
    c9, c10, c11, c12 = st.columns(4)
    operating_temp_unit = c9.selectbox("Temperature unit", TEMPERATURE_UNITS, index=0, key="cr_temp_unit")
    working_volume = c10.number_input("Working volume", value=18.0, key="cr_working_volume")
    working_volume_unit = c11.selectbox("Working volume unit", VOLUME_UNITS, index=0, key="cr_working_volume_unit")
    output_flow_unit = c12.selectbox("Output flow unit", MASS_FLOW_UNITS, index=0, key="cr_flow_out")
    residence_unit = st.selectbox("Residence-time output unit", TIME_UNITS, index=2, key="cr_time_out")
    temp_c = operating_temp if operating_temp_unit == "C" else (operating_temp - 32.0) * 5.0 / 9.0
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
        )
    )
    yield_unit = st.selectbox("Yield output unit", PERCENT_UNITS, index=0, key="cr_yield_out")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Crystals", f"{kg_h_to_mass_flow(result.crystals_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
    m2.metric("Mother liquor", f"{kg_h_to_mass_flow(result.mother_liquor_kg_h, output_flow_unit):,.1f} {output_flow_unit}")
    m3.metric("Circulation ratio", f"{result.circulation_ratio:,.2f}")
    if result.residence_time_h is not None:
        residence_s = result.residence_time_h * 3600.0
        m4.metric("Residence time", f"{seconds_to_time(residence_s, residence_unit):,.2f} {residence_unit}")
    st.metric("Yield", f"{_display_percent(result.yield_fraction_of_feed_solids, yield_unit):,.2f} {yield_unit}")
    _show_notes(result.notes)



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
    roadmap = [
        {"priority": 1, "area": "Solution BPE", "next_step": "Refine >60 DS citric estimation with better literature and extend stronger product-specific fructose/dextrose correlations."},
        {"priority": 2, "area": "Hydraulics", "next_step": "Add branch-network splitting/merging, cavitation-aware valve checks, and suction/discharge vessel modeling."},
        {"priority": 3, "area": "Steam jets", "next_step": "Import workbook-derived curve families and compare multiple models side-by-side."},
        {"priority": 4, "area": "Evaporators", "next_step": "Add design-calibrated evaporator mode using workbook logic without requiring plant DS back-calcs."},
        {"priority": 5, "area": "Crystallizers", "next_step": "Add citric/fructose solubility correlations and supersaturation screens."},
        {"priority": 6, "area": "Quick tools", "next_step": "Add tank volume, blend/dilution, brix/solids, and utility cost estimate tools."},
    ]
    st.dataframe(pd.DataFrame(roadmap), use_container_width=True)
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
