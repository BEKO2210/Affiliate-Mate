from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from affiliate_mate.decision import EvaluationPolicy, evaluate_candidate
from affiliate_mate.learning_backtest import BacktestPolicy, backtest_policy_change
from affiliate_mate.learning_models import (
    ForecastSnapshot,
    OutcomeEvent,
    OutcomeKind,
    OutcomeTotals,
    ScoringPolicyVersion,
    sha256_json,
)
from affiliate_mate.learning_reports import PerformancePolicy, build_performance_report
from affiliate_mate.learning_store import LearningStore
from affiliate_mate.models import ProductCandidate


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def make_candidate(product_id: str, *, monthly_searches: int = 5000) -> ProductCandidate:
    return ProductCandidate(
        product_id=product_id,
        title=f"Product {product_id}",
        marketplace="DE",
        currency="EUR",
        price=200.0,
        commission_rate=0.05,
        monthly_searches=monthly_searches,
        youtube_competition=20,
        buyer_intent=80,
        content_gap=80,
        evidence_quality=90,
        estimated_ctr=0.05,
        estimated_conversion_rate=0.04,
    )


def make_policy(version: str, evaluation: EvaluationPolicy) -> ScoringPolicyVersion:
    return ScoringPolicyVersion(
        version=version,
        policy_payload=evaluation.to_dict(),
        created_at=dt(1),
    )


def make_forecast(
    candidate: ProductCandidate,
    policy_entry: ScoringPolicyVersion,
    policy: EvaluationPolicy,
    *,
    forecast_id: str,
    predicted_at: datetime,
    package_digest: str | None = None,
) -> ForecastSnapshot:
    decision = evaluate_candidate(candidate, policy=policy, available_fields=None)
    payload = asdict(candidate)
    return ForecastSnapshot(
        forecast_id=forecast_id,
        product_id=candidate.product_id,
        marketplace=candidate.marketplace,
        currency=candidate.currency,
        content_id=f"video-{forecast_id}",
        category="audio",
        price=candidate.price,
        predicted_at=predicted_at,
        horizon_days=2,
        policy_version=policy_entry.version,
        policy_digest=policy_entry.digest,
        analysis_digest=forecast_id[0] * 64,
        candidate_digest=sha256_json(payload),
        accepted=decision.accepted,
        opportunity_score=decision.score.opportunity_score,
        predicted_ctr=candidate.estimated_ctr,
        predicted_conversion_rate=candidate.estimated_conversion_rate,
        predicted_value_per_1000_views=candidate.estimated_value_per_1000_views,
        commission_per_sale=candidate.commission_per_sale,
        candidate_payload=payload,
        available_fields=(),
        provided_fields_tracked=False,
        package_digest=package_digest,
    )


def add_complete_outcomes(store: LearningStore, forecast: ForecastSnapshot) -> None:
    effective = forecast.predicted_at + timedelta(days=1)
    observed = effective + timedelta(hours=1)
    common = {
        "source": "test",
        "product_id": forecast.product_id,
        "marketplace": forecast.marketplace,
        "content_id": forecast.content_id,
        "effective_at": effective,
        "observed_at": observed,
        "ingested_at": observed,
        "window_start": forecast.predicted_at,
        "window_end": effective,
        "package_digest": forecast.package_digest,
    }
    store.add_outcomes(
        [
            OutcomeEvent(
                source_event_id=f"{forecast.forecast_id}-views",
                kind=OutcomeKind.VIDEO_VIEW,
                count=1000,
                **common,
            ),
            OutcomeEvent(
                source_event_id=f"{forecast.forecast_id}-clicks",
                kind=OutcomeKind.AFFILIATE_CLICK,
                count=50,
                **common,
            ),
            OutcomeEvent(
                source_event_id=f"{forecast.forecast_id}-orders",
                kind=OutcomeKind.ORDER,
                count=2,
                **common,
            ),
            OutcomeEvent(
                source_event_id=f"{forecast.forecast_id}-commission",
                kind=OutcomeKind.COMMISSION,
                amount_minor=1000,
                currency="EUR",
                **common,
            ),
        ]
    )


def test_jpy_minor_units_are_not_divided_by_one_hundred() -> None:
    totals = OutcomeTotals(
        views=1000,
        gross_commission_minor=1500,
        currency="JPY",
    )
    assert totals.realized_value_per_1000_views == 1500.0


