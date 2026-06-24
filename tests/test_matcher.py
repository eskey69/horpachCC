from horpach_catalog_control.matcher import match_products


def test_matcher_returns_required_buckets():
    result = match_products([], [])
    assert set(result) == {
        "MATCHED_BENZARA",
        "NEW_BENZARA",
        "ORPHAN_STORE",
        "OTHER_SUPPLIER",
        "CONFLICT",
    }

