"""Application state models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engineering_app.core.curves import CurveLibrary
from engineering_app.core.models import CaseSnapshot


@dataclass
class ImportState:
    curve_workbook_path: Optional[str] = None
    bpe_workbook_path: Optional[str] = None
    curve_import_ready: bool = False
    bpe_import_ready: bool = False
    last_error: Optional[str] = None


@dataclass
class UIState:
    current_screen: str = "dashboard"
    theme: str = "dark"


@dataclass
class AppState:
    ui: UIState = field(default_factory=UIState)
    imports: ImportState = field(default_factory=ImportState)
    curve_library: CurveLibrary = field(default_factory=CurveLibrary)
    active_case: Optional[CaseSnapshot] = None
    recent_case_paths: list[str] = field(default_factory=list)
