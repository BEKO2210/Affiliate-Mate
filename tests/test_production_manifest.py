from __future__ import annotations

from datetime import UTC, datetime

import pytest

from affiliate_mate.disclosures import disclosure_template
from affiliate_mate.production_adapters import DryRunYouTubePublisher
from affiliate_mate.production_manifest import (
    artifact_from_path,
    build_production_package,
    build_publish_dry_run,
    sign_production_package,
    verify_signoff,
)
from affiliate_mate.production_models import (
    AdapterExecutionPlan,
    ArtifactKind,
    ArtifactRecord,
    ScriptSegmentKind,
)
from affiliate_mate.production_planner import (
    build_dry_run_adapter_plans,
    build_thumbnail_brief,
    build_video_metadata,
)
from affiliate_mate.script_compiler import (
    StrictTemplateScriptGenerator,
    build_script_request,
    generate_and_validate_script,
)

from .production_helpers import build_approved_store


def _package(tmp_path, *, with_artifacts: bool):
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    disclosure = disclosure_template(locale="en-US")
    request = build_script_request(
        store,
        authorization,
        working_title="Example Product",
        language="en",
        disclosure=disclosure,
    )
    script = generate_and_validate_script(
        store,
        authorization,
        request,
        StrictTemplateScriptGenerator(),
    )
    metadata = build_video_metadata(
        product_title="Example Product",
        affiliate_url="https://example.invalid/affiliate",
        disclosure=disclosure,
        tags=("example", "review"),
    )
    factual_claim_ids = tuple(
        claim_id
        for segment in script.segments
        if segment.kind is ScriptSegmentKind.FACT
        for claim_id in segment.claim_ids
    )
    thumbnail = build_thumbnail_brief(
        product_title="Example Product",
        claim_ids=factual_claim_ids,
    )
    artifacts = ()
    if with_artifacts:
        payloads = {
            ArtifactKind.SCRIPT: ("script", "script.json", "application/json", b"{}"),
            ArtifactKind.NARRATION: ("narration", "voice.wav", "audio/wav", b"voice"),
            ArtifactKind.VIDEO: ("video", "video.mp4", "video/mp4", b"video"),
            ArtifactKind.THUMBNAIL: ("thumbnail", "thumb.png", "image/png", b"thumb"),
            ArtifactKind.METADATA: ("metadata", "metadata.json", "application/json", b"{}"),
        }
        records = []
        for kind, (logical_name, path, media_type, data) in payloads.items():
            source = tmp_path / path
            source.write_bytes(data)
            records.append(
                artifact_from_path(
                    source,
                    logical_name=logical_name,
                    kind=kind,
                    media_type=media_type,
                )
            )
        artifacts = tuple(records)
    package = build_production_package(
        store,
        authorization,
        script=script,
        metadata=metadata,
        thumbnail=thumbnail,
        adapter_plans=build_dry_run_adapter_plans(script, thumbnail),
        artifacts=artifacts,
        created_at=datetime(2026, 8, 25, 3, 0, tzinfo=UTC),
    )
    return store, authorization, package


def test_package_signoff_is_bound_to_exact_digest(tmp_path) -> None:
    store, _authorization, package = _package(tmp_path, with_artifacts=False)
    signoff = sign_production_package(
        package,
        actor="editor",
        reason="Final package checked.",
        created_at=datetime(2026, 8, 25, 3, 5, tzinfo=UTC),
    )
    assert verify_signoff(package, signoff) is True
    store.close()


def test_publish_dry_run_requires_rendered_artifacts(tmp_path) -> None:
    store, authorization, package = _package(tmp_path, with_artifacts=False)
    signoff = sign_production_package(package, actor="editor", reason="Checked.")
    report = build_publish_dry_run(
        store,
        authorization,
        package,
        signoff,
        DryRunYouTubePublisher(),
        artifact_root=tmp_path,
    )
    assert report.ready_for_live_adapter is False
    assert any(check.code == "required_artifacts" and not check.passed for check in report.checks)
    store.close()


def test_publish_dry_run_can_validate_complete_package(tmp_path) -> None:
    store, authorization, package = _package(tmp_path, with_artifacts=True)
    signoff = sign_production_package(package, actor="editor", reason="Checked.")
    report = build_publish_dry_run(
        store,
        authorization,
        package,
        signoff,
        DryRunYouTubePublisher(),
        artifact_root=tmp_path,
    )
    assert report.ready_for_live_adapter is True
    assert all(check.passed for check in report.checks)
    assert report.plan.side_effecting is False
    store.close()


def test_missing_signoff_blocks_publish(tmp_path) -> None:
    store, authorization, package = _package(tmp_path, with_artifacts=True)
    report = build_publish_dry_run(
        store,
        authorization,
        package,
        None,
        DryRunYouTubePublisher(),
        artifact_root=tmp_path,
    )
    assert report.ready_for_live_adapter is False
    assert any("Missing or stale" in failure for failure in report.failures)
    store.close()


def test_artifact_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError, match="safe relative"):
        ArtifactRecord(
            logical_name="video",
            kind=ArtifactKind.VIDEO,
            path="../video.mp4",
            media_type="video/mp4",
            sha256="0" * 64,
            size_bytes=1,
        )


def test_publish_dry_run_rejects_side_effecting_adapter(tmp_path) -> None:
    class UnsafePublisher:
        name = "unsafe"

        def plan(self, metadata, *, package_digest):
            return AdapterExecutionPlan(
                adapter=self.name,
                action="publish",
                input_digest=package_digest,
                side_effecting=True,
            )

    store, authorization, package = _package(tmp_path, with_artifacts=True)
    signoff = sign_production_package(package, actor="editor", reason="Checked.")
    with pytest.raises(ValueError, match="must not be side-effecting"):
        build_publish_dry_run(
            store,
            authorization,
            package,
            signoff,
            UnsafePublisher(),
        )
    store.close()


def test_artifact_tampering_blocks_publish(tmp_path) -> None:
    store, authorization, package = _package(tmp_path, with_artifacts=True)
    signoff = sign_production_package(package, actor="editor", reason="Checked.")
    (tmp_path / "video.mp4").write_bytes(b"tampered")
    report = build_publish_dry_run(
        store,
        authorization,
        package,
        signoff,
        DryRunYouTubePublisher(),
        artifact_root=tmp_path,
    )
    assert report.ready_for_live_adapter is False
    assert any(check.code == "artifact_integrity" and not check.passed for check in report.checks)
    store.close()


def test_invalid_affiliate_url_is_rejected() -> None:
    disclosure = disclosure_template(locale="en-US")
    with pytest.raises(ValueError, match="absolute HTTP"):
        build_video_metadata(
            product_title="Example",
            affiliate_url="javascript:alert(1)",
            disclosure=disclosure,
        )
