"""Normalized import contracts for workbook-derived engineering data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WorkbookSource:
    path: str
    modified_time: Optional[float] = None
    checksum: Optional[str] = None


@dataclass
class SheetPreview:
    sheet_name: str
    max_row: int
    max_column: int
    sample_rows: list[list[Any]] = field(default_factory=list)
    merged_ranges: list[str] = field(default_factory=list)
    hidden: bool = False
    freeze_panes: Optional[str] = None
    formula_cell_count: int = 0
    header_candidates: list[list[str]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class CurveImportMapping:
    sheet_name: str
    x_column: str
    y_column: str
    family_column: Optional[str] = None
    metadata_columns: list[str] = field(default_factory=list)
    units: dict[str, str] = field(default_factory=dict)


@dataclass
class BPERecord:
    solids_wt_pct: float
    temperature_c: Optional[float]
    pressure_kpa_abs: Optional[float]
    bpe_c: float
    density_kg_m3: Optional[float] = None
    viscosity_cp: Optional[float] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class SolubilityRecord:
    temperature_c: float
    solubility_wt_pct: float
    mother_liquor_notes: Optional[str] = None


@dataclass
class NormalizedTable:
    sheet_name: str
    classification: str
    header: list[str]
    rows: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
