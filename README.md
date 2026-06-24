# Horpach Catalog Control

## Krotkie podsumowanie (PL)

To repo zawiera lokalna aplikacje Python do analizy katalogu Benzara i eksportu WooCommerce dla Horpach.com. Narzedzie tworzy raporty XLSX i CSV do bezpiecznej oceny dopasowan, logistyki, jakosci danych, wykluczen cenowych, automatycznych holdow, kandydatow Core i tylko tych kolejek recznej weryfikacji, ktore rzeczywiscie wymagaja decyzji czlowieka.

MVP v1 nadal nie wykonuje zadnych zmian w WooCommerce, WordPressie, FTP, MySQL ani innych systemach produkcyjnych.

## Overview

Horpach Catalog Control compares the current Benzara operational catalog with a WooCommerce WordPress WXR export and produces decision-support outputs for catalog safety checks.

The pipeline now answers:

- which products are matched to the current Benzara feed
- why a matched product is `PRICE_READY` or excluded from price import
- which products are `PASS`, `REVIEW`, `HOLD_LOGISTICS`, `OUT_OF_STOCK`, `ORPHAN`, `OTHER_SUPPLIER`, or `CONFLICT`
- which products have missing or invalid operational data
- which orphaned WooCommerce products look like historical Benzara products
- which records can be auto-held, auto-archived, or kept outside the Benzara workflow
- which records truly require manual review
- which Benzara products form an initial `CORE_CANDIDATES` shortlist

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
- assigns a separate `recommended_operational_action` layer
- generates management reports, price-update CSV, manual-review queue, auto-hold summary, and Core Candidates workbook

## Non-Goals

The tool does not:

- call WooCommerce REST API
- modify WordPress, WooCommerce, MySQL, FTP, or production data
- import CSV files into production
- generate AI titles, descriptions, or bundle logic
- delete products, media, or catalog records
- invent missing values
- approve profitability or merchandising strategy

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
- Core candidate count
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

Automatic hold summary workbook:

```text
output/AUTO_HOLD_SUMMARY.xlsx
```

Core candidates workbook:

```text
output/CORE_CANDIDATES.xlsx
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
- `AUTO_PASS`
- `AUTO_HOLD_LOGISTICS`
- `AUTO_HOLD_OUT_OF_STOCK`
- `AUTO_ARCHIVE_ORPHAN_CANDIDATES`
- `KEEP_OUTSIDE_BENZARA_FLOW`
- `CORE_CANDIDATES`
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

### Recommended operational actions

- `AUTO_PASS`
- `AUTO_HOLD_LOGISTICS`
- `AUTO_HOLD_OUT_OF_STOCK`
- `AUTO_ARCHIVE_ORPHAN_CANDIDATE`
- `KEEP_OUTSIDE_BENZARA_FLOW`
- `MANUAL_REVIEW_HIGH`
- `MANUAL_REVIEW_MEDIUM`
- `MANUAL_REVIEW_LOW`

## Operational Workflow

The `recommended_operational_action` layer is intentionally separate from logistics, commercial, catalog, and supplier analysis. It represents the practical next step.

`AUTO_PASS` identifies products that are operationally clean enough for future pricing or shortlist work.

`AUTO_HOLD_LOGISTICS` and `AUTO_HOLD_OUT_OF_STOCK` remove clear non-actionable cases from the default manual queue.

`AUTO_ARCHIVE_ORPHAN_CANDIDATE` captures likely historical Benzara store products that should be reviewed separately from active catalog work.

`KEEP_OUTSIDE_BENZARA_FLOW` isolates confirmed non-Benzara supplier products from Benzara pricing or import logic.

`MANUAL_REVIEW_QUEUE.xlsx` now contains only records assigned `MANUAL_REVIEW_HIGH`, `MANUAL_REVIEW_MEDIUM`, or `MANUAL_REVIEW_LOW`.

## Core Candidates

`CORE_CANDIDATES.xlsx` is a logistics and data-quality shortlist only.

It is not a profitability-approved, merchandising-approved, or launch-approved list.

The shortlist is derived from records with `AUTO_PASS` plus configurable stock, image, category, packaging, and keyword scoring rules from `config.yaml`.

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
- Core Candidate stock threshold
- Core Candidate exclusion keywords
- Core Candidate score weights and package-size thresholds

## Test Runner

Run the automated suite with a normal pytest invocation:

```bash
python -m pytest -q
```

Coverage includes parsers, matching, logistics, data quality, supplier classification, operational actions, summary reconciliation, and integration-style pipeline verification.

## Safety Rules

- Source files are read-only inputs.
- Outputs are generated locally only.
- Missing critical values trigger review instead of guessed defaults.
- Bundle and non-Benzara pricing remain outside automatic price-update scope.
- Orphaned or other-supplier WooCommerce products are reported, not modified.
- Core Candidates are only a shortlist for later business review.

## Documentation Map

- Product requirements: [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md)
- Technical architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Delivery plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)