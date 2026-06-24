"""Operational decision rules."""

from __future__ import annotations

from .models import CatalogDecision, LogisticsEvaluation


def decide_catalog_status(product: dict, logistics: LogisticsEvaluation) -> CatalogDecision:
    _ = product
    if logistics.status.value == "HOLD_LOGISTICS":
        return CatalogDecision.HOLD_LOGISTICS
    return CatalogDecision.REVIEW

