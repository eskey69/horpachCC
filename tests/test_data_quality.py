from horpach_catalog_control.data_quality import (
    assess_benzara_product,
    assess_woo_product,
    build_duplicate_context,
    merge_quality_results,
)
from horpach_catalog_control.models import DataQualityStatus


def test_assess_benzara_product_marks_missing_shipping_data_as_review():
    duplicate_context = build_duplicate_context([], [])
    result = assess_benzara_product(
        {
            "sku": "BM-1",
            "ean": "111",
            "brand": "Benzara",
            "origin": "India",
            "regular_price": 99.0,
            "stock_qty": 5,
            "stock_status": "instock",
            "weight_lb": None,
            "length_in": 10,
            "width_in": None,
            "height_in": 12,
        },
        duplicate_context,
    )
    assert result.status is DataQualityStatus.REVIEW
    assert "missing_weight" in result.reason_codes
    assert "missing_dimensions" in result.reason_codes


def test_assess_benzara_product_marks_invalid_values_and_missing_sku_as_critical():
    duplicate_context = build_duplicate_context([], [])
    result = assess_benzara_product(
        {
            "sku": None,
            "ean": "111",
            "brand": "Benzara",
            "origin": "India",
            "regular_price": -10,
            "stock_qty": 5,
            "stock_status": "instock",
            "weight_lb": -1,
            "length_in": 10,
            "width_in": 0,
            "height_in": 12,
        },
        duplicate_context,
    )
    assert result.status is DataQualityStatus.CRITICAL
    assert "missing_sku" in result.reason_codes
    assert "invalid_price" in result.reason_codes
    assert "invalid_weight" in result.reason_codes
    assert "invalid_dimensions" in result.reason_codes


def test_duplicate_context_flags_duplicate_sku_and_duplicate_ean():
    duplicate_context = build_duplicate_context(
        [
            {"sku": "BM-1", "ean": "EAN-1"},
            {"sku": "BM-1", "ean": "EAN-2"},
        ],
        [
            {"sku": "WOO-1", "global_unique_id": "EAN-2"},
            {"sku": "WOO-1", "global_unique_id": "EAN-2"},
        ],
    )
    benzara_result = assess_benzara_product(
        {
            "sku": "BM-1",
            "ean": "EAN-2",
            "brand": "Benzara",
            "origin": "India",
            "regular_price": 100,
            "stock_qty": 5,
            "stock_status": "instock",
            "weight_lb": 10,
            "length_in": 10,
            "width_in": 10,
            "height_in": 10,
        },
        duplicate_context,
    )
    woo_result = assess_woo_product(
        {
            "sku": "WOO-1",
            "global_unique_id": "EAN-2",
            "regular_price": 80,
            "stock_status": "instock",
            "weight_lb": 5,
            "length_in": 8,
            "width_in": 8,
            "height_in": 8,
        },
        duplicate_context,
    )
    merged = merge_quality_results(benzara_result, woo_result)

    assert benzara_result.status is DataQualityStatus.CRITICAL
    assert "duplicate_benzara_sku" in benzara_result.reason_codes
    assert "duplicate_ean" in benzara_result.reason_codes
    assert woo_result.status is DataQualityStatus.CRITICAL
    assert "duplicate_woo_sku" in woo_result.reason_codes
    assert "duplicate_ean" in woo_result.reason_codes
    assert merged.status is DataQualityStatus.CRITICAL
