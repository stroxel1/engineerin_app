from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import plotly.express as px
import streamlit as st

from engineering_app.core.crystallizers import CrystallizerInputs, estimate_crystallizer
from engineering_app.core.evaporators import EvaporatorInputs, estimate_evaporation
from engineering_app.core.hydraulics import calculate_hydraulics_with_units
from engineering_app.core.quicktools import flash_fraction, pressure_conversion, steam_for_duty, temperature_conversion, thermal_point
from engineering_app.core.steam import duty_from_steam_flow
from engineering_app.core.units import LENGTH_UNITS, MASS_FLOW_UNITS, PRESSURE_UNITS, TEMPERATURE_UNITS, VOLUME_UNITS, VOLUMETRIC_FLOW_UNITS

st.set_page_config(page_title="Engineering App", page_icon="⚙️", layout="wide")


def _show_notes(notes: list[str]) -> None:
    for note in notes:
        st.caption(f"- {note}")


def render_dashboard() -> None:
    st.title("Engineering App")
    st.write("Practical plant engineering tools for steam, hydraulics, evaporation, and crystallization.")
    cols = st.columns(4)
    cards = [
        ("Quick tools", "Pressure, temperature, and thermal conversions"),
        ("Hydraulics", "Velocity, pressure drop, TDH, and line residence time"),
        ("Evaporators", "Duty, steam demand, and ΔT screen"),
        ("Crystallizers", "Yield, slurry rate, circulation ratio, and residence time"),
    ]
    for col, (title, desc) in zip(cols, cards):
        with col:
            st.metric(title, "Ready")
            st.caption(desc)


def render_quick_tools() -> None:
    st.header("Quick Tools")
    tab1, tab2, tab3, tab4 = st.tabs(["Pressure", "Temperature", "Thermal Point", "Steam Flash"])

    with tab1:
        c1, c2, c3 = st.columns(3)
        value = c1.number_input("Pressure value", value=15.0)
        from_unit = c2.selectbox("From unit", PRESSURE_UNITS, index=5)
        to_unit = c3.selectbox("To unit", PRESSURE_UNITS, index=0)
        result = pressure_conversion(value, from_unit, to_unit)
        st.metric("Converted pressure", f"{result:,.3f} {to_unit}")

    with tab2:
        c1, c2, c3 = st.columns(3)
        value = c1.number_input("Temperature value", value=212.0)
        from_unit = c2.selectbox("From unit", TEMPERATURE_UNITS, index=1)
        to_unit = c3.selectbox("To unit", TEMPERATURE_UNITS, index=0)
        result = temperature_conversion(value, from_unit, to_unit)
        st.metric("Converted temperature", f"{result:,.2f} °{to_unit}")

    with tab3:
        c1, c2, c3 = st.columns(3)
        pressure_value = c1.number_input("Operating pressure", value=25.0)
        pressure_unit = c2.selectbox("Pressure basis", PRESSURE_UNITS, index=0, key="tp_unit")
        bpe_c = c3.number_input("BPE (°C)", value=3.0)
        point = thermal_point(pressure_value, pressure_unit, bpe_c)
        st.json(asdict(point))

    with tab4:
        c1, c2, c3, c4 = st.columns(4)
        condensate_temp_c = c1.number_input("Condensate temperature (°C)", value=120.0)
        flash_pressure_value = c2.number_input("Flash pressure", value=10.0)
        flash_pressure_unit = c3.selectbox("Flash pressure unit", PRESSURE_UNITS, index=0, key="flash_unit")
        condensate_flow = c4.number_input("Condensate flow (kg/h)", value=10000.0)
        result = flash_fraction(condensate_temp_c, flash_pressure_value, flash_pressure_unit, condensate_flow)
        m1, m2, m3 = st.columns(3)
        m1.metric("Flash fraction", f"{result.flash_fraction:.3f}")
        m2.metric("Flash steam", f"{result.flash_steam_kg_h:,.1f} kg/h")
        m3.metric("Remaining liquid", f"{result.remaining_liquid_kg_h:,.1f} kg/h")
        _show_notes(result.notes)


