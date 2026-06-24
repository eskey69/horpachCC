from horpach_catalog_control.logistics import evaluate_logistics
from horpach_catalog_control.models import LogisticsStatus


def test_logistics_placeholder_defaults_to_review():
    result = evaluate_logistics({})
    assert result.status is LogisticsStatus.REVIEW_LOGISTICS
    assert "not_implemented" in result.reason_codes

