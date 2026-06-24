"""Command-line interface for the project skeleton."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .benzara_parser import inspect_benzara_input, parse_benzara_xml
from .config import load_config
from .decisions import decide_catalog_status
from .excel_report import write_workbook
from .logistics import evaluate_logistics
from .matcher import match_products
from .price_exports import build_price_update_rows, write_price_update_csv
from .utils import ensure_directory, summarize_file
from .woo_wxr_parser import inspect_woocommerce_input, parse_woocommerce_wxr

MATCHED_COLUMNS = [
    "WooCommerce ID",
    "SKU",
    "Current Title",
    "Current Status",
    "Current Regular Price",
    "Current Sale Price",
    "Current Stock Qty",
    "Current Stock Status",
    "Current Categories",
    "Benzara Name",
    "Benzara Brand",
    "Primary Category",
    "Benzara EAN",
    "Benzara Regular Price",
    "Benzara Stock Qty",
    "Benzara Stock Status",
    "Weight lb",
    "Length in",
    "Width in",
    "Height in",
    "Volume in3",
    "Dim Weight lb",
    "Length + Girth in",
    "Logistics Status",
    "Logistics Reasons",
    "Catalog Decision",
    "Recommended Price Update",
    "Match Strategy",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="horpach_catalog_control")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect-inputs", help="Inspect source input files.")
    inspect_parser.add_argument("--benzara-input", default="data/latest.xml")
    inspect_parser.add_argument("--woocommerce-input", default="data/horpachcom.WordPress.2026-06-24.xml")

    validate_parser = subparsers.add_parser("validate-config", help="Validate config.yaml.")
    validate_parser.add_argument("--config", default="config.yaml")

    run_parser = subparsers.add_parser("run", help="Run the local reporting pipeline skeleton.")
    run_parser.add_argument("--config", default="config.yaml")
    run_parser.add_argument("--benzara-input", default="data/latest.xml")
    run_parser.add_argument("--woocommerce-input", default="data/horpachcom.WordPress.2026-06-24.xml")
    run_parser.add_argument("--output-dir", default="output")
    run_parser.add_argument("--dry-run", action="store_true")

    return parser


def _cmd_validate_config(config_path: str) -> int:
    settings = load_config(config_path)
    print(f"Config valid: {settings.app.name}")
    return 0


def _cmd_inspect_inputs(benzara_input: str, woocommerce_input: str) -> int:
    print(summarize_file(benzara_input))
    print(summarize_file(woocommerce_input))
    print(inspect_benzara_input(benzara_input))
    print(inspect_woocommerce_input(woocommerce_input))
    return 0


def _primary_category(categories: list[str] | None) -> str | None:
    if not categories:
        return None
    return categories[0]


def _matched_row(match: dict, logistics_config) -> dict:
    benzara = match["benzara"]
    woo = match["woo"]
    logistics = evaluate_logistics(benzara, config=logistics_config)
    decision = decide_catalog_status(benzara, logistics)
    return {
        "WooCommerce ID": woo.get("post_id"),
        "SKU": benzara.get("sku") or woo.get("sku"),
        "Current Title": woo.get("title"),
        "Current Status": woo.get("post_status"),
        "Current Regular Price": woo.get("regular_price"),
        "Current Sale Price": woo.get("sale_price"),
        "Current Stock Qty": woo.get("stock_qty"),
        "Current Stock Status": woo.get("stock_status"),
        "Current Categories": ", ".join(woo.get("categories") or []),
        "Woo Shipping Class": woo.get("shipping_class"),
        "Benzara Name": benzara.get("name"),
        "Benzara Brand": benzara.get("brand"),
        "Primary Category": _primary_category(benzara.get("categories")),
        "Benzara EAN": benzara.get("ean"),
        "Benzara Regular Price": benzara.get("regular_price"),
        "Benzara Stock Qty": benzara.get("stock_qty"),
        "Benzara Stock Status": benzara.get("stock_status"),
        "Weight lb": logistics.metrics.billable_weight_lb if logistics.metrics.billable_weight_lb is not None else benzara.get("weight_lb"),
        "Length in": benzara.get("length_in"),
        "Width in": benzara.get("width_in"),
        "Height in": benzara.get("height_in"),
        "Volume in3": logistics.metrics.volume_in3,
        "Dim Weight lb": logistics.metrics.dim_weight_lb,
        "Length + Girth in": logistics.metrics.length_plus_girth_in,
        "Logistics Status": logistics.status.value,
        "Logistics Reasons": ", ".join(logistics.reason_codes),
        "Catalog Decision": decision.value,
        "Recommended Price Update": benzara.get("regular_price") if decision.value == "PASS" else None,
        "Match Strategy": match.get("match_strategy"),
    }


def _benzara_only_row(benzara: dict, logistics_config) -> dict:
    logistics = evaluate_logistics(benzara, config=logistics_config)
    decision = decide_catalog_status(benzara, logistics)
    return {
        "WooCommerce ID": None,
        "SKU": benzara.get("sku"),
        "Current Title": None,
        "Current Status": None,
        "Current Regular Price": None,
        "Current Sale Price": None,
        "Current Stock Qty": None,
        "Current Stock Status": None,
        "Current Categories": None,
        "Woo Shipping Class": None,
        "Benzara Name": benzara.get("name"),
        "Benzara Brand": benzara.get("brand"),
        "Primary Category": _primary_category(benzara.get("categories")),
        "Benzara EAN": benzara.get("ean"),
        "Benzara Regular Price": benzara.get("regular_price"),
        "Benzara Stock Qty": benzara.get("stock_qty"),
        "Benzara Stock Status": benzara.get("stock_status"),
        "Weight lb": benzara.get("weight_lb"),
        "Length in": benzara.get("length_in"),
        "Width in": benzara.get("width_in"),
        "Height in": benzara.get("height_in"),
        "Volume in3": logistics.metrics.volume_in3,
        "Dim Weight lb": logistics.metrics.dim_weight_lb,
        "Length + Girth in": logistics.metrics.length_plus_girth_in,
        "Logistics Status": logistics.status.value,
        "Logistics Reasons": ", ".join(logistics.reason_codes),
        "Catalog Decision": decision.value,
        "Recommended Price Update": None,
        "Match Strategy": "new_benzara",
    }


def _woo_only_row(woo: dict, decision: str) -> dict:
    return {
        "WooCommerce ID": woo.get("post_id"),
        "SKU": woo.get("sku"),
        "Current Title": woo.get("title"),
        "Current Status": woo.get("post_status"),
        "Current Regular Price": woo.get("regular_price"),
        "Current Sale Price": woo.get("sale_price"),
        "Current Stock Qty": woo.get("stock_qty"),
        "Current Stock Status": woo.get("stock_status"),
        "Current Categories": ", ".join(woo.get("categories") or []),
        "Woo Shipping Class": woo.get("shipping_class"),
        "Benzara Name": None,
        "Benzara Brand": None,
        "Primary Category": None,
        "Benzara EAN": None,
        "Benzara Regular Price": None,
        "Benzara Stock Qty": None,
        "Benzara Stock Status": None,
        "Weight lb": woo.get("weight_lb"),
        "Length in": woo.get("length_in"),
        "Width in": woo.get("width_in"),
        "Height in": woo.get("height_in"),
        "Volume in3": None,
        "Dim Weight lb": None,
        "Length + Girth in": None,
        "Logistics Status": None,
        "Logistics Reasons": None,
        "Catalog Decision": decision,
        "Recommended Price Update": None,
        "Match Strategy": None,
    }


def _conflict_row(conflict: dict) -> dict:
    return {
        "Conflict Type": conflict.get("type"),
        "SKU": conflict.get("sku"),
        "EAN": conflict.get("ean"),
        "Woo Candidate Count": len(conflict.get("woo_candidates") or []),
        "Woo Title": (conflict.get("woo") or {}).get("title") if conflict.get("woo") else None,
        "Benzara Name": (conflict.get("benzara") or {}).get("name") if conflict.get("benzara") else None,
    }


def _counter_rows(counter: Counter, section: str, label: str) -> list[dict]:
    rows: list[dict] = []
    for key, value in counter.most_common():
        rows.append({"Section": section, "Metric": label, "Key": key, "Value": value})
    return rows


def _build_summary_rows(matches: dict[str, list[dict]], matched_rows: list[dict], new_rows: list[dict], orphan_rows: list[dict], other_supplier_rows: list[dict], sections: dict[str, list[dict]]) -> list[dict]:
    summary: list[dict] = [
        {"Section": "Counts", "Metric": "WooCommerce products", "Key": "total", "Value": len(matches["MATCHED_BENZARA"]) + len(matches["ORPHAN_STORE"]) + len(matches["OTHER_SUPPLIER"]) + len(matches["CONFLICT"])},
        {"Section": "Counts", "Metric": "Benzara products", "Key": "total", "Value": len(matches["MATCHED_BENZARA"]) + len(matches["NEW_BENZARA"]) + len(matches["CONFLICT"])},
        {"Section": "Counts", "Metric": "Shared SKU matches", "Key": "total", "Value": len(matches["MATCHED_BENZARA"])},
        {"Section": "Counts", "Metric": "New Benzara", "Key": "total", "Value": len(matches["NEW_BENZARA"])},
        {"Section": "Counts", "Metric": "Orphan store", "Key": "total", "Value": len(matches["ORPHAN_STORE"])},
        {"Section": "Counts", "Metric": "Other supplier", "Key": "total", "Value": len(matches["OTHER_SUPPLIER"])},
        {"Section": "Counts", "Metric": "Conflicts", "Key": "total", "Value": len(matches["CONFLICT"])},
        {"Section": "Counts", "Metric": "PASS", "Key": "total", "Value": len(sections["PRICE_UPDATE_PASS"]) + len(sections["NEW_BENZARA_PASS"])},
        {"Section": "Counts", "Metric": "REVIEW", "Key": "total", "Value": len(sections["NEW_BENZARA_REVIEW"]) + len([row for row in matched_rows if row["Catalog Decision"] == "REVIEW"])},
        {"Section": "Counts", "Metric": "HOLD_LOGISTICS", "Key": "total", "Value": len(sections["HOLD_LOGISTICS"])},
        {"Section": "Counts", "Metric": "OUT_OF_STOCK", "Key": "total", "Value": len(sections["OUT_OF_STOCK"])},
        {"Section": "Counts", "Metric": "PRICE_UPDATE_PASS", "Key": "total", "Value": len(sections["PRICE_UPDATE_PASS"])},
    ]

    all_benzara_rows = matched_rows + new_rows
    all_woo_rows = matched_rows + orphan_rows + other_supplier_rows
    category_counter = Counter(row.get("Primary Category") or "Uncategorized" for row in all_benzara_rows)
    brand_counter = Counter(row.get("Benzara Brand") or "Unknown" for row in all_benzara_rows)
    decision_counter = Counter(row.get("Catalog Decision") or "Unknown" for row in all_benzara_rows)
    shipping_class_counter = Counter(row.get("Woo Shipping Class") or "None" for row in all_woo_rows)
    woo_status_counter = Counter(row.get("Current Stock Status") or "Unknown" for row in all_woo_rows)

    summary.extend(_counter_rows(category_counter, "Breakdown", "Primary Category"))
    summary.extend(_counter_rows(brand_counter, "Breakdown", "Brand"))
    summary.extend(_counter_rows(decision_counter, "Breakdown", "Catalog Decision"))
    summary.extend(_counter_rows(shipping_class_counter, "Woo Breakdown", "Shipping Class"))
    summary.extend(_counter_rows(woo_status_counter, "Woo Breakdown", "Stock Status"))
    return summary


def _build_sections(matches: dict[str, list[dict]], logistics_config) -> tuple[dict[str, list[dict]], list[dict]]:
    matched_rows = [_matched_row(match, logistics_config) for match in matches["MATCHED_BENZARA"]]
    new_rows = [_benzara_only_row(record, logistics_config) for record in matches["NEW_BENZARA"]]
    orphan_rows = [_woo_only_row(record, "ORPHAN") for record in matches["ORPHAN_STORE"]]
    other_supplier_rows = [_woo_only_row(record, "OTHER_SUPPLIER") for record in matches["OTHER_SUPPLIER"]]
    conflict_rows = [_conflict_row(record) for record in matches["CONFLICT"]]

    sections = {
        "MATCHED_BENZARA": matched_rows,
        "PRICE_UPDATE_PASS": [row for row in matched_rows if row["Catalog Decision"] == "PASS"],
        "NEW_BENZARA_PASS": [row for row in new_rows if row["Catalog Decision"] == "PASS"],
        "NEW_BENZARA_REVIEW": [row for row in new_rows if row["Catalog Decision"] == "REVIEW"],
        "HOLD_LOGISTICS": [row for row in matched_rows + new_rows if row.get("Catalog Decision") == "HOLD_LOGISTICS"],
        "OUT_OF_STOCK": [row for row in matched_rows + new_rows if row.get("Catalog Decision") == "OUT_OF_STOCK"],
        "ORPHAN_STORE": orphan_rows,
        "OTHER_SUPPLIER": other_supplier_rows,
        "CONFLICTS": conflict_rows,
    }

    summary = _build_summary_rows(matches, matched_rows, new_rows, orphan_rows, other_supplier_rows, sections)
    return sections, summary


def _build_rules_rows(settings) -> list[dict]:
    return [
        {"Rule": "dim_divisor", "Value": settings.logistics.dim_divisor},
        {"Rule": "hold.actual_weight_lb_gt", "Value": settings.logistics.hold.actual_weight_lb_gt},
        {"Rule": "hold.longest_side_in_gt", "Value": settings.logistics.hold.longest_side_in_gt},
        {"Rule": "hold.length_plus_girth_in_gt", "Value": settings.logistics.hold.length_plus_girth_in_gt},
        {"Rule": "hold.volume_in3_gt", "Value": settings.logistics.hold.volume_in3_gt},
        {"Rule": "hold.dim_weight_lb_gt", "Value": settings.logistics.hold.dim_weight_lb_gt},
        {"Rule": "review.actual_weight_lb_min", "Value": settings.logistics.review.actual_weight_lb_min},
        {"Rule": "review.actual_weight_lb_max", "Value": settings.logistics.review.actual_weight_lb_max},
        {"Rule": "review.longest_side_in_min", "Value": settings.logistics.review.longest_side_in_min},
        {"Rule": "review.longest_side_in_max", "Value": settings.logistics.review.longest_side_in_max},
    ]


def _write_log(output_dir: str | Path, lines: list[str]) -> Path:
    path = Path(output_dir) / 'run.log'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def _cmd_run(config_path: str, benzara_input: str, woocommerce_input: str, output_dir: str, dry_run: bool) -> int:
    settings = load_config(config_path)
    ensure_directory(output_dir)
    benzara_products = parse_benzara_xml(benzara_input)
    woo_products = parse_woocommerce_wxr(woocommerce_input)
    matches = match_products(benzara_products, woo_products)
    report_sections, summary_rows = _build_sections(matches, settings.logistics)
    price_rows = build_price_update_rows(report_sections["MATCHED_BENZARA"])
    rules_rows = _build_rules_rows(settings)

    log_lines = [
        f"config={settings.app.name}",
        f"benzara_records={len(benzara_products)}",
        f"woocommerce_records={len(woo_products)}",
        *(f"bucket.{key}={len(value)}" for key, value in matches.items()),
        f"price_update_rows={len(price_rows)}",
    ]

    if dry_run:
        print("Dry run complete.")
        print(f"Config: {settings.app.name}")
        print(f"Benzara records: {len(benzara_products)}")
        print(f"WooCommerce records: {len(woo_products)}")
        print(f"Matched records: {len(matches['MATCHED_BENZARA'])}")
        print(f"Price update rows: {len(price_rows)}")
        return 0

    csv_path = Path(output_dir) / Path(settings.reporting.price_update_csv).name
    workbook_path = Path(output_dir) / Path(settings.reporting.workbook).name
    log_path = _write_log(output_dir, log_lines)
    write_price_update_csv(csv_path, price_rows)
    write_workbook(workbook_path, report_sections, summary_rows, rules_rows)
    print(f"Wrote CSV: {csv_path}")
    print(f"Wrote workbook: {workbook_path}")
    print(f"Wrote log: {log_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-config":
        return _cmd_validate_config(args.config)
    if args.command == "inspect-inputs":
        return _cmd_inspect_inputs(args.benzara_input, args.woocommerce_input)
    if args.command == "run":
        return _cmd_run(
            args.config,
            args.benzara_input,
            args.woocommerce_input,
            args.output_dir,
            args.dry_run,
        )
    parser.error(f"Unsupported command: {args.command}")
    return 2
