"""Normalization helpers for workbook-derived engineering data.

These routines are intentionally conservative: they extract table-shaped data
from workbook previews so real source spreadsheets can be mapped quickly once
available, without pretending we already know the vendor sheet schema.
"""

from __future__ import annotations

from typing import Any

from engineering_app.core.curves import CurveLibrary
from engineering_app.io.contracts import NormalizedTable
from engineering_app.io.schema_inference import classify_sheet


def _row_populated_count(row: list[Any]) -> int:
    return sum(1 for cell in row if cell not in (None, ""))


def _stringify_header(row: list[Any]) -> list[str]:
    header: list[str] = []
    for index, cell in enumerate(row, start=1):
        value = str(cell).strip() if cell not in (None, "") else f"column_{index}"
        header.append(value)
    return header


def _choose_header(rows: list[list[Any]]) -> tuple[list[str], int] | tuple[None, None]:
    best_index = None
    best_score = -1
    best_header = None

    for index, row in enumerate(rows):
        score = _row_populated_count(row)
        if score >= 2 and score > best_score:
            best_index = index
            best_score = score
            best_header = _stringify_header(row)

    if best_header is None or best_index is None:
        return None, None
    return best_header, best_index


def normalize_preview_table(sheet_name: str, sample_rows: list[list[Any]]) -> NormalizedTable | None:
    header, header_index = _choose_header(sample_rows)
    if header is None or header_index is None:
        return None

    records: list[dict[str, Any]] = []
    notes: list[str] = []

    for row in sample_rows[header_index + 1 :]:
        if _row_populated_count(row) < 2:
            continue
        padded = list(row) + [None] * (len(header) - len(row))
        record = {column: padded[idx] for idx, column in enumerate(header)}
        records.append(record)

    classification = classify_sheet(sheet_name, sample_rows)
    if not records:
        notes.append("No table-shaped data rows were detected below the inferred header row.")

    return NormalizedTable(
        sheet_name=sheet_name,
        classification=classification,
        header=header,
        rows=records,
        notes=notes,
    )


def normalize_curve_workbook(inspection: dict[str, Any]) -> CurveLibrary:
    """Convert workbook inspection output into a normalized curve library.

    Placeholder until real spreadsheet structure is inspected and mapped.
    The function now validates the available sheet shapes so workbook profiling
    yields something actionable before full curve parsing exists.
    """

    _ = [
        normalize_preview_table(sheet.get("sheet_name", ""), sheet.get("sample_rows", []))
        for sheet in inspection.get("sheet_previews", [])
    ]
    return CurveLibrary(curves=[])


def normalize_bpe_workbook(inspection: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert workbook inspection output into normalized BPE records.

    Returns preview-normalized table rows so the import path can be exercised
    before final mappings are defined.
    """

    normalized: list[dict[str, Any]] = []
    for sheet in inspection.get("sheet_previews", []):
        table = normalize_preview_table(sheet.get("sheet_name", ""), sheet.get("sample_rows", []))
        if table and table.classification == "bpe_table":
            normalized.extend(table.rows)
    return normalized


def normalize_inspection(inspection: dict[str, Any]) -> list[dict[str, Any]]:
    """Return preview-normalized tables for every inspected sheet."""

    tables: list[dict[str, Any]] = []
    for sheet in inspection.get("sheet_previews", []):
        table = normalize_preview_table(sheet.get("sheet_name", ""), sheet.get("sample_rows", []))
        if table is not None:
            tables.append(
                {
                    "sheet_name": table.sheet_name,
                    "classification": table.classification,
                    "header": table.header,
                    "row_count": len(table.rows),
                    "rows": table.rows,
                    "notes": table.notes,
                }
            )
    return tables
