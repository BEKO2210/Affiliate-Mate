"""Immutable domain models for the research workspace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourceKind(StrEnum):
    OFFICIAL = "official"
    MANUFACTURER = "manufacturer"
    MANUAL = "manual"
    EDITORIAL = "editorial"
    RETAILER = "retailer"
    USER_REVIEW = "user_review"
    VIDEO = "video"
    DATASET = "dataset"
    OTHER = "other"


class ClaimRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClaimState(StrEnum):
    DRAFT = "draft"
    SUPPORTED = "supported"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class EvidenceStance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class ApprovalState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ResearchSource:
    source_id: str
    product_id: str
    kind: SourceKind
    title: str
    locator: str
    publisher: str
    retrieved_at: datetime
    published_at: datetime | None = None
    checksum: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for field_name in ("source_id", "product_id", "title", "locator", "publisher"):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_aware(self.retrieved_at, "retrieved_at")
        if self.published_at is not None:
            _require_aware(self.published_at, "published_at")
        if self.checksum is not None and not self.checksum.strip():
            raise ValueError("checksum must be non-empty when supplied")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dictionary when supplied")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "product_id": self.product_id,
            "kind": self.kind.value,
            "title": self.title,
            "locator": self.locator,
            "publisher": self.publisher,
            "retrieved_at": self.retrieved_at.astimezone(UTC).isoformat(),
            "published_at": (
                None if self.published_at is None else self.published_at.astimezone(UTC).isoformat()
            ),
            "checksum": self.checksum,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True, slots=True)
class ResearchClaim:
    claim_id: str
    product_id: str
    text: str
    risk: ClaimRisk
    created_at: datetime
    created_by: str

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "product_id", "text", "created_by"):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_aware(self.created_at, "created_at")

    def to_dict(self, *, state: ClaimState | None = None) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "product_id": self.product_id,
            "text": self.text,
            "risk": self.risk.value,
            "state": None if state is None else state.value,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "created_by": self.created_by,
        }


@dataclass(frozen=True, slots=True)
class ClaimStateEvent:
    event_id: int | None
    claim_id: str
    state: ClaimState
    actor: str
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.claim_id, "claim_id")
        _require_text(self.actor, "actor")
        _require_text(self.reason, "reason")
        _require_aware(self.created_at, "created_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "claim_id": self.claim_id,
            "state": self.state.value,
            "actor": self.actor,
            "reason": self.reason,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ClaimEvidenceLink:
    claim_id: str
    source_id: str
    stance: EvidenceStance
    locator: str
    quote: str | None
    created_at: datetime
    created_by: str

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "source_id", "locator", "created_by"):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_aware(self.created_at, "created_at")
        if self.quote is not None and not self.quote.strip():
            raise ValueError("quote must be non-empty when supplied")

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "source_id": self.source_id,
            "stance": self.stance.value,
            "locator": self.locator,
            "quote": self.quote,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "created_by": self.created_by,
        }


@dataclass(frozen=True, slots=True)
class ResearchNote:
    note_id: str
    product_id: str
    title: str
    body: str
    created_at: datetime
    created_by: str

    def __post_init__(self) -> None:
        for field_name in ("note_id", "product_id", "title", "body", "created_by"):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_aware(self.created_at, "created_at")

    def to_dict(self, *, claim_ids: tuple[str, ...] = ()) -> dict[str, object]:
        return {
            "note_id": self.note_id,
            "product_id": self.product_id,
            "title": self.title,
            "body": self.body,
            "claim_ids": list(claim_ids),
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "created_by": self.created_by,
        }


@dataclass(frozen=True, slots=True)
class ApprovalEvent:
    event_id: int | None
    product_id: str
    state: ApprovalState
    actor: str
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("product_id", "actor", "reason"):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_aware(self.created_at, "created_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "product_id": self.product_id,
            "state": self.state.value,
            "actor": self.actor,
            "reason": self.reason,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }
