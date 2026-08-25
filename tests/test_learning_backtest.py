from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest

from affiliate_mate.decision import EvaluationPolicy, evaluate_candidate
from affiliate_mate.learning_backtest import (
    BacktestPolicy,
    PolicyFold,
    backtest_policy_change,
    walk_forward_backtest,
)
from affiliate_mate.learning_models import (
    ForecastSnapshot,
    OutcomeEvent,
    OutcomeKind,
    ScoringPolicyVersion,
    sha256_json,
)
from affiliate_mate.learning_reports import PerformancePolicy
from affiliate_mate.learning_store import LearningStore
from affiliate_mate.models import ProductCandidate


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="p1",
        title="Strong product",
        marketplace="DE",
        currency="EUR",
        price=200.0,
        commission_rate=0.05,
        monthly_searches=5000,
        youtube_competition=20,
        buyer_intent=80,
        content_gap=80,
        evidence_quality=90,
        estimated_ctr=0.05,
        estimated_conversion_rate=0.04,
    )


def policy(version: str, *, created_at: datetime | None = None) -> ScoringPolicyVersion:
    return ScoringPolicyVersion(
        version=version,
        policy_payload=EvaluationPolicy().to_dict(),
        created_at=dt(1) if created_at is None else created_at,
    )


def forecast(
    baseline: ScoringPolicyVersion,
    predicted_at: datetime,
    forecast_id: str,
) -> ForecastSnapshot:
    item = candidate()
    decision = evaluate_candidate(item, policy=EvaluationPolicy(), available_fields=None)
    payload = asdict(item)
    return ForecastSnapshot(
        forecast_id=forecast_id,
        product_id=item.product_id,
        marketplace=item.marketplace,
        currency=item.currency,
        content_id=f"video-{forecast_id}",
        category="audio",
        price=item.price,
        predicted_at=predicted_at,
        horizon_days=2,
        policy_version=baseline.version,
        policy_digest=baseline.digest,
        analysis_digest=("a" if forecast_id == "f1" else "b") * 64,
        candidate_digest=sha256_json(payload),
        accepted=decision.accepted,
        opportunity_score=decision.score.opportunity_score,
        predicted_ctr=item.estimated_ctr,
        predicted_conversion_rate=item.estimated_conversion_rate,
        predicted_value_per_1000_views=item.estimated_value_per_1000_views,
        commission_per_sale=item.commission_per_sale,
        candidate_payload=payload,
        available_fields=(),
        provided_fields_tracked=False,
    )


def add_complete_outcomes(
    store: LearningStore,
    item: ForecastSnapshot,
    *,
    net_minor: int = 1000,
    ingested_delay_days: int = 1,
) -> None:
    effective = item.predicted_at + timedelta(days=1)
    observed = effective + timedelta(days=1)
    ingested = observed + timedelta(days=ingested_delay_days)
    common = {
        "source": "test",
        "product_id": item.product_id,
        "marketplace": item.marketplace,
        "content_id": item.content_id,
        "effective_at": effective,
        "observed_at": observed,
        "ingested_at": ingested,
        "window_start": item.predicted_at,
        "window_end": effective,
    }
    store.add_outcomes(
        [
            OutcomeEvent(
                source_event_id=f"{item.forecast_id}-views",
                kind=OutcomeKind.VIDEO_VIEW,
                count=1000,
                **common,
            ),
            OutcomeEvent(
                source_event_id=f"{item.forecast_id}-clicks",
                kind=OutcomeKind.AFFILIATE_CLICK,
                count=50,
                **common,
            ),
            OutcomeEvent(
                source_event_id=f"{item.forecast_id}-orders",
                kind=OutcomeKind.ORDER,
                count=2,
                **common,
            ),
            OutcomeEvent(
                source_event_id=f"{item.forecast_id}-commission",
                kind=OutcomeKind.COMMISSION,
                amount_minor=net_minor,
                currency="EUR",
                **common,
            ),
        ]
    )


def test_backtest_replays_baseline_and_never_auto_promotes_state(tmp_path) -> None:
    baseline = policy("baseline")
    challenger = policy("challenger")
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.register_policy(baseline)
        store.register_policy(challenger)
        for index, day in enumerate((11, 14), start=1):
            item = forecast(baseline, dt(day), f"f{index}")
            store.add_forecast(item)
            add_complete_outcomes(store, item)
        report = backtest_policy_change(
            store,
            baseline_version="baseline",
            candidate_version="challenger",
            marketplace="DE",
            train_cutoff=dt(10),
            evaluation_end=dt(20),
            evaluated_at=dt(25),
            policy=BacktestPolicy(
                min_evaluation_forecasts=2,
                min_candidate_selections=1,
                performance_policy=PerformancePolicy(reporting_lag_days=0),
            ),
        )
        assert report.promotion_eligible
        assert report.baseline_replay_mismatches == 0
        assert store.get_policy("challenger") == challenger


def test_policy_created_after_train_cutoff_is_rejected(tmp_path) -> None:
    baseline = policy("baseline")
    future = policy("future", created_at=dt(12))
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.register_policy(baseline)
        store.register_policy(future)
        with pytest.raises(ValueError, match="created after train_cutoff"):
            backtest_policy_change(
                store,
                baseline_version="baseline",
                candidate_version="future",
                marketplace="DE",
                train_cutoff=dt(10),
                evaluation_end=dt(20),
                evaluated_at=dt(25),
            )


def test_baseline_replay_mismatch_blocks_promotion(tmp_path) -> None:
    baseline = policy("baseline")
    challenger = policy("challenger")
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.register_policy(baseline)
        store.register_policy(challenger)
        item = replace(forecast(baseline, dt(11), "f1"), accepted=False)
        store.add_forecast(item)
        add_complete_outcomes(store, item)
        report = backtest_policy_change(
            store,
            baseline_version="baseline",
            candidate_version="challenger",
            marketplace="DE",
            train_cutoff=dt(10),
            evaluation_end=dt(20),
            evaluated_at=dt(25),
            policy=BacktestPolicy(
                min_evaluation_forecasts=1,
                min_candidate_selections=1,
                performance_policy=PerformancePolicy(reporting_lag_days=0),
            ),
        )
    assert report.baseline_replay_mismatches == 1
    assert not report.promotion_eligible


def test_walk_forward_rejects_backwards_overlapping_folds(tmp_path) -> None:
    folds = [
        PolicyFold("b", "c", "DE", dt(10), dt(20)),
        PolicyFold("b2", "c2", "DE", dt(15), dt(25)),
    ]
    with (
        LearningStore(tmp_path / "learning.sqlite3") as store,
        pytest.raises(ValueError, match="must not overlap backwards"),
    ):
        walk_forward_backtest(store, folds, evaluated_at=dt(30))
