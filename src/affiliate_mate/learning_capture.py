"""Freeze point-in-time opportunity forecasts before outcomes are visible."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from .analysis import AnalysisResult
from .decision import EvaluationPolicy
from .learning_models import ForecastSnapshot, ScoringPolicyVersion, sha256_json


def evaluation_policy_from_version(version: ScoringPolicyVersion) -> EvaluationPolicy:
    payload = dict(version.policy_payload)
    fields = payload.get("required_evidence_fields")
    if isinstance(fields, list):
        payload["required_evidence_fields"] = tuple(str(item) for item in fields)
    try:
        return EvaluationPolicy(**payload)
    except TypeError as exc:
        raise ValueError(
            f"policy {version.version!r} is not a compatible EvaluationPolicy payload"
        ) from exc


def capture_forecast(
    result: AnalysisResult,
    *,
    predicted_at: datetime,
    horizon_days: int,
    content_id: str,
    category: str,
    policy_version: ScoringPolicyVersion,
    evaluation_policy: EvaluationPolicy,
    package_digest: str | None = None,
) -> ForecastSnapshot:
    """Freeze one analysis result with explicit policy and time lineage.

    If an AnalysisResult carries persisted evidence, every applied or skipped observation must
    have existed by `predicted_at`. This prevents callers from accidentally freezing a forecast
    that already contains future evidence.
    """

    if predicted_at.tzinfo is None or predicted_at.utcoffset() is None:
        raise ValueError("predicted_at must be timezone-aware")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be > 0")
    if policy_version.policy_payload != evaluation_policy.to_dict():
        raise ValueError(
            "policy_version payload must exactly match the EvaluationPolicy used for analysis"
        )
    if policy_version.created_at > predicted_at:
        raise ValueError("policy_version must exist by predicted_at")

    resolution = result.evidence_resolution
    if resolution is not None:
        observations = resolution.applied + resolution.skipped_low_confidence
        future = [
            observation
            for observation in observations
            if observation.observed_at > predicted_at
        ]
        if future:
            sources = ", ".join(
                sorted({f"{item.signal}@{item.observed_at.isoformat()}" for item in future})
            )
            raise ValueError(f"forecast contains evidence observed after predicted_at: {sources}")

    candidate_payload = asdict(result.candidate)
    candidate_digest = sha256_json(candidate_payload)
    analysis_payload = result.to_dict()
    analysis_digest = sha256_json(analysis_payload)
    identity_payload = {
        "product_id": result.candidate.product_id,
        "marketplace": result.candidate.marketplace,
        "content_id": content_id,
        "package_digest": package_digest,
        "predicted_at": predicted_at.isoformat(),
        "horizon_days": horizon_days,
        "policy_version": policy_version.version,
        "policy_digest": policy_version.digest,
        "analysis_digest": analysis_digest,
    }
    forecast_id = sha256_json(identity_payload)

    return ForecastSnapshot(
        forecast_id=forecast_id,
        product_id=result.candidate.product_id,
        marketplace=result.candidate.marketplace,
        currency=result.candidate.currency,
        content_id=content_id.strip(),
        category=category.strip(),
        price=result.candidate.price,
        predicted_at=predicted_at,
        horizon_days=horizon_days,
        policy_version=policy_version.version,
        policy_digest=policy_version.digest,
        analysis_digest=analysis_digest,
        candidate_digest=candidate_digest,
        accepted=result.decision.accepted,
        opportunity_score=result.decision.score.opportunity_score,
        predicted_ctr=result.candidate.estimated_ctr,
        predicted_conversion_rate=result.candidate.estimated_conversion_rate,
        predicted_value_per_1000_views=result.candidate.estimated_value_per_1000_views,
        commission_per_sale=result.candidate.commission_per_sale,
        candidate_payload=candidate_payload,
        available_fields=(
            ()
            if result.provided_fields is None
            else tuple(sorted(result.provided_fields))
        ),
        provided_fields_tracked=result.provided_fields is not None,
        package_digest=package_digest,
    )
