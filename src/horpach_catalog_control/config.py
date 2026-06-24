"""Configuration loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class HoldConfig(BaseModel):
    actual_weight_lb_gt: float
    longest_side_in_gt: float
    length_plus_girth_in_gt: float
    volume_in3_gt: float
    dim_weight_lb_gt: float
    shipping_class_keywords: list[str] = Field(default_factory=list)


class ReviewConfig(BaseModel):
    actual_weight_lb_min: float
    actual_weight_lb_max: float
    longest_side_in_min: float
    longest_side_in_max: float
    dim_weight_lb_min: float
    dim_weight_lb_max: float
    keyword_flags: list[str] = Field(default_factory=list)


class LogisticsConfig(BaseModel):
    dim_divisor: float
    hold: HoldConfig
    review: ReviewConfig


class SupplierConfig(BaseModel):
    benzara_sku_prefixes: list[str] = Field(default_factory=list)
    benzara_brands: list[str] = Field(default_factory=list)
    historical_import_meta_keys: list[str] = Field(default_factory=list)
    confirmed_other_supplier_prefixes: list[str] = Field(default_factory=list)
    confirmed_other_supplier_brands: list[str] = Field(default_factory=list)


class CoreCandidateWeights(BaseModel):
    pass_logistics: int = 25
    stock_at_least_threshold: int = 20
    valid_image_url: int = 15
    valid_brand: int = 10
    valid_category: int = 10
    lightweight_package: int = 10
    compact_dimensions: int = 10
    fragile_keyword_penalty: int = 30
    borderline_dimensions_penalty: int = 20
    low_stock_penalty: int = 20
    patio_keyword_penalty: int = 25
    set_keyword_penalty: int = 25


class CoreCandidateConfig(BaseModel):
    minimum_stock_qty: int = 10
    lightweight_weight_lb_max: float = 25.0
    compact_longest_side_in_max: float = 30.0
    compact_volume_in3_max: float = 7000.0
    borderline_longest_side_in_min: float = 30.0
    borderline_volume_in3_min: float = 5000.0
    excluded_category_keywords: list[str] = Field(default_factory=list)
    excluded_name_keywords: list[str] = Field(default_factory=list)
    fragile_keywords: list[str] = Field(default_factory=list)
    patio_keywords: list[str] = Field(default_factory=list)
    set_keywords: list[str] = Field(default_factory=list)
    score_weights: CoreCandidateWeights = Field(default_factory=CoreCandidateWeights)


class ReportingConfig(BaseModel):
    price_update_csv: str
    workbook: str
    manual_review_workbook: str
    auto_hold_workbook: str
    core_candidates_workbook: str


class AppConfig(BaseModel):
    name: str
    log_file: str


class Settings(BaseModel):
    app: AppConfig
    logistics: LogisticsConfig
    supplier: SupplierConfig
    core_candidates: CoreCandidateConfig
    reporting: ReportingConfig



def load_config(config_path: str | Path = "config.yaml") -> Settings:
    path = Path(config_path)
    with path.open("r", encoding="utf-8-sig") as handle:
        content = handle.read()
    try:
        import yaml  # type: ignore

        raw: dict[str, Any] = yaml.safe_load(content) or {}
    except ModuleNotFoundError:
        raw = json.loads(content)
    return Settings.model_validate(raw)
