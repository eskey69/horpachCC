"""Pipeline analysis and report assembly."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .data_quality import assess_benzara_product, assess_woo_product, build_duplicate_context, merge_quality_results
from .models import (
    CatalogDecision,
    CommercialStatus,
    DataQualityStatus,
    LogisticsStatus,
    PriceUpdateResult,
    PriceUpdateStatus,
    RecommendedOperationalAction,
    SupplierClassification,
)
from .logistics import evaluate_logistics
from .matcher import match_products
from .supplier_classification import classify_supplier, suggest_supplier_action

HIGH_REASON_CODES = {
    "missing_sku",
    "missing_woocommerce_sku",
    "invalid_price",
    "invalid_weight",
    "invalid_dimensions",
    "duplicate_benzara_sku",
    "duplicate_woo_sku",
    "duplicate_ean",
}
MEDIUM_REASON_CODES = {
    "missing_weight",
    "missing_dimensions",
    "missing_stock",
    "missing_price",
    "missing_woocommerce_price",
    "suspected_bundle_product",
}
LOW_REASON_CODES = {
    "missing_brand",
    "missing_origin",
    "missing_ean",
}
MANUAL_ACTIONS = {
    RecommendedOperationalAction.MANUAL_REVIEW_HIGH.value,
    RecommendedOperationalAction.MANUAL_REVIEW_MEDIUM.value,
    RecommendedOperationalAction.MANUAL_REVIEW_LOW.value,
}
ROLE_HINTS = (
    ("Occasional Tables", ("side table", "end table", "accent table", "coffee table", "console table", "table")),
    ("Accent Seating", ("chair", "stool", "bench", "ottoman", "accent chair")),
    ("Storage", ("cabinet", "bookcase", "shelf", "sideboard", "console", "dresser")),
    ("Lighting", ("lamp", "lighting", "chandelier", "sconce")),
    ("Decor", ("mirror", "wall art", "artwork", "decor")),
)


def _primary_category(categories: list[str] | None) -> str | None:
    if not categories:
        return None
    return categories[0]


def _is_bundle_product(woo: dict | None) -> bool:
    if not woo:
        return False
    meta = woo.get("meta", {}) or {}
    prefixed_meta = woo.get("prefixed_meta", {}) or {}
    value = prefixed_meta.get("_fxc_bundle_flag") or meta.get("_fxc_bundle_flag")
    return str(value).strip().lower() in {"1", "true", "yes"}


def _valid_positive_price(value) -> bool:
    try:
        return value is not None and float(value) > 0
    except (TypeError, ValueError):
        return False


def _is_instock(product: dict | None) -> bool:
    product = product or {}
    stock_status = str(product.get("stock_status") or "").lower()
    stock_qty = product.get("stock_qty")
    return stock_status == "instock" and stock_qty is not None and stock_qty > 0


def _usable_image_url(benzara: dict | None) -> str | None:
    if not benzara:
        return None
    for value in benzara.get("images") or []:
        candidate = str(value or "").strip()
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return candidate
    return None


def _text_blob(record: dict) -> str:
    return " ".join(
        str(record.get(key) or "")
        for key in ("Title", "Benzara Name", "Primary Category", "Current Categories", "Brand")
    ).lower()


def _dimensions_string(record: dict) -> str:
    values = [record.get("Length in"), record.get("Width in"), record.get("Height in")]
    return " x ".join("" if value is None else str(value) for value in values)


def _determine_commercial_status(bucket: str, logistics, quality, benzara: dict | None, woo: dict | None) -> CommercialStatus:
    if bucket == "ORPHAN_STORE":
        return CommercialStatus.ORPHAN
    if bucket == "OTHER_SUPPLIER":
        return CommercialStatus.OTHER_SUPPLIER
    if bucket == "CONFLICT":
        return CommercialStatus.CONFLICT

    product = benzara or woo or {}
    if not _is_instock(product):
        return CommercialStatus.OUT_OF_STOCK
    if quality.status is DataQualityStatus.CRITICAL:
        return CommercialStatus.MISSING_DATA
    if logistics.status is LogisticsStatus.PASS_LOGISTICS and _valid_positive_price(product.get("regular_price")):
        return CommercialStatus.PRICE_READY
    return CommercialStatus.PRICE_REVIEW


def _determine_catalog_decision(bucket: str, logistics, quality, commercial_status: CommercialStatus) -> CatalogDecision:
    if commercial_status is CommercialStatus.OUT_OF_STOCK:
        return CatalogDecision.OUT_OF_STOCK
    if bucket == "ORPHAN_STORE":
        return CatalogDecision.ORPHAN
    if bucket == "OTHER_SUPPLIER":
        return CatalogDecision.OTHER_SUPPLIER
    if bucket == "CONFLICT":
        return CatalogDecision.CONFLICT
    if logistics.status is LogisticsStatus.HOLD_LOGISTICS:
        return CatalogDecision.HOLD_LOGISTICS
    if logistics.status is LogisticsStatus.REVIEW_LOGISTICS or quality.status is not DataQualityStatus.OK or commercial_status is not CommercialStatus.PRICE_READY:
        return CatalogDecision.REVIEW
    return CatalogDecision.PASS


def _price_update_result(bucket: str, benzara: dict | None, logistics, commercial_status: CommercialStatus, quality, is_bundle: bool) -> PriceUpdateResult:
    if bucket == "CONFLICT":
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_CONFLICT,
            exclusion_reason="Conflicting matched product record",
            suggested_action="Resolve conflict before any pricing decision",
        )
    if bucket != "MATCHED_BENZARA":
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_OTHER,
            exclusion_reason="Product is not an active matched Benzara record",
            suggested_action="Do not use for direct Benzara price update",
        )

    benzara = benzara or {}
    sku = benzara.get("sku")
    price = benzara.get("regular_price")
    if not sku:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_MISSING_SKU,
            exclusion_reason="Missing SKU for matched Benzara product",
            suggested_action="Investigate missing SKU before pricing",
        )
    if price is None:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_MISSING_BENZARA_PRICE,
            exclusion_reason="Missing Benzara regular price in current feed",
            suggested_action="Investigate missing supplier price",
        )
    if not _valid_positive_price(price):
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_INVALID_BENZARA_PRICE,
            exclusion_reason="Invalid Benzara regular price in current feed",
            suggested_action="Manual pricing review required",
        )
    if is_bundle:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_BUNDLE_PRODUCT,
            exclusion_reason="Bundle product is excluded from direct Benzara price update",
            suggested_action="Keep current price; bundle handling is manual",
        )
    if commercial_status is CommercialStatus.OUT_OF_STOCK:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_OUT_OF_STOCK,
            exclusion_reason="Out of stock in current Benzara feed",
            suggested_action="Keep current price; wait for stock",
        )
    if logistics.status is LogisticsStatus.HOLD_LOGISTICS:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_HOLD_LOGISTICS,
            exclusion_reason="Excluded because product is on logistics hold",
            suggested_action="Do not update; logistics hold",
        )
    if logistics.status is LogisticsStatus.REVIEW_LOGISTICS:
        reason = "Review logistics required"
        if logistics.reason_codes:
            reason = f"Review logistics: {', '.join(logistics.reason_codes)}"
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_REVIEW_LOGISTICS,
            exclusion_reason=reason,
            suggested_action="Eligible after logistics review",
        )
    if commercial_status is CommercialStatus.MISSING_DATA or quality.status is DataQualityStatus.CRITICAL:
        return PriceUpdateResult(
            status=PriceUpdateStatus.EXCLUDED_OTHER,
            exclusion_reason="Critical data-quality issue blocks safe pricing",
            suggested_action="Manual pricing review required",
        )
    return PriceUpdateResult(
        status=PriceUpdateStatus.PRICE_READY,
        exclusion_reason="Meets current pricing eligibility rules",
        suggested_action="Safe candidate for price update",
    )

def _combine_reason_codes(logistics, quality, supplier_result, price_update: PriceUpdateResult, is_bundle: bool, bucket: str) -> list[str]:
    reason_codes: list[str] = []
    reason_codes.extend(logistics.reason_codes)
    reason_codes.extend(quality.reason_codes)
    reason_codes.extend(supplier_result.reason_codes)
    if is_bundle:
        reason_codes.append("suspected_bundle_product")
    if price_update.status is PriceUpdateStatus.EXCLUDED_MISSING_BENZARA_PRICE:
        reason_codes.append("missing_benzara_price")
    if price_update.status is PriceUpdateStatus.EXCLUDED_CONFLICT or bucket == "CONFLICT":
        reason_codes.append("match_conflict")
    return list(dict.fromkeys(code for code in reason_codes if code))


def _review_priority(bucket: str, record: dict) -> str | None:
    reasons = set(record.get("Reason Codes List", []))
    if (
        bucket == "CONFLICT"
        or record.get("Catalog Decision") == CatalogDecision.CONFLICT.value
        or record.get("Price Update Status") == PriceUpdateStatus.EXCLUDED_CONFLICT.value
        or record.get("Data Quality Status") == DataQualityStatus.CRITICAL.value
        or any(code in HIGH_REASON_CODES for code in reasons)
    ):
        return "HIGH"
    if (
        record.get("Logistics Status") == LogisticsStatus.REVIEW_LOGISTICS.value
        or record.get("Supplier Classification") == SupplierClassification.UNKNOWN_SUPPLIER.value
        or record.get("Price Update Status") in {
            PriceUpdateStatus.EXCLUDED_MISSING_BENZARA_PRICE.value,
            PriceUpdateStatus.EXCLUDED_REVIEW_LOGISTICS.value,
            PriceUpdateStatus.EXCLUDED_BUNDLE_PRODUCT.value,
        }
        or record.get("Is Bundle Product")
        or any(code in MEDIUM_REASON_CODES for code in reasons)
    ):
        return "MEDIUM"
    if record.get("Data Quality Status") == DataQualityStatus.REVIEW.value or any(code in LOW_REASON_CODES for code in reasons):
        return "LOW"
    return None


def _auto_pass_eligible(record: dict) -> bool:
    return (
        record.get("Logistics Status") == LogisticsStatus.PASS_LOGISTICS.value
        and record.get("Commercial Status") == CommercialStatus.PRICE_READY.value
        and record.get("Data Quality Status") == DataQualityStatus.OK.value
        and record.get("Supplier Classification") == SupplierClassification.BENZARA_MATCHED.value
        and str(record.get("Benzara Stock Status") or "").lower() == "instock"
        and _valid_positive_price(record.get("Benzara Price"))
    )


def _recommended_operational_action(record: dict, priority: str | None) -> RecommendedOperationalAction:
    if priority == "HIGH":
        return RecommendedOperationalAction.MANUAL_REVIEW_HIGH
    if record.get("Supplier Classification") == SupplierClassification.OTHER_SUPPLIER_CONFIRMED.value:
        return RecommendedOperationalAction.KEEP_OUTSIDE_BENZARA_FLOW
    if record.get("Supplier Classification") == SupplierClassification.BENZARA_ORPHAN_SUSPECTED.value:
        return RecommendedOperationalAction.AUTO_ARCHIVE_ORPHAN_CANDIDATE
    if record.get("Logistics Status") == LogisticsStatus.HOLD_LOGISTICS.value:
        return RecommendedOperationalAction.AUTO_HOLD_LOGISTICS
    if record.get("Commercial Status") == CommercialStatus.OUT_OF_STOCK.value:
        return RecommendedOperationalAction.AUTO_HOLD_OUT_OF_STOCK
    if priority == "MEDIUM":
        return RecommendedOperationalAction.MANUAL_REVIEW_MEDIUM
    if priority == "LOW":
        return RecommendedOperationalAction.MANUAL_REVIEW_LOW
    if _auto_pass_eligible(record):
        return RecommendedOperationalAction.AUTO_PASS
    return RecommendedOperationalAction.MANUAL_REVIEW_MEDIUM


def _recommended_action_text(action: RecommendedOperationalAction) -> str:
    if action is RecommendedOperationalAction.AUTO_PASS:
        return "Eligible for future price update, Core shortlist review, or controlled import review."
    if action is RecommendedOperationalAction.AUTO_HOLD_LOGISTICS:
        return "Exclude from active catalog strategy; do not import or promote."
    if action is RecommendedOperationalAction.AUTO_HOLD_OUT_OF_STOCK:
        return "Do not import or publish while unavailable. Recheck in future feed."
    if action is RecommendedOperationalAction.AUTO_ARCHIVE_ORPHAN_CANDIDATE:
        return "Keep existing product unchanged for now; consider hiding or archiving after business review."
    if action is RecommendedOperationalAction.KEEP_OUTSIDE_BENZARA_FLOW:
        return "Keep outside Benzara pricing/import workflow."
    if action is RecommendedOperationalAction.MANUAL_REVIEW_HIGH:
        return "Resolve critical data or match conflict before any pricing or catalog action."
    if action is RecommendedOperationalAction.MANUAL_REVIEW_MEDIUM:
        return "Manual operational review required before pricing or import consideration."
    return "Low-priority metadata review recommended."


def _review_type(record: dict) -> str:
    reasons = set(record.get("Reason Codes List", []))
    if record.get("Catalog Decision") == CatalogDecision.CONFLICT.value or "match_conflict" in reasons:
        return "Conflicting Match"
    if any(code in {"duplicate_benzara_sku", "duplicate_woo_sku", "duplicate_ean"} for code in reasons):
        return "Duplicate Identifier"
    if any(code in {"invalid_price", "invalid_weight", "invalid_dimensions", "missing_sku", "missing_woocommerce_sku"} for code in reasons):
        return "Critical Data Quality"
    if record.get("Logistics Status") == LogisticsStatus.REVIEW_LOGISTICS.value:
        return "Review Logistics"
    if record.get("Supplier Classification") == SupplierClassification.UNKNOWN_SUPPLIER.value:
        return "Unknown Supplier"
    if record.get("Is Bundle Product"):
        return "Bundle Review"
    if any(code in {"missing_weight", "missing_dimensions", "missing_stock", "missing_price", "missing_benzara_price"} for code in reasons):
        return "Missing Operational Data"
    if any(code in LOW_REASON_CODES for code in reasons):
        return "Metadata Completion"
    return "Manual Review"


def _review_batch(priority: str | None) -> str | None:
    if priority == "HIGH":
        return "HIGH_PRIORITY"
    if priority == "MEDIUM":
        return "MEDIUM_PRIORITY"
    if priority == "LOW":
        return "LOW_PRIORITY"
    return None


def _sort_score(priority: str | None) -> int:
    if priority == "HIGH":
        return 100
    if priority == "MEDIUM":
        return 50
    if priority == "LOW":
        return 10
    return 0


def _core_excluded_by_keywords(record: dict, settings) -> bool:
    category_text = " ".join(
        value.lower()
        for value in [record.get("Primary Category"), record.get("Current Categories")]
        if value
    )
    name_text = _text_blob(record)
    if any(keyword.lower() in category_text for keyword in settings.core_candidates.excluded_category_keywords):
        return True
    if any(keyword.lower() in name_text for keyword in settings.core_candidates.excluded_name_keywords):
        return True
    return False


def _infer_role(record: dict) -> str:
    text = _text_blob(record)
    for label, keywords in ROLE_HINTS:
        if any(keyword in text for keyword in keywords):
            return label
    return record.get("Primary Category") or "General Catalog"


def _infer_horpach_category(record: dict) -> str:
    return record.get("Primary Category") or record.get("Current Categories") or _infer_role(record)


def _build_core_candidate_row(record: dict, settings) -> dict | None:
    if record.get("Recommended Operational Action") != RecommendedOperationalAction.AUTO_PASS.value:
        return None
    if _core_excluded_by_keywords(record, settings):
        return None

    weights = settings.core_candidates.score_weights
    text = _text_blob(record)
    stock_qty = record.get("Benzara Stock Qty") or 0
    image_url = record.get("Image URL")
    weight_lb = record.get("Weight lb")
    longest_side = record.get("longest_side_in")
    volume = record.get("volume_in3")

    score = 0
    reasons: list[str] = []

    score += weights.pass_logistics
    reasons.append("PASS_LOGISTICS")
    if stock_qty >= settings.core_candidates.minimum_stock_qty:
        score += weights.stock_at_least_threshold
        reasons.append(f"stock>={settings.core_candidates.minimum_stock_qty}")
    else:
        score -= weights.low_stock_penalty
        reasons.append("low_stock")
    if image_url:
        score += weights.valid_image_url
        reasons.append("valid_image")
    if record.get("Brand"):
        score += weights.valid_brand
        reasons.append("valid_brand")
    if record.get("Primary Category"):
        score += weights.valid_category
        reasons.append("valid_category")
    if weight_lb is not None and weight_lb <= settings.core_candidates.lightweight_weight_lb_max:
        score += weights.lightweight_package
        reasons.append("lightweight_package")
    if longest_side is not None and volume is not None and longest_side <= settings.core_candidates.compact_longest_side_in_max and volume <= settings.core_candidates.compact_volume_in3_max:
        score += weights.compact_dimensions
        reasons.append("compact_package")
    elif longest_side is not None and volume is not None and (longest_side >= settings.core_candidates.borderline_longest_side_in_min or volume >= settings.core_candidates.borderline_volume_in3_min):
        score -= weights.borderline_dimensions_penalty
        reasons.append("borderline_dimensions")
    if any(keyword.lower() in text for keyword in settings.core_candidates.fragile_keywords):
        score -= weights.fragile_keyword_penalty
        reasons.append("fragile_keyword")
    if any(keyword.lower() in text for keyword in settings.core_candidates.patio_keywords):
        score -= weights.patio_keyword_penalty
        reasons.append("patio_keyword")
    if any(keyword.lower() in text for keyword in settings.core_candidates.set_keywords):
        score -= weights.set_keyword_penalty
        reasons.append("set_keyword")

    score = max(0, min(100, score))
    return {
        "Priority Score": score,
        "SKU": record.get("SKU"),
        "Benzara Name": record.get("Benzara Name"),
        "Brand": record.get("Brand"),
        "Primary Category": record.get("Primary Category"),
        "Stock Qty": stock_qty,
        "Benzara Regular Price": record.get("Benzara Price"),
        "Weight lb": record.get("Weight lb"),
        "Length": record.get("Length in"),
        "Width": record.get("Width in"),
        "Height": record.get("Height in"),
        "Volume": record.get("Volume in3"),
        "Dim Weight": record.get("Dim Weight lb"),
        "Length + Girth": record.get("Length + Girth in"),
        "Image URL": image_url,
        "Logistics Status": record.get("Logistics Status"),
        "Data Quality Status": record.get("Data Quality Status"),
        "Recommended Operational Action": record.get("Recommended Operational Action"),
        "Candidate Reasons": "; ".join(reasons),
        "Potential Product Role": _infer_role(record),
        "Potential Horpach Category": _infer_horpach_category(record),
    }

def _base_action_row(record: dict) -> dict:
    return {
        "WooCommerce ID": record.get("WooCommerce ID"),
        "SKU": record.get("SKU"),
        "Title": record.get("Title"),
        "Current Price": record.get("Current Price"),
        "Benzara Price": record.get("Benzara Price"),
        "Stock": record.get("Stock"),
        "Weight": record.get("Weight lb"),
        "Dimensions": _dimensions_string(record),
        "Logistics Status": record.get("Logistics Status"),
        "Commercial Status": record.get("Commercial Status"),
        "Supplier Classification": record.get("Supplier Classification"),
        "Data Quality Status": record.get("Data Quality Status"),
        "Recommended Operational Action": record.get("Recommended Operational Action"),
        "Reason Codes": record.get("Reason Codes"),
        "Suggested Action": record.get("Suggested Action"),
    }


def _manual_review_row(record: dict) -> dict:
    return {
        "Recommended Operational Action": record.get("Recommended Operational Action"),
        "Review Batch": record.get("Review Batch"),
        "Review Priority": record.get("Review Priority"),
        "Sort Score": record.get("Sort Score"),
        "Review Type": record.get("Review Type"),
        "WooCommerce ID": record.get("WooCommerce ID"),
        "SKU": record.get("SKU"),
        "Title": record.get("Title"),
        "Current Price": record.get("Current Price"),
        "Benzara Price": record.get("Benzara Price"),
        "Stock": record.get("Stock"),
        "Weight": record.get("Weight lb"),
        "Dimensions": _dimensions_string(record),
        "Logistics Status": record.get("Logistics Status"),
        "Commercial Status": record.get("Commercial Status"),
        "Supplier Classification": record.get("Supplier Classification"),
        "Reason Codes": record.get("Reason Codes"),
        "Suggested Action": record.get("Suggested Action"),
    }


def _common_row(bucket: str, benzara: dict | None, woo: dict | None, match_strategy: str | None, settings, duplicate_context, known_benzara_brands: set[str]) -> dict:
    source_product = benzara or woo or {}
    logistics = evaluate_logistics(source_product, config=settings.logistics)
    benzara_quality = assess_benzara_product(benzara, duplicate_context) if benzara else None
    woo_quality = assess_woo_product(woo, duplicate_context) if woo else None
    quality = merge_quality_results(*[result for result in (benzara_quality, woo_quality) if result is not None])
    supplier_result = classify_supplier(bucket=bucket, woo=woo, config=settings.supplier, known_benzara_brands=known_benzara_brands)
    is_bundle = _is_bundle_product(woo)
    commercial_status = _determine_commercial_status(bucket, logistics, quality, benzara, woo)
    catalog_decision = _determine_catalog_decision(bucket, logistics, quality, commercial_status)
    price_update = _price_update_result(bucket, benzara, logistics, commercial_status, quality, is_bundle)
    image_url = _usable_image_url(benzara)

    row = {
        "Source Bucket": bucket,
        "Match Strategy": match_strategy,
        "WooCommerce ID": woo.get("post_id") if woo else None,
        "SKU": (benzara or {}).get("sku") or (woo or {}).get("sku"),
        "EAN": (benzara or {}).get("ean") or (woo or {}).get("global_unique_id"),
        "Global Unique ID": (woo or {}).get("global_unique_id"),
        "Current Title": (woo or {}).get("title"),
        "Title": (woo or {}).get("title") or (benzara or {}).get("name"),
        "Current Regular Price": (woo or {}).get("regular_price"),
        "Current Sale Price": (woo or {}).get("sale_price"),
        "Current Price": (woo or {}).get("regular_price"),
        "Benzara Price": (benzara or {}).get("regular_price"),
        "Price": (benzara or {}).get("regular_price") if benzara else (woo or {}).get("regular_price"),
        "Benzara Name": (benzara or {}).get("name"),
        "Benzara Brand": (benzara or {}).get("brand"),
        "Brand": (benzara or {}).get("brand") or (woo or {}).get("brand"),
        "Origin": (benzara or {}).get("origin"),
        "Primary Category": _primary_category((benzara or {}).get("categories")),
        "Current Categories": ", ".join((woo or {}).get("categories") or []),
        "Woo Shipping Class": (woo or {}).get("shipping_class"),
        "Image URL": image_url,
        "Stock": f"{(benzara or woo or {}).get('stock_qty')} / {(benzara or woo or {}).get('stock_status')}",
        "Benzara Stock Qty": (benzara or {}).get("stock_qty"),
        "Benzara Stock Status": (benzara or {}).get("stock_status"),
        "Current Stock Qty": (woo or {}).get("stock_qty"),
        "Current Stock Status": (woo or {}).get("stock_status"),
        "actual_weight_lb": logistics.metrics.actual_weight_lb,
        "length_in": logistics.metrics.length_in,
        "width_in": logistics.metrics.width_in,
        "height_in": logistics.metrics.height_in,
        "volume_in3": logistics.metrics.volume_in3,
        "dim_weight_lb": logistics.metrics.dim_weight_lb,
        "girth_in": logistics.metrics.girth_in,
        "length_plus_girth_in": logistics.metrics.length_plus_girth_in,
        "billable_weight_lb": logistics.metrics.billable_weight_lb,
        "longest_side_in": logistics.metrics.longest_side_in,
        "Weight lb": logistics.metrics.actual_weight_lb,
        "Length in": logistics.metrics.length_in,
        "Width in": logistics.metrics.width_in,
        "Height in": logistics.metrics.height_in,
        "Volume in3": logistics.metrics.volume_in3,
        "Dim Weight lb": logistics.metrics.dim_weight_lb,
        "Length + Girth in": logistics.metrics.length_plus_girth_in,
        "Logistics Status": logistics.status.value,
        "Logistics Reasons": ";".join(logistics.reason_codes),
        "Logistics Reasons List": logistics.reason_codes,
        "logistics_threshold_hits": ";".join(logistics.threshold_hits),
        "logistics_missing_data": bool(logistics.missing_data),
        "logistics_missing_data_reasons": ";".join(logistics.missing_data),
        "Commercial Status": commercial_status.value,
        "Catalog Decision": catalog_decision.value,
        "Price Update Status": price_update.status.value,
        "Price Update Exclusion Reason": price_update.exclusion_reason,
        "Price Update Suggested Action": price_update.suggested_action,
        "Data Quality Status": quality.status.value,
        "Data Quality Reason Codes": ";".join(quality.reason_codes),
        "Data Quality Reason Codes List": quality.reason_codes,
        "Supplier Classification": supplier_result.classification.value,
        "Classification Reason Codes": ";".join(supplier_result.reason_codes),
        "Classification Reason Codes List": supplier_result.reason_codes,
        "Supplier Suggested Action": suggest_supplier_action(supplier_result),
        "Is Bundle Product": is_bundle,
        "Recommended Price Update": (benzara or {}).get("regular_price") if price_update.status is PriceUpdateStatus.PRICE_READY else None,
    }

    row["Reason Codes List"] = _combine_reason_codes(logistics, quality, supplier_result, price_update, is_bundle, bucket)
    row["Reason Codes"] = ";".join(row["Reason Codes List"])
    row["Review Priority"] = _review_priority(bucket, row)
    row["Review Batch"] = _review_batch(row["Review Priority"])
    row["Sort Score"] = _sort_score(row["Review Priority"])
    row["Recommended Operational Action"] = _recommended_operational_action(row, row["Review Priority"]).value
    row["Review Type"] = _review_type(row)
    row["Operational Suggested Action"] = _recommended_action_text(RecommendedOperationalAction(row["Recommended Operational Action"]))
    row["Suggested Action"] = row["Operational Suggested Action"]
    return row


def _conflict_row(conflict: dict, settings, duplicate_context, known_benzara_brands: set[str]) -> dict:
    woo = conflict.get("woo")
    benzara = conflict.get("benzara")
    record = _common_row("CONFLICT", benzara, woo, None, settings, duplicate_context, known_benzara_brands)
    record.update(
        {
            "Conflict Type": conflict.get("type"),
            "Woo Candidate Count": len(conflict.get("woo_candidates") or []),
            "Price Update Status": PriceUpdateStatus.EXCLUDED_CONFLICT.value,
            "Price Update Exclusion Reason": "Excluded due to conflicting match state",
            "Price Update Suggested Action": "Resolve conflict before any update",
            "Reason Codes List": list(dict.fromkeys(record.get("Reason Codes List", []) + ["match_conflict"])),
        }
    )
    record["Reason Codes"] = ";".join(record["Reason Codes List"])
    record["Review Priority"] = _review_priority("CONFLICT", record)
    record["Review Batch"] = _review_batch(record["Review Priority"])
    record["Sort Score"] = _sort_score(record["Review Priority"])
    record["Recommended Operational Action"] = _recommended_operational_action(record, record["Review Priority"]).value
    record["Review Type"] = _review_type(record)
    record["Operational Suggested Action"] = _recommended_action_text(RecommendedOperationalAction(record["Recommended Operational Action"]))
    record["Suggested Action"] = record["Operational Suggested Action"]
    return record

def _counter_rows(records: list[dict], field: str, section: str, label: str) -> list[dict]:
    counter = Counter((record.get(field) or "Unknown") for record in records)
    return [{"Section": section, "Metric": label, "Key": key, "Value": value} for key, value in counter.most_common()]


def _summary_count_rows(all_records: list[dict], match_results: dict[str, list[dict]], price_ready_rows: list[dict], price_excluded_rows: list[dict], core_candidate_rows: list[dict]) -> list[dict]:
    return [
        {"Section": "Counts", "Metric": "WooCommerce products", "Key": "total", "Value": sum(len(match_results[key]) for key in ("MATCHED_BENZARA", "ORPHAN_STORE", "OTHER_SUPPLIER", "CONFLICT"))},
        {"Section": "Counts", "Metric": "Benzara products", "Key": "total", "Value": sum(len(match_results[key]) for key in ("MATCHED_BENZARA", "NEW_BENZARA", "CONFLICT"))},
        {"Section": "Counts", "Metric": "Total analyzed records", "Key": "total", "Value": len(all_records)},
        {"Section": "Counts", "Metric": "Matched", "Key": "total", "Value": len(match_results["MATCHED_BENZARA"])},
        {"Section": "Counts", "Metric": "Price ready", "Key": "total", "Value": len(price_ready_rows)},
        {"Section": "Counts", "Metric": "Price excluded", "Key": "total", "Value": len(price_excluded_rows)},
        {"Section": "Counts", "Metric": "PASS logistics", "Key": "total", "Value": sum(1 for row in all_records if row.get("Logistics Status") == LogisticsStatus.PASS_LOGISTICS.value)},
        {"Section": "Counts", "Metric": "REVIEW logistics", "Key": "total", "Value": sum(1 for row in all_records if row.get("Logistics Status") == LogisticsStatus.REVIEW_LOGISTICS.value)},
        {"Section": "Counts", "Metric": "HOLD logistics", "Key": "total", "Value": sum(1 for row in all_records if row.get("Logistics Status") == LogisticsStatus.HOLD_LOGISTICS.value)},
        {"Section": "Counts", "Metric": "Out of stock", "Key": "total", "Value": sum(1 for row in all_records if row.get("Commercial Status") == CommercialStatus.OUT_OF_STOCK.value)},
        {"Section": "Counts", "Metric": "Data quality critical", "Key": "total", "Value": sum(1 for row in all_records if row.get("Data Quality Status") == DataQualityStatus.CRITICAL.value)},
        {"Section": "Counts", "Metric": "Core Candidate Count", "Key": "total", "Value": len(core_candidate_rows)},
        {"Section": "Counts", "Metric": "Auto Hold Logistics Count", "Key": "total", "Value": sum(1 for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.AUTO_HOLD_LOGISTICS.value)},
        {"Section": "Counts", "Metric": "Auto Hold Out Of Stock Count", "Key": "total", "Value": sum(1 for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.AUTO_HOLD_OUT_OF_STOCK.value)},
        {"Section": "Counts", "Metric": "Archive Orphan Candidate Count", "Key": "total", "Value": sum(1 for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.AUTO_ARCHIVE_ORPHAN_CANDIDATE.value)},
        {"Section": "Counts", "Metric": "Other Supplier Count", "Key": "total", "Value": sum(1 for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.KEEP_OUTSIDE_BENZARA_FLOW.value)},
        {"Section": "Counts", "Metric": "Manual Review Queue Count", "Key": "total", "Value": sum(1 for row in all_records if row.get("Recommended Operational Action") in MANUAL_ACTIONS)},
    ]


def _reconciliation_warnings(all_records: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    total = len(all_records)
    action_counter = Counter(row.get("Recommended Operational Action") for row in all_records)
    reconciled = sum(action_counter.values())
    if total != reconciled:
        warnings.append({"Section": "Validation", "Metric": "Action Reconciliation", "Key": "count_mismatch", "Value": f"{reconciled}/{total}"})
    for row in all_records:
        if not row.get("Recommended Operational Action"):
            warnings.append(
                {
                    "Section": "Validation",
                    "Metric": "Missing Action",
                    "Key": str(row.get("SKU") or row.get("WooCommerce ID") or "unknown"),
                    "Value": row.get("Title") or row.get("Benzara Name") or "Unknown",
                }
            )
    return warnings


def _build_manual_review_rows(records: list[dict]) -> list[dict]:
    rows = [_manual_review_row(record) for record in records if record.get("Recommended Operational Action") in MANUAL_ACTIONS]
    rows.sort(key=lambda row: (-int(row.get("Sort Score") or 0), row.get("Review Type") or "", str(row.get("SKU") or "")))
    return rows


def _build_auto_hold_summary_rows(all_records: list[dict]) -> list[dict]:
    target_actions = {
        RecommendedOperationalAction.AUTO_HOLD_LOGISTICS.value,
        RecommendedOperationalAction.AUTO_HOLD_OUT_OF_STOCK.value,
        RecommendedOperationalAction.AUTO_ARCHIVE_ORPHAN_CANDIDATE.value,
        RecommendedOperationalAction.KEEP_OUTSIDE_BENZARA_FLOW.value,
    }
    rows = []
    for action in sorted(target_actions):
        rows.append({"Section": "Counts", "Metric": "Recommended Operational Action", "Key": action, "Value": sum(1 for row in all_records if row.get("Recommended Operational Action") == action)})
    return rows


def build_pipeline_outputs(settings, benzara_products: list[dict], woo_products: list[dict]) -> dict:
    duplicate_context = build_duplicate_context(benzara_products, woo_products)
    match_results = match_products(benzara_products, woo_products)
    known_benzara_brands = {brand.lower() for brand in settings.supplier.benzara_brands}
    known_benzara_brands.update({str(product.get("brand")).lower() for product in benzara_products if product.get("brand")})

    matched_rows = [
        _common_row("MATCHED_BENZARA", match["benzara"], match["woo"], match.get("match_strategy"), settings, duplicate_context, known_benzara_brands)
        for match in match_results["MATCHED_BENZARA"]
    ]
    new_rows = [
        _common_row("NEW_BENZARA", product, None, "new_benzara", settings, duplicate_context, known_benzara_brands)
        for product in match_results["NEW_BENZARA"]
    ]
    orphan_rows = [
        _common_row("ORPHAN_STORE", None, product, "orphan_store", settings, duplicate_context, known_benzara_brands)
        for product in match_results["ORPHAN_STORE"]
    ]
    other_supplier_rows = [
        _common_row("OTHER_SUPPLIER", None, product, "other_supplier", settings, duplicate_context, known_benzara_brands)
        for product in match_results["OTHER_SUPPLIER"]
    ]
    conflict_rows = [_conflict_row(conflict, settings, duplicate_context, known_benzara_brands) for conflict in match_results["CONFLICT"]]

    all_records = matched_rows + new_rows + orphan_rows + other_supplier_rows + conflict_rows
    price_ready_rows = [row for row in matched_rows if row["Price Update Status"] == PriceUpdateStatus.PRICE_READY.value]
    price_excluded_rows = [row for row in matched_rows if row["Price Update Status"] != PriceUpdateStatus.PRICE_READY.value]

    data_quality_rows = [
        {
            "Source": row.get("Source Bucket"),
            "WooCommerce ID": row.get("WooCommerce ID"),
            "SKU": row.get("SKU"),
            "EAN": row.get("EAN"),
            "Title": row.get("Title"),
            "Data Quality Status": row.get("Data Quality Status"),
            "Reason Codes": row.get("Data Quality Reason Codes"),
            "Suggested Action": "Critical fix required" if row.get("Data Quality Status") == DataQualityStatus.CRITICAL.value else "Manual data review required",
            "Weight": row.get("Weight lb"),
            "Length": row.get("Length in"),
            "Width": row.get("Width in"),
            "Height": row.get("Height in"),
            "Price": row.get("Price"),
            "Stock Status": row.get("Benzara Stock Status") or row.get("Current Stock Status"),
        }
        for row in all_records
        if row.get("Data Quality Status") != DataQualityStatus.OK.value
    ]

    supplier_rows = [
        {
            "WooCommerce ID": row.get("WooCommerce ID"),
            "SKU": row.get("SKU"),
            "Title": row.get("Title"),
            "Brand": row.get("Brand"),
            "Global Unique ID": row.get("Global Unique ID"),
            "Current Categories": row.get("Current Categories"),
            "Supplier Classification": row.get("Supplier Classification"),
            "Classification Reason Codes": row.get("Classification Reason Codes"),
            "Suggested Action": row.get("Supplier Suggested Action"),
        }
        for row in matched_rows + new_rows + orphan_rows + other_supplier_rows + conflict_rows
    ]

    logistics_rows = [
        {
            "Source Bucket": row.get("Source Bucket"),
            "WooCommerce ID": row.get("WooCommerce ID"),
            "SKU": row.get("SKU"),
            "Title": row.get("Title"),
            "logistics_status": row.get("Logistics Status"),
            "actual_weight_lb": row.get("actual_weight_lb"),
            "length_in": row.get("length_in"),
            "width_in": row.get("width_in"),
            "height_in": row.get("height_in"),
            "volume_in3": row.get("volume_in3"),
            "dim_weight_lb": row.get("dim_weight_lb"),
            "girth_in": row.get("girth_in"),
            "length_plus_girth_in": row.get("length_plus_girth_in"),
            "billable_weight_lb": row.get("billable_weight_lb"),
            "longest_side_in": row.get("longest_side_in"),
            "logistics_threshold_hits": row.get("logistics_threshold_hits"),
            "logistics_missing_data": row.get("logistics_missing_data"),
            "logistics_missing_data_reasons": row.get("logistics_missing_data_reasons"),
            "Logistics Reasons": row.get("Logistics Reasons"),
            "Recommended Operational Action": row.get("Recommended Operational Action"),
        }
        for row in all_records
        if row.get("Logistics Status") != LogisticsStatus.PASS_LOGISTICS.value
    ]

    price_update_excluded_sheet = [
        {
            "WooCommerce ID": row.get("WooCommerce ID"),
            "SKU": row.get("SKU"),
            "Current Title": row.get("Current Title"),
            "Current Regular Price": row.get("Current Regular Price"),
            "Current Sale Price": row.get("Current Sale Price"),
            "Benzara Regular Price": row.get("Benzara Price"),
            "Benzara Stock Qty": row.get("Benzara Stock Qty"),
            "Benzara Stock Status": row.get("Benzara Stock Status"),
            "Woo Shipping Class": row.get("Woo Shipping Class"),
            "Logistics Status": row.get("Logistics Status"),
            "Logistics Reasons": row.get("Logistics Reasons"),
            "Catalog Decision": row.get("Catalog Decision"),
            "Price Update Status": row.get("Price Update Status"),
            "Price Update Exclusion Reason": row.get("Price Update Exclusion Reason"),
            "Suggested Action": row.get("Price Update Suggested Action"),
        }
        for row in price_excluded_rows
    ]

    auto_pass_rows = [_base_action_row(row) for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.AUTO_PASS.value]
    auto_hold_logistics_rows = [_base_action_row(row) for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.AUTO_HOLD_LOGISTICS.value]
    auto_hold_out_of_stock_rows = [_base_action_row(row) for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.AUTO_HOLD_OUT_OF_STOCK.value]
    auto_archive_orphan_rows = [_base_action_row(row) for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.AUTO_ARCHIVE_ORPHAN_CANDIDATE.value]
    keep_outside_rows = [_base_action_row(row) for row in all_records if row.get("Recommended Operational Action") == RecommendedOperationalAction.KEEP_OUTSIDE_BENZARA_FLOW.value]

    core_candidate_rows = [row for row in (_build_core_candidate_row(record, settings) for record in all_records) if row is not None]
    core_candidate_rows.sort(key=lambda row: (-int(row.get("Priority Score") or 0), str(row.get("SKU") or "")))

    report_sections = {
        "MATCHED_BENZARA": matched_rows,
        "PRICE_UPDATE_PASS": price_ready_rows,
        "PRICE_UPDATE_EXCLUDED": price_update_excluded_sheet,
        "AUTO_PASS": auto_pass_rows,
        "AUTO_HOLD_LOGISTICS": auto_hold_logistics_rows,
        "AUTO_HOLD_OUT_OF_STOCK": auto_hold_out_of_stock_rows,
        "AUTO_ARCHIVE_ORPHAN_CANDIDATES": auto_archive_orphan_rows,
        "KEEP_OUTSIDE_BENZARA_FLOW": keep_outside_rows,
        "CORE_CANDIDATES": core_candidate_rows,
        "NEW_BENZARA_PASS": [row for row in new_rows if row.get("Catalog Decision") == CatalogDecision.PASS.value],
        "NEW_BENZARA_REVIEW": [row for row in new_rows if row.get("Catalog Decision") in {CatalogDecision.REVIEW.value, CatalogDecision.HOLD_LOGISTICS.value, CatalogDecision.OUT_OF_STOCK.value}],
        "HOLD_LOGISTICS": [row for row in all_records if row.get("Logistics Status") == LogisticsStatus.HOLD_LOGISTICS.value],
        "OUT_OF_STOCK": [row for row in all_records if row.get("Catalog Decision") == CatalogDecision.OUT_OF_STOCK.value],
        "ORPHAN_STORE": orphan_rows,
        "OTHER_SUPPLIER": other_supplier_rows,
        "CONFLICTS": conflict_rows,
        "DATA_QUALITY": data_quality_rows,
        "SUPPLIER_CLASSIFICATION": supplier_rows,
        "LOGISTICS_DIAGNOSTICS": logistics_rows,
    }

    summary_rows = _summary_count_rows(all_records, match_results, price_ready_rows, price_excluded_rows, core_candidate_rows)
    summary_rows.extend(_counter_rows(all_records, "Recommended Operational Action", "Breakdown", "Recommended Operational Action"))
    summary_rows.extend(_counter_rows([row for row in all_records if row.get("Review Priority")], "Review Priority", "Breakdown", "Manual Review Priority"))
    summary_rows.extend(_counter_rows(all_records, "Primary Category", "Breakdown", "Primary Category"))
    summary_rows.extend(_counter_rows(all_records, "Benzara Brand", "Breakdown", "Brand"))
    summary_rows.extend(_counter_rows(all_records, "Catalog Decision", "Breakdown", "Catalog Decision"))
    summary_rows.extend(_counter_rows(all_records, "Price Update Status", "Breakdown", "Price Update Status"))
    summary_rows.extend(_counter_rows(price_excluded_rows, "Price Update Exclusion Reason", "Breakdown", "Price Update Exclusion Reason"))
    summary_rows.extend(_counter_rows(all_records, "Data Quality Status", "Breakdown", "Data Quality Status"))
    summary_rows.extend(_counter_rows(all_records, "Supplier Classification", "Breakdown", "Supplier Classification"))
    summary_rows.extend(_counter_rows(all_records, "Woo Shipping Class", "Woo Breakdown", "Shipping Class"))
    summary_rows.extend(_counter_rows(all_records, "Current Stock Status", "Woo Breakdown", "Stock Status"))
    reconciliation_rows = _reconciliation_warnings(all_records)
    summary_rows.extend(reconciliation_rows or [{"Section": "Validation", "Metric": "Action Reconciliation", "Key": "status", "Value": "OK"}])

    rules_rows = [
        {"Section": "Run", "Rule": "timestamp_utc", "Value": datetime.now(timezone.utc).isoformat()},
        {"Section": "Run", "Rule": "version", "Value": "phase-3-operational-actions"},
        {"Section": "Logistics", "Rule": "dim_divisor", "Value": settings.logistics.dim_divisor},
        {"Section": "Logistics", "Rule": "hold.actual_weight_lb_gt", "Value": settings.logistics.hold.actual_weight_lb_gt},
        {"Section": "Logistics", "Rule": "hold.longest_side_in_gt", "Value": settings.logistics.hold.longest_side_in_gt},
        {"Section": "Logistics", "Rule": "hold.length_plus_girth_in_gt", "Value": settings.logistics.hold.length_plus_girth_in_gt},
        {"Section": "Logistics", "Rule": "hold.volume_in3_gt", "Value": settings.logistics.hold.volume_in3_gt},
        {"Section": "Logistics", "Rule": "hold.dim_weight_lb_gt", "Value": settings.logistics.hold.dim_weight_lb_gt},
        {"Section": "Logistics", "Rule": "review.actual_weight_lb_min", "Value": settings.logistics.review.actual_weight_lb_min},
        {"Section": "Logistics", "Rule": "review.actual_weight_lb_max", "Value": settings.logistics.review.actual_weight_lb_max},
        {"Section": "Supplier", "Rule": "benzara_sku_prefixes", "Value": ";".join(settings.supplier.benzara_sku_prefixes)},
        {"Section": "Supplier", "Rule": "benzara_brands", "Value": ";".join(settings.supplier.benzara_brands)},
        {"Section": "Supplier", "Rule": "historical_import_meta_keys", "Value": ";".join(settings.supplier.historical_import_meta_keys)},
        {"Section": "Action", "Rule": "AUTO_PASS", "Value": "pass logistics + price ready + data quality OK + Benzara matched + in stock + valid Benzara price"},
        {"Section": "Action", "Rule": "AUTO_HOLD_LOGISTICS", "Value": "hold logistics unless escalated by critical conflict"},
        {"Section": "Action", "Rule": "AUTO_HOLD_OUT_OF_STOCK", "Value": "out of stock unless escalated by critical data issue"},
        {"Section": "Action", "Rule": "AUTO_ARCHIVE_ORPHAN_CANDIDATE", "Value": "suspected historical Benzara orphan without severe invalid/conflict state"},
        {"Section": "Action", "Rule": "KEEP_OUTSIDE_BENZARA_FLOW", "Value": "confirmed non-Benzara supplier record"},
        {"Section": "Core Candidates", "Rule": "minimum_stock_qty", "Value": settings.core_candidates.minimum_stock_qty},
        {"Section": "Core Candidates", "Rule": "excluded_category_keywords", "Value": ";".join(settings.core_candidates.excluded_category_keywords)},
        {"Section": "Core Candidates", "Rule": "excluded_name_keywords", "Value": ";".join(settings.core_candidates.excluded_name_keywords)},
        {"Section": "Price Update", "Rule": "eligibility", "Value": "matched + pass logistics + in stock + valid Benzara price + not bundle + no conflict"},
    ]

    manual_review_rows = _build_manual_review_rows(all_records)
    auto_hold_summary_rows = _build_auto_hold_summary_rows(all_records)
    auto_hold_sections = {
        "AUTO_HOLD_LOGISTICS": auto_hold_logistics_rows,
        "AUTO_HOLD_OUT_OF_STOCK": auto_hold_out_of_stock_rows,
        "AUTO_ARCHIVE_ORPHAN_CANDIDATES": auto_archive_orphan_rows,
        "KEEP_OUTSIDE_BENZARA_FLOW": keep_outside_rows,
    }

    log_lines = [
        f"config={settings.app.name}",
        f"benzara_records={len(benzara_products)}",
        f"woocommerce_records={len(woo_products)}",
        *(f"bucket.{key}={len(value)}" for key, value in match_results.items()),
        f"price_ready={len(price_ready_rows)}",
        f"price_excluded={len(price_excluded_rows)}",
        f"data_quality_critical={sum(1 for row in all_records if row.get('Data Quality Status') == DataQualityStatus.CRITICAL.value)}",
        f"manual_review_queue={len(manual_review_rows)}",
        f"core_candidates={len(core_candidate_rows)}",
        f"auto_hold_logistics={len(auto_hold_logistics_rows)}",
        f"auto_hold_out_of_stock={len(auto_hold_out_of_stock_rows)}",
        f"auto_archive_orphan_candidates={len(auto_archive_orphan_rows)}",
        f"keep_outside_benzara_flow={len(keep_outside_rows)}",
        f"validation_warnings={len(reconciliation_rows)}",
    ]

    return {
        "match_results": match_results,
        "all_records": all_records,
        "report_sections": report_sections,
        "summary_rows": summary_rows,
        "rules_rows": rules_rows,
        "manual_review_rows": manual_review_rows,
        "price_rows": price_ready_rows,
        "core_candidate_rows": core_candidate_rows,
        "auto_hold_summary_rows": auto_hold_summary_rows,
        "auto_hold_sections": auto_hold_sections,
        "validation_warnings": reconciliation_rows,
        "log_lines": log_lines,
    }


