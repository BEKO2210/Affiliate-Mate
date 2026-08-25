from dataclasses import replace
from datetime import UTC, datetime

import pytest

from affiliate_mate.decision import EvaluationPolicy
from affiliate_mate.learning_models import (
    ForecastSnapshot,
    OutcomeEvent,
    OutcomeKind,
    ScoringPolicyVersion,
    sha256_json,
)
from affiliate_mate.learning_store import LearningConflictError, LearningStore


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def policy() -> ScoringPolicyVersion:
    return ScoringPolicyVersion(
        version="baseline",
        policy_payload=EvaluationPolicy().to_dict(),
        created_at=dt(1),
    )


def forecast(entry: ScoringPolicyVersion) -> ForecastSnapshot:
    return ForecastSnapshot(
        forecast_id="forecast-1",
        product_id="p1",
        marketplace="DE",
        currency="EUR",
        content_id="video-1",
        category="audio",
        price=120.0,
        predicted_at=dt(2),
        horizon_days=30,
        policy_version=entry.version,
        policy_digest=entry.digest,
        analysis_digest="a" * 64,
        candidate_digest=sha256_json({"product_id": "p1"}),
        accepted=True,
        opportunity_score=70.0,
        predicted_ctr=0.04,
        predicted_conversion_rate=0.03,
        predicted_value_per_1000_views=4.0,
        commission_per_sale=4.0,
        candidate_payload={"product_id": "p1"},
        available_fields=("monthly_searches",),
        provided_fields_tracked=True,
    )


def test_store_is_idempotent_but_immutable(tmp_path) -> None:
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        entry = policy()
        assert store.register_policy(entry)
        assert not store.register_policy(entry)
        item = forecast(entry)
        assert store.add_forecast(item)
        assert not store.add_forecast(item)
        with pytest.raises(LearningConflictError):
            store.add_forecast(replace(item, opportunity_score=71.0))


def test_forecast_cannot_use_policy_created_in_future(tmp_path) -> None:
    entry = ScoringPolicyVersion(
        version="future",
        policy_payload=EvaluationPolicy().to_dict(),
        created_at=dt(3),
    )
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.register_policy(entry)
        with pytest.raises(ValueError, match="created after"):
            store.add_forecast(replace(forecast(entry), predicted_at=dt(2)))


def test_as_of_excludes_late_ingestion_even_when_effective_date_is_old(tmp_path) -> None:
    event = OutcomeEvent(
        source="affiliate",
        source_event_id="row-1",
        kind=OutcomeKind.ORDER,
        product_id="p1",
        marketplace="DE",
        content_id="video-1",
        effective_at=dt(3),
        observed_at=dt(5),
        ingested_at=dt(7),
        window_start=dt(2),
        window_end=dt(4),
        count=1,
    )
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        assert store.add_outcome(event)
        assert store.list_outcomes(product_id="p1", as_of=dt(6)) == []
        assert store.list_outcomes(product_id="p1", as_of=dt(8)) == [event]


def test_outcome_identity_replay_is_idempotent_and_mutation_conflicts(tmp_path) -> None:
    event = OutcomeEvent(
        source="youtube",
        source_event_id="row-1",
        kind=OutcomeKind.VIDEO_VIEW,
        product_id="p1",
        marketplace="DE",
        content_id="video-1",
        effective_at=dt(3),
        observed_at=dt(4),
        ingested_at=dt(5),
        window_start=dt(2),
        window_end=dt(3),
        count=100,
    )
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        assert store.add_outcome(event)
        assert not store.add_outcome(event)
        with pytest.raises(LearningConflictError):
            store.add_outcome(replace(event, count=101))


def test_policy_parent_must_exist_and_precede_child(tmp_path) -> None:
    child = ScoringPolicyVersion(
        version="child",
        policy_payload=EvaluationPolicy().to_dict(),
        created_at=dt(2),
        parent_version="missing",
    )
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        with pytest.raises(KeyError, match="parent"):
            store.register_policy(child)

        parent = ScoringPolicyVersion(
            version="parent",
            policy_payload=EvaluationPolicy().to_dict(),
            created_at=dt(3),
        )
        store.register_policy(parent)
        with pytest.raises(ValueError, match="after child"):
            store.register_policy(replace(child, parent_version="parent"))


def test_add_outcomes_rolls_back_entire_batch_on_conflict(tmp_path) -> None:
    first = OutcomeEvent(
        source="youtube",
        source_event_id="row-1",
        kind=OutcomeKind.VIDEO_VIEW,
        product_id="p1",
        marketplace="DE",
        content_id="video-1",
        effective_at=dt(3),
        observed_at=dt(4),
        ingested_at=dt(5),
        window_start=dt(2),
        window_end=dt(3),
        count=100,
    )
    conflicting = replace(first, count=101)
    second = replace(first, source_event_id="row-2", count=200)
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.add_outcome(first)
        with pytest.raises(LearningConflictError):
            store.add_outcomes([second, conflicting])
        assert store.list_outcomes(product_id="p1") == [first]


def test_time_bounded_queries_reject_naive_timestamps(tmp_path) -> None:
    naive = dt(1).replace(tzinfo=None)
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        with pytest.raises(ValueError, match="timezone-aware"):
            store.list_forecasts(start=naive)
        with pytest.raises(ValueError, match="timezone-aware"):
            store.list_outcomes(as_of=naive)
