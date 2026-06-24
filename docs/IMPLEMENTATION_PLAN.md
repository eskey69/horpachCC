# Implementation Plan

## Delivery Strategy

Build the project in small, verifiable phases so that parsing, matching, and reporting can each be validated independently before the full pipeline is assembled.

## Phase 0. Project Bootstrap

Deliverables:

- repository layout
- `requirements.txt`
- `config.yaml`
- package skeleton under `src/`
- `tests/` with fixture directories
- `data/` and `output/` placeholders

Exit criteria:

- `python -m horpach_catalog_control --help` works
- `validate-config` works

## Phase 1. Input Inspection

Deliverables:

- source path validation
- quick input summary command
- XML root, namespace, and record-count inspection

Exit criteria:

- `inspect-inputs` confirms both files are readable
- namespaces and core record structures are logged

## Phase 2. Parsers

Deliverables:

- Benzara parser
- WooCommerce WXR parser
- normalized Pydantic models
- recoverable parser warnings

Exit criteria:

- unit tests pass for both parsers
- small fixture inputs produce stable normalized records

## Phase 3. Matching Engine

Deliverables:

- SKU-first match logic
- EAN fallback logic
- conflict detection
- final bucket assignment

Exit criteria:

- matcher tests pass
- ambiguous records are routed to `CONFLICT`

## Phase 4. Logistics and Decisions

Deliverables:

- dimensional calculations
- logistics status assignment
- reason-code emission
- catalog decision precedence

Exit criteria:

- threshold tests pass
- out-of-stock precedence is verified

## Phase 5. Report Generation

Deliverables:

- CSV export for price updates
- XLSX workbook generation
- summary metrics
- rule/config worksheet

Exit criteria:

- CSV duplicate SKU validation passes
- workbook contains all required sheets

## Phase 6. End-to-End Run

Deliverables:

- final `run` command
- `--dry-run` support
- `output/run.log`
- final run summary

Exit criteria:

- end-to-end run completes on real input files
- output files are created in `output/`

## Testing Plan

### Required unit coverage

- Benzara XML parsing
- Woo WXR parsing
- SKU matching
- EAN fallback matching
- volume calculation
- dimensional weight
- girth
- length plus girth
- PASS / REVIEW / HOLD boundaries
- out-of-stock precedence
- orphan and other-supplier logic

### Recommended follow-up coverage

- end-to-end dry-run test
- workbook smoke test
- CSV schema validation test

## Recommended Order of Work

1. Bootstrap the package and config layer.
2. Implement `inspect-inputs`.
3. Implement both parsers with fixtures.
4. Implement matcher and conflict rules.
5. Implement logistics calculations.
6. Implement decision logic.
7. Implement CSV and Excel outputs.
8. Run tests.
9. Run against local real data.

## Risks

### Data-shape risk

The real Benzara and WXR files may differ from assumptions in the prompt.

Mitigation:

- inspect actual XML structure before hard-coding selectors
- keep parser logic defensive and logged

### Ambiguous supplier ownership

Some store products may not clearly indicate whether they belong to Benzara.

Mitigation:

- treat ambiguous records as `CONFLICT` or `OTHER_SUPPLIER`
- avoid automatic update eligibility when provenance is unclear

### Missing dimensions and weight

Many products may lack complete logistics data.

Mitigation:

- route missing critical shipping fields to review
- never upgrade such products to pass automatically

### WXR namespace complexity

WordPress exports often contain nested namespaces and repeated meta keys.

Mitigation:

- build namespace-aware parser fixtures early
- keep meta extraction explicit and test-driven

## Open Questions

The current prompt is strong, but a few details should be confirmed before implementation:

1. How should bundles be detected in the current WooCommerce export?
2. Is shipping class stored only in taxonomy terms, only in meta, or both?
3. Which categories define the business "main category" breakdown in `SUMMARY`?
4. Should `_global_unique_id` be treated strictly as EAN/GTIN, or can it contain other identifier types?
5. Should malformed numeric fields be treated as missing, or should they also trigger explicit parser warnings in the report?

## Definition of Done

The MVP implementation is done when:

- the code runs locally on the provided input files
- tests cover the required rule set
- output files are generated successfully
- no production-facing integration is used
- the result is auditable through logs and reports
