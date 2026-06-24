"""Logistics calculations and status classification."""

from __future__ import annotations

import re

from .models import LogisticsEvaluation, LogisticsMetrics, LogisticsStatus

DEFAULT_DIM_DIVISOR = 139.0
DEFAULT_HOLD_WEIGHT_GT = 50.0
DEFAULT_HOLD_LONGEST_SIDE_GT = 48.0
DEFAULT_HOLD_LENGTH_PLUS_GIRTH_GT = 130.0
DEFAULT_HOLD_VOLUME_GT = 17280.0
DEFAULT_HOLD_DIM_WEIGHT_GT = 70.0
DEFAULT_REVIEW_WEIGHT_MIN = 35.0
DEFAULT_REVIEW_WEIGHT_MAX = 50.0
DEFAULT_REVIEW_LONGEST_SIDE_MIN = 42.0
DEFAULT_REVIEW_LONGEST_SIDE_MAX = 48.0
DEFAULT_REVIEW_DIM_WEIGHT_MIN = 50.0
DEFAULT_REVIEW_DIM_WEIGHT_MAX = 70.0
DEFAULT_REVIEW_KEYWORDS = (
    "fragile",
    "mirror",
    "glass",
    "marble",
    "patio",
    "room divider",
    "divider",
    "screen",
    "wall art",
    "canvas art",
    "artwork",
    "set of",
    "2pc",
    "3pc",
    "4pc",
    "5pc",
    "6pc",
    "piece set",
)
DEFAULT_HOLD_SHIPPING_KEYWORDS = ("freight",)
SET_PATTERNS = (
    r"\bset of\b",
    r"\b\d+pc\b",
    r"\b\d+ piece\b",
    r"\bmulti[- ]piece\b",
)

HOLD_REASON_CODES = {
    "weight_over_50lb",
    "longest_side_over_48in",
    "length_plus_girth_over_130in",
    "volume_over_17280in3",
    "dim_weight_over_70lb",
    "freight_shipping_class",
}


def _safe_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cfg_get(config, *path, default=None):
    current = config
    for segment in path:
        if current is None:
            return default
        if hasattr(current, segment):
            current = getattr(current, segment)
        elif isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return default
    return current


def calculate_metrics(product: dict, config=None) -> LogisticsMetrics:
    dim_divisor = float(_cfg_get(config, "dim_divisor", default=DEFAULT_DIM_DIVISOR))
    weight = _safe_float(product.get("weight_lb"))
    length = _safe_float(product.get("length_in"))
    width = _safe_float(product.get("width_in"))
    height = _safe_float(product.get("height_in"))

    volume = None
    dim_weight = None
    girth = None
    length_plus_girth = None
    longest_side = None
    billable_weight = None

    valid_dimensions = all(value is not None and value > 0 for value in (length, width, height))
    if valid_dimensions:
        volume = length * width * height
        dim_weight = volume / dim_divisor
        girth = 2 * (width + height)
        length_plus_girth = length + girth
        longest_side = max(length, width, height)
    elif any(value is not None for value in (length, width, height)):
        longest_side = max(value for value in (length, width, height) if value is not None)

    candidate_weights = [value for value in (weight, dim_weight) if value is not None]
    if candidate_weights:
        billable_weight = max(candidate_weights)

    return LogisticsMetrics(
        actual_weight_lb=weight,
        length_in=length,
        width_in=width,
        height_in=height,
        volume_in3=volume,
        dim_weight_lb=dim_weight,
        girth_in=girth,
        length_plus_girth_in=length_plus_girth,
        billable_weight_lb=billable_weight,
        longest_side_in=longest_side,
    )


