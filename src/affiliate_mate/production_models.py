"""Immutable production-domain models with explicit research lineage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

PRODUCTION_AUTH_SCHEMA_VERSION = "affiliate-mate.production-authorization.v1"
SCRIPT_SCHEMA_VERSION = "affiliate-mate.script.v1"
PRODUCTION_PACKAGE_SCHEMA_VERSION = "affiliate-mate.production-package.v1"
PRODUCTION_SIGNOFF_SCHEMA_VERSION = "affiliate-mate.production-signoff.v1"
PUBLISH_PLAN_SCHEMA_VERSION = "affiliate-mate.publish-plan.v1"


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_digest(value: str, field_name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_safe_relative_path(value: str) -> None:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not value.strip()
        or ".." in path.parts
        or "." == value
        or "\\" in value
    ):
        raise ValueError("artifact path must be a safe relative POSIX path")


class ScriptSegmentKind(StrEnum):
    INTRO = "intro"
    FACT = "fact"
    DISCLOSURE = "disclosure"
    CTA = "cta"
    OUTRO = "outro"


class ArtifactKind(StrEnum):
    SCRIPT = "script"
    NARRATION = "narration"
    VIDEO = "video"
    THUMBNAIL = "thumbnail"
    METADATA = "metadata"
    CAPTIONS = "captions"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ProductionAuthorization:
    product_id: str
    approval_event_id: int
    research_digest: str
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.product_id, "product_id")
        if self.approval_event_id <= 0:
            raise ValueError("approval_event_id must be positive")
        _require_digest(self.research_digest, "research_digest")
        _require_aware(self.created_at, "created_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PRODUCTION_AUTH_SCHEMA_VERSION,
            "product_id": self.product_id,
            "approval_event_id": self.approval_event_id,
            "research_digest": self.research_digest,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    claim_id: str
    text: str
    source_ids: tuple[str, ...]
    source_locators: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.claim_id, "claim_id")
        _require_text(self.text, "text")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("source_ids must not contain duplicates")
        if len(self.source_ids) != len(self.source_locators):
            raise ValueError("source_ids and source_locators must have equal length")

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "source_ids": list(self.source_ids),
            "source_locators": list(self.source_locators),
        }


@dataclass(frozen=True, slots=True)
class ScriptRequest:
    product_id: str
    research_digest: str
    language: str
    working_title: str
    claims: tuple[GroundedClaim, ...]
    spoken_disclosure: str
    description_disclosure: str
    constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.product_id, "product_id")
        _require_digest(self.research_digest, "research_digest")
        _require_text(self.language, "language")
        _require_text(self.working_title, "working_title")
        _require_text(self.spoken_disclosure, "spoken_disclosure")
        _require_text(self.description_disclosure, "description_disclosure")
        if not self.claims:
            raise ValueError("script request must contain at least one grounded claim")
        claim_ids = tuple(claim.claim_id for claim in self.claims)
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("script request claims must have unique IDs")
        if any(not constraint.strip() for constraint in self.constraints):
            raise ValueError("script constraints must not contain empty values")
        if len(set(self.constraints)) != len(self.constraints):
            raise ValueError("script constraints must not contain duplicates")

    def to_dict(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "research_digest": self.research_digest,
            "language": self.language,
            "working_title": self.working_title,
            "claims": [claim.to_dict() for claim in self.claims],
            "spoken_disclosure": self.spoken_disclosure,
            "description_disclosure": self.description_disclosure,
            "constraints": list(self.constraints),
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.to_dict()))


@dataclass(frozen=True, slots=True)
class ScriptSegment:
    segment_id: str
    kind: ScriptSegmentKind
    text: str
    claim_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.segment_id, "segment_id")
        _require_text(self.text, "text")
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("claim_ids must not contain duplicates")
        if self.kind is ScriptSegmentKind.FACT and not self.claim_ids:
            raise ValueError("fact segments must reference at least one claim")

    def to_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "kind": self.kind.value,
            "text": self.text,
            "claim_ids": list(self.claim_ids),
        }


@dataclass(frozen=True, slots=True)
class ScriptDocument:
    product_id: str
    research_digest: str
    language: str
    title: str
    segments: tuple[ScriptSegment, ...]
    generator: str
    request_digest: str
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.product_id, "product_id")
        _require_digest(self.research_digest, "research_digest")
        _require_text(self.language, "language")
        _require_text(self.title, "title")
        _require_text(self.generator, "generator")
        _require_digest(self.request_digest, "request_digest")
        _require_aware(self.created_at, "created_at")
        if not self.segments:
            raise ValueError("script must contain at least one segment")
        segment_ids = tuple(segment.segment_id for segment in self.segments)
        if len(set(segment_ids)) != len(segment_ids):
            raise ValueError("script segment IDs must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCRIPT_SCHEMA_VERSION,
            "product_id": self.product_id,
            "research_digest": self.research_digest,
            "language": self.language,
            "title": self.title,
            "segments": [segment.to_dict() for segment in self.segments],
            "generator": self.generator,
            "request_digest": self.request_digest,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.to_dict()))

    @property
    def narration_text(self) -> str:
        return "\n\n".join(segment.text for segment in self.segments)


@dataclass(frozen=True, slots=True)
class DisclosureBundle:
    locale: str
    network: str
    spoken: str
    description: str

    def __post_init__(self) -> None:
        for field_name in ("locale", "network", "spoken", "description"):
            _require_text(str(getattr(self, field_name)), field_name)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    title: str
    description: str
    tags: tuple[str, ...]
    affiliate_url: str
    disclosure: str

    def __post_init__(self) -> None:
        _require_text(self.title, "title")
        _require_text(self.description, "description")
        _require_text(self.affiliate_url, "affiliate_url")
        parsed_url = urlsplit(self.affiliate_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("affiliate_url must be an absolute HTTP(S) URL")
        _require_text(self.disclosure, "disclosure")
        normalized_tags = tuple(tag.strip() for tag in self.tags)
        if normalized_tags != self.tags:
            raise ValueError("tags must be pre-trimmed")
        if any(not tag for tag in normalized_tags):
            raise ValueError("tags must not contain empty values")
        if len({tag.casefold() for tag in normalized_tags}) != len(normalized_tags):
            raise ValueError("tags must not contain duplicates")

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "affiliate_url": self.affiliate_url,
            "disclosure": self.disclosure,
        }


@dataclass(frozen=True, slots=True)
class ThumbnailBrief:
    headline: str
    visual_direction: str
    claim_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.headline, "headline")
        _require_text(self.visual_direction, "visual_direction")
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("thumbnail claim_ids must not contain duplicates")

    def to_dict(self) -> dict[str, object]:
        return {
            "headline": self.headline,
            "visual_direction": self.visual_direction,
            "claim_ids": list(self.claim_ids),
        }


@dataclass(frozen=True, slots=True)
class AdapterExecutionPlan:
    adapter: str
    action: str
    input_digest: str
    side_effecting: bool
    required_environment: tuple[str, ...] = ()
    parameters: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_text(self.adapter, "adapter")
        _require_text(self.action, "action")
        _require_digest(self.input_digest, "input_digest")
        if len(set(self.required_environment)) != len(self.required_environment):
            raise ValueError("required_environment must not contain duplicates")
        canonical_json(dict(self.parameters or {}))

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "action": self.action,
            "input_digest": self.input_digest,
            "side_effecting": self.side_effecting,
            "required_environment": list(self.required_environment),
            "parameters": dict(self.parameters or {}),
        }


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    logical_name: str
    kind: ArtifactKind
    path: str
    media_type: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        _require_text(self.logical_name, "logical_name")
        _require_safe_relative_path(self.path)
        _require_text(self.media_type, "media_type")
        _require_digest(self.sha256, "sha256")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "logical_name": self.logical_name,
            "kind": self.kind.value,
            "path": self.path,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class ProductionPackage:
    product_id: str
    approval_event_id: int
    research_digest: str
    script: ScriptDocument
    metadata: VideoMetadata
    thumbnail: ThumbnailBrief
    adapter_plans: tuple[AdapterExecutionPlan, ...]
    artifacts: tuple[ArtifactRecord, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.product_id, "product_id")
        if self.approval_event_id <= 0:
            raise ValueError("approval_event_id must be positive")
        _require_digest(self.research_digest, "research_digest")
        _require_aware(self.created_at, "created_at")
        if self.script.product_id != self.product_id:
            raise ValueError("script belongs to a different product")
        if self.script.research_digest != self.research_digest:
            raise ValueError("script research digest differs from production package")
        if not self.adapter_plans:
            raise ValueError("production package must contain at least one adapter plan")
        logical_names = tuple(artifact.logical_name for artifact in self.artifacts)
        if len(set(logical_names)) != len(logical_names):
            raise ValueError("artifact logical names must be unique")
        paths = tuple(artifact.path for artifact in self.artifacts)
        if len(set(paths)) != len(paths):
            raise ValueError("artifact paths must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PRODUCTION_PACKAGE_SCHEMA_VERSION,
            "product_id": self.product_id,
            "approval_event_id": self.approval_event_id,
            "research_digest": self.research_digest,
            "script": self.script.to_dict(),
            "metadata": self.metadata.to_dict(),
            "thumbnail": self.thumbnail.to_dict(),
            "adapter_plans": [plan.to_dict() for plan in self.adapter_plans],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.to_dict()))


@dataclass(frozen=True, slots=True)
class ProductionSignoff:
    product_id: str
    package_digest: str
    actor: str
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.product_id, "product_id")
        _require_digest(self.package_digest, "package_digest")
        _require_text(self.actor, "actor")
        _require_text(self.reason, "reason")
        _require_aware(self.created_at, "created_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PRODUCTION_SIGNOFF_SCHEMA_VERSION,
            "product_id": self.product_id,
            "package_digest": self.package_digest,
            "actor": self.actor,
            "reason": self.reason,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PublishCheck:
    code: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PublishDryRun:
    product_id: str
    platform: str
    package_digest: str
    ready_for_live_adapter: bool
    checks: tuple[PublishCheck, ...]
    plan: AdapterExecutionPlan

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(check.message for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PUBLISH_PLAN_SCHEMA_VERSION,
            "product_id": self.product_id,
            "platform": self.platform,
            "package_digest": self.package_digest,
            "ready_for_live_adapter": self.ready_for_live_adapter,
            "checks": [check.to_dict() for check in self.checks],
            "failures": list(self.failures),
            "plan": self.plan.to_dict(),
        }
