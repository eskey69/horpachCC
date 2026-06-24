"""CSV export generation for price updates."""

from __future__ import annotations

import csv
from pathlib import Path

CSV_COLUMNS = [
    "SKU",
    "Regular price",
    "Sale price",
    "Meta: _horpach_catalog_decision",
    "Meta: _horpach_logistics_status",
    "Meta: _horpach_logistics_reasons",
]


def build_price_update_rows(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        if record.get("Catalog Decision") != "PASS":
            continue
        regular_price = record.get("Benzara Regular Price")
        sku = record.get("SKU")
        if sku in (None, "") or regular_price is None:
            continue
        rows.append(
            {
                "SKU": sku,
                "Regular price": regular_price,
                "Sale price": "",
                "Meta: _horpach_catalog_decision": record.get("Catalog Decision"),
                "Meta: _horpach_logistics_status": record.get("Logistics Status"),
                "Meta: _horpach_logistics_reasons": record.get("Logistics Reasons"),
            }
        )
    return rows


def _validate_unique_skus(rows: list[dict]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        sku = str(row.get("SKU") or "").strip()
        if not sku:
            continue
        if sku in seen:
            duplicates.add(sku)
        seen.add(sku)
    if duplicates:
        raise ValueError(f"Duplicate SKU values detected in price export: {sorted(duplicates)}")



def write_price_update_csv(output_path: str | Path, rows: list[dict]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _validate_unique_skus(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in CSV_COLUMNS})
    return path
