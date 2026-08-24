import pytest

from affiliate_mate.decision import EvaluationPolicy, evaluate_candidate
from affiliate_mate.models import ProductCandidate


REQUIRED = frozenset(
    {
        "product_id",
        "title",
        "price",
        "commission_rate",
        "monthly_searches",
        "youtube_competition",
        "buyer_intent",
        "content_gap",
        "evidence_quality",
    }
)


def candidate(**overrides):
    data = {
        "product_id": "strong",
        "title": "Strong Product",
        "marketplace": "DE",
        "currency": "EUR",
        "price": 350.0,
        "commission_rate": 0.05,
        "monthly_searches": 5000,
        "youtube_competition": 25,
        "buyer_intent": 90,
        "content_gap": 80,
        "evidence_quality": 90,
        "estimated_ctr": 0.05,
        "estimated_conversion_rate": 0.03,
    }
    data.update(overrides)
    return ProductCandidate(**data)


def test_strong_complete_candidate_is_shortlisted():
    report = evaluate_candidate(candidate(), available_fields=REQUIRED)
    assert report.accepted
    assert report.rejection_reasons == ()
    assert all(gate.passed for gate in report.gates)


def test_missing_required_evidence_fails_closed():
    fields = REQUIRED - {"youtube_competition", "evidence_quality"}
    report = evaluate_candidate(candidate(), available_fields=fields)
    assert not report.accepted
    assert report.gates[0].code == "required_evidence"
    assert not report.gates[0].passed
    assert "evidence_quality" in report.gates[0].message
    assert "youtube_competition" in report.gates[0].message


def test_programmatic_candidate_without_field_tracking_is_not_falsely_marked_missing():
    report = evaluate_candidate(candidate(), available_fields=None)
    completeness = report.gates[0]
    assert completeness.passed
    assert completeness.actual == "not tracked"


@pytest.mark.parametrize(
    ("overrides", "gate_code"),
    [
        ({"price": 50.0, "commission_rate": 0.01}, "commission_per_sale"),
        ({"monthly_searches": 10}, "monthly_searches"),
        ({"youtube_competition": 99}, "youtube_competition"),
        ({"buyer_intent": 10}, "buyer_intent"),
        ({"evidence_quality": 10}, "evidence_quality"),
        (
            {"estimated_ctr": 0.001, "estimated_conversion_rate": 0.001},
            "estimated_value_per_1000_views",
        ),
    ],
)
def test_each_hard_gate_can_reject(overrides, gate_code):
    report = evaluate_candidate(candidate(**overrides), available_fields=REQUIRED)
    failed = {gate.code for gate in report.gates if not gate.passed}
    assert gate_code in failed
    assert not report.accepted


def test_score_floor_is_policy_configurable():
    item = candidate()
    strict = EvaluationPolicy(min_opportunity_score=99)
    report = evaluate_candidate(item, policy=strict, available_fields=REQUIRED)
    assert "opportunity_score" in {gate.code for gate in report.gates if not gate.passed}


def test_policy_rejects_invalid_thresholds():
    with pytest.raises(ValueError, match="min_opportunity_score"):
        EvaluationPolicy(min_opportunity_score=101)


def test_decision_dict_is_automation_safe_and_contains_all_gate_results():
    report = evaluate_candidate(candidate(), available_fields=REQUIRED)
    payload = report.to_dict()
    assert payload["status"] == "shortlist"
    assert len(payload["gates"]) == 8
    assert payload["score"]["product_id"] == "strong"
    assert len(payload["explanations"]) == 3
