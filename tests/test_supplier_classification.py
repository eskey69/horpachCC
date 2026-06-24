from horpach_catalog_control.config import SupplierConfig
from horpach_catalog_control.models import SupplierClassification
from horpach_catalog_control.supplier_classification import classify_supplier, suggest_supplier_action


CONFIG = SupplierConfig(
    benzara_sku_prefixes=["BM", "UPT"],
    benzara_brands=["Benzara", "The Urban Port"],
    historical_import_meta_keys=["_fxc_last_classification"],
    confirmed_other_supplier_prefixes=["ACME"],
    confirmed_other_supplier_brands=["Acme Home"],
)


def test_supplier_classification_marks_current_matches_as_benzara():
    result = classify_supplier(
        bucket="MATCHED_BENZARA",
        woo={"sku": "BM-100"},
        config=CONFIG,
        known_benzara_brands={"benzara"},
    )
    assert result.classification is SupplierClassification.BENZARA_MATCHED
    assert suggest_supplier_action(result) == "Treat as active Benzara match"


def test_supplier_classification_detects_historical_benzara_signals():
    result = classify_supplier(
        bucket="ORPHAN_STORE",
        woo={
            "sku": "BM-100",
            "title": "Archive Cabinet",
            "prefixed_meta": {"_fxc_last_classification": "parcel"},
        },
        config=CONFIG,
        known_benzara_brands={"benzara", "the urban port"},
    )
    assert result.classification is SupplierClassification.BENZARA_ORPHAN_SUSPECTED
    assert result.reason_codes[0] in {"benzara_like_sku_prefix", "historical_import_metadata_present"}


def test_supplier_classification_marks_known_other_supplier():
    result = classify_supplier(
        bucket="OTHER_SUPPLIER",
        woo={"sku": "ACME-22", "title": "Acme Home Lamp", "prefixed_meta": {}},
        config=CONFIG,
        known_benzara_brands={"benzara"},
    )
    assert result.classification is SupplierClassification.OTHER_SUPPLIER_CONFIRMED
    assert suggest_supplier_action(result) == "Keep outside Benzara update workflow"


def test_supplier_classification_falls_back_to_unknown():
    result = classify_supplier(
        bucket="ORPHAN_STORE",
        woo={"sku": "ZZ-22", "title": "Minimal Lamp", "prefixed_meta": {}},
        config=CONFIG,
        known_benzara_brands={"benzara"},
    )
    assert result.classification is SupplierClassification.UNKNOWN_SUPPLIER
