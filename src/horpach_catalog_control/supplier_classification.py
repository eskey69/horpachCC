"""Supplier classification helpers."""

from __future__ import annotations

from .models import SupplierClassification, SupplierClassificationResult


BENZARA_BUCKETS = {"MATCHED_BENZARA", "NEW_BENZARA"}


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _starts_with_any(value: str | None, prefixes: list[str]) -> bool:
    if value is None:
        return False
    upper = value.upper()
    return any(upper.startswith(prefix.upper()) for prefix in prefixes)


def classify_supplier(*, bucket: str, woo: dict | None, config, known_benzara_brands: set[str]) -> SupplierClassificationResult:
    if bucket in BENZARA_BUCKETS:
        return SupplierClassificationResult(
            classification=SupplierClassification.BENZARA_MATCHED,
            reason_codes=["current_benzara_feed_record"],
        )

    woo = woo or {}
    sku = _normalize(woo.get("sku"))
    title = (_normalize(woo.get("title")) or "").lower()
    brand = (_normalize(woo.get("brand")) or "").lower()
    prefixed_meta = woo.get("prefixed_meta", {}) or {}

    if _starts_with_any(sku, config.benzara_sku_prefixes):
        return SupplierClassificationResult(
            classification=SupplierClassification.BENZARA_ORPHAN_SUSPECTED,
            reason_codes=["benzara_like_sku_prefix"],
        )

    if any(key in prefixed_meta for key in config.historical_import_meta_keys):
        return SupplierClassificationResult(
            classification=SupplierClassification.BENZARA_ORPHAN_SUSPECTED,
            reason_codes=["historical_import_metadata_present"],
        )

    if any(signal in title for signal in known_benzara_brands) or any(signal and signal in brand for signal in known_benzara_brands):
        return SupplierClassificationResult(
            classification=SupplierClassification.BENZARA_ORPHAN_SUSPECTED,
            reason_codes=["benzara_brand_like_signal"],
        )

    if _starts_with_any(sku, config.confirmed_other_supplier_prefixes):
        return SupplierClassificationResult(
            classification=SupplierClassification.OTHER_SUPPLIER_CONFIRMED,
            reason_codes=["known_other_supplier_sku_prefix"],
        )

    if any(brand_signal.lower() in title or brand_signal.lower() in brand for brand_signal in config.confirmed_other_supplier_brands):
        return SupplierClassificationResult(
            classification=SupplierClassification.OTHER_SUPPLIER_CONFIRMED,
            reason_codes=["known_other_supplier_brand_signal"],
        )

    return SupplierClassificationResult(
        classification=SupplierClassification.UNKNOWN_SUPPLIER,
        reason_codes=["insufficient_supplier_evidence"],
    )


def suggest_supplier_action(result: SupplierClassificationResult) -> str:
    if result.classification is SupplierClassification.BENZARA_MATCHED:
        return "Treat as active Benzara record"
    if result.classification is SupplierClassification.BENZARA_ORPHAN_SUSPECTED:
        return "Review as likely historical Benzara product"
    if result.classification is SupplierClassification.OTHER_SUPPLIER_CONFIRMED:
        return "Keep outside Benzara update workflow"
    return "Manual supplier verification required"