def test_unknown_currency_minor_units_fail_closed() -> None:
    with pytest.raises(ValueError, match="unsupported currency minor-unit exponent"):
        OutcomeEvent(
            source="affiliate",
            source_event_id="money-1",
            kind=OutcomeKind.COMMISSION,
            product_id="p1",
            marketplace="ZZ",
            content_id="video-1",
            effective_at=dt(2),
            observed_at=dt(2),
            ingested_at=dt(2),
            window_start=dt(1),
            window_end=dt(2),
            amount_minor=100,
            currency="ZZZ",
        )


def test_overlapping_count_snapshots_are_rejected(tmp_path) -> None:
    policy = EvaluationPolicy()
    entry = make_policy("baseline", policy)
    forecast = make_forecast(
        make_candidate("p1"),
        entry,
        policy,
        forecast_id="f1",
        predicted_at=dt(1),
    )
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.add_outcomes(
            [
                OutcomeEvent(
                    source="youtube-export",
                    source_event_id="views-a",
                    kind=OutcomeKind.VIDEO_VIEW,
                    product_id=forecast.product_id,
                    marketplace=forecast.marketplace,
                    content_id=forecast.content_id,
                    effective_at=dt(2),
                    observed_at=dt(2),
                    ingested_at=dt(2),
                    window_start=dt(1),
                    window_end=dt(2),
                    count=100,
                ),
                OutcomeEvent(
                    source="youtube-export",
                    source_event_id="views-b",
                    kind=OutcomeKind.VIDEO_VIEW,
                    product_id=forecast.product_id,
                    marketplace=forecast.marketplace,
                    content_id=forecast.content_id,
                    effective_at=dt(2),
                    observed_at=dt(2),
                    ingested_at=dt(2),
                    window_start=dt(1),
                    window_end=dt(2),
                    count=150,
                ),
            ]
        )
        with pytest.raises(ValueError, match="overlapping aggregate outcome windows"):
            build_performance_report(store, forecast, evaluated_at=dt(5))


def test_package_bound_forecast_rejects_unbound_outcome(tmp_path) -> None:
    policy = EvaluationPolicy()
    entry = make_policy("baseline", policy)
    forecast = make_forecast(
        make_candidate("p1"),
        entry,
        policy,
        forecast_id="f1",
        predicted_at=dt(1),
        package_digest="a" * 64,
    )
    event = OutcomeEvent(
        source="youtube-export",
        source_event_id="views",
        kind=OutcomeKind.VIDEO_VIEW,
        product_id=forecast.product_id,
        marketplace=forecast.marketplace,
        content_id=forecast.content_id,
        effective_at=dt(2),
        observed_at=dt(2),
        ingested_at=dt(2),
        window_start=dt(1),
        window_end=dt(2),
        count=100,
    )
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.add_outcome(event)
        with pytest.raises(ValueError, match="package lineage"):
            build_performance_report(store, forecast, evaluated_at=dt(5))


def test_candidate_selection_without_observable_outcome_blocks_promotion(tmp_path) -> None:
    baseline_policy = EvaluationPolicy(min_monthly_searches=1000)
    challenger_policy = EvaluationPolicy(min_monthly_searches=100)
    baseline = make_policy("baseline", baseline_policy)
    challenger = make_policy("challenger", challenger_policy)
    complete = make_forecast(
        make_candidate("strong", monthly_searches=5000),
        baseline,
        baseline_policy,
        forecast_id="a1",
        predicted_at=dt(11),
    )
    unobservable = make_forecast(
        make_candidate("medium", monthly_searches=500),
        baseline,
        baseline_policy,
        forecast_id="b1",
        predicted_at=dt(12),
    )
    assert complete.accepted
    assert not unobservable.accepted

    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.register_policy(baseline)
        store.register_policy(challenger)
        store.add_forecast(complete)
        store.add_forecast(unobservable)
        add_complete_outcomes(store, complete)
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

    assert report.baseline_unobservable_selections == 0
    assert report.candidate_unobservable_selections == 1
    assert not report.promotion_eligible
    assert any("candidate selected forecasts without observable" in gate for gate in report.gates)
    assert report.to_dict()["schema_version"] == "affiliate-mate.backtest-report.v2"
