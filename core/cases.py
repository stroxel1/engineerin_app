"""Case management helpers for saving and loading engineering studies."""

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any


class CaseStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, payload: Any) -> Path:
        if is_dataclass(payload):
            payload = asdict(payload)
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2))
        return path
