"""Leakage-resistant policy replay, holdout backtests, and walk-forward evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .decision import evaluate_candidate
from .learning_capture import evaluation_policy_from_version
from .learning_models import (
    BACKTEST_SCHEMA_VERSION,
    WALK_FORWARD_SCHEMA_VERSION,
    ForecastSnapshot,
    sha256_json,
)
from .learning_reports import PerformancePolicy, PerformanceReport, build_performance_report
from .learning_store import LearningStore
from .models import ProductCandidate
from .money import minor_units_to_major


@dataclass(frozen=True, slots=True)
class BacktestPolicy:
    min_evaluation_forecasts: int = 10
    min_candidate_selections: int = 3
    max_relative_ev_regression: float = 0.05
    require_zero_baseline_replay_mismatches: bool = True
    require_zero_unobservable_selections: bool = True
    performance_policy: PerformancePolicy = field(default_factory=PerformancePolicy)

    def __post_init__(self) -> None:
        if self.min_evaluation_forecasts < 1:
            raise ValueError("min_evaluation_forecasts must be >= 1")
        if self.min_candidate_selections < 1:
            raise ValueError("min_candidate_selections must be >= 1")
        if self.max_relative_ev_regression < 0:
            raise ValueError("max_relative_ev_regression must be >= 0")


@dataclass(frozen=True, slots=True)
class SelectionMetrics:
    selected: int
    views: int
    net_commission_minor: int
    currency: str | None
    realized_value_per_1000_views: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BacktestReport:
    baseline_version: str
    candidate_version: str
    marketplace: str
    train_cutoff: datetime
    evaluation_end: datetime
    evaluated_at: datetime
    evaluation_forecasts: int
    excluded_immature_or_incomplete: int
    baseline_replay_mismatches: int
    baseline_unobservable_selections: int
    candidate_unobservable_selections: int
    baseline: SelectionMetrics
    candidate: SelectionMetrics
    relative_ev_delta: float | None
    promotion_eligible: bool
    gates: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": BACKTEST_SCHEMA_VERSION,
            "baseline_version": self.baseline_version,
            "candidate_version": self.candidate_version,
            "marketplace": self.marketplace,
            "train_cutoff": self.train_cutoff.isoformat(),
            "evaluation_end": self.evaluation_end.isoformat(),
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluation_forecasts": self.evaluation_forecasts,
            "excluded_immature_or_incomplete": self.excluded_immature_or_incomplete,
            "baseline_replay_mismatches": self.baseline_replay_mismatches,
            "baseline_unobservable_selections": self.baseline_unobservable_selections,
            "candidate_unobservable_selections": self.candidate_unobservable_selections,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "relative_ev_delta": self.relative_ev_delta,
            "promotion_eligible": self.promotion_eligible,
            "gates": list(self.gates),
        }

    @property
    def digest(self) -> str:
        return sha256_json(self.to_dict())


def _available_fields(forecast: ForecastSnapshot) -> frozenset[str] | None:
    if not forecast.provided_fields_tracked:
        return None
    return frozenset(forecast.available_fields)


def _candidate(forecast: ForecastSnapshot) -> ProductCandidate:
    try:
        return ProductCandidate(**forecast.candidate_payload)
    except TypeError as exc:
        raise ValueError(
            f"forecast {forecast.forecast_id} has an incompatible candidate snapshot"
        ) from exc


def _selection_metrics(
    selected: Iterable[tuple[ForecastSnapshot, PerformanceReport]],
) -> SelectionMetrics:
    rows = list(selected)
    views = sum(report.totals.views for _, report in rows)
    net = sum(report.totals.net_commission_minor for _, report in rows)
    currencies = {
        report.totals.currency
        for _, report in rows
        if report.totals.currency is not None
    }
    if len(currencies) > 1:
        raise ValueError("backtest selection spans multiple realized currencies")
    currency = next(iter(currencies), None)
    ev = (
        None
        if views <= 0 or currency is None
        else minor_units_to_major(net, currency) * 1000.0 / views
    )
    return SelectionMetrics(
        selected=len(rows),
        views=views,
        net_commission_minor=net,
        currency=currency,
        realized_value_per_1000_views=ev,
    )


def _relative_delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None or baseline == 0:
        return None
    return (candidate - baseline) / abs(baseline)


def backtest_policy_change(
    store: LearningStore,
    *,
    baseline_version: str,
    candidate_version: str,
    marketplace: str,
    train_cutoff: datetime,
    evaluation_end: datetime,
    evaluated_at: datetime,
    policy: BacktestPolicy | None = None,
) -> BacktestReport:
    """Evaluate a candidate policy strictly after its training cutoff.

    Policies must have existed by `train_cutoff`. Forecasts are immutable snapshots from
    [train_cutoff, evaluation_end). Outcomes are filtered by what was observed and ingested by
    `evaluated_at`. Historical baseline acceptance is replayed and mismatches are surfaced.

    A policy that selects an item whose realized outcome is not observable cannot receive
    implicit credit by having that item disappear from evaluation. Such selections are counted
    explicitly and block promotion under the default policy.
    """

    for field_name, value in (
        ("train_cutoff", train_cutoff),
        ("evaluation_end", evaluation_end),
        ("evaluated_at", evaluated_at),
    ):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
    if baseline_version == candidate_version:
        raise ValueError("candidate policy must differ from baseline policy")
    if not train_cutoff < evaluation_end:
        raise ValueError("train_cutoff must be before evaluation_end")
    if evaluated_at < evaluation_end:
        raise ValueError("evaluated_at must not be before evaluation_end")
    active_policy = BacktestPolicy() if policy is None else policy
    baseline_entry = store.get_policy(baseline_version)
    candidate_entry = store.get_policy(candidate_version)
    if baseline_entry is None:
        raise KeyError(f"unknown baseline policy: {baseline_version}")
    if candidate_entry is None:
        raise KeyError(f"unknown candidate policy: {candidate_version}")
    if baseline_entry.created_at > train_cutoff:
        raise ValueError("baseline policy was created after train_cutoff")
    if candidate_entry.created_at > train_cutoff:
        raise ValueError("candidate policy was created after train_cutoff")

    baseline_policy = evaluation_policy_from_version(baseline_entry)
    candidate_policy = evaluation_policy_from_version(candidate_entry)
    forecasts = store.list_forecasts(
        start=train_cutoff,
        end=evaluation_end,
        marketplace=marketplace,
    )

    complete: list[tuple[ForecastSnapshot, PerformanceReport, bool]] = []
    excluded = 0
    baseline_replay_mismatches = 0
    baseline_unobservable_selections = 0
    candidate_unobservable_selections = 0
    for forecast in forecasts:
        if forecast.policy_version != baseline_version:
            raise ValueError(
                "evaluation cohort contains a forecast created under a different baseline "
                f"policy: {forecast.forecast_id} uses {forecast.policy_version}"
            )
        candidate = _candidate(forecast)
        replay = evaluate_candidate(
            candidate,
            policy=baseline_policy,
            available_fields=_available_fields(forecast),
        )
        if replay.accepted != forecast.accepted:
            baseline_replay_mismatches += 1
        challenger = evaluate_candidate(
            candidate,
            policy=candidate_policy,
            available_fields=_available_fields(forecast),
        )
        performance = build_performance_report(
            store,
            forecast,
            evaluated_at=evaluated_at,
            policy=active_policy.performance_policy,
        )
        if not performance.sample_eligible:
            excluded += 1
            if forecast.accepted:
                baseline_unobservable_selections += 1
            if challenger.accepted:
                candidate_unobservable_selections += 1
            continue
        complete.append((forecast, performance, challenger.accepted))

    baseline_selected: list[tuple[ForecastSnapshot, PerformanceReport]] = []
    candidate_selected: list[tuple[ForecastSnapshot, PerformanceReport]] = []
    for forecast, performance, challenger_accepted in complete:
        if forecast.accepted:
            baseline_selected.append((forecast, performance))
        if challenger_accepted:
            candidate_selected.append((forecast, performance))

    baseline_metrics = _selection_metrics(baseline_selected)
    candidate_metrics = _selection_metrics(candidate_selected)
    relative_ev_delta = _relative_delta(
        candidate_metrics.realized_value_per_1000_views,
        baseline_metrics.realized_value_per_1000_views,
    )

    gates: list[str] = []
    if len(complete) < active_policy.min_evaluation_forecasts:
        gates.append(
            "insufficient evaluation forecasts: "
            f"{len(complete)} < {active_policy.min_evaluation_forecasts}"
        )
    if candidate_metrics.selected < active_policy.min_candidate_selections:
        gates.append(
            "insufficient candidate selections: "
            f"{candidate_metrics.selected} < {active_policy.min_candidate_selections}"
        )
    if (
        active_policy.require_zero_baseline_replay_mismatches
        and baseline_replay_mismatches
    ):
        gates.append(
            f"baseline replay mismatch count is {baseline_replay_mismatches}, expected 0"
        )
    if active_policy.require_zero_unobservable_selections:
        if baseline_unobservable_selections:
            gates.append(
                "baseline selected forecasts without observable complete outcomes: "
                f"{baseline_unobservable_selections}"
            )
        if candidate_unobservable_selections:
            gates.append(
                "candidate selected forecasts without observable complete outcomes: "
                f"{candidate_unobservable_selections}"
            )
    if baseline_metrics.currency != candidate_metrics.currency:
        gates.append("baseline and candidate realized currencies differ")
    if relative_ev_delta is None:
        gates.append("relative realized EV/1K delta is not estimable")
    elif relative_ev_delta < -active_policy.max_relative_ev_regression:
        gates.append(
            "candidate realized EV/1K regressed beyond allowed threshold: "
            f"{relative_ev_delta:.4f}"
        )

    return BacktestReport(
        baseline_version=baseline_version,
        candidate_version=candidate_version,
        marketplace=marketplace.strip().upper(),
        train_cutoff=train_cutoff,
        evaluation_end=evaluation_end,
        evaluated_at=evaluated_at,
        evaluation_forecasts=len(complete),
        excluded_immature_or_incomplete=excluded,
        baseline_replay_mismatches=baseline_replay_mismatches,
        baseline_unobservable_selections=baseline_unobservable_selections,
        candidate_unobservable_selections=candidate_unobservable_selections,
        baseline=baseline_metrics,
        candidate=candidate_metrics,
        relative_ev_delta=relative_ev_delta,
        promotion_eligible=not gates,
        gates=tuple(gates),
    )


@dataclass(frozen=True, slots=True)
class PolicyFold:
    baseline_version: str
    candidate_version: str
    marketplace: str
    train_cutoff: datetime
    evaluation_end: datetime

    def __post_init__(self) -> None:
        if self.train_cutoff.tzinfo is None or self.train_cutoff.utcoffset() is None:
            raise ValueError("train_cutoff must be timezone-aware")
        if self.evaluation_end.tzinfo is None or self.evaluation_end.utcoffset() is None:
            raise ValueError("evaluation_end must be timezone-aware")
        if not self.train_cutoff < self.evaluation_end:
            raise ValueError("train_cutoff must be before evaluation_end")


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    evaluated_at: datetime
    folds: tuple[BacktestReport, ...]
    promotion_eligible: bool

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_version": WALK_FORWARD_SCHEMA_VERSION,
            "evaluated_at": self.evaluated_at.isoformat(),
            "promotion_eligible": self.promotion_eligible,
            "folds": [fold.to_dict() for fold in self.folds],
        }
        return payload

    @property
    def digest(self) -> str:
        return sha256_json(self.to_dict())


def walk_forward_backtest(
    store: LearningStore,
    folds: Iterable[PolicyFold],
    *,
    evaluated_at: datetime,
    policy: BacktestPolicy | None = None,
) -> WalkForwardReport:
    """Evaluate independently versioned candidate policies over non-overlapping future folds."""

    ordered = sorted(folds, key=lambda fold: (fold.train_cutoff, fold.evaluation_end))
    if not ordered:
        raise ValueError("at least one fold is required")
    previous_end: datetime | None = None
    for fold in ordered:
        if previous_end is not None and fold.train_cutoff < previous_end:
            raise ValueError("walk-forward evaluation windows must not overlap backwards")
        previous_end = fold.evaluation_end

    reports = tuple(
        backtest_policy_change(
            store,
            baseline_version=fold.baseline_version,
            candidate_version=fold.candidate_version,
            marketplace=fold.marketplace,
            train_cutoff=fold.train_cutoff,
            evaluation_end=fold.evaluation_end,
            evaluated_at=evaluated_at,
            policy=policy,
        )
        for fold in ordered
    )
    return WalkForwardReport(
        evaluated_at=evaluated_at,
        folds=reports,
        promotion_eligible=all(report.promotion_eligible for report in reports),
    )
