from datetime import UTC, datetime, timedelta

import pytest

from affiliate_mate.models import ProductCandidate
from affiliate_mate.trend_intelligence import (
    CSVTrendEvidenceProvider,
    TrendPoint,
    analyze_trend,
)


def _point(day: int, value: float) -> TrendPoint:
    return TrendPoint(datetime(2026, 8, day, tzinfo=UTC), value)


def _candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="p1",
        title="Example GPS",
        marketplace="DE",
        currency="EUR",
        price=299.0,
        commission_rate=0.04,
        monthly_searches=100,
        youtube_competition=50,
        buyer_intent=60,
        content_gap=55,
        evidence_quality=80,
    )


def test_upward_and_downward_trends_land_on_opposite_sides_of_neutral() -> None:
    upward = analyze_trend([_point(1, 10), _point(2, 12), _point(3, 30), _point(4, 36)])
    downward = analyze_trend([_point(1, 40), _point(2, 35), _point(3, 15), _point(4, 10)])
    assert upward.trend_strength > 50
    assert downward.trend_strength < 50
    assert upward.recent_vs_prior_ratio > 1
    assert downward.recent_vs_prior_ratio < 1


def test_flat_series_has_neutral_trend_and_zero_seasonality() -> None:
    metrics = analyze_trend([_point(1, 20), _point(2, 20), _point(3, 20), _point(4, 20)])
    assert metrics.trend_strength == 50
    assert metrics.seasonality == 0


def test_trend_requires_enough_points() -> None:
    with pytest.raises(ValueError, match="four"):
        analyze_trend([_point(1, 1), _point(2, 2), _point(3, 3)])


def test_csv_trend_provider_emits_expiring_auxiliary_signals(tmp_path) -> None:
    path = tmp_path / "trend.csv"
    rows = [
        "product_id,marketplace,observed_at,value",
        "p1,DE,2026-05-01T00:00:00Z,50",
        "p1,DE,2026-06-01T00:00:00Z,60",
        "p1,DE,2026-07-01T00:00:00Z,90",
        "p1,DE,2026-08-01T00:00:00Z,100",
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    provider = CSVTrendEvidenceProvider.from_csv(path)
    observations = provider.collect(_candidate())
    assert {item.signal for item in observations} == {"trend_strength", "seasonality"}
    assert all(item.expires_at is not None for item in observations)
    trend = next(item for item in observations if item.signal == "trend_strength")
    assert trend.expires_at == datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=14)
