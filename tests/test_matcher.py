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


def test_matcher_matches_on_sku():
    benzara = [{"sku": "ABC-1", "ean": "111"}]
    woo = [{"post_id": 10, "sku": "ABC-1", "global_unique_id": "111"}]
    result = match_products(benzara, woo)
    assert len(result["MATCHED_BENZARA"]) == 1
    assert result["MATCHED_BENZARA"][0]["match_strategy"] == "sku"


def test_matcher_falls_back_to_ean_when_sku_missing_in_store_match():
    benzara = [{"sku": "ABC-1", "ean": "111"}]
    woo = [{"post_id": 11, "sku": None, "global_unique_id": "111"}]
    result = match_products(benzara, woo)
    assert len(result["MATCHED_BENZARA"]) == 1
    assert result["MATCHED_BENZARA"][0]["match_strategy"] == "ean"


def test_matcher_marks_orphan_store_when_sku_not_in_benzara():
    benzara = [{"sku": "ABC-1", "ean": "111"}]
    woo = [{"post_id": 12, "sku": "ZZZ-9", "global_unique_id": "999"}]
    result = match_products(benzara, woo)
    assert len(result["ORPHAN_STORE"]) == 1


def test_matcher_marks_other_supplier_when_store_sku_missing():
    result = match_products([], [{"post_id": 13, "sku": None, "global_unique_id": None}])
    assert len(result["OTHER_SUPPLIER"]) == 1


def test_matcher_marks_conflict_for_duplicate_woo_sku():
    benzara = [{"sku": "ABC-1", "ean": "111"}]
    woo = [
        {"post_id": 14, "sku": "ABC-1", "global_unique_id": "111"},
        {"post_id": 15, "sku": "ABC-1", "global_unique_id": "222"},
    ]
    result = match_products(benzara, woo)
    assert len(result["CONFLICT"]) == 1
    assert result["CONFLICT"][0]["type"] == "duplicate_woo_sku"
