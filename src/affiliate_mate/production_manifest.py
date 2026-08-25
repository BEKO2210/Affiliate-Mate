"""Content-addressed production packages, signoff, and fail-closed publish dry-runs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .production_adapters import PublisherAdapter
from .production_models import (
    AdapterExecutionPlan,
    ArtifactKind,
    ArtifactRecord,
    ProductionAuthorization,
    ProductionPackage,
    ProductionSignoff,
    PublishCheck,
    PublishDryRun,
    ScriptDocument,
    ThumbnailBrief,
    VideoMetadata,
    sha256_bytes,
)
from .production_policy import (
    ProductionAuthorizationError,
    ScriptGroundingError,
    assert_authorization_current,
    validate_script_grounding,
)
from .research_store import ResearchWorkspaceStore

REQUIRED_LIVE_ARTIFACTS = frozenset(
    {
        ArtifactKind.SCRIPT,
        ArtifactKind.NARRATION,
        ArtifactKind.VIDEO,
        ArtifactKind.THUMBNAIL,
        ArtifactKind.METADATA,
    }
)


def artifact_from_path(
    path: str | Path,
    *,
    logical_name: str,
    kind: ArtifactKind,
    media_type: str,
    root: str | Path | None = None,
) -> ArtifactRecord:
    source = Path(path)
    data = source.read_bytes()
    if root is None:
        relative = source.name
    else:
        relative = source.resolve().relative_to(Path(root).resolve()).as_posix()
    return ArtifactRecord(
        logical_name=logical_name,
        kind=kind,
        path=relative,
        media_type=media_type,
        sha256=sha256_bytes(data),
        size_bytes=len(data),
    )


def verify_artifact_record(record: ArtifactRecord, *, root: str | Path) -> bool:
    source = Path(root) / record.path
    try:
        data = source.read_bytes()
    except OSError:
        return False
    return len(data) == record.size_bytes and sha256_bytes(data) == record.sha256


def build_production_package(
    store: ResearchWorkspaceStore,
    authorization: ProductionAuthorization,
    *,
    script: ScriptDocument,
    metadata: VideoMetadata,
    thumbnail: ThumbnailBrief,
    adapter_plans: tuple[AdapterExecutionPlan, ...],
    artifacts: tuple[ArtifactRecord, ...] = (),
    created_at: datetime | None = None,
) -> ProductionPackage:
    """Build a package only while the approved research capability is current."""

    assert_authorization_current(store, authorization)
    validate_script_grounding(store, authorization, script)
    referenced_claim_ids = {
        claim_id for segment in script.segments for claim_id in segment.claim_ids
    }
    if not set(thumbnail.claim_ids).issubset(referenced_claim_ids):
        raise ValueError("thumbnail references claim IDs that are not present in the script")
    if metadata.disclosure not in metadata.description:
        raise ValueError("metadata description must contain the configured affiliate disclosure")
    moment = datetime.now(UTC) if created_at is None else created_at
    return ProductionPackage(
        product_id=authorization.product_id,
        approval_event_id=authorization.approval_event_id,
        research_digest=authorization.research_digest,
        script=script,
        metadata=metadata,
        thumbnail=thumbnail,
        adapter_plans=adapter_plans,
        artifacts=artifacts,
        created_at=moment,
    )


def sign_production_package(
    package: ProductionPackage,
    *,
    actor: str,
    reason: str,
    created_at: datetime | None = None,
) -> ProductionSignoff:
    moment = datetime.now(UTC) if created_at is None else created_at
    return ProductionSignoff(
        product_id=package.product_id,
        package_digest=package.digest,
        actor=actor,
        reason=reason,
        created_at=moment,
    )


def verify_signoff(package: ProductionPackage, signoff: ProductionSignoff) -> bool:
    return signoff.product_id == package.product_id and signoff.package_digest == package.digest


def build_publish_dry_run(
    store: ResearchWorkspaceStore,
    authorization: ProductionAuthorization,
    package: ProductionPackage,
    signoff: ProductionSignoff | None,
    publisher: PublisherAdapter,
    *,
    artifact_root: str | Path | None = None,
    require_rendered_artifacts: bool = True,
) -> PublishDryRun:
    """Return readiness without invoking a network publisher."""

    checks: list[PublishCheck] = []
    try:
        assert_authorization_current(store, authorization)
    except ProductionAuthorizationError as exc:
        checks.append(PublishCheck("research_authorization", False, str(exc)))
    else:
        checks.append(
            PublishCheck(
                "research_authorization",
                True,
                "Research approval and snapshot are current.",
            )
        )

    lineage_ok = (
        package.product_id == authorization.product_id
        and package.approval_event_id == authorization.approval_event_id
        and package.research_digest == authorization.research_digest
    )
    checks.append(
        PublishCheck(
            "package_lineage",
            lineage_ok,
            (
                "Production package matches the approved research lineage."
                if lineage_ok
                else "Production package does not match the approved research lineage."
            ),
        )
    )

    try:
        validate_script_grounding(store, authorization, package.script)
    except (ProductionAuthorizationError, ScriptGroundingError) as exc:
        checks.append(PublishCheck("script_grounding", False, str(exc)))
    else:
        checks.append(
            PublishCheck(
                "script_grounding",
                True,
                "Structured factual script segments reference current supported claims.",
            )
        )

    signoff_ok = signoff is not None and verify_signoff(package, signoff)
    checks.append(
        PublishCheck(
            "production_signoff",
            signoff_ok,
            (
                "Human production signoff matches the exact package digest."
                if signoff_ok
                else "Missing or stale human production signoff."
            ),
        )
    )

    disclosure_ok = (
        bool(package.metadata.disclosure.strip())
        and package.metadata.disclosure in package.metadata.description
    )
    checks.append(
        PublishCheck(
            "affiliate_disclosure",
            disclosure_ok,
            (
                "Affiliate disclosure is present in metadata."
                if disclosure_ok
                else "Affiliate disclosure is missing from metadata description."
            ),
        )
    )

    present_kinds = {artifact.kind for artifact in package.artifacts}
    missing = sorted(kind.value for kind in REQUIRED_LIVE_ARTIFACTS - present_kinds)
    records_present = not missing
    checks.append(
        PublishCheck(
            "required_artifacts",
            records_present or not require_rendered_artifacts,
            (
                "All required live-publish artifact records are present."
                if records_present
                else "Missing required artifacts: " + ", ".join(missing)
            ),
        )
    )

    if require_rendered_artifacts:
        verified = (
            artifact_root is not None
            and records_present
            and all(verify_artifact_record(record, root=artifact_root) for record in package.artifacts)
        )
        checks.append(
            PublishCheck(
                "artifact_integrity",
                verified,
                (
                    "Artifact bytes match every content-addressed manifest record."
                    if verified
                    else "Artifact bytes were not verified or differ from the manifest."
                ),
            )
        )

    ready = all(check.passed for check in checks)
    plan = publisher.plan(package.metadata, package_digest=package.digest)
    if plan.side_effecting:
        raise ValueError("publish dry-run adapter must not be side-effecting")
    return PublishDryRun(
        product_id=package.product_id,
        platform="youtube",
        package_digest=package.digest,
        ready_for_live_adapter=ready,
        checks=tuple(checks),
        plan=plan,
    )
