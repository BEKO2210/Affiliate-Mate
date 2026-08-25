from datetime import UTC, datetime

import pytest

from affiliate_mate.analysis import analyze_candidate
from affiliate_mate.decision import EvaluationPolicy
from affiliate_mate.evidence import EvidenceObservation, SQLiteEvidenceStore
from affiliate_mate.learning_capture import capture_forecast
from affiliate_mate.learning_models import ScoringPolicyVersion
from affiliate_mate.models import ProductCandidate


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="p1",
        title="Product",
        marketplace="DE",
        currency="EUR",
        price=100,
        commission_rate=0.05,
        monthly_searches=1000,
        youtube_competition=30,
        buyer_intent=70,
        content_gap=70,
        evidence_quality=80,
        estimated_ctr=0.04,
        estimated_conversion_rate=0.03,
    )


def test_capture_rejects_analysis_that_contains_future_evidence() -> None:
    item = candidate()
    evaluation_policy = EvaluationPolicy()
    policy_version = ScoringPolicyVersion(
        version="baseline",
        policy_payload=evaluation_policy.to_dict(),
        created_at=dt(1),
    )
    with SQLiteEvidenceStore(":memory:") as evidence:
        evidence.add(
            EvidenceObservation(
                product_id="p1",
                signal="monthly_searches",
                value=2000,
                source="future",
                observed_at=dt(5),
            )
        )
        result = analyze_candidate(
            item,
            policy=evaluation_policy,
            evidence_store=evidence,
            as_of=dt(6),
        )
    with pytest.raises(ValueError, match="observed after predicted_at"):
        capture_forecast(
            result,
            predicted_at=dt(4),
            horizon_days=30,
            content_id="video-1",
            category="audio",
            policy_version=policy_version,
            evaluation_policy=evaluation_policy,
        )


def test_capture_policy_payload_must_match_analysis_policy() -> None:
    item = candidate()
    evaluation_policy = EvaluationPolicy()
    wrong_version = ScoringPolicyVersion(
        version="wrong",
        policy_payload=EvaluationPolicy(min_monthly_searches=999).to_dict(),
        created_at=dt(1),
    )
    result = analyze_candidate(item, policy=evaluation_policy)
    with pytest.raises(ValueError, match="must exactly match"):
        capture_forecast(
            result,
            predicted_at=dt(4),
            horizon_days=30,
            content_id="video-1",
            category="audio",
            policy_version=wrong_version,
            evaluation_policy=evaluation_policy,
        )
