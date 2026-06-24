"""Logistics calculations and status classification."""

from __future__ import annotations

from .models import LogisticsEvaluation, LogisticsMetrics, LogisticsStatus


def evaluate_logistics(product: dict) -> LogisticsEvaluation:
    _ = product
    return LogisticsEvaluation(
        status=LogisticsStatus.REVIEW_LOGISTICS,
        reason_codes=["not_implemented"],
        metrics=LogisticsMetrics(),
    )

