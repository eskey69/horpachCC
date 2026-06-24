from pathlib import Path

from horpach_catalog_control.analysis import build_pipeline_outputs
from horpach_catalog_control.benzara_parser import parse_benzara_xml
from horpach_catalog_control.config import Settings
from horpach_catalog_control.price_exports import build_price_update_rows
from horpach_catalog_control.woo_wxr_parser import parse_woocommerce_wxr


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def build_settings(*, permissive: bool = False) -> Settings:
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
                    "longest_side_in_gt": 48,
                    "length_plus_girth_in_gt": 130,
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
            "reporting": {
                "price_update_csv": "output/IMPORT_PRICE_UPDATE_BENZARA_PASS.csv",
                "workbook": "output/HORPACH_CATALOG_CONTROL_REPORT.xlsx",
                "manual_review_workbook": "output/MANUAL_REVIEW_QUEUE.xlsx",
            },
        }
    )


def _matched_row(outputs: dict, sku: str) -> dict:
    return next(row for row in outputs["report_sections"]["MATCHED_BENZARA"] if row["SKU"] == sku)


def _summary_value(outputs: dict, metric: str) -> int:
    for row in outputs["summary_rows"]:
        if row.get("Metric") == metric and row.get("Key") == "total":
            return row["Value"]
    raise AssertionError(f"Missing summary metric: {metric}")


def test_pipeline_separates_logistics_commercial_and_catalog_statuses():
    settings = build_settings(permissive=True)
    benzara = [
        {
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
        }
    ]
    woo = [
        {
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
        }
    ]

    outputs = build_pipeline_outputs(settings, benzara, woo)
    row = _matched_row(outputs, "BM-OUT")

    assert row["Logistics Status"] == "PASS_LOGISTICS"
    assert row["Commercial Status"] == "OUT_OF_STOCK"
    assert row["Catalog Decision"] == "OUT_OF_STOCK"
    assert row["Price Update Status"] == "EXCLUDED_OUT_OF_STOCK"
    assert row["Price Update Exclusion Reason"] == "Out of stock in current Benzara feed"


def test_pipeline_marks_missing_benzara_price_as_critical_and_excluded():
    settings = build_settings(permissive=True)
    benzara = [
        {
            "sku": "BM-NOPRICE",
            "ean": "EAN-NOPRICE",
            "name": "Side Table",
            "regular_price": None,
            "stock_qty": 8,
            "stock_status": "instock",
            "weight_lb": 18,
            "length_in": 18,
            "width_in": 18,
            "height_in": 18,
            "brand": "Benzara",
            "origin": "India",
            "categories": ["Tables"],
        }
    ]
    woo = [
        {
            "post_id": 2,
            "sku": "BM-NOPRICE",
            "global_unique_id": "EAN-NOPRICE",
            "title": "Side Table",
            "regular_price": 199.0,
            "sale_price": None,
            "stock_qty": 4,
            "stock_status": "instock",
            "shipping_class": "Parcel",
            "categories": ["Tables"],
            "prefixed_meta": {},
            "meta": {},
            "weight_lb": 18,
            "length_in": 18,
            "width_in": 18,
            "height_in": 18,
        }
    ]

    outputs = build_pipeline_outputs(settings, benzara, woo)
    row = _matched_row(outputs, "BM-NOPRICE")

    assert row["Data Quality Status"] == "CRITICAL"
    assert "missing_price" in row["Data Quality Reason Codes List"]
    assert row["Commercial Status"] == "MISSING_DATA"
    assert row["Catalog Decision"] == "REVIEW"
    assert row["Price Update Status"] == "EXCLUDED_MISSING_BENZARA_PRICE"


def test_pipeline_summary_reconciles_price_ready_and_excluded_counts():
    settings = build_settings(permissive=True)
    benzara = [
        {
            "sku": "BM-READY",
            "ean": "EAN-1",
            "name": "Accent Chair",
            "regular_price": 129.0,
            "stock_qty": 10,
            "stock_status": "instock",
            "weight_lb": 20,
            "length_in": 20,
            "width_in": 18,
            "height_in": 18,
            "brand": "Benzara",
            "origin": "India",
            "categories": ["Chairs"],
        },
        {
            "sku": "BM-HOLD",
            "ean": "EAN-2",
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
        },
    ]
    woo = [
        {
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
        },
        {
            "post_id": 11,
            "sku": "BM-HOLD",
            "global_unique_id": "EAN-2",
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
        },
    ]

    outputs = build_pipeline_outputs(settings, benzara, woo)
    assert len(outputs["match_results"]["MATCHED_BENZARA"]) == 2
    assert len(outputs["price_rows"]) == 1
    assert len(outputs["report_sections"]["PRICE_UPDATE_EXCLUDED"]) == 1
    assert _summary_value(outputs, "Matched") == 2
    assert _summary_value(outputs, "Price ready") == 1
    assert _summary_value(outputs, "Price excluded") == 1


def test_fixture_pipeline_produces_reports_price_rows_and_review_queue():
    settings = build_settings(permissive=True)
    benzara_products = parse_benzara_xml(FIXTURE_DIR / "benzara_sample.xml")
    woo_products = parse_woocommerce_wxr(FIXTURE_DIR / "woo_wxr_sample.xml")

    outputs = build_pipeline_outputs(settings, benzara_products, woo_products)
    price_rows = build_price_update_rows(outputs["price_rows"])

    assert outputs["report_sections"]["MATCHED_BENZARA"]
    assert outputs["summary_rows"]
    assert all(row["Meta: _horpach_price_update_status"] == "PRICE_READY" for row in price_rows)
    assert outputs["manual_review_rows"]
    assert len(outputs["price_rows"]) + len(outputs["report_sections"]["PRICE_UPDATE_EXCLUDED"]) == len(
        outputs["match_results"]["MATCHED_BENZARA"]
    )
