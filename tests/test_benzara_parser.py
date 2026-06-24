from horpach_catalog_control.benzara_parser import inspect_benzara_input, parse_benzara_xml


def test_inspect_benzara_input_reports_path():
    result = inspect_benzara_input("data/latest.xml")
    assert result["path"].endswith("data\\latest.xml") or result["path"].endswith("data/latest.xml")


def test_parse_benzara_xml_returns_list():
    assert parse_benzara_xml("data/latest.xml") == []

