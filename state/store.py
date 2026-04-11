"""Minimal central state store."""

from __future__ import annotations

from dataclasses import replace

from engineering_app.state.models import AppState


class AppStore:
    def __init__(self, initial_state: AppState | None = None):
        self.state = initial_state or AppState()

    def set_screen(self, screen: str) -> None:
        self.state.ui = replace(self.state.ui, current_screen=screen)

    def set_curve_workbook(self, path: str) -> None:
        self.state.imports = replace(self.state.imports, curve_workbook_path=path)

    def set_bpe_workbook(self, path: str) -> None:
        self.state.imports = replace(self.state.imports, bpe_workbook_path=path)
