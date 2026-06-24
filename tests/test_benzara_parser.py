from pathlib import Path

from horpach_catalog_control.benzara_parser import inspect_benzara_input, parse_benzara_xml


FIXTURE = Path(__file__).parent / "fixtures" / "benzara_sample.xml"


def test_inspect_benzara_input_reports_record_count():
    result = inspect_benzara_input(FIXTURE)
    assert result["root_tag"] == "catalog"
    assert result["product_like_records"] == 2


def test_parse_benzara_xml_extracts_core_fields():
    records = parse_benzara_xml(FIXTURE)
    assert len(records) == 2
    assert records[0]["sku"] == "BENZ-001"
    assert records[0]["regular_price"] == 129.99
    assert records[0]["stock_qty"] == 8
    assert records[0]["categories"] == ["Accent Chair", "Living Room"]
    assert records[0]["images"] == ["https://example.com/a.jpg", "https://example.com/b.jpg"]
    assert records[0]["brand"] == "Benzara"
    assert records[0]["material"] == "Rosewood"
