"""Operational decision rules."""

from __future__ import annotations

from .models import CatalogDecision, LogisticsEvaluation, LogisticsStatus


def decide_catalog_status(product: dict, logistics: LogisticsEvaluation) -> CatalogDecision:
    stock_status = str(product.get("stock_status") or "").lower()
    stock_qty = product.get("stock_qty")
    if stock_status != "instock" or stock_qty is None or stock_qty <= 0:
        return CatalogDecision.OUT_OF_STOCK
    if logistics.status is LogisticsStatus.HOLD_LOGISTICS:
        return CatalogDecision.HOLD_LOGISTICS
    if logistics.status is LogisticsStatus.REVIEW_LOGISTICS:
        return CatalogDecision.REVIEW
    return CatalogDecision.PASS
