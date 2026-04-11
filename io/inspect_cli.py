"""CLI for inspecting and classifying engineering workbooks.

Usage:
    python -m engineering_app.io.inspect_cli path/to/workbook.xlsx
    python -m engineering_app.io.inspect_cli path/to/workbook.xlsx --normalized
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from engineering_app.io.normalizers import normalize_inspection
from engineering_app.io.schema_inference import classify_sheet
from engineering_app.io.workbook_inspector import inspect_workbook, WorkbookInspectorError


def build_summary(inspection: dict[str, Any], include_normalized: bool = False) -> dict[str, Any]:
    sheet_summaries = []

    for sheet in inspection.get("sheet_previews", []):
        sample_rows = sheet.get("sample_rows", [])
        sheet_summaries.append(
            {
                "sheet_name": sheet.get("sheet_name"),
                "dimensions": {
                    "max_row": sheet.get("max_row"),
                    "max_column": sheet.get("max_column"),
                },
                "hidden": sheet.get("hidden", False),
                "freeze_panes": sheet.get("freeze_panes"),
                "merged_ranges": sheet.get("merged_ranges", []),
                "formula_cell_count": sheet.get("formula_cell_count", 0),
                "header_candidates": sheet.get("header_candidates", []),
                "stats": sheet.get("stats", {}),
                "classification": classify_sheet(sheet.get("sheet_name", ""), sample_rows),
                "sample_rows": sample_rows,
            }
        )

    payload = {
        "source": inspection.get("source", {}),
        "sheet_count": len(sheet_summaries),
        "sheets": sheet_summaries,
    }
    if include_normalized:
        payload["normalized_tables"] = normalize_inspection(inspection)
    return payload


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print(
            "Usage: python -m engineering_app.io.inspect_cli path/to/workbook.xlsx [--normalized]",
            file=sys.stderr,
        )
        return 2

    include_normalized = "--normalized" in argv
    positional = [arg for arg in argv if arg != "--normalized"]
    if not positional:
        print("Workbook path is required", file=sys.stderr)
        return 2

    path = Path(positional[0]).expanduser()
    if not path.exists():
        print(f"Workbook not found: {path}", file=sys.stderr)
        return 1

    try:
        inspection = inspect_workbook(path)
    except WorkbookInspectorError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(build_summary(inspection, include_normalized=include_normalized), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
