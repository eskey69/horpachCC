"""Excel report generation."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from .constants import WORKSHEET_NAMES


def build_workbook() -> Workbook:
    workbook = Workbook()
    workbook.active.title = WORKSHEET_NAMES[0]
    for name in WORKSHEET_NAMES[1:]:
        workbook.create_sheet(title=name)
    return workbook


def write_workbook(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = build_workbook()
    workbook.save(path)
    return path

