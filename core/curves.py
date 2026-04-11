"""Curve ingestion and interpolation helpers.

Planned responsibilities:
- inspect workbook sheets and infer curve tables
- normalize ejector/thermo-compressor curve data
- interpolate operating points between known curve lines
- support plotting-friendly outputs for the UI layer
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CurvePoint:
    x: float
    y: float
    meta: Dict[str, float] = field(default_factory=dict)


@dataclass
class PerformanceCurve:
    name: str
    x_label: str
    y_label: str
    points: List[CurvePoint]
    family: Optional[str] = None
    source_sheet: Optional[str] = None


@dataclass
class CurveLibrary:
    curves: List[PerformanceCurve] = field(default_factory=list)

    def list_names(self) -> List[str]:
        return [curve.name for curve in self.curves]
