from dataclasses import replace
from datetime import UTC, datetime

from affiliate_mate.decision import EvaluationPolicy
from affiliate_mate.learning_models import (
    ForecastSnapshot,
    OutcomeEvent,
    OutcomeKind,
    OutcomeTotals,
    ScoringPolicyVersion,
    sha256_json,
)
from affiliate_mate.learning_reports import (
    CalibrationPolicy,
    PerformancePolicy,
    PerformanceReport,
    build_calibration_report,
    build_performance_report,
    wilson_interval,
)
from affiliate_mate.learning_store import LearningStore


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def policy() -> ScoringPolicyVersion:
    return ScoringPolicyVersion(
        version="baseline",
        policy_payload=EvaluationPolicy().to_dict(),
        created_at=dt(1),
    )


def forecast(entry: ScoringPolicyVersion, forecast_id: str = "f1") -> ForecastSnapshot:
    return ForecastSnapshot(
        forecast_id=forecast_id,
        product_id="p1",
        marketplace="DE",
        currency="EUR",
        content_id=f"video-{forecast_id}",
        category="audio",
        price=120.0,
        predicted_at=dt(1),
        horizon_days=2,
        policy_version=entry.version,
        policy_digest=entry.digest,
        analysis_digest="a" * 64,
        candidate_digest=sha256_json({"product_id": "p1"}),
        accepted=True,
        opportunity_score=70,
        predicted_ctr=0.04,
        predicted_conversion_rate=0.05,
        predicted_value_per_1000_views=6.0,
        commission_per_sale=3.0,
        candidate_payload={"product_id": "p1"},
        available_fields=(),
        provided_fields_tracked=False,
    )


def event(
    item: ForecastSnapshot,
    kind: OutcomeKind,
    *,
    source_event_id: str,
    count: int = 0,
    amount_minor: int = 0,
    observed_at: datetime | None = None,
    ingested_at: datetime | None = None,
) -> OutcomeEvent:
    observed = dt(2) if observed_at is None else observed_at
    ingested = observed if ingested_at is None else ingested_at
    return OutcomeEvent(
        source="test",
        source_event_id=source_event_id,
        kind=kind,
        product_id=item.product_id,
        marketplace=item.marketplace,
        content_id=item.content_id,
        effective_at=dt(2),
        observed_at=observed,
        ingested_at=ingested,
        window_start=dt(1),
        window_end=dt(2),
        count=count,
        amount_minor=amount_minor,
        currency="EUR" if kind in {
            OutcomeKind.COMMISSION,
            OutcomeKind.REFUND,
            OutcomeKind.REVERSAL,
        } else None,
    )


def test_performance_report_waits_for_delayed_report_ingestion(tmp_path) -> None:
    entry = policy()
    item = forecast(entry)
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.register_policy(entry)
        store.add_forecast(item)
        store.add_outcomes(
            [
                event(item, OutcomeKind.VIDEO_VIEW, source_event_id="views", count=1000),
                event(item, OutcomeKind.AFFILIATE_CLICK, source_event_id="clicks", count=50),
                event(item, OutcomeKind.ORDER, source_event_id="orders", count=3),
                event(
                    item,
                    OutcomeKind.COMMISSION,
                    source_event_id="commission",
                    amount_minor=700,
                    observed_at=dt(5),
                    ingested_at=dt(5),
                ),
            ]
        )
        early = build_performance_report(
            store,
            item,
            evaluated_at=dt(4),
            policy=PerformancePolicy(reporting_lag_days=1),
        )
        late = build_performance_report(
            store,
            item,
            evaluated_at=dt(6),
            policy=PerformancePolicy(reporting_lag_days=1),
        )
    assert early.mature
    assert "commission" in early.missing_kinds
    assert not early.sample_eligible
    assert late.sample_eligible
    assert late.totals.realized_value_per_1000_views == 7.0


def test_refunds_and_reversals_reduce_realized_value(tmp_path) -> None:
    entry = policy()
    item = forecast(entry)
    with LearningStore(tmp_path / "learning.sqlite3") as store:
        store.register_policy(entry)
        store.add_forecast(item)
        store.add_outcomes(
            [
                event(item, OutcomeKind.VIDEO_VIEW, source_event_id="v", count=1000),
                event(item, OutcomeKind.AFFILIATE_CLICK, source_event_id="c", count=50),
                event(item, OutcomeKind.ORDER, source_event_id="o", count=4),
                event(item, OutcomeKind.COMMISSION, source_event_id="g", amount_minor=1200),
                event(item, OutcomeKind.REFUND, source_event_id="r", amount_minor=300),
                event(item, OutcomeKind.REVERSAL, source_event_id="x", amount_minor=100),
            ]
        )
        report = build_performance_report(
            store,
            item,
            evaluated_at=dt(6),
            policy=PerformancePolicy(reporting_lag_days=1),
        )
    assert report.totals.net_commission_minor == 800
    assert report.totals.realized_value_per_1000_views == 8.0


def test_calibration_uses_weighted_denominators_and_minimum_samples() -> None:
    entry = policy()
    base = forecast(entry)
    reports = []
    for index in range(3):
        item = replace(
            base,
            forecast_id=f"f{index}",
            content_id=f"video-{index}",
            predicted_ctr=0.04,
            predicted_conversion_rate=0.10,
        )
        reports.append(
            PerformanceReport(
                forecast=item,
                evaluated_at=dt(6),
                horizon_end=dt(3),
                mature=True,
                required_kinds_present=True,
                missing_kinds=(),
                totals=OutcomeTotals(
                    views=1000,
                    clicks=50,
                    orders=5,
                    gross_commission_minor=1000,
                    currency="EUR",
                ),
                event_count=3,
            )
        )
    result = build_calibration_report(
        reports,
        evaluated_at=dt(6),
        policy=CalibrationPolicy(
            min_forecasts=3,
            min_views=1000,
            min_clicks=50,
            min_orders=5,
            relative_drift_threshold=0.10,
        ),
    )
    cohort = result.cohorts[0]
    assert cohort.realized_ctr == 0.05
    assert cohort.ctr_state == "drift"
    assert cohort.realized_conversion_rate == 0.10
    assert cohort.conversion_state == "stable"


def test_wilson_interval_contains_observed_rate() -> None:
    interval = wilson_interval(50, 1000)
    assert interval is not None
    low, high = interval
    assert low < 0.05 < high
