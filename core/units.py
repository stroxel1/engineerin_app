"""Engineering unit conversion helpers.

Internal canonical basis:
- pressure: kPa absolute
- temperature: degC
- mass flow: kg/h
- volumetric flow: m3/h
- length: m
"""

from __future__ import annotations

ATM_KPA = 101.325
KPA_PER_BAR = 100.0
KPA_PER_PSI = 6.894757293168361
KPA_PER_MPA = 1000.0
KPA_PER_MBAR = 0.1
KPA_PER_TORR = 0.13332236842105263
KPA_PER_MMHG = KPA_PER_TORR
KPA_PER_INHG = 3.386389
KPA_PER_INH2O = 0.24908891
KPA_PER_MMH2O = 0.00980665

PRESSURE_UNITS = (
    "kPa",
    "kpaa",
    "kPag",
    "bara",
    "barg",
    "psia",
    "psig",
    "mbar",
    "Torr",
    "inHg vacuum",
    "% vacuum",
    "microns",
)
TEMPERATURE_UNITS = ("C", "F")
DELTA_TEMPERATURE_UNITS = ("C", "F")
MASS_FLOW_UNITS = ("kg/h", "lb/h", "kg/min", "t/h")
VOLUMETRIC_FLOW_UNITS = ("m3/h", "m3/min", "gpm", "L/min")
LENGTH_UNITS = ("m", "ft", "mm", "in")
VOLUME_UNITS = ("m3", "L", "gal", "ft3")
DENSITY_UNITS = ("kg/m3", "lb/ft3", "sg")
VISCOSITY_UNITS = ("cP", "Pa·s")
POWER_UNITS = ("kW", "BTU/h", "MMBTU/h")
VELOCITY_UNITS = ("m/s", "ft/s")
TIME_UNITS = ("s", "min", "h")
PERCENT_UNITS = ("%", "fraction")


def c_to_f(value_c: float) -> float:
    return value_c * 9.0 / 5.0 + 32.0


def f_to_c(value_f: float) -> float:
    return (value_f - 32.0) * 5.0 / 9.0


def delta_c_to_f(value_c: float) -> float:
    return value_c * 9.0 / 5.0


def delta_f_to_c(value_f: float) -> float:
    return value_f * 5.0 / 9.0


def temperature_to_c(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"c", "degc", "°c"}:
        return value
    if u in {"f", "degf", "°f"}:
        return f_to_c(value)
    raise ValueError(f"Unsupported temperature unit: {unit}")


def c_to_temperature(value_c: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"c", "degc", "°c"}:
        return value_c
    if u in {"f", "degf", "°f"}:
        return c_to_f(value_c)
    raise ValueError(f"Unsupported temperature unit: {unit}")


def delta_temperature_to_c(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"c", "degc", "°c"}:
        return value
    if u in {"f", "degf", "°f"}:
        return delta_f_to_c(value)
    raise ValueError(f"Unsupported delta-temperature unit: {unit}")


def c_to_delta_temperature(value_c: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"c", "degc", "°c"}:
        return value_c
    if u in {"f", "degf", "°f"}:
        return delta_c_to_f(value_c)
    raise ValueError(f"Unsupported delta-temperature unit: {unit}")


def pressure_to_kpa_abs(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"kpaa", "kpa abs", "kpa"}:
        return value
    if u in {"kpag", "kpa g"}:
        return value + ATM_KPA
    if u in {"bara", "bar abs", "bar(a)"}:
        return value * KPA_PER_BAR
    if u in {"barg", "bar g", "bar(g)"}:
        return value * KPA_PER_BAR + ATM_KPA
    if u in {"psia", "psi abs"}:
        return value * KPA_PER_PSI
    if u in {"psig", "psi g"}:
        return value * KPA_PER_PSI + ATM_KPA
    if u in {"mpa", "mpaa", "mpa abs"}:
        return value * KPA_PER_MPA
    if u in {"mbar", "mbar abs"}:
        return value * KPA_PER_MBAR
    if u in {"torr", "mmhg"}:
        return value * KPA_PER_TORR
    if u in {"inhg", "in hg"}:
        return value * KPA_PER_INHG
    if u in {"inh2o", "in h2o"}:
        return value * KPA_PER_INH2O
    if u in {"mmh2o", "mm h2o"}:
        return value * KPA_PER_MMH2O
    if u in {"% vacuum", "%vacuum", "percent vacuum"}:
        return ATM_KPA * (1.0 - value / 100.0)
    if u in {"inhg vacuum", "inhg vac"}:
        return ATM_KPA - value * KPA_PER_INHG
    if u in {"micron", "microns"}:
        return (value / 1000.0) * KPA_PER_TORR
    raise ValueError(f"Unsupported pressure unit: {unit}")


