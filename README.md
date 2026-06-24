# Horpach Catalog Control

## Krotkie podsumowanie (PL)

To repo zawiera dokumentacje dla lokalnej aplikacji Python, ktora ma analizowac katalog Benzara i eksport WooCommerce, a nastepnie przygotowywac bezpieczne raporty XLSX/CSV dla Horpach.com. MVP v1 nie wykonuje zadnych zmian w sklepie, nie laczy sie z API i nie uruchamia importow produkcyjnych.

## Overview

Horpach Catalog Control is a local Python application for catalog analysis, product matching, logistics screening, and report generation for Horpach.com.

The application compares:

- the current Benzara operational catalog (`latest.xml`)
- the current WordPress/WooCommerce export (`horpachcom.WordPress.2026-06-24.xml`)

The tool is intentionally limited to decision support and output generation. It does not connect to WooCommerce, FTP, MySQL, or external APIs in MVP v1.

## Primary Goal

Generate safe, reviewable outputs that help decide:

- which Benzara products already exist in the store
- which new Benzara products are operationally safe to consider
- which products should be blocked or manually reviewed for logistics reasons
- which existing Benzara products are eligible for price-only updates

## MVP v1 Scope

The first version should:

- parse and normalize Benzara XML data
- parse and normalize WooCommerce products from a WordPress WXR export
- match products primarily by SKU
- use EAN/GTIN only as a controlled fallback
- classify logistics risk using configurable thresholds
- assign catalog decisions for operational review
- generate:
  - one XLSX management report
  - one CSV file for later WooCommerce import
  - one run log

## Non-Goals

MVP v1 must not:

- call the WooCommerce REST API
- modify WordPress, WooCommerce, MySQL, or FTP content
- import CSV files into production
- update descriptions, titles, slugs, categories, images, or URLs
- remove products or media
- invent missing values
- generate AI content

## Expected Repository Layout

```text
horpachCC/
|-- README.md
|-- docs/
|   |-- PROJECT_SPEC.md
|   |-- ARCHITECTURE.md
|   `-- IMPLEMENTATION_PLAN.md
|-- data/
|-- output/
`-- src/
```

The final code structure for MVP v1 is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Inputs

Place local source files in the project `data/` directory before running the implementation:

- `data/latest.xml`
- `data/horpachcom.WordPress.2026-06-24.xml`

Optional supporting source for validation:

- `FTP Benzara JUNE (15-06-2026).xlsx`

## Planned CLI

```bash
python -m horpach_catalog_control run \
  --benzara-input data/latest.xml \
  --woocommerce-input data/horpachcom.WordPress.2026-06-24.xml \
  --output-dir output
```

Additional commands:

```bash
python -m horpach_catalog_control validate-config
python -m horpach_catalog_control inspect-inputs
python -m horpach_catalog_control run --dry-run
```

## Planned Outputs

### Main Excel report

```text
output/HORPACH_CATALOG_CONTROL_REPORT.xlsx
```

### Price update CSV

```text
output/IMPORT_PRICE_UPDATE_BENZARA_PASS.csv
```

Required minimum columns:

```text
SKU
Regular price
Sale price
Meta: _horpach_catalog_decision
Meta: _horpach_logistics_status
Meta: _horpach_logistics_reasons
```

### Run log

```text
output/run.log
```

## Status Model

### Product matching statuses

- `MATCHED_BENZARA`
- `NEW_BENZARA`
- `ORPHAN_STORE`
- `OTHER_SUPPLIER`
- `CONFLICT`

### Logistics statuses

- `PASS_LOGISTICS`
- `REVIEW_LOGISTICS`
- `HOLD_LOGISTICS`

### Catalog decisions

- `PASS`
- `REVIEW`
- `HOLD_LOGISTICS`
- `OUT_OF_STOCK`
- `ORPHAN`
- `OTHER_SUPPLIER`
- `CONFLICT`

## Safety Rules

The project follows strict operational guardrails:

- source data is read-only
- output files are generated locally only
- missing critical values must trigger review, not guessed defaults
- all logistics thresholds must live in configuration
- orphaned store products must be reported, not deleted
- other suppliers must not be touched by Benzara price logic
- bundle and non-Benzara pricing must remain unchanged

## Configuration

All thresholds and keyword-driven logistics rules should live in `config.yaml`.

Examples of configurable values:

- dimensional-weight divisor
- hold thresholds
- review thresholds
- keyword sets for fragile or large-item review
- shipping class flags

## Installation Plan

Target stack:

- Python 3.11+
- `pydantic`
- `PyYAML`
- `openpyxl`
- `pytest`
- `lxml` or `xml.etree.ElementTree` with `iterparse`

## MVP v1 Limitations

- no production writes
- no direct store synchronization
- no image/media processing
- no automatic bundle strategy
- no AI-assisted title or content generation
- no database layer

## MVP v2 Direction

Planned future expansion:

- product evaluation for bundle strategy
- queueing into `Core`, `Bundle Pool`, `Extended`, and `Hold`
- controlled AI-assisted title and description generation for approved products only
- controlled content-update export
- optional WooCommerce API integration after the reporting workflow is proven safe

## Documentation Map

- Product requirements: [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md)
- Technical architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Delivery plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
