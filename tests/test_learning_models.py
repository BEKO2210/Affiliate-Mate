from datetime import UTC, datetime

import pytest

from affiliate_mate.learning_models import (
    ForecastSnapshot,
    OutcomeEvent,
    OutcomeKind,
    ScoringPolicyVersion,
    sha256_json,
)


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def test_outcome_event_preserves_three_time_axes_and_signed_reversal() -> None:
    event = OutcomeEvent(
        source="affiliate",
        source_event_id="row-1",
        kind=OutcomeKind.REVERSAL,
        product_id="p1",
        marketplace="DE",
        content_id="video-1",
        effective_at=dt(2),
        observed_at=dt(4),
        ingested_at=dt(5),
        window_start=dt(1),
        window_end=dt(3),
        amount_minor=499,
        currency="EUR",
    )
    assert event.signed_amount_minor == -499
    assert event.to_dict()["observed_at"].startswith("2026-01-04")


def test_outcome_rejects_observation_before_effective_time() -> None:
    with pytest.raises(ValueError, match="observed_at"):
        OutcomeEvent(
            source="affiliate",
            source_event_id="row-1",
            kind=OutcomeKind.ORDER,
            product_id="p1",
            marketplace="DE",
            content_id="video-1",
            effective_at=dt(3),
            observed_at=dt(2),
            ingested_at=dt(4),
            window_start=dt(1),
            window_end=dt(3),
            count=1,
        )


def test_policy_digest_is_deterministic() -> None:
    first = ScoringPolicyVersion(
        version="baseline",
        policy_payload={"b": 2, "a": 1},
        created_at=dt(1),
    )
    second = ScoringPolicyVersion(
        version="baseline-copy",
        policy_payload={"a": 1, "b": 2},
        created_at=dt(1),
    )
    assert first.digest == second.digest


def test_forecast_rejects_invalid_probability() -> None:
    policy = ScoringPolicyVersion(
        version="baseline",
        policy_payload={"min_monthly_searches": 100},
        created_at=dt(1),
    )
    with pytest.raises(ValueError, match="predicted_ctr"):
        ForecastSnapshot(
            forecast_id="f1",
            product_id="p1",
            marketplace="DE",
            currency="EUR",
            content_id="video-1",
            category="audio",
            price=100.0,
            predicted_at=dt(2),
            horizon_days=30,
            policy_version=policy.version,
            policy_digest=policy.digest,
            analysis_digest="a" * 64,
            candidate_digest=sha256_json({"product_id": "p1"}),
            accepted=True,
            opportunity_score=70,
            predicted_ctr=1.1,
            predicted_conversion_rate=0.03,
            predicted_value_per_1000_views=5.0,
            commission_per_sale=4.0,
            candidate_payload={"product_id": "p1"},
            available_fields=(),
            provided_fields_tracked=False,
        )


def test_forecast_candidate_digest_is_self_verifying() -> None:
    policy = ScoringPolicyVersion(
        version="baseline",
        policy_payload={"min_monthly_searches": 100},
        created_at=dt(1),
    )
    payload = {"product_id": "p1", "price": 100.0}
    with pytest.raises(ValueError, match="candidate_digest"):
        ForecastSnapshot(
            forecast_id="f1",
            product_id="p1",
            marketplace="DE",
            currency="EUR",
            content_id="video-1",
            category="audio",
            price=100.0,
            predicted_at=dt(2),
            horizon_days=30,
            policy_version=policy.version,
            policy_digest=policy.digest,
            analysis_digest="a" * 64,
            candidate_digest=sha256_json({"product_id": "different"}),
            accepted=True,
            opportunity_score=70,
            predicted_ctr=0.04,
            predicted_conversion_rate=0.03,
            predicted_value_per_1000_views=5.0,
            commission_per_sale=4.0,
            candidate_payload=payload,
            available_fields=(),
            provided_fields_tracked=False,
        )