def kpa_abs_to_pressure(value_kpa_abs: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"kpaa", "kpa abs", "kpa"}:
        return value_kpa_abs
    if u in {"kpag", "kpa g"}:
        return value_kpa_abs - ATM_KPA
    if u in {"bara", "bar abs", "bar(a)"}:
        return value_kpa_abs / KPA_PER_BAR
    if u in {"barg", "bar g", "bar(g)"}:
        return (value_kpa_abs - ATM_KPA) / KPA_PER_BAR
    if u in {"psia", "psi abs"}:
        return value_kpa_abs / KPA_PER_PSI
    if u in {"psig", "psi g"}:
        return (value_kpa_abs - ATM_KPA) / KPA_PER_PSI
    if u in {"mpa", "mpaa", "mpa abs"}:
        return value_kpa_abs / KPA_PER_MPA
    if u in {"mbar", "mbar abs"}:
        return value_kpa_abs / KPA_PER_MBAR
    if u in {"torr", "mmhg"}:
        return value_kpa_abs / KPA_PER_TORR
    if u in {"inhg", "in hg"}:
        return value_kpa_abs / KPA_PER_INHG
    if u in {"inh2o", "in h2o"}:
        return value_kpa_abs / KPA_PER_INH2O
    if u in {"mmh2o", "mm h2o"}:
        return value_kpa_abs / KPA_PER_MMH2O
    if u in {"% vacuum", "%vacuum", "percent vacuum"}:
        return (1.0 - value_kpa_abs / ATM_KPA) * 100.0
    if u in {"inhg vacuum", "inhg vac"}:
        return (ATM_KPA - value_kpa_abs) / KPA_PER_INHG
    if u in {"micron", "microns"}:
        return (value_kpa_abs / KPA_PER_TORR) * 1000.0
    raise ValueError(f"Unsupported pressure unit: {unit}")


def mass_flow_to_kg_h(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"kg/h", "kgph"}:
        return value
    if u in {"lb/h", "lbph"}:
        return value * 0.45359237
    if u in {"kg/min"}:
        return value * 60.0
    if u in {"t/h", "tph", "metric ton/h"}:
        return value * 1000.0
    raise ValueError(f"Unsupported mass-flow unit: {unit}")


def kg_h_to_mass_flow(value_kg_h: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"kg/h", "kgph"}:
        return value_kg_h
    if u in {"lb/h", "lbph"}:
        return value_kg_h / 0.45359237
    if u in {"kg/min"}:
        return value_kg_h / 60.0
    if u in {"t/h", "tph", "metric ton/h"}:
        return value_kg_h / 1000.0
    raise ValueError(f"Unsupported mass-flow unit: {unit}")


def volumetric_flow_to_m3_h(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"m3/h", "m^3/h"}:
        return value
    if u in {"m3/min", "m^3/min"}:
        return value * 60.0
    if u in {"gpm", "usgpm"}:
        return value * 0.227124707
    if u in {"l/min", "lpm"}:
        return value * 0.06
    raise ValueError(f"Unsupported volumetric-flow unit: {unit}")


def m3_h_to_volumetric_flow(value_m3_h: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"m3/h", "m^3/h"}:
        return value_m3_h
    if u in {"m3/min", "m^3/min"}:
        return value_m3_h / 60.0
    if u in {"gpm", "usgpm"}:
        return value_m3_h / 0.227124707
    if u in {"l/min", "lpm"}:
        return value_m3_h / 0.06
    raise ValueError(f"Unsupported volumetric-flow unit: {unit}")


