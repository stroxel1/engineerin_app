"""Vendor-specific workbook mapping presets for steam-jet / ejector curves.

These presets let the app auto-detect known vendor workbook formats and apply
correct column mappings without requiring manual selection.

Supported vendors (initial set):
- Croll-Reynolds (CR): suction-load / motive-steam / motive-pressure tables
- Graham: capacity / entrainment / motive-pressure curve families
- Schutte & Koerting (S&K): suction capacity / steam consumption / motive pressure
- Koerting (international): similar to S&K but often metric (kg/h, bara)
- GEA: product-focused with model series and motive header splits
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VendorColumnMapping:
    """Column mapping for a specific vendor's workbook format."""
    vendor: str
    """Vendor display name, e.g. 'Croll-Reynolds'"""
    
    name_tokens: set = field(default_factory=lambda: {"model", "type", "ejector", "nozzle"})
    """Tokens for identifying the curve/model name column"""
    
    x_tokens: set = field(default_factory=lambda: {"suction", "capacity", "entrainment", "vapour", "vapor"})
    """Tokens for the x-axis (independent variable, typically suction load)"""
    
    y_tokens: set = field(default_factory=lambda: {"steam", "consumption", "motive"})
    """Tokens for the y-axis (dependent variable, typically motive steam)"""
    
    family_tokens: set = field(default_factory=lambda: {"pressure", "motive", "steam"})
    """Tokens for identifying family-split columns (motive pressure variants)"""
    
    family_column_patterns: list = field(default_factory=lambda: [
        "motive_steam_pressure", "motive_pressure", "steam_pressure",
        "header_pressure", "motive_steam", "header"
    ])
    """Exact or partial column names that typically hold family split values"""
    
    penalty_tokens: set = field(default_factory=lambda: {"discharge", "back"})
    """Tokens that should NOT be used for x or y axes"""
    
    x_unit_hint: str | None = None
    """Typical unit for x-axis if known (e.g. 'lb/hr', 'kg/h')"""
    
    y_unit_hint: str | None = None
    """Typical unit for y-axis if known"""
    
    notes: str = ""
    """Helpful description for the user"""


# Vendor presets
CROLL_REYNOLDS = VendorColumnMapping(
    vendor="Croll-Reynolds",
    name_tokens={"model", "type", "ejector", "nozzle", "unit"},
    x_tokens={"suction", "capacity", "air", "vapour", "vapor", "evacuation", "lb_hr"},
    y_tokens={"steam", "consumption", "motive_steam", "hp"},
    family_tokens={"pressure", "motive", "steam"},
    family_column_patterns=["motive_steam_pressure", "header_pressure", "motive_pressure"],
    penalty_tokens={"discharge", "back", "atmospheric"},
    x_unit_hint="lb/hr",
    y_unit_hint="lb/hr",
    notes="Croll-Reynolds style curves: X = suction capacity (lb/hr air/vapor), Y = motive steam consumption. Family typically split by motive steam pressure.",
)

GRAHAM = VendorColumnMapping(
    vendor="Graham",
    name_tokens={"model", "series", "ejector", "tag"},
    x_tokens={"suction", "entrainment", "capacity", "air", "vapor"},
    y_tokens={"steam", "motive", "consumption"},
    family_tokens={"motive", "pressure", "steam", "header"},
    family_column_patterns=["motive_steam_pressure", "steam_header", "motive_pressure", "steam"],
    penalty_tokens={"discharge", "back", "atmospheric", "temperature"},
    x_unit_hint="lb/hr",
    y_unit_hint="lb/hr",
    notes="Graham-style curves: X = entrainment/suction capacity, Y = motive steam. Family often split by motive pressure header.",
)

SCHUTTE_KOERTING = VendorColumnMapping(
    vendor="Schutte & Koerting",
    name_tokens={"model", "type", "ejector", "series", "nozzle"},
    x_tokens={"suction", "capacity", "air", "vapor", "entrainment", "kg_h", "kg_hr"},
    y_tokens={"steam", "consumption", "motive", "kg_h", "kg_hr"},
    family_tokens={"pressure", "motive", "steam", "bara", "barg"},
    family_column_patterns=["motive_pressure", "steam_pressure", "header", "motive_pressure_bara", "suction_pressure"],
    penalty_tokens={"discharge", "back", "atmospheric"},
    x_unit_hint="kg/h",
    y_unit_hint="kg/h",
    notes="Schutte & Koerting style curves: metric basis, X = suction kg/h, Y = motive steam kg/h. Family split by motive pressure (bara/barg).",
)

GEA = VendorColumnMapping(
    vendor="GEA",
    name_tokens={"model", "ejector", "type", "series", "nozzle", "nr"},
    x_tokens={"suction", "capacity", "load", "vapour", "vapor", "entrainment"},
    y_tokens={"steam", "motive", "consumption"},
    family_tokens={"motive", "pressure", "steam", "series", "header"},
    family_column_patterns=["motive_pressure", "steam_header", "series", "model_series"],
    penalty_tokens={"discharge", "back", "atmospheric"},
    x_unit_hint="kg/h",
    y_unit_hint="kg/h",
    notes="GEA-style curves: X = suction capacity, Y = motive steam. Family often split by model series and motive pressure.",
)


# Registry of all vendor presets
VENDOR_PRESETS: list[VendorColumnMapping] = [
    CROLL_REYNOLDS,
    GRAHAM,
    SCHUTTE_KOERTING,
    GEA,
]
VENDOR_NAMES: list[str] = [p.vendor for p in VENDOR_PRESETS]
GENERIC_AUTO_DETECT = "(auto-detect from workbook)"


