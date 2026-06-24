"""CSV export generation for price updates."""

from __future__ import annotations

from pathlib import Path


def build_price_update_rows(records: list[dict]) -> list[dict]:
    return list(records)


def write_price_update_csv(output_path: str | Path, rows: list[dict]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    _ = rows
    return path

