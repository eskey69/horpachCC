"""Excel report generation."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .constants import WORKSHEET_NAMES

HEADER_FILL = PatternFill(fill_type="solid", fgColor="D9E2F3")
SECTION_FILLS = {
    "PASS": PatternFill(fill_type="solid", fgColor="E2F0D9"),
    "REVIEW": PatternFill(fill_type="solid", fgColor="FFF2CC"),
    "HOLD_LOGISTICS": PatternFill(fill_type="solid", fgColor="F4CCCC"),
    "OUT_OF_STOCK": PatternFill(fill_type="solid", fgColor="D9D9D9"),
}
USD_COLUMNS = {"Current Regular Price", "Current Sale Price", "Benzara Regular Price", "Recommended Price Update"}
NUMERIC_COLUMNS = {"Weight lb", "Length in", "Width in", "Height in", "Volume in3", "Dim Weight lb", "Length + Girth in"}



def build_workbook() -> Workbook:
    workbook = Workbook()
    workbook.active.title = WORKSHEET_NAMES[0]
    for name in WORKSHEET_NAMES[1:]:
        workbook.create_sheet(title=name)
    return workbook



def _autosize_and_filter(worksheet) -> None:
    if worksheet.max_row >= 1 and worksheet.max_column >= 1:
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
    for column_cells in worksheet.columns:
        values = [str(cell.value) for cell in column_cells if cell.value is not None]
        width = min(max((len(value) for value in values), default=10) + 2, 50)
        worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = width



def _style_header(row) -> None:
    for cell in row:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL



def _apply_formats(worksheet) -> None:
    header_map = {cell.column: cell.value for cell in worksheet[1]}
    for row in worksheet.iter_rows(min_row=2):
        decision_value = None
        for cell in row:
            header = header_map.get(cell.column)
            if header in USD_COLUMNS and isinstance(cell.value, (int, float)):
                cell.number_format = '$#,##0.00'
            elif header in NUMERIC_COLUMNS and isinstance(cell.value, (int, float)):
                cell.number_format = '0.00'
            if header == "Catalog Decision":
                decision_value = cell.value
        fill = SECTION_FILLS.get(decision_value)
        if fill is not None:
            for cell in row:
                cell.fill = fill



def _write_table(worksheet, rows: list[dict]) -> None:
    if not rows:
        worksheet.append(["No rows"])
        _style_header(worksheet[1])
        _autosize_and_filter(worksheet)
        return
    headers = list(rows[0].keys())
    worksheet.append(headers)
    _style_header(worksheet[1])
    for row in rows:
        worksheet.append([row.get(header) for header in headers])
    _apply_formats(worksheet)
    _autosize_and_filter(worksheet)



def write_workbook(output_path: str | Path, report_sections: dict[str, list[dict]], summary_rows: list[dict], rules_rows: list[dict]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = build_workbook()

    summary_ws = workbook["SUMMARY"]
    _write_table(summary_ws, summary_rows)

    sheet_to_section = {
        "MATCHED_BENZARA": report_sections.get("MATCHED_BENZARA", []),
        "PRICE_UPDATE_PASS": report_sections.get("PRICE_UPDATE_PASS", []),
        "NEW_BENZARA_PASS": report_sections.get("NEW_BENZARA_PASS", []),
        "NEW_BENZARA_REVIEW": report_sections.get("NEW_BENZARA_REVIEW", []),
        "HOLD_LOGISTICS": report_sections.get("HOLD_LOGISTICS", []),
        "OUT_OF_STOCK": report_sections.get("OUT_OF_STOCK", []),
        "ORPHAN_STORE": report_sections.get("ORPHAN_STORE", []),
        "OTHER_SUPPLIER": report_sections.get("OTHER_SUPPLIER", []),
        "CONFLICTS": report_sections.get("CONFLICTS", []),
        "RULES_AND_CONFIG": rules_rows,
    }

    for sheet_name, rows in sheet_to_section.items():
        ws = workbook[sheet_name]
        _write_table(ws, rows)

    workbook.save(path)
    return path
