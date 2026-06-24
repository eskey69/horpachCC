from pathlib import Path

from horpach_catalog_control.woo_wxr_parser import inspect_woocommerce_input, parse_woocommerce_wxr


FIXTURE = Path(__file__).parent / "fixtures" / "woo_wxr_sample.xml"


def test_inspect_woocommerce_input_reports_products():
    result = inspect_woocommerce_input(FIXTURE)
    assert result["root_tag"] == "rss"
    assert result["product_records"] == 1


def test_parse_woocommerce_wxr_extracts_namespaced_meta():
    records = parse_woocommerce_wxr(FIXTURE)
    assert len(records) == 1
    assert records[0]["post_id"] == 101
    assert records[0]["sku"] == "BENZ-001"
    assert records[0]["global_unique_id"] == "1234567890123"
    assert records[0]["content"] == "Long content"
    assert records[0]["excerpt"] == "Short excerpt"
    assert records[0]["categories"] == ["Living Room"]
    assert records[0]["tags"] == ["featured"]
    assert records[0]["shipping_class"] == "Freight Quote"
    assert records[0]["prefixed_meta"]["_horpach_catalog_decision"] == "PASS"
