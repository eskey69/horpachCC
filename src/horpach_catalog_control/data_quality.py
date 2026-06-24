"""Data quality analysis for Benzara and WooCommerce records."""

from __future__ import annotations

from collections import Counter

from .models import DataQualityResult, DataQualityStatus

STATUS_RANK = {
    DataQualityStatus.OK: 0,
    DataQualityStatus.REVIEW: 1,
    DataQualityStatus.CRITICAL: 2,
}

CRITICAL_CODES = {
    'missing_sku',
    'missing_woocommerce_sku',
    'missing_price',
    'missing_woocommerce_price',
    'invalid_price',
    'invalid_weight',
    'invalid_dimensions',
    'duplicate_benzara_sku',
    'duplicate_woo_sku',
    'duplicate_ean',
}

REVIEW_CODES = {
    'missing_ean',
    'missing_brand',
    'missing_origin',
    'missing_stock',
    'missing_weight',
    'missing_dimensions',
}


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _as_float(value) -> float | None:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _duplicate_values(records: list[dict], key: str) -> set[str]:
    counter = Counter(_normalize(record.get(key)) for record in records)
    return {value for value, count in counter.items() if value and count > 1}


def build_duplicate_context(benzara_products: list[dict], woo_products: list[dict]) -> dict[str, set[str]]:
    return {
        'duplicate_benzara_sku': _duplicate_values(benzara_products, 'sku'),
        'duplicate_woo_sku': _duplicate_values(woo_products, 'sku'),
        'duplicate_benzara_ean': _duplicate_values(benzara_products, 'ean'),
        'duplicate_woo_ean': _duplicate_values(woo_products, 'global_unique_id'),
    }


def _status_from_codes(codes: list[str]) -> DataQualityStatus:
    if any(code in CRITICAL_CODES for code in codes):
        return DataQualityStatus.CRITICAL
    if any(code in REVIEW_CODES for code in codes):
        return DataQualityStatus.REVIEW
    return DataQualityStatus.OK


def assess_benzara_product(product: dict, duplicate_context: dict[str, set[str]]) -> DataQualityResult:
    reasons: list[str] = []
    sku = _normalize(product.get('sku'))
    ean = _normalize(product.get('ean'))
    brand = _normalize(product.get('brand'))
    origin = _normalize(product.get('origin'))
    price = _as_float(product.get('regular_price'))
    stock_qty = _as_int(product.get('stock_qty'))
    stock_status = _normalize(product.get('stock_status'))
    weight = _as_float(product.get('weight_lb'))
    length = _as_float(product.get('length_in'))
    width = _as_float(product.get('width_in'))
    height = _as_float(product.get('height_in'))

    if sku is None:
        reasons.append('missing_sku')
    if ean is None:
        reasons.append('missing_ean')
    if brand is None:
        reasons.append('missing_brand')
    if origin is None:
        reasons.append('missing_origin')
    if price is None:
        reasons.append('missing_price')
    elif price <= 0:
        reasons.append('invalid_price')
    if stock_status is None or stock_qty is None:
        reasons.append('missing_stock')
    if weight is None:
        reasons.append('missing_weight')
    elif weight <= 0:
        reasons.append('invalid_weight')

    dims = [length, width, height]
    if any(value is None for value in dims):
        reasons.append('missing_dimensions')
    elif any(value <= 0 for value in dims if value is not None):
        reasons.append('invalid_dimensions')

    if sku is not None and sku in duplicate_context['duplicate_benzara_sku']:
        reasons.append('duplicate_benzara_sku')
    if ean is not None and (ean in duplicate_context['duplicate_benzara_ean'] or ean in duplicate_context['duplicate_woo_ean']):
        reasons.append('duplicate_ean')

    deduped = list(dict.fromkeys(reasons))
    return DataQualityResult(status=_status_from_codes(deduped), reason_codes=deduped)


def assess_woo_product(product: dict, duplicate_context: dict[str, set[str]]) -> DataQualityResult:
    reasons: list[str] = []
    sku = _normalize(product.get('sku'))
    ean = _normalize(product.get('global_unique_id'))
    price = _as_float(product.get('regular_price'))
    stock_status = _normalize(product.get('stock_status'))
    weight = _as_float(product.get('weight_lb'))
    length = _as_float(product.get('length_in'))
    width = _as_float(product.get('width_in'))
    height = _as_float(product.get('height_in'))

    if sku is None:
        reasons.append('missing_woocommerce_sku')
    if price is None:
        reasons.append('missing_woocommerce_price')
    elif price <= 0:
        reasons.append('invalid_price')
    if stock_status is None:
        reasons.append('missing_stock')
    if weight is None:
        reasons.append('missing_weight')
    elif weight <= 0:
        reasons.append('invalid_weight')
    dims = [length, width, height]
    if any(value is None for value in dims):
        reasons.append('missing_dimensions')
    elif any(value <= 0 for value in dims if value is not None):
        reasons.append('invalid_dimensions')
    if sku is not None and sku in duplicate_context['duplicate_woo_sku']:
        reasons.append('duplicate_woo_sku')
    if ean is not None and (ean in duplicate_context['duplicate_woo_ean'] or ean in duplicate_context['duplicate_benzara_ean']):
        reasons.append('duplicate_ean')

    deduped = list(dict.fromkeys(reasons))
    return DataQualityResult(status=_status_from_codes(deduped), reason_codes=deduped)


def merge_quality_results(*results: DataQualityResult) -> DataQualityResult:
    filtered = [result for result in results if result is not None]
    if not filtered:
        return DataQualityResult(status=DataQualityStatus.OK, reason_codes=[])
    status = max((result.status for result in filtered), key=lambda item: STATUS_RANK[item])
    reasons: list[str] = []
    for result in filtered:
        reasons.extend(result.reason_codes)
    return DataQualityResult(status=status, reason_codes=list(dict.fromkeys(reasons)))


def suggest_data_quality_action(result: DataQualityResult) -> str:
    if result.status is DataQualityStatus.CRITICAL:
        return 'Fix critical data before import or pricing'
    if result.status is DataQualityStatus.REVIEW:
        return 'Manual data review required'
    return 'No action required'
