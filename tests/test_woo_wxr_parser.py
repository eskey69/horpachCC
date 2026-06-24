from horpach_catalog_control.woo_wxr_parser import inspect_woocommerce_input, parse_woocommerce_wxr


def test_inspect_woocommerce_input_reports_path():
    result = inspect_woocommerce_input("data/store.xml")
    assert "path" in result


def test_parse_woocommerce_wxr_returns_list():
    assert parse_woocommerce_wxr("data/store.xml") == []

