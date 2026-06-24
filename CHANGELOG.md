# Changelog

## 2026-06-24

### Added

- `data_quality.py` module for missing, invalid, and duplicate record diagnostics.
- `supplier_classification.py` module for Benzara match, orphan suspicion, other-supplier, and unknown-supplier classification.
- `analysis.py` pipeline assembly layer for consolidated report generation.
- `PRICE_UPDATE_EXCLUDED`, `DATA_QUALITY`, `SUPPLIER_CLASSIFICATION`, and `LOGISTICS_DIAGNOSTICS` workbook sections.
- `MANUAL_REVIEW_QUEUE.xlsx` export for consolidated human review.
- pytest coverage for price-update status handling, exclusion reasons, data-quality rules, supplier classification, and integration-style pipeline checks.
- source-checkout wrapper package so `python -m horpach_catalog_control ...` works without editable install.

### Changed

- Separated `logistics_status`, `commercial_status`, and `catalog_decision` in pipeline outputs.
- Expanded logistics diagnostics with actual weight, dimensions, volume, dim weight, billable weight, longest side, threshold hits, and missing-data flags.
- Refined price update export so only `PRICE_READY` rows enter the CSV.
- Updated CLI summaries and workbook generation to expose the new explainability fields.
- Updated README to document new statuses, outputs, and workflow.