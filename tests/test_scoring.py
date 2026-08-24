from affiliate_mate.models import ProductCandidate
from affiliate_mate.scoring import (
    explain_score,
    rank_candidates,
    score_candidate,
    score_contributions,
)


def candidate(**overrides):
    data = {
        "product_id": "A1",
        "title": "Test Product",
        "marketplace": "DE",
        "currency": "EUR",
        "price": 250.0,
        "commission_rate": 0.04,
        "monthly_searches": 1200,
        "youtube_competition": 35,
        "buyer_intent": 80,
        "content_gap": 70,
        "evidence_quality": 75,
        "estimated_ctr": 0.05,
        "estimated_conversion_rate": 0.03,
    }
    data.update(overrides)
    return ProductCandidate(**data)


def test_commission_and_value_math():
    item = candidate()
    assert item.commission_per_sale == 10.0
    assert item.estimated_value_per_1000_views == 15.0


def test_score_stays_in_range():
    result = score_candidate(candidate())
    assert 0 <= result.opportunity_score <= 100


def test_lower_competition_improves_score():
    low = score_candidate(candidate(youtube_competition=10)).opportunity_score
    high = score_candidate(candidate(youtube_competition=90)).opportunity_score
    assert low > high


def test_ranking_prefers_stronger_opportunity():
    weak = candidate(
        product_id="weak",
        commission_rate=0.01,
        monthly_searches=50,
        youtube_competition=90,
        buyer_intent=30,
        content_gap=20,
    )
    strong = candidate(
        product_id="strong",
        commission_rate=0.08,
        monthly_searches=5000,
        youtube_competition=20,
        buyer_intent=90,
        content_gap=85,
    )
    ranked = rank_candidates([weak, strong])
    assert ranked[0][0].product_id == "strong"


def test_invalid_range_is_rejected():
    try:
        candidate(youtube_competition=101)
    except ValueError as exc:
        assert "youtube_competition" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_contributions_sum_to_score_with_rounding_tolerance():
    score = score_candidate(candidate())
    contributions = score_contributions(score)
    assert abs(sum(contributions.values()) - score.opportunity_score) <= 0.02


def test_score_explanation_is_deterministic_and_mentions_economics():
    score = score_candidate(candidate())
    first = explain_score(score)
    second = explain_score(score)
    assert first == second
    assert len(first) == 3
    assert "commission per sale" in first[2]
