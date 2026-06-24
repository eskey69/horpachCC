# Horpach Catalog Control

## Krotkie podsumowanie (PL)

To repo zawiera lokalna aplikacje Python do analizy katalogu Benzara i eksportu WooCommerce dla Horpach.com. Narzedzie tworzy raporty XLSX i CSV do bezpiecznej oceny dopasowan, logistyki, jakosci danych, wykluczen cenowych i kolejek do recznej weryfikacji. MVP v1 nadal nie wykonuje zadnych zmian w WooCommerce, WordPressie, FTP, MySQL ani innych systemach produkcyjnych.

## Overview

Horpach Catalog Control compares the current Benzara operational catalog with a WooCommerce WordPress WXR export and produces decision-support outputs for catalog safety checks.

The pipeline now answers:

- which products are matched to the current Benzara feed
- why a matched product is `PRICE_READY` or excluded from price import
- which products are `PASS`, `REVIEW`, `HOLD_LOGISTICS`, `OUT_OF_STOCK`, `ORPHAN`, `OTHER_SUPPLIER`, or `CONFLICT`
- which products have missing or invalid operational data
- which orphaned WooCommerce products look like historical Benzara products
- which records need manual review before any future import step

## Scope

The current implementation:

- parses and normalizes Benzara XML feed data
- parses and normalizes WooCommerce products from WordPress WXR export
- matches products primarily by SKU with controlled EAN fallback
- evaluates logistics using configurable thresholds and keyword heuristics
- separates `logistics_status`, `commercial_status`, and `catalog_decision`
- classifies price-update eligibility with explicit exclusion reasons
- scores data quality issues and duplicate identifiers
- classifies likely supplier origin for orphaned store products
- generates management reports, a CSV price-update export, and a manual-review workbook

## Non-Goals

The tool does not:

- call WooCommerce REST API
- modify WordPress, WooCommerce, MySQL, FTP, or production data
- import CSV files into production
- generate AI titles, descriptions, or bundle logic
- delete products, media, or catalog records
- invent missing values

## Repository Layout

```text
horpachCC/
|-- README.md
|-- CHANGELOG.md
|-- config.yaml
|-- data/
|-- docs/
|-- output/
|-- horpach_catalog_control/
|-- src/
`-- tests/
```

## Inputs

Place source files in `data/`:

- `data/latest.xml`
- `data/horpachcom.WordPress.2026-06-24.xml`

Optional validation source:

- `FTP Benzara JUNE (15-06-2026).xlsx`

## Installation

Install dependencies into your local Python environment:

```bash
python -m pip install -r requirements.txt
```

The repository includes a lightweight package wrapper so the CLI can be run directly from the source checkout with:

```bash
python -m horpach_catalog_control ...
```

## CLI

Supported commands:

```bash
python -m horpach_catalog_control inspect-inputs
python -m horpach_catalog_control validate-config
python -m horpach_catalog_control run
python -m horpach_catalog_control run --dry-run
```

Example run:

```bash
python -m horpach_catalog_control run \
  --benzara-input data/latest.xml \
  --woocommerce-input data/horpachcom.WordPress.2026-06-24.xml \
  --output-dir output
```

Normal run prints a concise summary for:

- Benzara records
- WooCommerce products
- matched products
- price-ready and price-excluded counts
- logistics breakdown
- out-of-stock count
- critical data-quality count
- manual review queue size
- output file paths

## Outputs

Main workbook:

```text
output/HORPACH_CATALOG_CONTROL_REPORT.xlsx
```

Price update CSV:

```text
output/IMPORT_PRICE_UPDATE_BENZARA_PASS.csv
```

Manual review workbook:

```text
output/MANUAL_REVIEW_QUEUE.xlsx
```

Run log:

```text
output/run.log
```

### Main workbook sheets

- `SUMMARY`
- `MATCHED_BENZARA`
- `PRICE_UPDATE_PASS`
- `PRICE_UPDATE_EXCLUDED`
- `NEW_BENZARA_PASS`
- `NEW_BENZARA_REVIEW`
- `HOLD_LOGISTICS`
- `OUT_OF_STOCK`
- `ORPHAN_STORE`
- `OTHER_SUPPLIER`
- `CONFLICTS`
- `DATA_QUALITY`
- `SUPPLIER_CLASSIFICATION`
- `LOGISTICS_DIAGNOSTICS`
- `RULES_AND_CONFIG`

## Status Model

### Match buckets

- `MATCHED_BENZARA`
- `NEW_BENZARA`
- `ORPHAN_STORE`
- `OTHER_SUPPLIER`
- `CONFLICT`

### Logistics statuses

- `PASS_LOGISTICS`
- `REVIEW_LOGISTICS`
- `HOLD_LOGISTICS`

### Commercial statuses

- `PRICE_READY`
- `PRICE_REVIEW`
- `OUT_OF_STOCK`
- `ORPHAN`
- `OTHER_SUPPLIER`
- `CONFLICT`
- `MISSING_DATA`

### Catalog decisions

- `PASS`
- `REVIEW`
- `HOLD_LOGISTICS`
- `OUT_OF_STOCK`
- `ORPHAN`
- `OTHER_SUPPLIER`
- `CONFLICT`

### Price update statuses

- `PRICE_READY`
- `EXCLUDED_OUT_OF_STOCK`
- `EXCLUDED_HOLD_LOGISTICS`
- `EXCLUDED_REVIEW_LOGISTICS`
- `EXCLUDED_MISSING_BENZARA_PRICE`
- `EXCLUDED_INVALID_BENZARA_PRICE`
- `EXCLUDED_BUNDLE_PRODUCT`
- `EXCLUDED_MISSING_SKU`
- `EXCLUDED_CONFLICT`
- `EXCLUDED_OTHER`

### Data quality statuses

- `OK`
- `REVIEW`
- `CRITICAL`

### Supplier classifications

- `BENZARA_MATCHED`
- `BENZARA_ORPHAN_SUSPECTED`
- `OTHER_SUPPLIER_CONFIRMED`
- `UNKNOWN_SUPPLIER`

## Report Features

`PRICE_UPDATE_EXCLUDED` explains every matched Benzara record that did not qualify for CSV export.

`DATA_QUALITY` highlights missing, invalid, or duplicate identifiers and operational values.

`SUPPLIER_CLASSIFICATION` distinguishes likely historical Benzara store products from genuine non-Benzara products.

`LOGISTICS_DIAGNOSTICS` exposes actual dimensions, billable weight, threshold hits, and missing-data flags for non-pass items.

`MANUAL_REVIEW_QUEUE.xlsx` combines logistics review, critical data issues, suspected historical Benzara orphans, unknown suppliers, and non-obvious price exclusions into one queue.

## Configuration

All operational rules live in `config.yaml`, including:

- dimensional-weight divisor
- hold and review thresholds
- keyword-based logistics review flags
- shipping class triggers
- Benzara SKU prefix and brand signals
- historical import metadata signals
- known non-Benzara supplier prefixes
- reporting output filenames

## Test Runner

Run the automated suite with a normal pytest invocation:

```bash
python -m pytest -q
```

Coverage includes parsers, matching, logistics, data quality, supplier classification, and integration-style pipeline verification.

## Safety Rules

- Source files are read-only inputs.
- Outputs are generated locally only.
- Missing critical values trigger review instead of guessed defaults.
- Bundle and non-Benzara pricing remain outside automatic price-update scope.
- Orphaned or other-supplier WooCommerce products are reported, not modified.

## Documentation Map

- Product requirements: [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md)
- Technical architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Delivery plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)