def render_hydraulics() -> None:
    st.header("Hydraulics")
    c1, c2, c3, c4 = st.columns(4)
    flow_value = c1.number_input("Flow", value=100.0)
    flow_unit = c2.selectbox("Flow unit", VOLUMETRIC_FLOW_UNITS, index=0)
    density = c3.number_input("Density (kg/m³)", value=998.0)
    viscosity = c4.number_input("Viscosity (cP)", value=1.0)

    c5, c6, c7, c8 = st.columns(4)
    pipe_id = c5.number_input("Pipe ID", value=52.5)
    pipe_id_unit = c6.selectbox("Pipe ID unit", LENGTH_UNITS, index=2)
    pipe_length = c7.number_input("Pipe length", value=120.0)
    pipe_length_unit = c8.selectbox("Pipe length unit", LENGTH_UNITS, index=0)

    c9, c10, c11, c12 = st.columns(4)
    roughness_mm = c9.number_input("Roughness (mm)", value=0.045)
    elevation_change = c10.number_input("Elevation change", value=12.0)
    elevation_unit = c11.selectbox("Elevation unit", LENGTH_UNITS, index=0)
    fitting_k = c12.number_input("Total fitting K", value=8.0)

    result = calculate_hydraulics_with_units(
        volumetric_flow_value=flow_value,
        volumetric_flow_unit=flow_unit,
        density_kg_m3=density,
        viscosity_cp=viscosity,
        pipe_id_value=pipe_id,
        pipe_id_unit=pipe_id_unit,
        pipe_length_value=pipe_length,
        pipe_length_unit=pipe_length_unit,
        roughness_mm=roughness_mm,
        elevation_change_value=elevation_change,
        elevation_change_unit=elevation_unit,
        fitting_k_total=fitting_k,
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Velocity", f"{result.velocity_m_s:,.2f} m/s")
    m2.metric("Pressure drop", f"{result.pressure_drop_kpa:,.1f} kPa")
    m3.metric("TDH", f"{result.total_dynamic_head_m:,.1f} m")
    m4.metric("Residence time", f"{result.residence_time_s:,.1f} s")
    st.json(asdict(result))
    _show_notes(result.notes)


def render_steam() -> None:
    st.header("Steam & Utilities")
    tab1, tab2 = st.tabs(["Steam for duty", "Duty from steam"])

    with tab1:
        c1, c2, c3 = st.columns(3)
        duty_kw = c1.number_input("Duty (kW)", value=2500.0)
        pressure_value = c2.number_input("Steam pressure", value=3.5)
        pressure_unit = c3.selectbox("Pressure unit", PRESSURE_UNITS, index=4, key="steam_for_duty_unit")
        result = steam_for_duty(duty_kw, pressure_value, pressure_unit)
        st.json(asdict(result))
        _show_notes(result.notes)

    with tab2:
        c1, c2, c3, c4 = st.columns(4)
        steam_flow = c1.number_input("Steam flow", value=4000.0)
        steam_flow_unit = c2.selectbox("Steam flow unit", MASS_FLOW_UNITS, index=0)
        pressure_value = c3.number_input("Steam pressure", value=3.5)
        pressure_unit = c4.selectbox("Pressure unit", PRESSURE_UNITS, index=4, key="duty_from_steam_unit")
        result = duty_from_steam_flow(steam_flow, steam_flow_unit, pressure_value, pressure_unit)
        st.json(asdict(result))
        _show_notes(result.notes)


def render_evaporators() -> None:
    st.header("Evaporators")
    c1, c2, c3, c4 = st.columns(4)
    feed_rate = c1.number_input("Feed rate", value=25000.0)
    feed_rate_unit = c2.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0)
    feed_solids = c3.number_input("Feed solids (wt%)", value=12.0)
    product_solids = c4.number_input("Product solids (wt%)", value=50.0)

    c5, c6, c7, c8 = st.columns(4)
    steam_pressure = c5.number_input("Steam pressure", value=3.5)
    steam_pressure_unit = c6.selectbox("Steam pressure unit", PRESSURE_UNITS, index=4, key="evap_steam_unit")
    operating_pressure = c7.number_input("Operating pressure", value=20.0)
    operating_pressure_unit = c8.selectbox("Operating pressure unit", PRESSURE_UNITS, index=0, key="evap_op_unit")

    c9, c10, c11, c12 = st.columns(4)
    passes = int(c9.number_input("Passes", min_value=1, value=2, step=1))
    recirc = c10.number_input("Recirculation ratio", value=4.0)
    bpe = c11.number_input("BPE (°C)", value=6.0)
    duty_per_kg = c12.number_input("Specific evaporation duty (kJ/kg)", value=2250.0)

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
            bpe_c=bpe,
            estimated_specific_evaporation_duty_kj_kg=duty_per_kg,
        )
    )

    df = pd.DataFrame(
        [
            {"Stream": "Feed", "kg/h": result.feed_rate_kg_h},
            {"Stream": "Product", "kg/h": result.product_rate_kg_h},
            {"Stream": "Evaporation", "kg/h": result.evaporation_rate_kg_h},
            {"Stream": "Steam", "kg/h": result.estimated_steam_flow_kg_h},
        ]
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        st.json(asdict(result))
        _show_notes(result.notes)
    with col2:
        st.plotly_chart(px.bar(df, x="Stream", y="kg/h", title="Evaporator Mass and Steam Screen"), use_container_width=True)


def render_crystallizers() -> None:
    st.header("Crystallizers")
    c1, c2, c3, c4 = st.columns(4)
    feed_rate = c1.number_input("Feed rate", value=12000.0)
    feed_rate_unit = c2.selectbox("Feed rate unit", MASS_FLOW_UNITS, index=0, key="cr_feed_unit")
    feed_solids = c3.number_input("Feed solids (wt%)", value=55.0)
    mother_liquor_solids = c4.number_input("Mother liquor solids (wt%)", value=45.0)

    c5, c6, c7, c8 = st.columns(4)
    slurry_solids = c5.number_input("Target slurry solids (wt%)", value=25.0)
    circulation = c6.number_input("Circulation rate", value=72000.0)
    circulation_unit = c7.selectbox("Circulation unit", MASS_FLOW_UNITS, index=0)
    operating_temp = c8.number_input("Operating temperature (°C)", value=45.0)

    c9, c10 = st.columns(2)
    working_volume = c9.number_input("Working volume", value=18.0)
    working_volume_unit = c10.selectbox("Working volume unit", VOLUME_UNITS, index=0)

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
            operating_temperature_c=operating_temp,
        )
    )
    st.json(asdict(result))
    _show_notes(result.notes)


PAGES = {
    "Dashboard": render_dashboard,
    "Quick Tools": render_quick_tools,
    "Hydraulics": render_hydraulics,
    "Steam & Utilities": render_steam,
    "Evaporators": render_evaporators,
    "Crystallizers": render_crystallizers,
}

with st.sidebar:
    st.title("Engineering App")
    page = st.radio("Section", list(PAGES.keys()))
    st.caption("Browser shell for plant engineering workflows.")

PAGES[page]()
