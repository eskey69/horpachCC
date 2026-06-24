# Architecture

## 1. Technical Goals

The implementation should optimize for:

- deterministic local processing
- safe handling of large XML files
- explicit traceability of business decisions
- simple deployment without external services
- easy inspection of generated outputs

## 2. Recommended Stack

- Python 3.11+
- `pydantic` for normalized data models
- `PyYAML` for configuration
- `openpyxl` for XLSX generation
- `pytest` for tests
- `lxml` or `xml.etree.ElementTree.iterparse` for streaming XML parsing

## 3. Proposed Repository Structure

```text
horpachCC/
|-- README.md
|-- requirements.txt
|-- config.yaml
|-- .gitignore
|-- docs/
|   |-- PROJECT_SPEC.md
|   |-- ARCHITECTURE.md
|   `-- IMPLEMENTATION_PLAN.md
|-- data/
|   `-- .gitkeep
|-- output/
|   `-- .gitkeep
|-- src/
|   `-- horpach_catalog_control/
|       |-- __init__.py
|       |-- __main__.py
|       |-- cli.py
|       |-- config.py
|       |-- models.py
|       |-- benzara_parser.py
|       |-- woo_wxr_parser.py
|       |-- matcher.py
|       |-- logistics.py
|       |-- decisions.py
|       |-- price_exports.py
|       |-- excel_report.py
|       |-- utils.py
|       `-- constants.py
`-- tests/
    |-- test_benzara_parser.py
    |-- test_woo_wxr_parser.py
    |-- test_matcher.py
    |-- test_logistics.py
    `-- fixtures/
```

## 4. Pipeline Overview

The application should run as a single local pipeline:

1. Load and validate configuration.
2. Inspect inputs and confirm file accessibility.
3. Parse Benzara XML into normalized product objects.
4. Parse WooCommerce WXR into normalized product objects.
5. Match records using SKU-first logic with controlled fallback.
6. Evaluate logistics metrics and status.
7. Compute catalog decisions.
8. Build filtered views for reporting.
9. Generate CSV and XLSX outputs.
10. Emit a final run summary and structured log.

## 5. Module Responsibilities

### `config.py`

- load `config.yaml`
- validate required thresholds and keyword sets
- expose typed config objects

### `models.py`

- define normalized Pydantic models
- define enums for match status, logistics status, and catalog decision
- provide internal report row models where helpful

### `benzara_parser.py`

- stream-read `latest.xml`
- normalize nested product fields
- handle missing and malformed records with recoverable errors

### `woo_wxr_parser.py`

- stream-read WXR XML
- handle WordPress namespaces explicitly
- extract only `product` post types
- flatten post meta and taxonomy structures

### `matcher.py`

- build indexes by SKU and EAN
- classify matches into final buckets
- detect collisions and emit `CONFLICT`

### `logistics.py`

- compute derived shipping metrics
- evaluate hold/review/pass rules
- attach machine-readable reason codes

### `decisions.py`

- apply decision precedence
- separate logistics status from catalog decision
- enforce out-of-stock priority

### `price_exports.py`

- generate CSV rows for price-update-safe products only
- validate duplicate SKU absence before saving

### `excel_report.py`

- generate workbook tabs
- format workbook consistently
- render summary tables and rule snapshots

### `cli.py` and `__main__.py`

- expose `run`
- expose `inspect-inputs`
- expose `validate-config`
- support `--dry-run`

### `utils.py`

- helper parsing utilities
- type coercion helpers
- safe numeric conversions
- logging helpers

### `constants.py`

- shared meta keys
- worksheet names
- default enumerations

## 6. Data Model Outline

### Benzara product

Suggested fields:

- source IDs and identifiers
- descriptive content
- pricing
- inventory
- dimensions and weight
- categories
- images
- attribute summary
- brand and origin

### Woo product

Suggested fields:

- WordPress identity
- Woo meta fields
- category and tag lists
- shipping class
- media references
- custom `_horpach_` and `_fxc_` meta blocks

### Matched product view

Suggested consolidated view:

- store identity
- Benzara identity
- match status
- logistics metrics
- logistics status
- reason codes
- catalog decision
- recommended price update

## 7. Parsing Strategy

The source files may be large, so parsing should be streaming-first.

Recommendations:

- use `iterparse` to avoid loading full XML trees when not needed
- normalize records incrementally
- clear parsed XML elements to reduce memory pressure
- isolate per-record parsing errors and continue where safe

## 8. Logging Strategy

Write run diagnostics to `output/run.log`.

Recommended log contents:

- startup metadata
- resolved input paths
- configuration snapshot summary
- parser warnings with source context
- match and classification counts
- CSV duplicate validation results
- output file save results

## 9. Error Handling

Treat errors in three classes:

### Fatal

- input file missing
- malformed config
- workbook or CSV cannot be written

### Recoverable

- malformed single record
- missing optional source fields
- namespace or meta inconsistency that affects one item only

### Review-triggering data quality issues

- missing SKU
- missing weight
- missing dimensions
- ambiguous matching candidates

## 10. Reporting Design

The Excel workbook should serve both operational and audit needs.

Design principles:

- one row per evaluated product in detailed sheets
- stable column names
- human-readable decisions
- machine-readable reason codes
- visible rule snapshot in `RULES_AND_CONFIG`

## 11. Performance Notes

- prefer streaming reads over full-document loads
- create lookup dictionaries once
- avoid expensive repeated taxonomy parsing
- keep workbook styling simple and deterministic

## 12. Test Strategy

Unit tests should use small fixtures that model:

- normal products
- missing-field edge cases
- namespace-heavy WXR examples
- duplicate SKU conflicts
- review and hold boundary values

Recommended additional tests later:

- integration test for end-to-end dry run
- regression fixtures from real anonymized data

## 13. Security Boundaries

The codebase must remain fully local and read-only with respect to production systems.

Disallowed for MVP v1:

- external write APIs
- production imports
- direct store updates
- AI-generated catalog content
