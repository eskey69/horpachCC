"""Command-line interface for the project skeleton."""

from __future__ import annotations

import argparse
from pathlib import Path

from .benzara_parser import inspect_benzara_input, parse_benzara_xml
from .config import load_config
from .excel_report import write_workbook
from .matcher import match_products
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


def _cmd_run(config_path: str, benzara_input: str, woocommerce_input: str, output_dir: str, dry_run: bool) -> int:
    settings = load_config(config_path)
    ensure_directory(output_dir)
    benzara_products = parse_benzara_xml(benzara_input)
    woo_products = parse_woocommerce_wxr(woocommerce_input)
    matches = match_products(benzara_products, woo_products)
    rows = build_price_update_rows(matches["MATCHED_BENZARA"])

    if dry_run:
        print("Dry run complete.")
        print(f"Config: {settings.app.name}")
        print(f"Benzara records: {len(benzara_products)}")
        print(f"WooCommerce records: {len(woo_products)}")
        print(f"Matched records: {len(matches['MATCHED_BENZARA'])}")
        return 0

    csv_path = Path(output_dir) / Path(settings.reporting.price_update_csv).name
    workbook_path = Path(output_dir) / Path(settings.reporting.workbook).name
    write_price_update_csv(csv_path, rows)
    write_workbook(workbook_path)
    print(f"Wrote CSV: {csv_path}")
    print(f"Wrote workbook: {workbook_path}")
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

