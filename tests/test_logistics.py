from horpach_catalog_control.decisions import decide_catalog_status
from horpach_catalog_control.logistics import calculate_metrics, evaluate_logistics
from horpach_catalog_control.models import CatalogDecision, LogisticsStatus


def test_calculate_metrics_computes_expected_values():
    metrics = calculate_metrics({"length_in": 20, "width_in": 10, "height_in": 5, "weight_lb": 8})
    assert metrics.volume_in3 == 1000
    assert round(metrics.dim_weight_lb, 4) == round(1000 / 139, 4)
    assert metrics.girth_in == 30
    assert metrics.length_plus_girth_in == 50
    assert metrics.billable_weight_lb == 8


def test_logistics_pass_for_small_complete_product():
    result = evaluate_logistics({
        "name": "Small Stool",
        "weight_lb": 12,
        "length_in": 18,
        "width_in": 18,
        "height_in": 18,
        "shipping_class": "small-parcel",
    })
    assert result.status is LogisticsStatus.PASS_LOGISTICS
    assert result.reason_codes == []


def test_logistics_review_for_borderline_and_keyword_product():
    result = evaluate_logistics({
        "name": "Glass Accent Table",
        "weight_lb": 40,
        "length_in": 45,
        "width_in": 8,
        "height_in": 8,
        "shipping_class": "small-parcel",
    })
    assert result.status is LogisticsStatus.REVIEW_LOGISTICS
    assert "weight_review_band" in result.reason_codes
    assert "longest_side_review_band" in result.reason_codes
    assert "keyword_review_flag" in result.reason_codes


def test_logistics_hold_for_freight_or_oversize_product():
    result = evaluate_logistics({
        "title": "Large Dresser",
        "weight_lb": 80,
        "length_in": 60,
        "width_in": 22,
        "height_in": 40,
        "shipping_class": "Freight Quote",
    })
    assert result.status is LogisticsStatus.HOLD_LOGISTICS
    assert "weight_over_50lb" in result.reason_codes
    assert "freight_shipping_class" in result.reason_codes


def test_logistics_review_for_missing_weight_or_dimensions():
    result = evaluate_logistics({"title": "Unknown Item", "length_in": 20, "width_in": 10})
    assert result.status is LogisticsStatus.REVIEW_LOGISTICS
    assert "missing_shipping_dimensions_or_weight" in result.reason_codes


def test_catalog_decision_out_of_stock_takes_precedence():
    logistics = evaluate_logistics({
        "title": "Large Dresser",
        "weight_lb": 80,
        "length_in": 60,
        "width_in": 22,
        "height_in": 40,
        "shipping_class": "Freight Quote",
    })
    decision = decide_catalog_status({"stock_status": "outofstock", "stock_qty": 0}, logistics)
    assert decision is CatalogDecision.OUT_OF_STOCK


def test_catalog_decision_pass_when_instock_and_logistics_pass():
    logistics = evaluate_logistics({
        "name": "Small Stool",
        "weight_lb": 12,
        "length_in": 18,
        "width_in": 18,
        "height_in": 18,
        "shipping_class": "small-parcel",
    })
    decision = decide_catalog_status({"stock_status": "instock", "stock_qty": 10}, logistics)
    assert decision is CatalogDecision.PASS
