"""Resolve normalized candidates against the latest valid persisted evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .evidence import EvidenceObservation, SQLiteEvidenceStore
from .models import ProductCandidate

CANDIDATE_EVIDENCE_SIGNALS = (
    "price",
    "commission_rate",
    "monthly_searches",
    "youtube_competition",
    "buyer_intent",
    "content_gap",
    "evidence_quality",
    "estimated_ctr",
    "estimated_conversion_rate",
)

INTEGER_SIGNALS = frozenset(
    {
        "monthly_searches",
        "youtube_competition",
        "buyer_intent",
        "content_gap",
        "evidence_quality",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceResolution:
    """The candidate after applying evidence plus a complete audit trail."""

    candidate: ProductCandidate
    applied: tuple[EvidenceObservation, ...]
    skipped_low_confidence: tuple[EvidenceObservation, ...]

    @property
    def applied_signals(self) -> frozenset[str]:
        return frozenset(item.signal for item in self.applied)

    def to_dict(self) -> dict[str, object]:
        return {
            "applied": [item.to_dict() for item in self.applied],
            "skipped_low_confidence": [
                item.to_dict() for item in self.skipped_low_confidence
            ],
        }


def _coerce_signal_value(signal: str, value: float) -> int | float:
    if signal not in INTEGER_SIGNALS:
        return float(value)
    rounded = round(value)
    if abs(value - rounded) > 1e-9:
        raise ValueError(f"Evidence signal {signal!r} must be integer-valued")
    return int(rounded)


def resolve_candidate_from_store(
    candidate: ProductCandidate,
    store: SQLiteEvidenceStore,
    *,
    as_of: datetime | None = None,
    min_confidence: float = 0.0,
) -> EvidenceResolution:
    """Apply the latest non-expired observation for each supported candidate signal."""

    if not 0 <= min_confidence <= 1:
        raise ValueError("min_confidence must be between 0 and 1")

    updates: dict[str, int | float] = {}
    applied: list[EvidenceObservation] = []
    skipped: list[EvidenceObservation] = []

    for signal in CANDIDATE_EVIDENCE_SIGNALS:
        observation = store.latest(
            candidate.product_id,
            signal,
            marketplace=candidate.marketplace,
            as_of=as_of,
        )
        if observation is None:
            continue
        if observation.confidence < min_confidence:
            skipped.append(observation)
            continue
        if (
            signal == "price"
            and observation.unit is not None
            and observation.unit.upper() != candidate.currency.upper()
        ):
            raise ValueError(
                "Price evidence currency mismatch: "
                f"{observation.unit} != {candidate.currency}"
            )
        updates[signal] = _coerce_signal_value(signal, observation.value)
        applied.append(observation)

    resolved = candidate if not updates else replace(candidate, **updates)
    return EvidenceResolution(
        candidate=resolved,
        applied=tuple(applied),
        skipped_low_confidence=tuple(skipped),
    )
