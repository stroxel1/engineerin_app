"""Main entrypoint for the citric process engineering app.

This is intentionally scaffolded first so the project structure is in place
before runtime package installation and workbook inspection are available.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class AppSection:
    key: str
    title: str
    description: str


SECTIONS: List[AppSection] = [
    AppSection(
        key="ejectors",
        title="Steam Jets / Thermo-Compressors",
        description="Compare operating points to imported performance curves.",
    ),
    AppSection(
        key="evaporators",
        title="Evaporators",
        description="Develop operating parameters for falling film and multi-pass systems.",
    ),
    AppSection(
        key="crystallizers",
        title="Crystallizers",
        description="Model forced-circulation crystallizer operating conditions.",
    ),
    AppSection(
        key="cases",
        title="Case Manager",
        description="Save and revisit process cases, assumptions, and notes.",
    ),
]


def get_app_manifest() -> Dict[str, List[dict]]:
    return {
        "sections": [
            {"key": s.key, "title": s.title, "description": s.description}
            for s in SECTIONS
        ]
    }


if __name__ == "__main__":
    import json

    print(json.dumps(get_app_manifest(), indent=2))
