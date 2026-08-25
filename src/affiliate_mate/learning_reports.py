"""Predicted-vs-realized and calibration reports with minimum-sample safeguards."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Iterable

from .learning_models import (
    CALIBRATION_SCHEMA_VERSION,
    PERFORMANCE_SCHEMA_VERSION,
    ForecastSnapshot,
    OutcomeEvent,
    OutcomeKind,
    OutcomeTotals,
    sha256_json,
)
from .learning_store import LearningStore


@dataclass(frozen=True, slots=True)
class PerformancePolicy:
    reporting_lag_days: int = 7
    require_video_views: bool = True
    require_affiliate_clicks: bool = True
    require_orders: bool = True
    require_commission_report: bool = True

    def __post_init__(self) -> None:
        if self.reporting_lag_days < 0:
            raise ValueError("reporting_lag_days must be >= 0")


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    forecast: ForecastSnapshot
    evaluated_at: datetime
    horizon_end: datetime
    mature: bool
    required_kinds_present: bool
    missing_kinds: tuple[str, ...]
    totals: OutcomeTotals
    event_count: int

    @property
    def prediction_error_ctr(self) -> float | None:
        actual = self.totals.ctr
        return None if actual is None else actual - self.forecast.predicted_ctr

    @property
    def prediction_error_conversion_rate(self) -> float | None:
        actual = self.totals.conversion_rate
        if actual is None:
            return None
        return actual - self.forecast.predicted_conversion_rate

    @property
    def prediction_error_value_per_1000_views(self) -> float | None:
        actual = self.totals.realized_value_per_1000_views
        if actual is None:
            return None
        return actual - self.forecast.predicted_value_per_1000_views

    @property
    def sample_eligible(self) -> bool:
        return self.mature and self.required_kinds_present

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PERFORMANCE_SCHEMA_VERSION,
            "forecast": self.forecast.to_dict(),
            "evaluated_at": self.evaluated_at.isoformat(),
            "horizon_end": self.horizon_end.isoformat(),
            "mature": self.mature,
            "required_kinds_present": self.required_kinds_present,
            "missing_kinds": list(self.missing_kinds),
            "sample_eligible": self.sample_eligible,
            "event_count": self.event_count,
            "totals": self.totals.to_dict(),
            "errors": {
                "ctr": self.prediction_error_ctr,
                "conversion_rate": self.prediction_error_conversion_rate,
                "value_per_1000_views": self.prediction_error_value_per_1000_views,
            },
        }

    @property
    def digest(self) -> str:
        return sha256_json(self.to_dict())


def _aggregate_outcomes(
    forecast: ForecastSnapshot,
    events: Iterable[OutcomeEvent],
) -> OutcomeTotals:
    views = clicks = orders = 0
    gross = refunds = reversals = 0
    currencies: set[str] = set()
    for event in events:
        if event.product_id != forecast.product_id or event.content_id != forecast.content_id:
            raise ValueError("outcome does not match forecast product/content lineage")
        if event.marketplace != forecast.marketplace:
            raise ValueError("outcome marketplace does not match forecast")
        if (
            forecast.package_digest is not None
            and event.package_digest is not None
            and event.package_digest != forecast.package_digest
        ):
            raise ValueError("outcome package lineage conflicts with forecast")
        if event.kind is OutcomeKind.VIDEO_VIEW:
            views += event.count
        elif event.kind is OutcomeKind.AFFILIATE_CLICK:
            clicks += event.count
        elif event.kind is OutcomeKind.ORDER:
            orders += event.count
        elif event.kind is OutcomeKind.COMMISSION:
            gross += event.amount_minor
            currencies.add(str(event.currency))
        elif event.kind is OutcomeKind.REFUND:
            refunds += event.amount_minor
            currencies.add(str(event.currency))
        elif event.kind is OutcomeKind.REVERSAL:
            reversals += event.amount_minor
            currencies.add(str(event.currency))
    if len(currencies) > 1:
        raise ValueError("mixed outcome currencies are not comparable without FX evidence")
    currency = next(iter(currencies), None)
    if currency is not None and currency.upper() != forecast.currency.upper():
        raise ValueError(
            f"outcome currency {currency} does not match forecast currency {forecast.currency}"
        )
    return OutcomeTotals(
        views=views,
        clicks=clicks,
        orders=orders,
        gross_commission_minor=gross,
        refunds_minor=refunds,
        reversals_minor=reversals,
        currency=currency,
    )


def build_performance_report(
    store: LearningStore,
    forecast: ForecastSnapshot,
    *,
    evaluated_at: datetime,
    policy: PerformancePolicy | None = None,
) -> PerformanceReport:
    """Compare a frozen forecast with only outcomes known by `evaluated_at`."""

    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")
    active_policy = PerformancePolicy() if policy is None else policy
    horizon_end = forecast.predicted_at + timedelta(days=forecast.horizon_days)
    maturity_time = horizon_end + timedelta(days=active_policy.reporting_lag_days)
    events = store.list_outcomes(
        product_id=forecast.product_id,
        content_id=forecast.content_id,
        effective_start=forecast.predicted_at,
        effective_end=horizon_end,
        as_of=evaluated_at,
    )
    kinds = {event.kind for event in events}
    required: set[OutcomeKind] = set()
    if active_policy.require_video_views:
        required.add(OutcomeKind.VIDEO_VIEW)
    if active_policy.require_affiliate_clicks:
        required.add(OutcomeKind.AFFILIATE_CLICK)
    if active_policy.require_orders:
        required.add(OutcomeKind.ORDER)
    if active_policy.require_commission_report:
        required.add(OutcomeKind.COMMISSION)
    missing = tuple(sorted(kind.value for kind in required - kinds))
    return PerformanceReport(
        forecast=forecast,
        evaluated_at=evaluated_at,
        horizon_end=horizon_end,
        mature=evaluated_at >= maturity_time,
        required_kinds_present=not missing,
        missing_kinds=missing,
        totals=_aggregate_outcomes(forecast, events),
        event_count=len(events),
    )


def price_band(price: float) -> str:
    if price < 50:
        return "lt_50"
    if price < 100:
        return "50_99"
    if price < 250:
        return "100_249"
    if price < 500:
        return "250_499"
    return "gte_500"


def wilson_interval(
    successes: int,
    trials: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float, float] | None:
    """Return the Wilson score interval for a binomial proportion."""

    if trials <= 0:
        return None
    if successes < 0 or successes > trials:
        raise ValueError("successes must be between 0 and trials")
    phat = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials
    center = (phat + z2 / (2 * trials)) / denominator
    margin = (
        z
        * math.sqrt((phat * (1 - phat) + z2 / (4 * trials)) / trials)
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


@dataclass(frozen=True, slots=True)
class CalibrationPolicy:
    min_forecasts: int = 3
    min_views: int = 1000
    min_clicks: int = 50
    min_orders: int = 5
    relative_drift_threshold: float = 0.25

    def __post_init__(self) -> None:
        for field_name in ("min_forecasts", "min_views", "min_clicks", "min_orders"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be >= 0")
        if self.relative_drift_threshold < 0:
            raise ValueError("relative_drift_threshold must be >= 0")


def _relative_error(actual: float, predicted: float) -> float | None:
    if predicted == 0:
        return None
    return (actual - predicted) / predicted


def _drift_state(
    *,
    actual: float | None,
    predicted: float | None,
    enough_sample: bool,
    threshold: float,
) -> str:
    if not enough_sample or actual is None or predicted is None:
        return "insufficient"
    error = _relative_error(actual, predicted)
    if error is None:
        return "insufficient"
    return "drift" if abs(error) > threshold else "stable"


@dataclass(frozen=True, slots=True)
class CalibrationCohort:
    marketplace: str
    category: str
    price_band: str
    forecast_count: int
    views: int
    clicks: int
    orders: int
    net_commission_minor: int
    currency: str | None
    predicted_ctr: float | None
    realized_ctr: float | None
    ctr_ci95: tuple[float, float] | None
    ctr_state: str
    predicted_conversion_rate: float | None
    realized_conversion_rate: float | None
    conversion_ci95: tuple[float, float] | None
    conversion_state: str
    predicted_value_per_1000_views: float | None
    realized_value_per_1000_views: float | None
    value_state: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["ctr_ci95"] = None if self.ctr_ci95 is None else list(self.ctr_ci95)
        data["conversion_ci95"] = (
            None if self.conversion_ci95 is None else list(self.conversion_ci95)
        )
        return data


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    evaluated_at: datetime
    policy: CalibrationPolicy
    cohort_dimensions: tuple[str, ...]
    included_forecasts: int
    excluded_forecasts: int
    cohorts: tuple[CalibrationCohort, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": CALIBRATION_SCHEMA_VERSION,
            "evaluated_at": self.evaluated_at.isoformat(),
            "policy": asdict(self.policy),
            "cohort_dimensions": list(self.cohort_dimensions),
            "included_forecasts": self.included_forecasts,
            "excluded_forecasts": self.excluded_forecasts,
            "cohorts": [cohort.to_dict() for cohort in self.cohorts],
        }

    @property
    def digest(self) -> str:
        return sha256_json(self.to_dict())


def build_calibration_report(
    reports: Iterable[PerformanceReport],
    *,
    evaluated_at: datetime,
    policy: CalibrationPolicy | None = None,
) -> CalibrationReport:
    """Aggregate only mature, explicitly complete performance reports."""

    active_policy = CalibrationPolicy() if policy is None else policy
    all_reports = list(reports)
    eligible = [report for report in all_reports if report.sample_eligible]
    grouped: dict[tuple[str, str, str], list[PerformanceReport]] = {}
    for report in eligible:
        key = (
            report.forecast.marketplace,
            report.forecast.category,
            price_band(report.forecast.price),
        )
        grouped.setdefault(key, []).append(report)

    cohorts: list[CalibrationCohort] = []
    for (marketplace, category, band), items in sorted(grouped.items()):
        views = sum(item.totals.views for item in items)
        clicks = sum(item.totals.clicks for item in items)
        orders = sum(item.totals.orders for item in items)
        net = sum(item.totals.net_commission_minor for item in items)
        currencies = {
            item.totals.currency
            for item in items
            if item.totals.currency is not None
        }
        if len(currencies) > 1:
            raise ValueError(
                f"calibration cohort {marketplace}/{category}/{band} spans multiple currencies"
            )
        currency = next(iter(currencies), None)

        predicted_ctr = (
            None
            if views <= 0
            else sum(item.totals.views * item.forecast.predicted_ctr for item in items) / views
        )
        realized_ctr = None if views <= 0 else clicks / views
        predicted_conversion = (
            None
            if clicks <= 0
            else sum(
                item.totals.clicks * item.forecast.predicted_conversion_rate
                for item in items
            )
            / clicks
        )
        realized_conversion = None if clicks <= 0 else orders / clicks
        predicted_value = (
            None
            if views <= 0
            else sum(
                item.totals.views * item.forecast.predicted_value_per_1000_views
                for item in items
            )
            / views
        )
        realized_value = (
            None
            if views <= 0 or currency is None
            else (net / 100.0) * 1000.0 / views
        )
        enough_forecasts = len(items) >= active_policy.min_forecasts
        cohorts.append(
            CalibrationCohort(
                marketplace=marketplace,
                category=category,
                price_band=band,
                forecast_count=len(items),
                views=views,
                clicks=clicks,
                orders=orders,
                net_commission_minor=net,
                currency=currency,
                predicted_ctr=predicted_ctr,
                realized_ctr=realized_ctr,
                ctr_ci95=wilson_interval(clicks, views),
                ctr_state=_drift_state(
                    actual=realized_ctr,
                    predicted=predicted_ctr,
                    enough_sample=enough_forecasts and views >= active_policy.min_views,
                    threshold=active_policy.relative_drift_threshold,
                ),
                predicted_conversion_rate=predicted_conversion,
                realized_conversion_rate=realized_conversion,
                conversion_ci95=wilson_interval(orders, clicks),
                conversion_state=_drift_state(
                    actual=realized_conversion,
                    predicted=predicted_conversion,
                    enough_sample=(
                        enough_forecasts
                        and clicks >= active_policy.min_clicks
                        and orders >= active_policy.min_orders
                    ),
                    threshold=active_policy.relative_drift_threshold,
                ),
                predicted_value_per_1000_views=predicted_value,
                realized_value_per_1000_views=realized_value,
                value_state=_drift_state(
                    actual=realized_value,
                    predicted=predicted_value,
                    enough_sample=enough_forecasts and views >= active_policy.min_views,
                    threshold=active_policy.relative_drift_threshold,
                ),
            )
        )

    return CalibrationReport(
        evaluated_at=evaluated_at,
        policy=active_policy,
        cohort_dimensions=("marketplace", "category", "price_band"),
        included_forecasts=len(eligible),
        excluded_forecasts=len(all_reports) - len(eligible),
        cohorts=tuple(cohorts),
    )
