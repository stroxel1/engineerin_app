"""Normalization helpers for workbook-derived engineering data.

These routines are intentionally conservative: they extract table-shaped data
from workbook previews so real source spreadsheets can be mapped quickly once
available, without pretending we already know the vendor sheet schema.
"""

from __future__ import annotations

from typing import Any

from engineering_app.core.curves import CurveLibrary, build_curve_library_from_table
from engineering_app.io.contracts import NormalizedTable
from engineering_app.io.schema_inference import classify_sheet

NAME_TOKENS = {"model", "curve", "curve_name", "model_name", "tag", "name", "ejector", "compressor"}
FAMILY_TOKENS = {"family", "basis", "series", "service", "motive", "steam", "pressure", "header", "discharge"}
X_TOKENS = {"load", "suction", "capacity", "flow", "vapour", "vapor", "evap", "lb_hr", "kg_h"}
Y_TOKENS = {"steam", "consumption", "motive", "head", "duty", "ratio", "entrainment", "discharge"}
PRESSURE_TOKENS = {"pressure", "psig", "psia", "barg", "bara", "kpa", "mbar"}


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


def _label_tokens(value: str) -> set[str]:
    cleaned = (
        str(value)
        .strip()
        .lower()
        .replace("%", " pct ")
        .replace("/", " ")
        .replace("-", " ")
        .replace("_", " ")
        .replace("(", " ")
        .replace(")", " ")
    )
    return {token for token in cleaned.split() if token}


def _is_numeric_like(value: Any) -> bool:
    if value in (None, "") or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return False
    return True


def _numeric_fraction(rows: list[dict[str, Any]], column: str) -> float:
    values = [row.get(column) for row in rows if row.get(column) not in (None, "")]
    if not values:
        return 0.0
    numeric = sum(1 for value in values if _is_numeric_like(value))
    return numeric / len(values)


def _distinct_values(rows: list[dict[str, Any]], column: str) -> list[str]:
    seen: list[str] = []
    for row in rows:
        value = row.get(column)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def _column_score(
    column: str,
    rows: list[dict[str, Any]],
    preferred_tokens: set[str],
    *,
    penalty_tokens: set[str] | None = None,
    require_numeric: bool = False,
) -> float:
    tokens = _label_tokens(column)
    score = float(len(tokens & preferred_tokens) * 10)
    if column.lower() in preferred_tokens:
        score += 12.0
    numeric_fraction = _numeric_fraction(rows, column)
    if require_numeric:
        score += numeric_fraction * 15.0
    elif numeric_fraction >= 0.8:
        score += 1.0
    if penalty_tokens:
        score -= float(len(tokens & penalty_tokens) * 8)
    if len(_distinct_values(rows, column)) <= 1:
        score -= 2.0
    return score


def _pick_column(
    rows: list[dict[str, Any]],
    columns: list[str],
    preferred_tokens: set[str],
    *,
    penalty_tokens: set[str] | None = None,
    require_numeric: bool = False,
    excluded: set[str] | None = None,
) -> str | None:
    excluded = excluded or set()
    ranked: list[tuple[float, str]] = []
    for column in columns:
        if column in excluded:
            continue
        score = _column_score(
            column,
            rows,
            preferred_tokens,
            penalty_tokens=penalty_tokens,
            require_numeric=require_numeric,
        )
        if require_numeric and _numeric_fraction(rows, column) < 0.6:
            continue
        ranked.append((score, column))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    best_score, best_column = ranked[0]
    if best_score <= 0:
        return None
    return best_column


def _derive_family_columns(rows: list[dict[str, Any]], columns: list[str], excluded: set[str]) -> list[str]:
    family_columns: list[str] = []
    for column in columns:
        if column in excluded:
            continue
        values = _distinct_values(rows, column)
        if len(values) <= 1 or len(values) > 6:
            continue
        tokens = _label_tokens(column)
        if tokens & FAMILY_TOKENS:
            family_columns.append(column)
    return family_columns


