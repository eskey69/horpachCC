"""Logistics calculations and status classification."""

from __future__ import annotations

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
    "screen",
)
DEFAULT_HOLD_SHIPPING_KEYWORDS = ("freight",)


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
    dim_divisor = float(_cfg_get(config, 'dim_divisor', default=DEFAULT_DIM_DIVISOR))
    length = _safe_float(product.get("length_in"))
    width = _safe_float(product.get("width_in"))
    height = _safe_float(product.get("height_in"))
    weight = _safe_float(product.get("weight_lb"))

    volume = None
    dim_weight = None
    girth = None
    length_plus_girth = None
    billable_weight = None

    if length is not None and width is not None and height is not None:
        volume = length * width * height
        dim_weight = volume / dim_divisor
        girth = 2 * (width + height)
        length_plus_girth = length + girth
    if weight is not None or dim_weight is not None:
        billable_weight = max(value for value in (weight, dim_weight) if value is not None)

    return LogisticsMetrics(
        volume_in3=volume,
        dim_weight_lb=dim_weight,
        girth_in=girth,
        length_plus_girth_in=length_plus_girth,
        billable_weight_lb=billable_weight,
    )


def evaluate_logistics(product: dict, config=None) -> LogisticsEvaluation:
    metrics = calculate_metrics(product, config=config)
    reasons: list[str] = []

    hold_weight_gt = float(_cfg_get(config, 'hold', 'actual_weight_lb_gt', default=DEFAULT_HOLD_WEIGHT_GT))
    hold_longest_side_gt = float(_cfg_get(config, 'hold', 'longest_side_in_gt', default=DEFAULT_HOLD_LONGEST_SIDE_GT))
    hold_length_plus_girth_gt = float(_cfg_get(config, 'hold', 'length_plus_girth_in_gt', default=DEFAULT_HOLD_LENGTH_PLUS_GIRTH_GT))
    hold_volume_gt = float(_cfg_get(config, 'hold', 'volume_in3_gt', default=DEFAULT_HOLD_VOLUME_GT))
    hold_dim_weight_gt = float(_cfg_get(config, 'hold', 'dim_weight_lb_gt', default=DEFAULT_HOLD_DIM_WEIGHT_GT))
    hold_shipping_keywords = tuple(_cfg_get(config, 'hold', 'shipping_class_keywords', default=list(DEFAULT_HOLD_SHIPPING_KEYWORDS)))
    review_weight_min = float(_cfg_get(config, 'review', 'actual_weight_lb_min', default=DEFAULT_REVIEW_WEIGHT_MIN))
    review_weight_max = float(_cfg_get(config, 'review', 'actual_weight_lb_max', default=DEFAULT_REVIEW_WEIGHT_MAX))
    review_longest_side_min = float(_cfg_get(config, 'review', 'longest_side_in_min', default=DEFAULT_REVIEW_LONGEST_SIDE_MIN))
    review_longest_side_max = float(_cfg_get(config, 'review', 'longest_side_in_max', default=DEFAULT_REVIEW_LONGEST_SIDE_MAX))
    review_dim_weight_min = float(_cfg_get(config, 'review', 'dim_weight_lb_min', default=DEFAULT_REVIEW_DIM_WEIGHT_MIN))
    review_dim_weight_max = float(_cfg_get(config, 'review', 'dim_weight_lb_max', default=DEFAULT_REVIEW_DIM_WEIGHT_MAX))
    review_keywords = tuple(_cfg_get(config, 'review', 'keyword_flags', default=list(DEFAULT_REVIEW_KEYWORDS)))

    weight = _safe_float(product.get("weight_lb"))
    length = _safe_float(product.get("length_in"))
    width = _safe_float(product.get("width_in"))
    height = _safe_float(product.get("height_in"))
    longest_side = max(value for value in (length, width, height) if value is not None) if any(
        value is not None for value in (length, width, height)
    ) else None

    shipping_class = str(product.get("shipping_class") or "")
    text_blob = " ".join(
        str(product.get(key) or "")
        for key in ("name", "title", "description", "short_description", "material", "color")
    ).lower()

    if weight is None or length is None or width is None or height is None:
        reasons.append("missing_shipping_dimensions_or_weight")

    if weight is not None and weight > hold_weight_gt:
        reasons.append("weight_over_50lb")
    if longest_side is not None and longest_side > hold_longest_side_gt:
        reasons.append("longest_side_over_48in")
    if metrics.length_plus_girth_in is not None and metrics.length_plus_girth_in > hold_length_plus_girth_gt:
        reasons.append("length_plus_girth_over_130in")
    if metrics.volume_in3 is not None and metrics.volume_in3 > hold_volume_gt:
        reasons.append("volume_over_17280in3")
    if metrics.dim_weight_lb is not None and metrics.dim_weight_lb > hold_dim_weight_gt:
        reasons.append("dim_weight_over_70lb")
    if any(keyword.lower() in shipping_class.lower() for keyword in hold_shipping_keywords):
        reasons.append("freight_shipping_class")

    hold_reasons = {
        "weight_over_50lb",
        "longest_side_over_48in",
        "length_plus_girth_over_130in",
        "volume_over_17280in3",
        "dim_weight_over_70lb",
        "freight_shipping_class",
    }
    if any(reason in hold_reasons for reason in reasons):
        return LogisticsEvaluation(status=LogisticsStatus.HOLD_LOGISTICS, reason_codes=reasons, metrics=metrics)

    if weight is not None and review_weight_min <= weight <= review_weight_max:
        reasons.append("weight_review_band")
    if longest_side is not None and review_longest_side_min <= longest_side <= review_longest_side_max:
        reasons.append("longest_side_review_band")
    if metrics.dim_weight_lb is not None and review_dim_weight_min <= metrics.dim_weight_lb <= review_dim_weight_max:
        reasons.append("dim_weight_review_band")
    if any(keyword.lower() in text_blob for keyword in review_keywords):
        reasons.append("keyword_review_flag")

    if reasons:
        return LogisticsEvaluation(status=LogisticsStatus.REVIEW_LOGISTICS, reason_codes=reasons, metrics=metrics)
    return LogisticsEvaluation(status=LogisticsStatus.PASS_LOGISTICS, reason_codes=[], metrics=metrics)
