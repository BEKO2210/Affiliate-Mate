"""Transparent scoring logic for product opportunities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import log1p

from .models import ProductCandidate


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    product_id: str
    opportunity_score: float
    economics: float
    demand: float
    competition_opportunity: float
    buyer_intent: float
    content_gap: float
    evidence_quality: float
    commission_per_sale: float
    estimated_value_per_1000_views: float


DEFAULT_WEIGHTS = {
    "economics": 0.30,
    "demand": 0.20,
    "competition_opportunity": 0.20,
    "buyer_intent": 0.15,
    "content_gap": 0.10,
    "evidence_quality": 0.05,
}

COMPONENT_LABELS = {
    "economics": "economics",
    "demand": "search demand",
    "competition_opportunity": "competition opportunity",
    "buyer_intent": "buyer intent",
    "content_gap": "content gap",
    "evidence_quality": "evidence quality",
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _economics_score(candidate: ProductCandidate) -> float:
    # 25 currency units per sale is treated as "excellent" for normalization.
    return _clamp((candidate.commission_per_sale / 25.0) * 100.0)


def _demand_score(monthly_searches: int) -> float:
    # Log scaling prevents giant keywords from drowning out everything else.
    # 10,000 monthly searches reaches the cap.
    if monthly_searches <= 0:
        return 0.0
    return _clamp((log1p(monthly_searches) / log1p(10_000)) * 100.0)


def _validate_weights(weights: dict[str, float]) -> None:
    if set(weights) != set(DEFAULT_WEIGHTS):
        raise ValueError(f"weights must contain exactly: {sorted(DEFAULT_WEIGHTS)}")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("weights must sum to 1.0")
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("weights must be non-negative")


def score_candidate(
    candidate: ProductCandidate,
    weights: dict[str, float] | None = None,
) -> ScoreBreakdown:
    """Score a candidate from 0 to 100 using transparent, inspectable inputs."""

    active_weights = DEFAULT_WEIGHTS if weights is None else weights
    _validate_weights(active_weights)

    components = {
        "economics": _economics_score(candidate),
        "demand": _demand_score(candidate.monthly_searches),
        "competition_opportunity": 100.0 - candidate.youtube_competition,
        "buyer_intent": float(candidate.buyer_intent),
        "content_gap": float(candidate.content_gap),
        "evidence_quality": float(candidate.evidence_quality),
    }
    total = sum(components[key] * active_weights[key] for key in active_weights)

    return ScoreBreakdown(
        product_id=candidate.product_id,
        opportunity_score=round(total, 2),
        economics=round(components["economics"], 2),
        demand=round(components["demand"], 2),
        competition_opportunity=round(components["competition_opportunity"], 2),
        buyer_intent=round(components["buyer_intent"], 2),
        content_gap=round(components["content_gap"], 2),
        evidence_quality=round(components["evidence_quality"], 2),
        commission_per_sale=round(candidate.commission_per_sale, 2),
        estimated_value_per_1000_views=round(
            candidate.estimated_value_per_1000_views, 2
        ),
    )


def score_contributions(
    breakdown: ScoreBreakdown,
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """Return each component's weighted point contribution to the 0-100 score."""

    active_weights = DEFAULT_WEIGHTS if weights is None else weights
    _validate_weights(active_weights)
    return {
        key: round(getattr(breakdown, key) * active_weights[key], 2)
        for key in active_weights
    }


def explain_score(
    breakdown: ScoreBreakdown,
    weights: dict[str, float] | None = None,
) -> tuple[str, ...]:
    """Generate deterministic, audit-friendly explanations for a score."""

    contributions = score_contributions(breakdown, weights)
    strongest = max(contributions, key=contributions.__getitem__)
    weakest = min(contributions, key=contributions.__getitem__)
    return (
        f"Strongest contribution: {COMPONENT_LABELS[strongest]} "
        f"(+{contributions[strongest]:.2f} points).",
        f"Weakest contribution: {COMPONENT_LABELS[weakest]} "
        f"(+{contributions[weakest]:.2f} points).",
        f"Economics assumption: {breakdown.commission_per_sale:.2f} commission per sale; "
        f"base EV/1K is {breakdown.estimated_value_per_1000_views:.2f}.",
    )


def rank_candidates(
    candidates: Iterable[ProductCandidate],
) -> list[tuple[ProductCandidate, ScoreBreakdown]]:
    """Return candidates sorted by opportunity score, highest first."""

    ranked = [(candidate, score_candidate(candidate)) for candidate in candidates]
    return sorted(
        ranked,
        key=lambda item: (
            item[1].opportunity_score,
            item[1].estimated_value_per_1000_views,
            item[0].product_id,
        ),
        reverse=True,
    )
