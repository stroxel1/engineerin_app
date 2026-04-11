"""Case management helpers for saving and loading engineering studies."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any


class CaseStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _case_path(self, name: str) -> Path:
        safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name.strip())
        if not safe:
            raise ValueError("Case name must contain at least one alphanumeric character")
        return self.root / f"{safe}.json"

    def save(self, name: str, payload: Any) -> Path:
        if is_dataclass(payload):
            payload = asdict(payload)
        path = self._case_path(name)
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path

    def load(self, name: str) -> dict[str, Any]:
        path = self._case_path(name)
        return json.loads(path.read_text())

    def list_cases(self) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            stat = path.stat()
            cases.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "modified_time": stat.st_mtime,
                    "size_bytes": stat.st_size,
                }
            )
        return cases
