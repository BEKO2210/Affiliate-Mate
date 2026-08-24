"""High-level analysis pipeline with stable automation output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from .decision import DecisionReport, EvaluationPolicy, evaluate_candidate
from .evidence import SQLiteEvidenceStore
from .io import CandidateInput
from .models import ProductCandidate
from .resolution import EvidenceResolution, resolve_candidate_from_store
from .sensitivity import SensitivityReport, analyze_sensitivity

ANALYSIS_SCHEMA_VERSION = "affiliate-mate.analysis.v1"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    candidate: ProductCandidate
    provided_fields: frozenset[str] | None
    decision: DecisionReport
    sensitivity: SensitivityReport
    evidence_resolution: EvidenceResolution | None = None

    def to_dict(self) -> dict[str, object]:
        candidate = asdict(self.candidate)
        return {
            "product": candidate,
            "provided_fields": (
                None if self.provided_fields is None else sorted(self.provided_fields)
            ),
            "decision": self.decision.to_dict(),
            "sensitivity": self.sensitivity.to_dict(),
            "evidence_resolution": (
                None
                if self.evidence_resolution is None
                else self.evidence_resolution.to_dict()
            ),
        }


def analyze_candidate(
    candidate: ProductCandidate,
    *,
    policy: EvaluationPolicy | None = None,
    provided_fields: frozenset[str] | None = None,
    evidence_store: SQLiteEvidenceStore | None = None,
    as_of: datetime | None = None,
    min_evidence_confidence: float = 0.0,
) -> AnalysisResult:
    resolution = None
    active_candidate = candidate
    active_fields = provided_fields
    if evidence_store is not None:
        resolution = resolve_candidate_from_store(
            candidate,
            evidence_store,
            as_of=as_of,
            min_confidence=min_evidence_confidence,
        )
        active_candidate = resolution.candidate
        if active_fields is not None:
            active_fields = active_fields | resolution.applied_signals

    return AnalysisResult(
        candidate=active_candidate,
        provided_fields=active_fields,
        decision=evaluate_candidate(
            active_candidate,
            policy=policy,
            available_fields=active_fields,
        ),
        sensitivity=analyze_sensitivity(active_candidate),
        evidence_resolution=resolution,
    )


def analyze_inputs(
    inputs: list[CandidateInput],
    *,
    policy: EvaluationPolicy | None = None,
    evidence_store: SQLiteEvidenceStore | None = None,
    as_of: datetime | None = None,
    min_evidence_confidence: float = 0.0,
) -> list[AnalysisResult]:
    """Analyze and deterministically rank input candidates, accepted first."""

    results = [
        analyze_candidate(
            item.candidate,
            policy=policy,
            provided_fields=item.provided_fields,
            evidence_store=evidence_store,
            as_of=as_of,
            min_evidence_confidence=min_evidence_confidence,
        )
        for item in inputs
    ]
    return sorted(
        results,
        key=lambda result: (
            result.decision.accepted,
            result.decision.score.opportunity_score,
            result.decision.score.estimated_value_per_1000_views,
            result.candidate.product_id,
        ),
        reverse=True,
    )


def build_automation_payload(
    results: list[AnalysisResult],
    *,
    policy: EvaluationPolicy | None = None,
) -> dict[str, object]:
    active_policy = EvaluationPolicy() if policy is None else policy
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "policy": active_policy.to_dict(),
        "summary": {
            "total": len(results),
            "shortlisted": sum(result.decision.accepted for result in results),
            "rejected": sum(not result.decision.accepted for result in results),
        },
        "results": [result.to_dict() for result in results],
    }
