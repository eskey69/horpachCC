# Project Specification

## 1. Purpose

Horpach Catalog Control is a local-only catalog analysis tool for Horpach.com.

Its purpose is to:

- compare the latest Benzara catalog with the current WooCommerce catalog state
- identify matched, new, orphaned, conflicting, and non-Benzara products
- screen products for logistics risk
- prepare safe reports and import-ready CSV files for later human review

## 2. Operating Constraints

The application is decision support only in MVP v1.

It must not:

- connect to WooCommerce REST API
- modify WordPress or WooCommerce directly
- upload data through FTP
- run production imports
- alter titles, descriptions, slugs, categories, URLs, or images
- guess missing source data

## 3. Input Sources

### 3.1 Benzara XML

Primary source:

- `latest.xml`

Optional validation source:

- `FTP Benzara JUNE (15-06-2026).xlsx`

Required extracted fields:

- `id`
- `sku`
- `ean`
- `name`
- `description`
- `short_description`
- `pricing.regular`
- `stock.qty`
- `stock.status`
- `shipping.weight`
- `shipping.length`
- `shipping.width`
- `shipping.height`
- `categories.category`
- `categories.tree`
- `images.image`
- material, color, and product type attributes
- `_brand`
- `_origin`
- assembly-needed signal
- inventory snapshot match signal

### 3.2 WooCommerce WXR Export

Primary source:

- `horpachcom.WordPress.2026-06-24.xml`

Only `wp:post_type = product` records are in scope.

Required extracted fields:

- WordPress post ID
- title
- post status
- slug
- URL
- content
- excerpt
- categories
- tags
- `_sku`
- `_regular_price`
- `_sale_price`
- `_price`
- `_stock`
- `_stock_status`
- `_manage_stock`
- `_weight`
- `_length`
- `_width`
- `_height`
- `_global_unique_id`
- `_thumbnail_id`
- `_product_image_gallery`
- shipping class
- `total_sales`
- all meta keys starting with `_horpach_`
- all meta keys starting with `_fxc_`

## 4. Matching Rules

### 4.1 Primary matching key

```text
WooCommerce _sku == Benzara sku
```

### 4.2 Controlled fallback

Use `_global_unique_id <-> ean` only when SKU is missing or clearly unusable.

### 4.3 Forbidden matching logic

- never auto-match by title only
- never silently merge ambiguous candidates

### 4.4 Matching outputs

- `MATCHED_BENZARA`
- `NEW_BENZARA`
- `ORPHAN_STORE`
- `OTHER_SUPPLIER`
- `CONFLICT`

## 5. Logistics Evaluation

For Benzara products and matched store products, compute:

```text
volume_in3 = length_in * width_in * height_in
dim_weight_lb = volume_in3 / 139
girth_in = 2 * (width_in + height_in)
length_plus_girth_in = length_in + girth_in
billable_weight_lb = max(actual_weight_lb, dim_weight_lb)
```

The divisor `139` must be configurable in `config.yaml`.

### 5.1 HOLD_LOGISTICS

Assign when at least one of the following is true:

- actual weight > 50 lb
- longest side > 48 in
- length + girth > 130 in
- volume > 17280 in3
- dimensional weight > 70 lb
- shipping class contains `freight`

Large mirrors, oversized wall art, room dividers, large patio sets, and large furniture should be at least keyword-flagged for review and must not be silently passed.

### 5.2 REVIEW_LOGISTICS

Assign when any of the following is true:

- actual weight between 35 and 50 lb
- longest side between 42 and 48 in
- dimensional weight between 50 and 70 lb
- fragile, mirror, glass, marble, or patio keywords are detected
- dimensions or weight are missing
- pack count is unknown but the item appears to be a set

### 5.3 PASS_LOGISTICS

Assign only when neither hold nor review logic applies.

### 5.4 Reason codes

Each logistics result must include machine-readable reason codes, for example:

```json
[
  "weight_over_50lb",
  "length_plus_girth_over_130in",
  "freight_shipping_class"
]
```

## 6. Catalog Decision Rules

Each product must receive `catalog_decision`.

Allowed values:

- `PASS`
- `REVIEW`
- `HOLD_LOGISTICS`
- `OUT_OF_STOCK`
- `ORPHAN`
- `OTHER_SUPPLIER`
- `CONFLICT`

Decision precedence:

1. If Benzara stock is not `instock` or quantity is `<= 0`, use `OUT_OF_STOCK`.
2. If the product is logistics hold, it cannot be `PASS`.
3. If critical data is missing, use `REVIEW`.
4. If a WooCommerce product has a SKU but does not exist in `latest.xml`, use `ORPHAN`.
5. Other suppliers must remain isolated from Benzara update logic.

## 7. Price Update Logic

Only matched Benzara products are eligible.

Required conditions:

- `MATCHED_BENZARA`
- `PASS_LOGISTICS`
- Benzara stock is `instock`
- Benzara regular price is valid

Generated update:

- `Regular price = latest.xml pricing.regular`
- `Sale price = empty`

Must not update:

- products from other suppliers
- bundles
- hold, review, out-of-stock, or orphan products
- any descriptive or media content

## 8. Output Files

### 8.1 CSV export

Path:

```text
output/IMPORT_PRICE_UPDATE_BENZARA_PASS.csv
```

Minimum columns:

- `SKU`
- `Regular price`
- `Sale price`
- `Meta: _horpach_catalog_decision`
- `Meta: _horpach_logistics_status`
- `Meta: _horpach_logistics_reasons`

Validation:

- the file must not contain duplicate SKU values

### 8.2 Excel report

Path:

```text
output/HORPACH_CATALOG_CONTROL_REPORT.xlsx
```

Required worksheets:

1. `SUMMARY`
2. `MATCHED_BENZARA`
3. `PRICE_UPDATE_PASS`
4. `NEW_BENZARA_PASS`
5. `NEW_BENZARA_REVIEW`
6. `HOLD_LOGISTICS`
7. `OUT_OF_STOCK`
8. `ORPHAN_STORE`
9. `OTHER_SUPPLIER`
10. `CONFLICTS`
11. `RULES_AND_CONFIG`

Formatting requirements:

- frozen top row
- filters
- width auto-fit
- USD formatting for prices
- numeric formatting for dimensions
- restrained business color palette
- conditional formatting for statuses

## 9. Summary Metrics

The `SUMMARY` worksheet must include:

- total WooCommerce products
- total Benzara products
- shared SKU count
- new Benzara SKU count
- orphan count
- other-supplier count
- PASS count
- REVIEW count
- HOLD_LOGISTICS count
- OUT_OF_STOCK count
- price-update-ready count
- category breakdown
- brand breakdown

## 10. Quality and Safety Requirements

- preserve source data integrity
- log actions to `output/run.log`
- continue parsing after recoverable errors when possible
- include record-level parser context in errors
- mark missing critical dimensions, weight, or SKU as reviewable
- keep all operational thresholds configurable

## 11. Testing Requirements

Unit tests must cover:

- Benzara XML parsing
- WooCommerce WXR parsing
- SKU matching
- EAN fallback matching
- volume calculation
- dimensional weight
- girth
- length plus girth
- PASS / REVIEW / HOLD thresholds
- out-of-stock precedence
- `OTHER_SUPPLIER` and `ORPHAN` rules

## 12. Acceptance Criteria

The MVP is successful when it can:

- read both source files locally
- parse them into stable normalized models
- generate a traceable matching result set
- classify logistics status with reason codes
- generate a duplicate-free price-update CSV
- generate the required Excel workbook
- run without touching production systems
