import pytest

from affiliate_mate.models import ProductCandidate
from affiliate_mate.sensitivity import analyze_sensitivity


def candidate(**overrides):
    data = {
        "product_id": "p1",
        "title": "Widget",
        "marketplace": "DE",
        "currency": "EUR",
        "price": 200.0,
        "commission_rate": 0.05,
        "monthly_searches": 1000,
        "youtube_competition": 40,
        "buyer_intent": 75,
        "content_gap": 65,
        "evidence_quality": 80,
        "estimated_ctr": 0.05,
        "estimated_conversion_rate": 0.04,
    }
    data.update(overrides)
    return ProductCandidate(**data)


def test_default_sensitivity_grid_contains_nine_points():
    report = analyze_sensitivity(candidate())
    assert len(report.points) == 9


def test_base_value_matches_candidate_formula():
    item = candidate()
    report = analyze_sensitivity(item)
    assert report.base_ev_per_1000_views == item.estimated_value_per_1000_views


def test_floor_base_ceiling_are_monotonic():
    report = analyze_sensitivity(candidate())
    assert report.floor_ev_per_1000_views < report.base_ev_per_1000_views
    assert report.base_ev_per_1000_views < report.ceiling_ev_per_1000_views
    assert report.downside_from_base_percent < 0
    assert report.upside_from_base_percent > 0


def test_sensitivity_rejects_non_positive_multipliers():
    with pytest.raises(ValueError, match="must be > 0"):
        analyze_sensitivity(candidate(), ctr_multipliers=(0.0, 1.0))


def test_sensitivity_caps_probability_at_one():
    item = candidate(estimated_ctr=0.9, estimated_conversion_rate=0.9)
    report = analyze_sensitivity(
        item,
        ctr_multipliers=(2.0,),
        conversion_multipliers=(2.0,),
    )
    point = report.points[0]
    assert point.estimated_ctr == 1.0
    assert point.estimated_conversion_rate == 1.0