def _format_family_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value).strip()


def _attach_family_label(rows: list[dict[str, Any]], family_column: str | None, derived_columns: list[str]) -> tuple[list[dict[str, Any]], str | None]:
    if family_column:
        family_tokens = _label_tokens(family_column)
        if family_tokens & {"family", "basis", "series"} and not family_tokens & PRESSURE_TOKENS:
            return rows, family_column
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            copied = dict(row)
            value = row.get(family_column)
            copied["__normalized_family"] = (
                f"{family_column}={_format_family_value(value)}" if value not in (None, "") else "screening-basis"
            )
            normalized_rows.append(copied)
        return normalized_rows, "__normalized_family"
    if not derived_columns:
        return rows, None

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        family_parts: list[str] = []
        for column in derived_columns:
            value = row.get(column)
            if value in (None, ""):
                continue
            family_parts.append(f"{column}={_format_family_value(value)}")
        copied = dict(row)
        copied["__normalized_family"] = " | ".join(family_parts) if family_parts else "screening-basis"
        normalized_rows.append(copied)
    return normalized_rows, "__normalized_family"


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

    Uses preview rows only, so results remain a screening aid. The goal is to
    recover useful candidate curves even when vendor workbooks use motive-basis
    columns instead of an explicit family field.
    """

    normalized_tables = [
        normalize_preview_table(sheet.get("sheet_name", ""), sheet.get("sample_rows", []))
        for sheet in inspection.get("sheet_previews", [])
    ]

    combined_curves = []
    notes: list[str] = []
    for table in normalized_tables:
        if table is None or table.classification != "curve_table" or not table.rows:
            continue

        columns = list(table.header)
        name_col = _pick_column(table.rows, columns, NAME_TOKENS, require_numeric=False)
        x_col = _pick_column(table.rows, columns, X_TOKENS, require_numeric=True)
        y_col = _pick_column(
            table.rows,
            columns,
            Y_TOKENS,
            penalty_tokens=PRESSURE_TOKENS,
            require_numeric=True,
            excluded={x_col} if x_col else None,
        )
        explicit_family_col = _pick_column(
            table.rows,
            columns,
            {"family", "basis", "series"},
            require_numeric=False,
            excluded={name_col, x_col, y_col} - {None},
        )

        if not name_col or not x_col or not y_col:
            notes.append(
                f"Skipped sheet '{table.sheet_name}' because a model/name, x, or y column could not be inferred from the preview rows."
            )
            continue

        derived_family_columns = _derive_family_columns(table.rows, columns, {name_col, x_col, y_col, explicit_family_col} - {None})
        rows_with_family, family_label = _attach_family_label(table.rows, explicit_family_col, derived_family_columns)
        library = build_curve_library_from_table(
            rows_with_family,
            x_label=x_col,
            y_label=y_col,
            curve_name_label=name_col,
            family_label=family_label,
            source_sheet=table.sheet_name,
        )
        if library.curves:
            combined_curves.extend(library.curves)
            if explicit_family_col:
                notes.append(
                    f"Sheet '{table.sheet_name}' normalized using {name_col} / {x_col} / {y_col} with explicit family column '{explicit_family_col}'."
                )
            elif derived_family_columns:
                notes.append(
                    f"Sheet '{table.sheet_name}' normalized using derived family basis from {', '.join(derived_family_columns)}."
                )
            else:
                notes.append(
                    f"Sheet '{table.sheet_name}' normalized using {name_col} / {x_col} / {y_col} with no family split detected."
                )
        else:
            notes.append(
                f"Sheet '{table.sheet_name}' looked like a curve table, but fewer than two numeric x/y rows were available per model in the preview window."
            )

    if not combined_curves and not notes:
        notes.append("No curve-like workbook previews were detected for normalization.")
    return CurveLibrary(curves=combined_curves, notes=notes)


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
