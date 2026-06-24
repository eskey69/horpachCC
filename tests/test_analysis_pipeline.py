from pathlib import Path

from horpach_catalog_control.analysis import build_pipeline_outputs
from horpach_catalog_control.benzara_parser import parse_benzara_xml
from horpach_catalog_control.config import Settings
from horpach_catalog_control.price_exports import build_price_update_rows
from horpach_catalog_control.woo_wxr_parser import parse_woocommerce_wxr


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def build_settings(*, permissive: bool = False) -> Settings:
    hold_longest_side_limit = 999999 if permissive else 48
    hold_length_plus_girth_limit = 999999 if permissive else 130
    hold_volume_limit = 999999 if permissive else 17280
    hold_dim_weight_limit = 999999 if permissive else 70
    review_weight_min = 999 if permissive else 35
    review_weight_max = 1000 if permissive else 50
    review_longest_side_min = 999 if permissive else 42
    review_longest_side_max = 1000 if permissive else 48
    review_dim_weight_min = 999 if permissive else 50
    review_dim_weight_max = 1000 if permissive else 70
    review_keywords = [] if permissive else ["mirror", "glass", "set of"]

    return Settings.model_validate(
        {
            "app": {"name": "test", "log_file": "output/run.log"},
            "logistics": {
                "dim_divisor": 139,
                "hold": {
                    "actual_weight_lb_gt": 50,
                    "longest_side_in_gt": hold_longest_side_limit,
                    "length_plus_girth_in_gt": hold_length_plus_girth_limit,
                    "volume_in3_gt": hold_volume_limit,
                    "dim_weight_lb_gt": hold_dim_weight_limit,
                    "shipping_class_keywords": ["freight"],
                },
                "review": {
                    "actual_weight_lb_min": review_weight_min,
                    "actual_weight_lb_max": review_weight_max,
                    "longest_side_in_min": review_longest_side_min,
                    "longest_side_in_max": review_longest_side_max,
                    "dim_weight_lb_min": review_dim_weight_min,
                    "dim_weight_lb_max": review_dim_weight_max,
                    "keyword_flags": review_keywords,
                },
            },
            "supplier": {
                "benzara_sku_prefixes": ["BM", "BMS", "UPT", "BENZ"],
                "benzara_brands": ["Benzara", "The Urban Port", "Benjara"],
                "historical_import_meta_keys": ["_fxc_last_classification", "_horpach_last_auto_cat_result"],
                "confirmed_other_supplier_prefixes": ["ACME"],
                "confirmed_other_supplier_brands": ["Acme Home"],
            },
            "core_candidates": {
                "minimum_stock_qty": 10,
                "lightweight_weight_lb_max": 25,
                "compact_longest_side_in_max": 30,
                "compact_volume_in3_max": 7000,
                "borderline_longest_side_in_min": 30,
                "borderline_volume_in3_min": 5000,
                "excluded_category_keywords": ["patio", "outdoor", "sofa"],
                "excluded_name_keywords": ["patio", "outdoor", "sofa", "sectional"],
                "fragile_keywords": ["mirror", "glass"],
                "patio_keywords": ["patio", "outdoor"],
                "set_keywords": ["set of", "2pc", "3pc"],
                "score_weights": {
                    "pass_logistics": 25,
                    "stock_at_least_threshold": 20,
                    "valid_image_url": 15,
                    "valid_brand": 10,
                    "valid_category": 10,
                    "lightweight_package": 10,
                    "compact_dimensions": 10,
                    "fragile_keyword_penalty": 30,
                    "borderline_dimensions_penalty": 20,
                    "low_stock_penalty": 20,
                    "patio_keyword_penalty": 25,
                    "set_keyword_penalty": 25,
                },
            },
            "reporting": {
                "price_update_csv": "output/IMPORT_PRICE_UPDATE_BENZARA_PASS.csv",
                "workbook": "output/HORPACH_CATALOG_CONTROL_REPORT.xlsx",
                "manual_review_workbook": "output/MANUAL_REVIEW_QUEUE.xlsx",
                "auto_hold_workbook": "output/AUTO_HOLD_SUMMARY.xlsx",
                "core_candidates_workbook": "output/CORE_CANDIDATES.xlsx",
            },
        }
    )


def _row_by_sku(outputs: dict, sku: str) -> dict:
    return next(row for row in outputs["all_records"] if row["SKU"] == sku)


def _summary_value(outputs: dict, metric: str) -> int | str:
    for row in outputs["summary_rows"]:
        if row.get("Metric") == metric and row.get("Key") == "total":
            return row["Value"]
    raise AssertionError(f"Missing summary metric: {metric}")


