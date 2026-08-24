"""Fail-closed opportunity gates and decision reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import ProductCandidate
from .scoring import ScoreBreakdown, explain_score, score_candidate

DEFAULT_REQUIRED_EVIDENCE_FIELDS = (
    "monthly_searches",
    "youtube_competition",
    "buyer_intent",
    "content_gap",
    "evidence_quality",
)


@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    """Explicit thresholds used to reject weak or under-evidenced opportunities."""

    min_commission_per_sale: float = 2.0
    min_monthly_searches: int = 100
    max_youtube_competition: int = 95
    min_buyer_intent: int = 35
    min_evidence_quality: int = 40
    min_estimated_value_per_1000_views: float = 1.0
    min_opportunity_score: float = 45.0
    required_evidence_fields: tuple[str, ...] = DEFAULT_REQUIRED_EVIDENCE_FIELDS

    def __post_init__(self) -> None:
        if self.min_commission_per_sale < 0:
            raise ValueError("min_commission_per_sale must be >= 0")
        if self.min_monthly_searches < 0:
            raise ValueError("min_monthly_searches must be >= 0")
        for field_name in (
            "max_youtube_competition",
            "min_buyer_intent",
            "min_evidence_quality",
            "min_opportunity_score",
        ):
            value = getattr(self, field_name)
            if not 0 <= value <= 100:
                raise ValueError(f"{field_name} must be between 0 and 100")
        if self.min_estimated_value_per_1000_views < 0:
            raise ValueError("min_estimated_value_per_1000_views must be >= 0")
        if len(set(self.required_evidence_fields)) != len(self.required_evidence_fields):
            raise ValueError("required_evidence_fields must not contain duplicates")

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["required_evidence_fields"] = list(self.required_evidence_fields)
        return result


@dataclass(frozen=True, slots=True)
class GateResult:
    code: str
    passed: bool
    actual: int | float | str | None
    operator: str
    threshold: int | float | str | None
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "passed": self.passed,
            "actual": self.actual,
            "operator": self.operator,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class DecisionReport:
    accepted: bool
    score: ScoreBreakdown
    gates: tuple[GateResult, ...]
    explanations: tuple[str, ...]

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        return tuple(gate.message for gate in self.gates if not gate.passed)

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "status": "shortlist" if self.accepted else "reject",
            "score": asdict(self.score),
            "gates": [gate.to_dict() for gate in self.gates],
            "rejection_reasons": list(self.rejection_reasons),
            "explanations": list(self.explanations),
        }


def _minimum_gate(code: str, actual: float, threshold: float, label: str) -> GateResult:
    passed = actual >= threshold
    return GateResult(
        code=code,
        passed=passed,
        actual=round(actual, 4),
        operator=">=",
        threshold=threshold,
        message=(
            f"{label} passes: {actual:.2f} >= {threshold:.2f}."
            if passed
            else f"{label} too low: {actual:.2f} < {threshold:.2f}."
        ),
    )


def _maximum_gate(code: str, actual: float, threshold: float, label: str) -> GateResult:
    passed = actual <= threshold
    return GateResult(
        code=code,
        passed=passed,
        actual=round(actual, 4),
        operator="<=",
        threshold=threshold,
        message=(
            f"{label} passes: {actual:.2f} <= {threshold:.2f}."
            if passed
            else f"{label} too high: {actual:.2f} > {threshold:.2f}."
        ),
    )


def _evidence_completeness_gate(
    policy: EvaluationPolicy,
    available_fields: frozenset[str] | None,
) -> GateResult:
    if available_fields is None:
        return GateResult(
            code="required_evidence",
            passed=True,
            actual="not tracked",
            operator="contains",
            threshold=", ".join(policy.required_evidence_fields),
            message="Input completeness was not tracked for this programmatic candidate.",
        )
    missing = sorted(set(policy.required_evidence_fields) - set(available_fields))
    if not missing:
        return GateResult(
            code="required_evidence",
            passed=True,
            actual="complete",
            operator="contains",
            threshold=", ".join(policy.required_evidence_fields),
            message="All required evidence fields are explicitly present.",
        )
    return GateResult(
        code="required_evidence",
        passed=False,
        actual=", ".join(missing),
        operator="contains",
        threshold=", ".join(policy.required_evidence_fields),
        message=f"Missing required evidence: {', '.join(missing)}.",
    )


def evaluate_candidate(
    candidate: ProductCandidate,
    *,
    policy: EvaluationPolicy | None = None,
    available_fields: frozenset[str] | None = None,
) -> DecisionReport:
    """Evaluate one product, preserving every gate result and score explanation."""

    active_policy = EvaluationPolicy() if policy is None else policy
    score = score_candidate(candidate)
    gates = (
        _evidence_completeness_gate(active_policy, available_fields),
        _minimum_gate(
            "commission_per_sale",
            candidate.commission_per_sale,
            active_policy.min_commission_per_sale,
            "Commission per sale",
        ),
        _minimum_gate(
            "monthly_searches",
            float(candidate.monthly_searches),
            float(active_policy.min_monthly_searches),
            "Monthly searches",
        ),
        _maximum_gate(
            "youtube_competition",
            float(candidate.youtube_competition),
            float(active_policy.max_youtube_competition),
            "YouTube competition",
        ),
        _minimum_gate(
            "buyer_intent",
            float(candidate.buyer_intent),
            float(active_policy.min_buyer_intent),
            "Buyer intent",
        ),
        _minimum_gate(
            "evidence_quality",
            float(candidate.evidence_quality),
            float(active_policy.min_evidence_quality),
            "Evidence quality",
        ),
        _minimum_gate(
            "estimated_value_per_1000_views",
            candidate.estimated_value_per_1000_views,
            active_policy.min_estimated_value_per_1000_views,
            "Estimated value per 1,000 views",
        ),
        _minimum_gate(
            "opportunity_score",
            score.opportunity_score,
            active_policy.min_opportunity_score,
            "Opportunity score",
        ),
    )
    return DecisionReport(
        accepted=all(gate.passed for gate in gates),
        score=score,
        gates=gates,
        explanations=explain_score(score),
    )