def evaluate_logistics(product: dict, config=None) -> LogisticsEvaluation:
    metrics = calculate_metrics(product, config=config)
    reason_codes: list[str] = []
    threshold_hits: list[str] = []
    missing_data: list[str] = []

    hold_weight_gt = float(_cfg_get(config, "hold", "actual_weight_lb_gt", default=DEFAULT_HOLD_WEIGHT_GT))
    hold_longest_side_gt = float(_cfg_get(config, "hold", "longest_side_in_gt", default=DEFAULT_HOLD_LONGEST_SIDE_GT))
    hold_length_plus_girth_gt = float(_cfg_get(config, "hold", "length_plus_girth_in_gt", default=DEFAULT_HOLD_LENGTH_PLUS_GIRTH_GT))
    hold_volume_gt = float(_cfg_get(config, "hold", "volume_in3_gt", default=DEFAULT_HOLD_VOLUME_GT))
    hold_dim_weight_gt = float(_cfg_get(config, "hold", "dim_weight_lb_gt", default=DEFAULT_HOLD_DIM_WEIGHT_GT))
    hold_shipping_keywords = tuple(_cfg_get(config, "hold", "shipping_class_keywords", default=list(DEFAULT_HOLD_SHIPPING_KEYWORDS)))
    review_weight_min = float(_cfg_get(config, "review", "actual_weight_lb_min", default=DEFAULT_REVIEW_WEIGHT_MIN))
    review_weight_max = float(_cfg_get(config, "review", "actual_weight_lb_max", default=DEFAULT_REVIEW_WEIGHT_MAX))
    review_longest_side_min = float(_cfg_get(config, "review", "longest_side_in_min", default=DEFAULT_REVIEW_LONGEST_SIDE_MIN))
    review_longest_side_max = float(_cfg_get(config, "review", "longest_side_in_max", default=DEFAULT_REVIEW_LONGEST_SIDE_MAX))
    review_dim_weight_min = float(_cfg_get(config, "review", "dim_weight_lb_min", default=DEFAULT_REVIEW_DIM_WEIGHT_MIN))
    review_dim_weight_max = float(_cfg_get(config, "review", "dim_weight_lb_max", default=DEFAULT_REVIEW_DIM_WEIGHT_MAX))
    review_keywords = tuple(_cfg_get(config, "review", "keyword_flags", default=list(DEFAULT_REVIEW_KEYWORDS)))

    shipping_class = str(product.get("shipping_class") or "")
    text_blob = " ".join(
        str(product.get(key) or "")
        for key in ("name", "title", "description", "short_description", "material", "color")
    ).lower()
    has_set_pattern = any(re.search(pattern, text_blob) for pattern in SET_PATTERNS)

    if metrics.actual_weight_lb is None:
        missing_data.append("missing_weight")
    elif metrics.actual_weight_lb <= 0:
        missing_data.append("invalid_weight")

    dimension_values = (metrics.length_in, metrics.width_in, metrics.height_in)
    if any(value is None for value in dimension_values):
        missing_data.append("missing_dimensions")
    elif any(value <= 0 for value in dimension_values if value is not None):
        missing_data.append("invalid_dimensions")

    if "missing_weight" in missing_data or "missing_dimensions" in missing_data:
        reason_codes.append("missing_shipping_dimensions_or_weight")
    if "invalid_weight" in missing_data:
        reason_codes.append("invalid_weight")
    if "invalid_dimensions" in missing_data:
        reason_codes.append("invalid_dimensions")

    if metrics.actual_weight_lb is not None and metrics.actual_weight_lb > hold_weight_gt:
        threshold_hits.append("actual_weight_over_50lb")
        reason_codes.append("weight_over_50lb")
    if metrics.longest_side_in is not None and metrics.longest_side_in > hold_longest_side_gt:
        threshold_hits.append("longest_side_over_48in")
        reason_codes.append("longest_side_over_48in")
    if metrics.length_plus_girth_in is not None and metrics.length_plus_girth_in > hold_length_plus_girth_gt:
        threshold_hits.append("length_plus_girth_over_130in")
        reason_codes.append("length_plus_girth_over_130in")
    if metrics.volume_in3 is not None and metrics.volume_in3 > hold_volume_gt:
        threshold_hits.append("volume_over_17280in3")
        reason_codes.append("volume_over_17280in3")
    if metrics.dim_weight_lb is not None and metrics.dim_weight_lb > hold_dim_weight_gt:
        threshold_hits.append("dim_weight_over_70lb")
        reason_codes.append("dim_weight_over_70lb")
    if any(keyword.lower() in shipping_class.lower() for keyword in hold_shipping_keywords):
        threshold_hits.append("freight_shipping_class")
        reason_codes.append("freight_shipping_class")

    if any(code in HOLD_REASON_CODES for code in reason_codes):
        return LogisticsEvaluation(
            status=LogisticsStatus.HOLD_LOGISTICS,
            reason_codes=list(dict.fromkeys(reason_codes)),
            threshold_hits=list(dict.fromkeys(threshold_hits)),
            missing_data=list(dict.fromkeys(missing_data)),
            metrics=metrics,
        )

    if metrics.actual_weight_lb is not None and review_weight_min <= metrics.actual_weight_lb <= review_weight_max:
        threshold_hits.append("actual_weight_review_band")
        reason_codes.append("weight_review_band")
    if metrics.longest_side_in is not None and review_longest_side_min <= metrics.longest_side_in <= review_longest_side_max:
        threshold_hits.append("longest_side_review_band")
        reason_codes.append("longest_side_review_band")
    if metrics.dim_weight_lb is not None and review_dim_weight_min <= metrics.dim_weight_lb <= review_dim_weight_max:
        threshold_hits.append("dim_weight_review_band")
        reason_codes.append("dim_weight_review_band")
    if any(keyword.lower() in text_blob for keyword in review_keywords):
        threshold_hits.append("keyword_review_flag")
        reason_codes.append("keyword_review_flag")
    if has_set_pattern:
        threshold_hits.append("set_or_multi_piece_review")
        reason_codes.append("set_or_multi_piece_review")

    deduped_reasons = list(dict.fromkeys(reason_codes))
    if deduped_reasons:
        return LogisticsEvaluation(
            status=LogisticsStatus.REVIEW_LOGISTICS,
            reason_codes=deduped_reasons,
            threshold_hits=list(dict.fromkeys(threshold_hits)),
            missing_data=list(dict.fromkeys(missing_data)),
            metrics=metrics,
        )
    return LogisticsEvaluation(
        status=LogisticsStatus.PASS_LOGISTICS,
        reason_codes=[],
        threshold_hits=list(dict.fromkeys(threshold_hits)),
        missing_data=list(dict.fromkeys(missing_data)),
        metrics=metrics,
    )