def get_vendor_preset(vendor_name: str) -> VendorColumnMapping | None:
    """Get a vendor preset by name, or None if not found."""
    for preset in VENDOR_PRESETS:
        if preset.vendor.lower() == vendor_name.lower():
            return preset
    return None


def detect_vendor_from_sheet(sheet_name: str, header: list[str]) -> VendorColumnMapping | None:
    """Try to auto-detect the vendor based on sheet name and column headers.
    
    Returns the matched preset or None if no confident match.
    """
    sheet_text = str(sheet_name).lower().replace("_", " ").replace("-", " ")
    header_text = " ".join(str(h).lower() for h in header)
    combined = f"{sheet_text} {header_text}"
    
    # Check each vendor by name match
    for preset in VENDOR_PRESETS:
        vendor_lower = preset.vendor.lower()
        # Check for vendor name in sheet or headers
        if any(token in combined for token in vendor_lower.replace("&", " and ").replace("-", " ").split()):
            return preset
    
    # Check for distinctive column patterns
    # Croll-Reynolds often uses "evacuation" or "air_load" 
    if any("evacuation" in str(h).lower() or "air_load" in str(h).lower() for h in header):
        return CROLL_REYNOLDS
    
    # S&K often uses metric units explicitly
    if header_text and ("bara" in header_text or "barg" in header_text):
        return SCHUTTE_KOERTING
    
    # Graham often uses "entrainment" prominently
    if any("entrainment" in str(h).lower() for h in header):
        return GRAHAM
    
    return None


@dataclass
class VendorMappingSuggestion:
    """Suggested column mapping from a vendor preset for a specific header."""
    vendor: str | None
    name_col: str | None
    x_col: str | None
    y_col: str | None
    family_col: str | None
    confidence: str
    """'high', 'medium', 'low', or 'none'."""
    notes: str = ""
    """Explanation of how the mapping was derived."""


def suggest_mapping_from_vendor_preset(
    columns: list[str],
    vendor_preset: str | None = None,
) -> VendorMappingSuggestion:
    """Run vendor preset heuristics against column names and return a suggested
    mapping with confidence level. Bridges vendor presets to the UI column selectors."""

    vendor: VendorColumnMapping | None = None
    if vendor_preset:
        vendor = get_vendor_preset(vendor_preset)
    else:
        vendor = detect_vendor_from_sheet("", columns)

    matched_vendor = vendor.vendor if vendor else None
    tokens = vendor if vendor else VendorColumnMapping(
        vendor="generic",
        name_tokens={"model", "curve", "tag", "name", "ejector"},
        x_tokens={"suction", "capacity", "flow", "load", "vapor", "vapour"},
        y_tokens={"steam", "consumption", "motive", "head", "duty"},
        family_tokens={"family", "basis", "series", "pressure", "header"},
        family_column_patterns=["family", "basis", "series", "motive_pressure", "header"],
        penalty_tokens={"discharge", "back", "atmospheric"},
    )

    def _pick(
        preferred: set, penalty: set, exclude: set[str] | None = None
    ) -> str | None:
        exclude = exclude or set()
        best_col: str | None = None
        best_score = 0.0
        for col in columns:
            if col in exclude:
                continue
            low = col.lower()
            score = sum(10.0 for t in preferred if t in low)
            score -= sum(8.0 for t in penalty if t in low)
            if low in preferred:
                score += 15.0
            if score > best_score:
                best_score = score
                best_col = col
        return best_col if best_score > 0 else None

    name_col = _pick(tokens.name_tokens, set())
    x_col = _pick(tokens.x_tokens, tokens.penalty_tokens, exclude={name_col} - {None})
    y_col = _pick(
        tokens.y_tokens, tokens.penalty_tokens,
        exclude={name_col, x_col} - {None},
    )
    fam_col = _pick(
        tokens.family_tokens, set(),
        exclude={name_col, x_col, y_col} - {None},
    )

    if fam_col is None and tokens.family_column_patterns:
        for col in columns:
            if col in {name_col, x_col, y_col} - {None}:
                continue
            low = col.lower().replace(" ", "_")
            if any(pat in low for pat in tokens.family_column_patterns):
                fam_col = col
                break

    assigned = sum(1 for c in [name_col, x_col, y_col] if c)
    if assigned >= 3:
        confidence = "high"
        conf_note = f"Confident mapping using {'vendor preset: ' + matched_vendor if matched_vendor else 'auto-detected tokens'}."
    elif assigned == 2:
        confidence = "medium"
        conf_note = f"2 of 3 core columns resolved from {'vendor preset' if matched_vendor else 'generic tokens'} — manual override recommended."
    elif assigned == 1:
        confidence = "low"
        conf_note = "Only 1 core column identified; manual override likely needed."
    else:
        confidence = "none"
        conf_note = "No columns matched vendor preset tokens; manual mapping needed."

    if vendor and vendor.x_unit_hint:
        conf_note += f" (X hint: {vendor.x_unit_hint})"
    if vendor and vendor.y_unit_hint:
        conf_note += f" (Y hint: {vendor.y_unit_hint})"

    return VendorMappingSuggestion(
        vendor=matched_vendor,
        name_col=name_col,
        x_col=x_col,
        y_col=y_col,
        family_col=fam_col,
        confidence=confidence,
        notes=conf_note,
    )
