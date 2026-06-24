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


class CatalogDecision(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    HOLD_LOGISTICS = "HOLD_LOGISTICS"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    ORPHAN = "ORPHAN"
    OTHER_SUPPLIER = "OTHER_SUPPLIER"
    CONFLICT = "CONFLICT"


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
    volume_in3: float | None = None
    dim_weight_lb: float | None = None
    girth_in: float | None = None
    length_plus_girth_in: float | None = None
    billable_weight_lb: float | None = None


class LogisticsEvaluation(BaseModel):
    status: LogisticsStatus
    reason_codes: list[str] = Field(default_factory=list)
    metrics: LogisticsMetrics = Field(default_factory=LogisticsMetrics)

