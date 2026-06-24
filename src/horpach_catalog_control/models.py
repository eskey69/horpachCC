"""Normalized models used across the pipeline."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    MATCHED_BENZARA = "MATCHED_BENZARA"
    NEW_BENZARA = "NEW_BENZARA"
    ORPHAN_STORE = "ORPHAN_STORE"
    OTHER_SUPPLIER = "OTHER_SUPPLIER"
    CONFLICT = "CONFLICT"


class LogisticsStatus(str, Enum):
    PASS_LOGISTICS = "PASS_LOGISTICS"
    REVIEW_LOGISTICS = "REVIEW_LOGISTICS"
    HOLD_LOGISTICS = "HOLD_LOGISTICS"


class CommercialStatus(str, Enum):
    PRICE_READY = "PRICE_READY"
    PRICE_REVIEW = "PRICE_REVIEW"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    ORPHAN = "ORPHAN"
    OTHER_SUPPLIER = "OTHER_SUPPLIER"
    CONFLICT = "CONFLICT"
    MISSING_DATA = "MISSING_DATA"


class CatalogDecision(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    HOLD_LOGISTICS = "HOLD_LOGISTICS"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    ORPHAN = "ORPHAN"
    OTHER_SUPPLIER = "OTHER_SUPPLIER"
    CONFLICT = "CONFLICT"


class PriceUpdateStatus(str, Enum):
    PRICE_READY = "PRICE_READY"
    EXCLUDED_OUT_OF_STOCK = "EXCLUDED_OUT_OF_STOCK"
    EXCLUDED_HOLD_LOGISTICS = "EXCLUDED_HOLD_LOGISTICS"
    EXCLUDED_REVIEW_LOGISTICS = "EXCLUDED_REVIEW_LOGISTICS"
    EXCLUDED_MISSING_BENZARA_PRICE = "EXCLUDED_MISSING_BENZARA_PRICE"
    EXCLUDED_INVALID_BENZARA_PRICE = "EXCLUDED_INVALID_BENZARA_PRICE"
    EXCLUDED_BUNDLE_PRODUCT = "EXCLUDED_BUNDLE_PRODUCT"
    EXCLUDED_MISSING_SKU = "EXCLUDED_MISSING_SKU"
    EXCLUDED_CONFLICT = "EXCLUDED_CONFLICT"
    EXCLUDED_OTHER = "EXCLUDED_OTHER"


class DataQualityStatus(str, Enum):
    OK = "OK"
    REVIEW = "REVIEW"
    CRITICAL = "CRITICAL"


class SupplierClassification(str, Enum):
    BENZARA_MATCHED = "BENZARA_MATCHED"
    BENZARA_ORPHAN_SUSPECTED = "BENZARA_ORPHAN_SUSPECTED"
    OTHER_SUPPLIER_CONFIRMED = "OTHER_SUPPLIER_CONFIRMED"
    UNKNOWN_SUPPLIER = "UNKNOWN_SUPPLIER"


class RecommendedOperationalAction(str, Enum):
    AUTO_PASS = "AUTO_PASS"
    AUTO_HOLD_LOGISTICS = "AUTO_HOLD_LOGISTICS"
    AUTO_HOLD_OUT_OF_STOCK = "AUTO_HOLD_OUT_OF_STOCK"
    AUTO_ARCHIVE_ORPHAN_CANDIDATE = "AUTO_ARCHIVE_ORPHAN_CANDIDATE"
    KEEP_OUTSIDE_BENZARA_FLOW = "KEEP_OUTSIDE_BENZARA_FLOW"
    MANUAL_REVIEW_HIGH = "MANUAL_REVIEW_HIGH"
    MANUAL_REVIEW_MEDIUM = "MANUAL_REVIEW_MEDIUM"
    MANUAL_REVIEW_LOW = "MANUAL_REVIEW_LOW"


class InputPaths(BaseModel):
    benzara_input: Path
    woocommerce_input: Path
    output_dir: Path = Path("output")
    dry_run: bool = False


class BenzaraProduct(BaseModel):
    source_id: str | None = None
    sku: str | None = None
    ean: str | None = None
    name: str | None = None
    regular_price: float | None = None
    stock_qty: int | None = None
    stock_status: str | None = None
    weight_lb: float | None = None
    length_in: float | None = None
    width_in: float | None = None
    height_in: float | None = None
    brand: str | None = None


class WooProduct(BaseModel):
    post_id: int | None = None
    sku: str | None = None
    global_unique_id: str | None = None
    title: str | None = None
    post_status: str | None = None
    regular_price: float | None = None
    sale_price: float | None = None
    stock_qty: int | None = None
    stock_status: str | None = None
    shipping_class: str | None = None


class LogisticsMetrics(BaseModel):
    actual_weight_lb: float | None = None
    length_in: float | None = None
    width_in: float | None = None
    height_in: float | None = None
    volume_in3: float | None = None
    dim_weight_lb: float | None = None
    girth_in: float | None = None
    length_plus_girth_in: float | None = None
    billable_weight_lb: float | None = None
    longest_side_in: float | None = None


class LogisticsEvaluation(BaseModel):
    status: LogisticsStatus
    reason_codes: list[str] = Field(default_factory=list)
    threshold_hits: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    metrics: LogisticsMetrics = Field(default_factory=LogisticsMetrics)


class DataQualityResult(BaseModel):
    status: DataQualityStatus
    reason_codes: list[str] = Field(default_factory=list)


class SupplierClassificationResult(BaseModel):
    classification: SupplierClassification
    reason_codes: list[str] = Field(default_factory=list)


class PriceUpdateResult(BaseModel):
    status: PriceUpdateStatus
    exclusion_reason: str
    suggested_action: str
