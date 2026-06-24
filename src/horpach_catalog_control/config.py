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


class ReportingConfig(BaseModel):
    price_update_csv: str
    workbook: str


class AppConfig(BaseModel):
    name: str
    log_file: str


class Settings(BaseModel):
    app: AppConfig
    logistics: LogisticsConfig
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