def length_to_m(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m":
        return value
    if u == "ft":
        return value * 0.3048
    if u == "mm":
        return value / 1000.0
    if u == "in":
        return value * 0.0254
    raise ValueError(f"Unsupported length unit: {unit}")


def m_to_length(value_m: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m":
        return value_m
    if u == "ft":
        return value_m / 0.3048
    if u == "mm":
        return value_m * 1000.0
    if u == "in":
        return value_m / 0.0254
    raise ValueError(f"Unsupported length unit: {unit}")


def volume_to_m3(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m3":
        return value
    if u in {"l", "liter", "liters"}:
        return value / 1000.0
    if u in {"gal", "gallon", "gallons"}:
        return value * 0.003785411784
    if u in {"ft3", "ft^3"}:
        return value * 0.028316846592
    raise ValueError(f"Unsupported volume unit: {unit}")


def m3_to_volume(value_m3: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m3":
        return value_m3
    if u in {"l", "liter", "liters"}:
        return value_m3 * 1000.0
    if u in {"gal", "gallon", "gallons"}:
        return value_m3 / 0.003785411784
    if u in {"ft3", "ft^3"}:
        return value_m3 / 0.028316846592
    raise ValueError(f"Unsupported volume unit: {unit}")


def density_to_kg_m3(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"kg/m3", "kg/m^3"}:
        return value
    if u in {"lb/ft3", "lb/ft^3"}:
        return value * 16.01846337
    if u == "sg":
        return value * 1000.0
    raise ValueError(f"Unsupported density unit: {unit}")


def kg_m3_to_density(value_kg_m3: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"kg/m3", "kg/m^3"}:
        return value_kg_m3
    if u in {"lb/ft3", "lb/ft^3"}:
        return value_kg_m3 / 16.01846337
    if u == "sg":
        return value_kg_m3 / 1000.0
    raise ValueError(f"Unsupported density unit: {unit}")


def viscosity_to_cp(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "cp":
        return value
    if u in {"pa·s", "pa*s", "pas"}:
        return value * 1000.0
    raise ValueError(f"Unsupported viscosity unit: {unit}")


def cp_to_viscosity(value_cp: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "cp":
        return value_cp
    if u in {"pa·s", "pa*s", "pas"}:
        return value_cp / 1000.0
    raise ValueError(f"Unsupported viscosity unit: {unit}")


def kw_to_power(value_kw: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "kw":
        return value_kw
    if u in {"btu/h", "btu/hr"}:
        return value_kw * 3412.141633
    if u == "mmbtu/h":
        return value_kw * 0.003412141633
    raise ValueError(f"Unsupported power unit: {unit}")


def power_to_kw(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "kw":
        return value
    if u in {"btu/h", "btu/hr"}:
        return value / 3412.141633
    if u == "mmbtu/h":
        return value / 0.003412141633
    raise ValueError(f"Unsupported power unit: {unit}")


def m_s_to_velocity(value_m_s: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m/s":
        return value_m_s
    if u == "ft/s":
        return value_m_s / 0.3048
    raise ValueError(f"Unsupported velocity unit: {unit}")


def velocity_to_m_s(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m/s":
        return value
    if u == "ft/s":
        return value * 0.3048
    raise ValueError(f"Unsupported velocity unit: {unit}")


def seconds_to_time(value_s: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "s":
        return value_s
    if u == "min":
        return value_s / 60.0
    if u == "h":
        return value_s / 3600.0
    raise ValueError(f"Unsupported time unit: {unit}")


def time_to_seconds(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "s":
        return value
    if u == "min":
        return value * 60.0
    if u == "h":
        return value * 3600.0
    raise ValueError(f"Unsupported time unit: {unit}")


def fraction_to_percent(value_fraction: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "%":
        return value_fraction * 100.0
    if u == "fraction":
        return value_fraction
    raise ValueError(f"Unsupported percent unit: {unit}")
