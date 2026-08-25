"""Deterministic trend and seasonality evidence from time-series exports."""

import csv
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .evidence import EvidenceObservation
from .freshness import SignalFreshnessPolicy
from .models import ProductCandidate


@dataclass(frozen=True, slots=True)
class TrendPoint:
    observed_at: datetime
    value: float

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("trend timestamps must be timezone-aware")
        if not math.isfinite(self.value) or self.value < 0:
            raise ValueError("trend values must be finite and >= 0")


@dataclass(frozen=True, slots=True)
class TrendMetrics:
    trend_strength: float
    seasonality: float
    recent_vs_prior_ratio: float
    points: int


def analyze_trend(points: list[TrendPoint]) -> TrendMetrics:
    """Summarize direction and volatility without forecasting future demand."""

    ordered = sorted(points, key=lambda point: point.observed_at)
    if len(ordered) < 4:
        raise ValueError("at least four trend points are required")
    values = [point.value for point in ordered]
    split = max(2, len(values) // 2)
    prior = values[:split]
    recent = values[split:]
    prior_mean = statistics.fmean(prior)
    recent_mean = statistics.fmean(recent)
    if prior_mean == 0:
        ratio = 1.0 if recent_mean == 0 else 2.0
    else:
        ratio = recent_mean / prior_mean

    bounded_ratio = max(0.01, min(100.0, ratio))
    direction = math.tanh(math.log(bounded_ratio))
    trend_strength = 50.0 + 50.0 * direction

    mean_value = statistics.fmean(values)
    if mean_value == 0:
        seasonality = 0.0
    else:
        coefficient_of_variation = statistics.pstdev(values) / mean_value
        seasonality = min(100.0, coefficient_of_variation * 100.0)

    return TrendMetrics(
        trend_strength=round(trend_strength, 2),
        seasonality=round(seasonality, 2),
        recent_vs_prior_ratio=round(ratio, 4),
        points=len(values),
    )


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("trend observed_at must include a timezone")
    return parsed.astimezone(UTC)


class CSVTrendEvidenceProvider:
    """Generate auxiliary trend evidence from user-owned time-series data."""

    def __init__(
        self,
        series: dict[tuple[str, str], list[TrendPoint]],
        *,
        source: str = "trend-csv",
        confidence: float = 0.75,
        freshness: SignalFreshnessPolicy | None = None,
    ) -> None:
        if not source.strip():
            raise ValueError("source must not be empty")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        self._series = series
        self._source = source
        self._confidence = confidence
        self._freshness = freshness or SignalFreshnessPolicy()

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        source: str = "trend-csv",
        confidence: float = 0.75,
        freshness: SignalFreshnessPolicy | None = None,
    ) -> "CSVTrendEvidenceProvider":
        series: dict[tuple[str, str], list[TrendPoint]] = {}
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"product_id", "marketplace", "observed_at", "value"}
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise ValueError(
                    "trend CSV missing required columns: " + ", ".join(sorted(missing))
                )
            for row_number, row in enumerate(reader, start=2):
                try:
                    key = (
                        row["product_id"].strip(),
                        row["marketplace"].strip().upper(),
                    )
                    if not key[0] or not key[1]:
                        raise ValueError("product_id and marketplace must not be empty")
                    point = TrendPoint(
                        observed_at=_parse_timestamp(row["observed_at"]),
                        value=float(row["value"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"invalid trend CSV row {row_number}: {exc}") from exc
                series.setdefault(key, []).append(point)
        return cls(
            series,
            source=source,
            confidence=confidence,
            freshness=freshness,
        )

    @property
    def name(self) -> str:
        return self._source

    def collect(self, candidate: ProductCandidate) -> list[EvidenceObservation]:
        points = self._series.get((candidate.product_id, candidate.marketplace.upper()))
        if not points:
            return []
        metrics = analyze_trend(points)
        observed_at = max(point.observed_at for point in points)
        metadata = {
            "points": metrics.points,
            "recent_vs_prior_ratio": metrics.recent_vs_prior_ratio,
            "method": "half-window-ratio-and-coefficient-of-variation",
        }
        observations = [
            EvidenceObservation(
                product_id=candidate.product_id,
                signal="trend_strength",
                value=metrics.trend_strength,
                source=self._source,
                marketplace=candidate.marketplace,
                observed_at=observed_at,
                confidence=self._confidence,
                unit="score_0_100",
                metadata=metadata,
            ),
            EvidenceObservation(
                product_id=candidate.product_id,
                signal="seasonality",
                value=metrics.seasonality,
                source=self._source,
                marketplace=candidate.marketplace,
                observed_at=observed_at,
                confidence=self._confidence,
                unit="score_0_100",
                metadata=metadata,
            ),
        ]
        return [self._freshness.apply(observation) for observation in observations]
