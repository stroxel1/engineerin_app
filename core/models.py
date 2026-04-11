"""Canonical engineering data models for the citric process application."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Literal, Optional


PhaseTag = Literal["liquid", "vapor", "slurry", "mixed"]
EquipmentType = Literal[
    "ejector",
    "thermo_compressor",
    "evaporator",
    "crystallizer",
]


@dataclass
class CaseMeta:
    name: str
    author: str = "Stephen"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    revision: int = 1
    source_workbooks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class FluidBasis:
    system_name: str = "citric_acid_solution"
    composition_basis: str = "wt_pct"
    acid_form: Optional[str] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class Stream:
    name: str
    total_mass_flow_kg_h: float
    temperature_c: float
    pressure_kpa_abs: float
    composition: dict[str, float]
    phase: PhaseTag
    density_kg_m3: Optional[float] = None
    cp_kj_kgk: Optional[float] = None
    viscosity_cp: Optional[float] = None
    enthalpy_kj_kg: Optional[float] = None
    bpe_c: Optional[float] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class OperatingPoint:
    motive_steam_pressure_kpa_abs: Optional[float] = None
    motive_steam_temperature_c: Optional[float] = None
    suction_pressure_kpa_abs: Optional[float] = None
    discharge_pressure_kpa_abs: Optional[float] = None
    suction_load_kg_h: Optional[float] = None
    motive_steam_flow_kg_h: Optional[float] = None
    non_condensable_gas_wt_pct: Optional[float] = None


@dataclass
class WorkbookReference:
    path: str
    role: str
    checksum: Optional[str] = None
    sheet_mappings: dict[str, Any] = field(default_factory=dict)


@dataclass
class EquipmentBlock:
    name: str
    equipment_type: EquipmentType
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    calculation_status: str = "draft"


@dataclass
class CaseSnapshot:
    meta: CaseMeta
    fluid_basis: FluidBasis = field(default_factory=FluidBasis)
    streams: list[Stream] = field(default_factory=list)
    operating_points: list[OperatingPoint] = field(default_factory=list)
    equipment_blocks: list[EquipmentBlock] = field(default_factory=list)
    workbook_references: list[WorkbookReference] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
