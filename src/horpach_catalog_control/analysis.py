"""Pipeline analysis and report assembly."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .data_quality import (
    assess_benzara_product,
    assess_woo_product,
    build_duplicate_context,
    merge_quality_results,
    suggest_data_quality_action,
)
from .models import (
    CatalogDecision,
    CommercialStatus,
    DataQualityStatus,
    LogisticsStatus,
    PriceUpdateResult,
    PriceUpdateStatus,
)
from .logistics import evaluate_logistics
from .matcher import match_products
from .supplier_classification import classify_supplier, suggest_supplier_action


def _primary_category(categories: list[str] | None) -> str | None:
    if not categories:
        return None
    return categories[0]


def _is_bundle_product(woo: dict | None) -> bool:
    if not woo:
        return False
    meta = woo.get('meta', {}) or {}
    prefixed_meta = woo.get('prefixed_meta', {}) or {}
    value = prefixed_meta.get('_fxc_bundle_flag') or meta.get('_fxc_bundle_flag')
    return str(value).strip().lower() in {'1', 'true', 'yes'}


def _valid_positive_price(value) -> bool:
    try:
        return value is not None and float(value) > 0
    except (TypeError, ValueError):
        return False


def _determine_commercial_status(bucket: str, logistics, quality, benzara: dict | None, woo: dict | None) -> CommercialStatus:
    if bucket == 'ORPHAN_STORE':
        return CommercialStatus.ORPHAN
    if bucket == 'OTHER_SUPPLIER':
        return CommercialStatus.OTHER_SUPPLIER
    if bucket == 'CONFLICT':
        return CommercialStatus.CONFLICT

    product = benzara or woo or {}
    stock_status = str(product.get('stock_status') or '').lower()
    stock_qty = product.get('stock_qty')
    if stock_status != 'instock' or stock_qty is None or stock_qty <= 0:
        return CommercialStatus.OUT_OF_STOCK
    if quality.status is DataQualityStatus.CRITICAL:
        return CommercialStatus.MISSING_DATA
    if logistics.status is LogisticsStatus.PASS_LOGISTICS and _valid_positive_price(product.get('regular_price')):
        return CommercialStatus.PRICE_READY
    return CommercialStatus.PRICE_REVIEW


def _determine_catalog_decision(bucket: str, logistics, quality, commercial_status: CommercialStatus) -> CatalogDecision:
    if commercial_status is CommercialStatus.OUT_OF_STOCK:
        return CatalogDecision.OUT_OF_STOCK
    if bucket == 'ORPHAN_STORE':
        return CatalogDecision.ORPHAN
    if bucket == 'OTHER_SUPPLIER':
        return CatalogDecision.OTHER_SUPPLIER
    if bucket == 'CONFLICT':
        return CatalogDecision.CONFLICT
    if logistics.status is LogisticsStatus.HOLD_LOGISTICS:
        return CatalogDecision.HOLD_LOGISTICS
    if logistics.status is LogisticsStatus.REVIEW_LOGISTICS or quality.status is not DataQualityStatus.OK or commercial_status is not CommercialStatus.PRICE_READY:
        return CatalogDecision.REVIEW
    return CatalogDecision.PASS


def _price_update_result(bucket: str, benzara: dict | None, logistics, commercial_status: CommercialStatus, quality, is_bundle: bool) -> PriceUpdateResult:
    if bucket == 'CONFLICT':
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_CONFLICT,
            exclusion_reason='Conflicting matched product record',
            suggested_action='Resolve conflict before any pricing decision',
        )
    if bucket != 'MATCHED_BENZARA':
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_OTHER,
            exclusion_reason='Product is not an active matched Benzara record',
            suggested_action='Do not use for direct Benzara price update',
        )

    benzara = benzara or {}
    sku = benzara.get('sku')
    price = benzara.get('regular_price')
    if not sku:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_MISSING_SKU,
            exclusion_reason='Missing SKU for matched Benzara product',
            suggested_action='Investigate missing SKU before pricing',
        )
    if price is None:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_MISSING_BENZARA_PRICE,
            exclusion_reason='Missing Benzara regular price in current feed',
            suggested_action='Investigate missing supplier price',
        )
    if not _valid_positive_price(price):
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_INVALID_BENZARA_PRICE,
            exclusion_reason='Invalid Benzara regular price in current feed',
            suggested_action='Manual pricing review required',
        )
    if is_bundle:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_BUNDLE_PRODUCT,
            exclusion_reason='Bundle product is excluded from direct Benzara price update',
            suggested_action='Keep current price; bundle handling is manual',
        )
    if commercial_status is CommercialStatus.OUT_OF_STOCK:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_OUT_OF_STOCK,
            exclusion_reason='Out of stock in current Benzara feed',
            suggested_action='Keep current price; wait for stock',
        )
    if logistics.status is LogisticsStatus.HOLD_LOGISTICS:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_HOLD_LOGISTICS,
            exclusion_reason='Excluded because product is on logistics hold',
            suggested_action='Do not update; logistics hold',
        )
    if logistics.status is LogisticsStatus.REVIEW_LOGISTICS:
        reason = 'Review logistics required'
        if logistics.reason_codes:
            reason = f"Review logistics: {', '.join(logistics.reason_codes)}"
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_REVIEW_LOGISTICS,
            exclusion_reason=reason,
            suggested_action='Eligible after logistics review',
        )
    if commercial_status is CommercialStatus.MISSING_DATA or quality.status is DataQualityStatus.CRITICAL:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_OTHER,
            exclusion_reason='Critical data-quality issue blocks safe pricing',
            suggested_action='Manual pricing review required',
        )
    return PriceUpdateResult(
        status=PriceUpdateStatus.PRICE_READY,
        exclusion_reason='Meets current pricing eligibility rules',
        suggested_action='Safe candidate for price update',
    )

def _review_priority(record: dict) -> str:
    reasons = set(record.get('Data Quality Reason Codes List', [])) | set(record.get('Logistics Reasons List', []))
    supplier = record.get('Supplier Classification')
    price_status = record.get('Price Update Status')
    if record.get('Catalog Decision') == 'CONFLICT' or 'freight_shipping_class' in reasons or 'invalid_dimensions' in reasons or 'invalid_price' in reasons or 'duplicate_benzara_sku' in reasons or 'duplicate_woo_sku' in reasons or 'duplicate_ean' in reasons:
        return 'HIGH'
    if record.get('Logistics Status') == 'REVIEW_LOGISTICS' or supplier in {'BENZARA_ORPHAN_SUSPECTED', 'UNKNOWN_SUPPLIER'} or 'missing_brand' in reasons or 'missing_origin' in reasons:
        return 'MEDIUM'
    if price_status in {'EXCLUDED_OTHER', 'EXCLUDED_MISSING_BENZARA_PRICE', 'EXCLUDED_INVALID_BENZARA_PRICE'}:
        return 'MEDIUM'
    return 'LOW'


def _review_type(record: dict) -> str:
    if record.get('Catalog Decision') == 'CONFLICT':
        return 'Conflicting Match'
    if record.get('Logistics Status') == 'HOLD_LOGISTICS':
        return 'Severe Logistics Hold'
    if record.get('Logistics Status') == 'REVIEW_LOGISTICS':
        return 'Review Logistics'
    if record.get('Data Quality Status') == 'CRITICAL':
        return 'Critical Data Quality'
    if record.get('Supplier Classification') == 'BENZARA_ORPHAN_SUSPECTED':
        return 'Orphan Suspected Benzara'
    if record.get('Supplier Classification') == 'UNKNOWN_SUPPLIER':
        return 'Unknown Supplier'
    return 'Manual Review'


def _common_row(bucket: str, benzara: dict | None, woo: dict | None, match_strategy: str | None, settings, duplicate_context, known_benzara_brands: set[str]) -> dict:
    source_product = benzara or woo or {}
    logistics = evaluate_logistics(source_product, config=settings.logistics)
    benzara_quality = assess_benzara_product(benzara, duplicate_context) if benzara else None
    woo_quality = assess_woo_product(woo, duplicate_context) if woo else None
    quality = merge_quality_results(*[result for result in (benzara_quality, woo_quality) if result is not None])
    supplier_result = classify_supplier(
        bucket=bucket,
        woo=woo,
        config=settings.supplier,
        known_benzara_brands=known_benzara_brands,
    )
    is_bundle = _is_bundle_product(woo)
    commercial_status = _determine_commercial_status(bucket, logistics, quality, benzara, woo)
    catalog_decision = _determine_catalog_decision(bucket, logistics, quality, commercial_status)
    price_update = _price_update_result(bucket, benzara, logistics, commercial_status, quality, is_bundle)

    return {
        'Source Bucket': bucket,
        'Match Strategy': match_strategy,
        'WooCommerce ID': woo.get('post_id') if woo else None,
        'SKU': (benzara or {}).get('sku') or (woo or {}).get('sku'),
        'EAN': (benzara or {}).get('ean') or (woo or {}).get('global_unique_id'),
        'Global Unique ID': (woo or {}).get('global_unique_id'),
        'Current Title': (woo or {}).get('title'),
        'Title': (woo or {}).get('title') or (benzara or {}).get('name'),
        'Current Regular Price': (woo or {}).get('regular_price'),
        'Current Sale Price': (woo or {}).get('sale_price'),
        'Current Price': (woo or {}).get('regular_price'),
        'Benzara Price': (benzara or {}).get('regular_price'),
        'Price': (benzara or {}).get('regular_price') if benzara else (woo or {}).get('regular_price'),
        'Benzara Name': (benzara or {}).get('name'),
        'Benzara Brand': (benzara or {}).get('brand'),
        'Brand': (benzara or {}).get('brand') or (woo or {}).get('brand'),
        'Origin': (benzara or {}).get('origin'),
        'Primary Category': _primary_category((benzara or {}).get('categories')),
        'Current Categories': ', '.join((woo or {}).get('categories') or []),
        'Woo Shipping Class': (woo or {}).get('shipping_class'),
        'Stock': f"{(benzara or woo or {}).get('stock_qty')} / {(benzara or woo or {}).get('stock_status')}",
        'Benzara Stock Qty': (benzara or {}).get('stock_qty'),
        'Benzara Stock Status': (benzara or {}).get('stock_status'),
        'Current Stock Qty': (woo or {}).get('stock_qty'),
        'Current Stock Status': (woo or {}).get('stock_status'),
        'actual_weight_lb': logistics.metrics.actual_weight_lb,
        'length_in': logistics.metrics.length_in,
        'width_in': logistics.metrics.width_in,
        'height_in': logistics.metrics.height_in,
        'volume_in3': logistics.metrics.volume_in3,
        'dim_weight_lb': logistics.metrics.dim_weight_lb,
        'girth_in': logistics.metrics.girth_in,
        'length_plus_girth_in': logistics.metrics.length_plus_girth_in,
        'billable_weight_lb': logistics.metrics.billable_weight_lb,
        'longest_side_in': logistics.metrics.longest_side_in,
        'Weight lb': logistics.metrics.actual_weight_lb,
        'Length in': logistics.metrics.length_in,
        'Width in': logistics.metrics.width_in,
        'Height in': logistics.metrics.height_in,
        'Volume in3': logistics.metrics.volume_in3,
        'Dim Weight lb': logistics.metrics.dim_weight_lb,
        'Length + Girth in': logistics.metrics.length_plus_girth_in,
        'Logistics Status': logistics.status.value,
        'Logistics Reasons': ';'.join(logistics.reason_codes),
        'Logistics Reasons List': logistics.reason_codes,
        'logistics_threshold_hits': ';'.join(logistics.threshold_hits),
        'logistics_missing_data': bool(logistics.missing_data),
        'logistics_missing_data_reasons': ';'.join(logistics.missing_data),
        'Commercial Status': commercial_status.value,
        'Catalog Decision': catalog_decision.value,
        'Price Update Status': price_update.status.value,
        'Price Update Exclusion Reason': price_update.exclusion_reason,
        'Price Update Suggested Action': price_update.suggested_action,
        'Suggested Action': price_update.suggested_action,
        'Data Quality Status': quality.status.value,
        'Data Quality Reason Codes': ';'.join(quality.reason_codes),
        'Data Quality Reason Codes List': quality.reason_codes,
        'Supplier Classification': supplier_result.classification.value,
        'Classification Reason Codes': ';'.join(supplier_result.reason_codes),
        'Supplier Suggested Action': suggest_supplier_action(supplier_result),
        'Is Bundle Product': is_bundle,
        'Recommended Price Update': (benzara or {}).get('regular_price') if price_update.status is PriceUpdateStatus.PRICE_READY else None,
    }


def _conflict_row(conflict: dict, settings, duplicate_context, known_benzara_brands: set[str]) -> dict:
    woo = conflict.get('woo')
    benzara = conflict.get('benzara')
    record = _common_row('CONFLICT', benzara, woo, None, settings, duplicate_context, known_benzara_brands)
    record.update({
        'Conflict Type': conflict.get('type'),
        'Woo Candidate Count': len(conflict.get('woo_candidates') or []),
        'Price Update Status': PriceUpdateStatus.EXCLUDED_CONFLICT.value,
        'Price Update Exclusion Reason': 'Excluded due to conflicting match state',
        'Suggested Action': 'Resolve conflict before any update',
    })
    return record

def _summary_count_rows(all_records: list[dict], match_results: dict[str, list[dict]], price_ready_rows: list[dict], price_excluded_rows: list[dict]) -> list[dict]:
    return [
        {'Section': 'Counts', 'Metric': 'WooCommerce products', 'Key': 'total', 'Value': sum(len(match_results[key]) for key in ('MATCHED_BENZARA', 'ORPHAN_STORE', 'OTHER_SUPPLIER', 'CONFLICT'))},
        {'Section': 'Counts', 'Metric': 'Benzara products', 'Key': 'total', 'Value': sum(len(match_results[key]) for key in ('MATCHED_BENZARA', 'NEW_BENZARA', 'CONFLICT'))},
        {'Section': 'Counts', 'Metric': 'Matched', 'Key': 'total', 'Value': len(match_results['MATCHED_BENZARA'])},
        {'Section': 'Counts', 'Metric': 'Price ready', 'Key': 'total', 'Value': len(price_ready_rows)},
        {'Section': 'Counts', 'Metric': 'Price excluded', 'Key': 'total', 'Value': len(price_excluded_rows)},
        {'Section': 'Counts', 'Metric': 'PASS logistics', 'Key': 'total', 'Value': sum(1 for row in all_records if row.get('Logistics Status') == 'PASS_LOGISTICS')},
        {'Section': 'Counts', 'Metric': 'REVIEW logistics', 'Key': 'total', 'Value': sum(1 for row in all_records if row.get('Logistics Status') == 'REVIEW_LOGISTICS')},
        {'Section': 'Counts', 'Metric': 'HOLD logistics', 'Key': 'total', 'Value': sum(1 for row in all_records if row.get('Logistics Status') == 'HOLD_LOGISTICS')},
        {'Section': 'Counts', 'Metric': 'Out of stock', 'Key': 'total', 'Value': sum(1 for row in all_records if row.get('Catalog Decision') == 'OUT_OF_STOCK')},
        {'Section': 'Counts', 'Metric': 'Data quality critical', 'Key': 'total', 'Value': sum(1 for row in all_records if row.get('Data Quality Status') == 'CRITICAL')},
    ]


def _counter_rows(records: list[dict], field: str, section: str, label: str) -> list[dict]:
    counter = Counter((record.get(field) or 'Unknown') for record in records)
    return [{'Section': section, 'Metric': label, 'Key': key, 'Value': value} for key, value in counter.most_common()]


def _build_manual_review_rows(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        needs_review = (
            record.get('Logistics Status') in {'REVIEW_LOGISTICS', 'HOLD_LOGISTICS'}
            or record.get('Data Quality Status') in {'REVIEW', 'CRITICAL'}
            or record.get('Supplier Classification') in {'BENZARA_ORPHAN_SUSPECTED', 'UNKNOWN_SUPPLIER'}
            or record.get('Price Update Status') in {
                'EXCLUDED_MISSING_BENZARA_PRICE',
                'EXCLUDED_INVALID_BENZARA_PRICE',
                'EXCLUDED_OTHER',
                'EXCLUDED_CONFLICT',
            }
            or record.get('Catalog Decision') == 'CONFLICT'
        )
        if not needs_review:
            continue
        reason_codes = []
        reason_codes.extend(record.get('Logistics Reasons List', []))
        reason_codes.extend(record.get('Data Quality Reason Codes List', []))
        if record.get('Classification Reason Codes'):
            reason_codes.extend(str(record.get('Classification Reason Codes')).split(';'))
        rows.append({
            'Review Type': _review_type(record),
            'Priority': _review_priority(record),
            'WooCommerce ID': record.get('WooCommerce ID'),
            'SKU': record.get('SKU'),
            'Title': record.get('Title'),
            'Current Price': record.get('Current Regular Price'),
            'Benzara Price': record.get('Benzara Price'),
            'Stock': record.get('Stock'),
            'Weight': record.get('Weight lb'),
            'Dimensions': ' x '.join(str(record.get(key)) for key in ('Length in', 'Width in', 'Height in')),
            'Logistics Status': record.get('Logistics Status'),
            'Commercial Status': record.get('Commercial Status'),
            'Supplier Classification': record.get('Supplier Classification'),
            'Reason Codes': ';'.join([code for code in reason_codes if code]),
            'Suggested Action': record.get('Suggested Action') or record.get('Supplier Suggested Action') or 'Manual review required',
        })
    rows.sort(key=lambda row: ({'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(row['Priority'], 3), row['Review Type'], str(row['SKU'])))
    return rows


def build_pipeline_outputs(settings, benzara_products: list[dict], woo_products: list[dict]) -> dict:
    duplicate_context = build_duplicate_context(benzara_products, woo_products)
    match_results = match_products(benzara_products, woo_products)
    known_benzara_brands = {brand.lower() for brand in settings.supplier.benzara_brands}
    known_benzara_brands.update({str(product.get('brand')).lower() for product in benzara_products if product.get('brand')})

    matched_rows = [
        _common_row('MATCHED_BENZARA', match['benzara'], match['woo'], match.get('match_strategy'), settings, duplicate_context, known_benzara_brands)
        for match in match_results['MATCHED_BENZARA']
    ]
    new_rows = [
        _common_row('NEW_BENZARA', product, None, 'new_benzara', settings, duplicate_context, known_benzara_brands)
        for product in match_results['NEW_BENZARA']
    ]
    orphan_rows = [
        _common_row('ORPHAN_STORE', None, product, 'orphan_store', settings, duplicate_context, known_benzara_brands)
        for product in match_results['ORPHAN_STORE']
    ]
    other_supplier_rows = [
        _common_row('OTHER_SUPPLIER', None, product, 'other_supplier', settings, duplicate_context, known_benzara_brands)
        for product in match_results['OTHER_SUPPLIER']
    ]
    conflict_rows = [
        _conflict_row(conflict, settings, duplicate_context, known_benzara_brands)
        for conflict in match_results['CONFLICT']
    ]

    all_records = matched_rows + new_rows + orphan_rows + other_supplier_rows + conflict_rows
    price_ready_rows = [row for row in matched_rows if row['Price Update Status'] == PriceUpdateStatus.PRICE_READY.value]
    price_excluded_rows = [row for row in matched_rows if row['Price Update Status'] != PriceUpdateStatus.PRICE_READY.value]

    data_quality_rows = [
        {
            'Source': row.get('Source Bucket'),
            'WooCommerce ID': row.get('WooCommerce ID'),
            'SKU': row.get('SKU'),
            'EAN': row.get('EAN'),
            'Title': row.get('Title'),
            'Data Quality Status': row.get('Data Quality Status'),
            'Reason Codes': row.get('Data Quality Reason Codes'),
            'Suggested Action': 'Critical fix required' if row.get('Data Quality Status') == 'CRITICAL' else 'Manual data review required',
            'Weight': row.get('Weight lb'),
            'Length': row.get('Length in'),
            'Width': row.get('Width in'),
            'Height': row.get('Height in'),
            'Price': row.get('Price'),
            'Stock Status': row.get('Benzara Stock Status') or row.get('Current Stock Status'),
        }
        for row in all_records if row.get('Data Quality Status') != DataQualityStatus.OK.value
    ]

    supplier_rows = [
        {
            'WooCommerce ID': row.get('WooCommerce ID'),
            'SKU': row.get('SKU'),
            'Title': row.get('Title'),
            'Brand': row.get('Brand'),
            'Global Unique ID': row.get('Global Unique ID'),
            'Current Categories': row.get('Current Categories'),
            'Supplier Classification': row.get('Supplier Classification'),
            'Classification Reason Codes': row.get('Classification Reason Codes'),
            'Suggested Action': row.get('Supplier Suggested Action'),
        }
        for row in matched_rows + orphan_rows + other_supplier_rows + conflict_rows
    ]
    logistics_rows = [
        {
            'Source Bucket': row.get('Source Bucket'),
            'WooCommerce ID': row.get('WooCommerce ID'),
            'SKU': row.get('SKU'),
            'Title': row.get('Title'),
            'logistics_status': row.get('Logistics Status'),
            'actual_weight_lb': row.get('actual_weight_lb'),
            'length_in': row.get('length_in'),
            'width_in': row.get('width_in'),
            'height_in': row.get('height_in'),
            'volume_in3': row.get('volume_in3'),
            'dim_weight_lb': row.get('dim_weight_lb'),
            'girth_in': row.get('girth_in'),
            'length_plus_girth_in': row.get('length_plus_girth_in'),
            'billable_weight_lb': row.get('billable_weight_lb'),
            'longest_side_in': row.get('longest_side_in'),
            'logistics_threshold_hits': row.get('logistics_threshold_hits'),
            'logistics_missing_data': row.get('logistics_missing_data'),
            'logistics_missing_data_reasons': row.get('logistics_missing_data_reasons'),
            'Logistics Reasons': row.get('Logistics Reasons'),
        }
        for row in all_records if row.get('Logistics Status') != LogisticsStatus.PASS_LOGISTICS.value
    ]

    price_update_excluded_sheet = [
        {
            'WooCommerce ID': row.get('WooCommerce ID'),
            'SKU': row.get('SKU'),
            'Current Title': row.get('Current Title'),
            'Current Regular Price': row.get('Current Regular Price'),
            'Current Sale Price': row.get('Current Sale Price'),
            'Benzara Regular Price': row.get('Benzara Price'),
            'Benzara Stock Qty': row.get('Benzara Stock Qty'),
            'Benzara Stock Status': row.get('Benzara Stock Status'),
            'Woo Shipping Class': row.get('Woo Shipping Class'),
            'Logistics Status': row.get('Logistics Status'),
            'Logistics Reasons': row.get('Logistics Reasons'),
            'Catalog Decision': row.get('Catalog Decision'),
            'Price Update Status': row.get('Price Update Status'),
            'Price Update Exclusion Reason': row.get('Price Update Exclusion Reason'),
            'Suggested Action': row.get('Price Update Suggested Action'),
        }
        for row in price_excluded_rows
    ]

    report_sections = {
        'MATCHED_BENZARA': matched_rows,
        'PRICE_UPDATE_PASS': price_ready_rows,
        'PRICE_UPDATE_EXCLUDED': price_update_excluded_sheet,
        'NEW_BENZARA_PASS': [row for row in new_rows if row.get('Catalog Decision') == CatalogDecision.PASS.value],
        'NEW_BENZARA_REVIEW': [row for row in new_rows if row.get('Catalog Decision') in {CatalogDecision.REVIEW.value, CatalogDecision.HOLD_LOGISTICS.value, CatalogDecision.OUT_OF_STOCK.value}],
        'HOLD_LOGISTICS': [row for row in all_records if row.get('Logistics Status') == LogisticsStatus.HOLD_LOGISTICS.value],
        'OUT_OF_STOCK': [row for row in all_records if row.get('Catalog Decision') == CatalogDecision.OUT_OF_STOCK.value],
        'ORPHAN_STORE': orphan_rows,
        'OTHER_SUPPLIER': other_supplier_rows,
        'CONFLICTS': conflict_rows,
        'DATA_QUALITY': data_quality_rows,
        'SUPPLIER_CLASSIFICATION': supplier_rows,
        'LOGISTICS_DIAGNOSTICS': logistics_rows,
    }

    summary_rows = _summary_count_rows(all_records, match_results, price_ready_rows, price_excluded_rows)
    summary_rows.extend(_counter_rows(all_records, 'Primary Category', 'Breakdown', 'Primary Category'))
    summary_rows.extend(_counter_rows(all_records, 'Benzara Brand', 'Breakdown', 'Brand'))
    summary_rows.extend(_counter_rows(all_records, 'Catalog Decision', 'Breakdown', 'Catalog Decision'))
    summary_rows.extend(_counter_rows(all_records, 'Price Update Status', 'Breakdown', 'Price Update Status'))
    summary_rows.extend(_counter_rows(price_excluded_rows, 'Price Update Exclusion Reason', 'Breakdown', 'Price Update Exclusion Reason'))
    summary_rows.extend(_counter_rows(all_records, 'Data Quality Status', 'Breakdown', 'Data Quality Status'))
    summary_rows.extend(_counter_rows(all_records, 'Supplier Classification', 'Breakdown', 'Supplier Classification'))
    summary_rows.extend(_counter_rows(all_records, 'Woo Shipping Class', 'Woo Breakdown', 'Shipping Class'))
    summary_rows.extend(_counter_rows(all_records, 'Current Stock Status', 'Woo Breakdown', 'Stock Status'))

    rules_rows = [
        {'Section': 'Run', 'Rule': 'timestamp_utc', 'Value': datetime.now(timezone.utc).isoformat()},
        {'Section': 'Run', 'Rule': 'version', 'Value': 'phase-2-safety-review'},
        {'Section': 'Logistics', 'Rule': 'dim_divisor', 'Value': settings.logistics.dim_divisor},
        {'Section': 'Logistics', 'Rule': 'hold.actual_weight_lb_gt', 'Value': settings.logistics.hold.actual_weight_lb_gt},
        {'Section': 'Logistics', 'Rule': 'hold.longest_side_in_gt', 'Value': settings.logistics.hold.longest_side_in_gt},
        {'Section': 'Logistics', 'Rule': 'hold.length_plus_girth_in_gt', 'Value': settings.logistics.hold.length_plus_girth_in_gt},
        {'Section': 'Logistics', 'Rule': 'hold.volume_in3_gt', 'Value': settings.logistics.hold.volume_in3_gt},
        {'Section': 'Logistics', 'Rule': 'hold.dim_weight_lb_gt', 'Value': settings.logistics.hold.dim_weight_lb_gt},
        {'Section': 'Logistics', 'Rule': 'review.actual_weight_lb_min', 'Value': settings.logistics.review.actual_weight_lb_min},
        {'Section': 'Logistics', 'Rule': 'review.actual_weight_lb_max', 'Value': settings.logistics.review.actual_weight_lb_max},
        {'Section': 'Supplier', 'Rule': 'benzara_sku_prefixes', 'Value': ';'.join(settings.supplier.benzara_sku_prefixes)},
        {'Section': 'Supplier', 'Rule': 'benzara_brands', 'Value': ';'.join(settings.supplier.benzara_brands)},
        {'Section': 'Supplier', 'Rule': 'historical_import_meta_keys', 'Value': ';'.join(settings.supplier.historical_import_meta_keys)},
        {'Section': 'Price Update', 'Rule': 'eligibility', 'Value': 'matched + pass logistics + in stock + valid Benzara price + not bundle + no conflict'},
    ]

    manual_review_rows = _build_manual_review_rows(all_records)
    log_lines = [
        f"config={settings.app.name}",
        f"benzara_records={len(benzara_products)}",
        f"woocommerce_records={len(woo_products)}",
        *(f"bucket.{key}={len(value)}" for key, value in match_results.items()),
        f"price_ready={len(price_ready_rows)}",
        f"price_excluded={len(price_excluded_rows)}",
        f"data_quality_critical={sum(1 for row in all_records if row.get('Data Quality Status') == 'CRITICAL')}",
        f"manual_review_queue={len(manual_review_rows)}",
    ]

    return {
        'match_results': match_results,
        'all_records': all_records,
        'report_sections': report_sections,
        'summary_rows': summary_rows,
        'rules_rows': rules_rows,
        'manual_review_rows': manual_review_rows,
        'price_rows': price_ready_rows,
        'log_lines': log_lines,
    }

