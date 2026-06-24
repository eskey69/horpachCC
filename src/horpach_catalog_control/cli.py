"""Command-line interface for the reporting pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import build_pipeline_outputs
from .benzara_parser import inspect_benzara_input, parse_benzara_xml
from .config import load_config
from .excel_report import (
    write_auto_hold_workbook,
    write_core_candidates_workbook,
    write_manual_review_workbook,
    write_workbook,
)
from .price_exports import build_price_update_rows, write_price_update_csv
from .utils import ensure_directory, summarize_file
from .woo_wxr_parser import inspect_woocommerce_input, parse_woocommerce_wxr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="horpach_catalog_control")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect-inputs", help="Inspect source input files.")
    inspect_parser.add_argument("--benzara-input", default="data/latest.xml")
    inspect_parser.add_argument("--woocommerce-input", default="data/horpachcom.WordPress.2026-06-24.xml")

    validate_parser = subparsers.add_parser("validate-config", help="Validate config.yaml.")
    validate_parser.add_argument("--config", default="config.yaml")

    run_parser = subparsers.add_parser("run", help="Run the local reporting pipeline.")
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


def _write_log(output_path: str | Path, lines: list[str]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _resolve_output_path(output_dir: str | Path, configured_path: str) -> Path:
    return Path(output_dir) / Path(configured_path).name


def _count_by_field(records: list[dict], field: str, value: str) -> int:
    return sum(1 for record in records if record.get(field) == value)


def _build_terminal_summary(outputs: dict, benzara_products: list[dict], woo_products: list[dict]) -> list[str]:
    all_records = outputs["all_records"]
    matches = outputs["match_results"]
    price_ready = len(outputs["price_rows"])
    price_excluded = len(outputs["report_sections"]["PRICE_UPDATE_EXCLUDED"])
    return [
        f"Benzara records: {len(benzara_products)}",
        f"WooCommerce products: {len(woo_products)}",
        f"Matched: {len(matches['MATCHED_BENZARA'])}",
        f"Price ready: {price_ready}",
        f"Price excluded: {price_excluded}",
        f"PASS logistics: {_count_by_field(all_records, 'Logistics Status', 'PASS_LOGISTICS')}",
        f"REVIEW logistics: {_count_by_field(all_records, 'Logistics Status', 'REVIEW_LOGISTICS')}",
        f"HOLD logistics: {_count_by_field(all_records, 'Logistics Status', 'HOLD_LOGISTICS')}",
        f"Out of stock: {_count_by_field(all_records, 'Commercial Status', 'OUT_OF_STOCK')}",
        f"Data quality critical: {_count_by_field(all_records, 'Data Quality Status', 'CRITICAL')}",
        f"Manual review queue: {len(outputs['manual_review_rows'])}",
        f"Core candidates: {len(outputs['core_candidate_rows'])}",
    ]


def _cmd_run(config_path: str, benzara_input: str, woocommerce_input: str, output_dir: str, dry_run: bool) -> int:
    settings = load_config(config_path)
    ensure_directory(output_dir)
    benzara_products = parse_benzara_xml(benzara_input)
    woo_products = parse_woocommerce_wxr(woocommerce_input)
    outputs = build_pipeline_outputs(settings, benzara_products, woo_products)
    summary_lines = _build_terminal_summary(outputs, benzara_products, woo_products)

    if dry_run:
        for line in summary_lines:
            print(line)
        print("Dry run complete.")
        return 0

    csv_path = _resolve_output_path(output_dir, settings.reporting.price_update_csv)
    workbook_path = _resolve_output_path(output_dir, settings.reporting.workbook)
    manual_review_path = _resolve_output_path(output_dir, settings.reporting.manual_review_workbook)
    auto_hold_path = _resolve_output_path(output_dir, settings.reporting.auto_hold_workbook)
    core_candidates_path = _resolve_output_path(output_dir, settings.reporting.core_candidates_workbook)
    log_path = _resolve_output_path(output_dir, settings.app.log_file)

    price_rows = build_price_update_rows(outputs["price_rows"])
    write_price_update_csv(csv_path, price_rows)
    write_workbook(workbook_path, outputs["report_sections"], outputs["summary_rows"], outputs["rules_rows"])
    write_manual_review_workbook(manual_review_path, outputs["manual_review_rows"])
    write_auto_hold_workbook(auto_hold_path, outputs["auto_hold_summary_rows"], outputs["auto_hold_sections"])
    write_core_candidates_workbook(core_candidates_path, outputs["core_candidate_rows"])
    _write_log(log_path, outputs["log_lines"])

    for line in summary_lines:
        print(line)
    print("Output files:")
    print(f"- {csv_path}")
    print(f"- {workbook_path}")
    print(f"- {manual_review_path}")
    print(f"- {auto_hold_path}")
    print(f"- {core_candidates_path}")
    print(f"- {log_path}")
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