def test_auto_pass_and_core_candidate_pipeline():
    settings = build_settings(permissive=True)
    benzara = [{
        "sku": "BM-READY",
        "ean": "EAN-1",
        "name": "Accent Chair",
        "regular_price": 129.0,
        "stock_qty": 12,
        "stock_status": "instock",
        "weight_lb": 20,
        "length_in": 20,
        "width_in": 18,
        "height_in": 18,
        "brand": "Benzara",
        "origin": "India",
        "categories": ["Chairs"],
        "images": ["https://example.com/chair.jpg"],
    }]
    woo = [{
        "post_id": 10,
        "sku": "BM-READY",
        "global_unique_id": "EAN-1",
        "title": "Accent Chair",
        "regular_price": 119.0,
        "sale_price": None,
        "stock_qty": 3,
        "stock_status": "instock",
        "shipping_class": "Parcel",
        "categories": ["Living Room"],
        "prefixed_meta": {},
        "meta": {},
        "weight_lb": 20,
        "length_in": 20,
        "width_in": 18,
        "height_in": 18,
    }]

    outputs = build_pipeline_outputs(settings, benzara, woo)
    row = _row_by_sku(outputs, "BM-READY")
    csv_rows = build_price_update_rows(outputs["price_rows"])

    assert row["Recommended Operational Action"] == "AUTO_PASS"
    assert outputs["manual_review_rows"] == []
    assert len(outputs["core_candidate_rows"]) == 1
    assert csv_rows[0]["Meta: _horpach_price_update_status"] == "PRICE_READY"


def test_auto_hold_out_of_stock_does_not_enter_manual_review():
    settings = build_settings(permissive=True)
    outputs = build_pipeline_outputs(
        settings,
        [{
            "sku": "BM-OUT",
            "ean": "EAN-OUT",
            "name": "Accent Stool",
            "regular_price": 149.0,
            "stock_qty": 0,
            "stock_status": "outofstock",
            "weight_lb": 12,
            "length_in": 20,
            "width_in": 18,
            "height_in": 16,
            "brand": "Benzara",
            "origin": "India",
            "categories": ["Stools"],
            "images": ["https://example.com/stool.jpg"],
        }],
        [{
            "post_id": 1,
            "sku": "BM-OUT",
            "global_unique_id": "EAN-OUT",
            "title": "Accent Stool",
            "regular_price": 139.0,
            "sale_price": None,
            "stock_qty": 2,
            "stock_status": "instock",
            "shipping_class": "Parcel",
            "categories": ["Living Room"],
            "prefixed_meta": {},
            "meta": {},
            "weight_lb": 12,
            "length_in": 20,
            "width_in": 18,
            "height_in": 16,
        }],
    )
    row = _row_by_sku(outputs, "BM-OUT")
    assert row["Recommended Operational Action"] == "AUTO_HOLD_OUT_OF_STOCK"
    assert outputs["manual_review_rows"] == []


def test_auto_hold_logistics_does_not_enter_manual_review():
    settings = build_settings(permissive=False)
    outputs = build_pipeline_outputs(
        settings,
        [{
            "sku": "BM-HOLD",
            "ean": "EAN-HOLD",
            "name": "Large Cabinet",
            "regular_price": 299.0,
            "stock_qty": 10,
            "stock_status": "instock",
            "weight_lb": 80,
            "length_in": 60,
            "width_in": 20,
            "height_in": 20,
            "brand": "Benzara",
            "origin": "India",
            "categories": ["Storage"],
            "images": ["https://example.com/cabinet.jpg"],
        }],
        [{
            "post_id": 11,
            "sku": "BM-HOLD",
            "global_unique_id": "EAN-HOLD",
            "title": "Large Cabinet",
            "regular_price": 289.0,
            "sale_price": None,
            "stock_qty": 1,
            "stock_status": "instock",
            "shipping_class": "Freight Quote",
            "categories": ["Storage"],
            "prefixed_meta": {},
            "meta": {},
            "weight_lb": 80,
            "length_in": 60,
            "width_in": 20,
            "height_in": 20,
        }],
    )
    row = _row_by_sku(outputs, "BM-HOLD")
    assert row["Recommended Operational Action"] == "AUTO_HOLD_LOGISTICS"
    assert outputs["manual_review_rows"] == []


def test_archive_orphan_candidate_action():
    settings = build_settings(permissive=True)
    outputs = build_pipeline_outputs(
        settings,
        [],
        [{
            "post_id": 20,
            "sku": "BM-ARCHIVE",
            "global_unique_id": "EAN-ARCHIVE",
            "title": "Benzara Archive Cabinet",
            "regular_price": 189.0,
            "sale_price": None,
            "stock_qty": 5,
            "stock_status": "instock",
            "shipping_class": "Parcel",
            "categories": ["Storage"],
            "prefixed_meta": {"_fxc_last_classification": "parcel"},
            "meta": {},
            "weight_lb": 15,
            "length_in": 20,
            "width_in": 20,
            "height_in": 20,
            "brand": "Benzara",
        }],
    )
    row = _row_by_sku(outputs, "BM-ARCHIVE")
    assert row["Recommended Operational Action"] == "AUTO_ARCHIVE_ORPHAN_CANDIDATE"
    assert outputs["manual_review_rows"] == []


