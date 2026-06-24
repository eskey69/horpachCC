# Changelog

## 2026-06-24

### Added

- `recommended_operational_action` layer to separate practical next steps from logistics, commercial, and catalog analysis.
- `AUTO_HOLD_SUMMARY.xlsx` workbook with automatic hold, archive-candidate, and outside-flow sheets.
- `CORE_CANDIDATES.xlsx` shortlist workbook with deterministic priority scoring.
- auto-action sheets in the main workbook: `AUTO_PASS`, `AUTO_HOLD_LOGISTICS`, `AUTO_HOLD_OUT_OF_STOCK`, `AUTO_ARCHIVE_ORPHAN_CANDIDATES`, and `KEEP_OUTSIDE_BENZARA_FLOW`.
- manual review queue sorting fields: `Review Batch`, `Review Priority`, and `Sort Score`.
- pytest coverage for operational actions, manual review filtering, core candidate eligibility, and action reconciliation.

### Changed

- Reduced the default manual review queue to only `MANUAL_REVIEW_HIGH`, `MANUAL_REVIEW_MEDIUM`, and `MANUAL_REVIEW_LOW` records.
- Updated supplier classification so current-feed `NEW_BENZARA` records are treated as Benzara records.
- Added deterministic Core Candidate scoring using configurable stock, image, dimension, and keyword signals.
- Expanded `SUMMARY` with action-layer reconciliation and Core Candidate counts.
- Updated README to document the new action layer, auto-hold workflow, and Core Candidate purpose.

## 2026-06-24 (earlier)

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