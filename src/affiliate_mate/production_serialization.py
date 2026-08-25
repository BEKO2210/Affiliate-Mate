"""Strict JSON deserialization for versioned production contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .production_models import (
    PRODUCTION_AUTH_SCHEMA_VERSION,
    PRODUCTION_PACKAGE_SCHEMA_VERSION,
    PRODUCTION_SIGNOFF_SCHEMA_VERSION,
    SCRIPT_SCHEMA_VERSION,
    AdapterExecutionPlan,
    ArtifactKind,
    ArtifactRecord,
    ProductionAuthorization,
    ProductionPackage,
    ProductionSignoff,
    ScriptDocument,
    ScriptSegment,
    ScriptSegmentKind,
    ThumbnailBrief,
    VideoMetadata,
)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _schema(data: dict[str, Any], expected: str) -> None:
    actual = str(data.get("schema_version", ""))
    if actual != expected:
        raise ValueError(f"unsupported schema_version {actual!r}; expected {expected!r}")


def authorization_from_dict(data: dict[str, Any]) -> ProductionAuthorization:
    _schema(data, PRODUCTION_AUTH_SCHEMA_VERSION)
    return ProductionAuthorization(
        product_id=str(data["product_id"]),
        approval_event_id=int(data["approval_event_id"]),
        research_digest=str(data["research_digest"]),
        created_at=_time(str(data["created_at"])),
    )


def script_from_dict(data: dict[str, Any]) -> ScriptDocument:
    _schema(data, SCRIPT_SCHEMA_VERSION)
    return ScriptDocument(
        product_id=str(data["product_id"]),
        research_digest=str(data["research_digest"]),
        language=str(data["language"]),
        title=str(data["title"]),
        segments=tuple(
            ScriptSegment(
                segment_id=str(item["segment_id"]),
                kind=ScriptSegmentKind(str(item["kind"])),
                text=str(item["text"]),
                claim_ids=tuple(str(value) for value in item.get("claim_ids", [])),
            )
            for item in data["segments"]
        ),
        generator=str(data["generator"]),
        request_digest=str(data["request_digest"]),
        created_at=_time(str(data["created_at"])),
    )


def package_from_dict(data: dict[str, Any]) -> ProductionPackage:
    _schema(data, PRODUCTION_PACKAGE_SCHEMA_VERSION)
    return ProductionPackage(
        product_id=str(data["product_id"]),
        approval_event_id=int(data["approval_event_id"]),
        research_digest=str(data["research_digest"]),
        script=script_from_dict(data["script"]),
        metadata=VideoMetadata(
            title=str(data["metadata"]["title"]),
            description=str(data["metadata"]["description"]),
            tags=tuple(str(value) for value in data["metadata"].get("tags", [])),
            affiliate_url=str(data["metadata"]["affiliate_url"]),
            disclosure=str(data["metadata"]["disclosure"]),
        ),
        thumbnail=ThumbnailBrief(
            headline=str(data["thumbnail"]["headline"]),
            visual_direction=str(data["thumbnail"]["visual_direction"]),
            claim_ids=tuple(str(value) for value in data["thumbnail"].get("claim_ids", [])),
        ),
        adapter_plans=tuple(
            AdapterExecutionPlan(
                adapter=str(item["adapter"]),
                action=str(item["action"]),
                input_digest=str(item["input_digest"]),
                side_effecting=bool(item["side_effecting"]),
                required_environment=tuple(
                    str(value) for value in item.get("required_environment", [])
                ),
                parameters=dict(item.get("parameters") or {}),
            )
            for item in data.get("adapter_plans", [])
        ),
        artifacts=tuple(
            ArtifactRecord(
                logical_name=str(item["logical_name"]),
                kind=ArtifactKind(str(item["kind"])),
                path=str(item["path"]),
                media_type=str(item["media_type"]),
                sha256=str(item["sha256"]),
                size_bytes=int(item["size_bytes"]),
            )
            for item in data.get("artifacts", [])
        ),
        created_at=_time(str(data["created_at"])),
    )


def signoff_from_dict(data: dict[str, Any]) -> ProductionSignoff:
    _schema(data, PRODUCTION_SIGNOFF_SCHEMA_VERSION)
    return ProductionSignoff(
        product_id=str(data["product_id"]),
        package_digest=str(data["package_digest"]),
        actor=str(data["actor"]),
        reason=str(data["reason"]),
        created_at=_time(str(data["created_at"])),
    )