def test_keep_outside_benzara_flow_action():
    settings = build_settings(permissive=True)
    outputs = build_pipeline_outputs(
        settings,
        [],
        [{
            "post_id": 21,
            "sku": "ACME-22",
            "global_unique_id": "EAN-ACME",
            "title": "Acme Home Lamp",
            "regular_price": 89.0,
            "sale_price": None,
            "stock_qty": 6,
            "stock_status": "instock",
            "shipping_class": "Parcel",
            "categories": ["Lighting"],
            "prefixed_meta": {},
            "meta": {},
            "weight_lb": 8,
            "length_in": 12,
            "width_in": 12,
            "height_in": 18,
            "brand": "Acme Home",
        }],
    )
    row = _row_by_sku(outputs, "ACME-22")
    assert row["Recommended Operational Action"] == "KEEP_OUTSIDE_BENZARA_FLOW"
    assert outputs["manual_review_rows"] == []


def test_manual_review_high_for_critical_data_issue():
    settings = build_settings(permissive=True)
    outputs = build_pipeline_outputs(
        settings,
        [{
            "sku": None,
            "ean": "EAN-BAD",
            "name": "Broken Table",
            "regular_price": -10.0,
            "stock_qty": 5,
            "stock_status": "instock",
            "weight_lb": -1,
            "length_in": 10,
            "width_in": 0,
            "height_in": 12,
            "brand": "Benzara",
            "origin": "India",
            "categories": ["Tables"],
            "images": ["https://example.com/broken.jpg"],
        }],
        [],
    )
    row = outputs["all_records"][0]
    assert row["Recommended Operational Action"] == "MANUAL_REVIEW_HIGH"
    assert len(outputs["manual_review_rows"]) == 1
    assert outputs["manual_review_rows"][0]["Review Priority"] == "HIGH"


def test_manual_review_medium_for_review_logistics():
    settings = build_settings(permissive=False)
    outputs = build_pipeline_outputs(
        settings,
        [{
            "sku": "BM-REVIEW",
            "ean": "EAN-REVIEW",
            "name": "Glass Accent Table",
            "regular_price": 129.0,
            "stock_qty": 9,
            "stock_status": "instock",
            "weight_lb": 40,
            "length_in": 45,
            "width_in": 8,
            "height_in": 8,
            "brand": "Benzara",
            "origin": "India",
            "categories": ["Tables"],
            "images": ["https://example.com/table.jpg"],
        }],
        [],
    )
    row = _row_by_sku(outputs, "BM-REVIEW")
    assert row["Recommended Operational Action"] == "MANUAL_REVIEW_MEDIUM"
    assert outputs["manual_review_rows"][0]["Review Priority"] == "MEDIUM"


def test_manual_review_low_for_metadata_only_issue():
    settings = build_settings(permissive=True)
    outputs = build_pipeline_outputs(
        settings,
        [{
            "sku": "BM-LOW",
            "ean": "EAN-LOW",
            "name": "Compact Shelf",
            "regular_price": 109.0,
            "stock_qty": 12,
            "stock_status": "instock",
            "weight_lb": 18,
            "length_in": 20,
            "width_in": 18,
            "height_in": 18,
            "brand": None,
            "origin": "India",
            "categories": ["Storage"],
            "images": ["https://example.com/shelf.jpg"],
        }],
        [],
    )
    row = _row_by_sku(outputs, "BM-LOW")
    assert row["Recommended Operational Action"] == "MANUAL_REVIEW_LOW"
    assert outputs["manual_review_rows"][0]["Review Priority"] == "LOW"


def test_summary_reconciliation_and_manual_queue_excludes_auto_records():
    settings = build_settings(permissive=True)
    benzara_products = parse_benzara_xml(FIXTURE_DIR / "benzara_sample.xml")
    woo_products = parse_woocommerce_wxr(FIXTURE_DIR / "woo_wxr_sample.xml")

    outputs = build_pipeline_outputs(settings, benzara_products, woo_products)
    action_rows = [row for row in outputs["summary_rows"] if row.get("Metric") == "Recommended Operational Action"]
    action_total = sum(row["Value"] for row in action_rows)

    assert action_total == len(outputs["all_records"])
    assert any(row.get("Metric") == "Action Reconciliation" and row.get("Value") == "OK" for row in outputs["summary_rows"])
    assert outputs["manual_review_rows"] == []
    assert _summary_value(outputs, "Core Candidate Count") == 1


