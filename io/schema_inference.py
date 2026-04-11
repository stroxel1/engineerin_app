"""Heuristics for classifying workbook sheets before formal mapping."""

from __future__ import annotations

from itertools import islice
from typing import Any, Iterable


CURVE_HINTS = {"ejector", "thermo", "compressor", "curve", "steam", "suction", "discharge"}
BPE_HINTS = {"bpe", "boiling", "elevation", "citric", "solids", "density", "viscosity"}
SOLUBILITY_HINTS = {"solubility", "crystal", "mother", "slurry", "supersaturation"}
HEADER_CURVE_HINTS = {"motive", "suction", "discharge", "capacity", "load", "pressure", "steam"}
HEADER_BPE_HINTS = {"temperature", "bpe", "density", "viscosity", "solids", "wt%", "wt_pct"}
HEADER_SOLUBILITY_HINTS = {"solubility", "crystal", "temperature", "mother", "liquor"}


def _normalize_tokens(values: Iterable[Any]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if value is None:
            continue
        for token in str(value).lower().replace("%", " % ").replace("_", " ").split():
            token = token.strip()
            if token:
                tokens.add(token)
    return tokens


def classify_sheet(sheet_name: str, rows: Iterable[Iterable[object]]) -> str:
    preview_rows = list(islice(rows, 8))
    text = " ".join(
        [sheet_name]
        + [" ".join(str(cell) for cell in row if cell is not None) for row in preview_rows]
    )
    lower = text.lower()
    tokens = _normalize_tokens(cell for row in preview_rows for cell in row)

    if any(hint in lower for hint in CURVE_HINTS) or len(tokens & HEADER_CURVE_HINTS) >= 2:
        return "curve_table"
    if any(hint in lower for hint in BPE_HINTS) or len(tokens & HEADER_BPE_HINTS) >= 2:
        return "bpe_table"
    if any(hint in lower for hint in SOLUBILITY_HINTS) or len(tokens & HEADER_SOLUBILITY_HINTS) >= 2:
        return "solubility_table"
    return "unknown"
