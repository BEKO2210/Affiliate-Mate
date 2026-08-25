"""Credential-free golden acceptance path spanning the v1 trust chain."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .analysis import analyze_candidate
from .decision import EvaluationPolicy
from .disclosures import disclosure_template
from .io import load_candidate_inputs_csv
from .learning_capture import capture_forecast
from .learning_models import OutcomeEvent, OutcomeKind, ScoringPolicyVersion
from .learning_reports import PerformancePolicy, build_performance_report
from .learning_store import LearningStore
from .production_adapters import DryRunYouTubePublisher
from .production_manifest import (
    artifact_from_path,
    build_production_package,
    build_publish_dry_run,
    sign_production_package,
)
from .production_models import ArtifactKind, ScriptSegmentKind
from .production_planner import (
    build_dry_run_adapter_plans,
    build_thumbnail_brief,
    build_video_metadata,
)
from .production_policy import require_production_authorization
from .research_models import (
    ApprovalState,
    ClaimEvidenceLink,
    ClaimRisk,
    ClaimState,
    EvidenceStance,
    ResearchClaim,
    ResearchNote,
    ResearchSource,
    SourceKind,
)
from .research_policy import evaluate_approval_guard, transition_product_approval
from .research_store import ResearchWorkspaceStore
from .script_compiler import (
    StrictTemplateScriptGenerator,
    build_script_request,
    generate_and_validate_script,
)
from .workspace import create_demo_workspace


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _build_research(store: ResearchWorkspaceStore, *, product_id: str, at: datetime) -> None:
    store.add_source(
        ResearchSource(
            source_id="acceptance-source-manufacturer",
            product_id=product_id,
            kind=SourceKind.MANUFACTURER,
            title="Manufacturer specification",
            locator="https://example.invalid/manufacturer-spec",
            publisher="Example Manufacturer",
            retrieved_at=at,
        )
    )
    store.add_source(
        ResearchSource(
            source_id="acceptance-source-editorial",
            product_id=product_id,
            kind=SourceKind.EDITORIAL,
            title="Independent reference",
            locator="https://example.invalid/independent-reference",
            publisher="Independent Publisher",
            retrieved_at=at,
        )
    )
    store.add_claim(
        ResearchClaim(
            claim_id="acceptance-claim",
            product_id=product_id,
            text="The demo product is represented by the supplied synthetic catalog record.",
            risk=ClaimRisk.MEDIUM,
            created_at=at,
            created_by="acceptance-editor",
        )
    )
    store.add_evidence_link(
        ClaimEvidenceLink(
            claim_id="acceptance-claim",
            source_id="acceptance-source-manufacturer",
            stance=EvidenceStance.SUPPORTS,
            locator="Synthetic specification record",
            quote=None,
            created_at=at,
            created_by="acceptance-editor",
        )
    )
    store.transition_claim(
        "acceptance-claim",
        ClaimState.SUPPORTED,
        actor="acceptance-reviewer",
        reason="Golden acceptance verified the cited synthetic source.",
        expected_state=ClaimState.DRAFT,
        created_at=at,
    )
    store.add_note(
        ResearchNote(
            note_id="acceptance-note",
            product_id=product_id,
            title="Acceptance evidence note",
            body="The claim is backed by the synthetic manufacturer record used by this offline test.",
            created_at=at,
            created_by="acceptance-editor",
        ),
        claim_ids=("acceptance-claim",),
    )
    transition_product_approval(
        store,
        product_id,
        ApprovalState.IN_REVIEW,
        actor="acceptance-reviewer",
        reason="Golden acceptance review started.",
        expected_state=ApprovalState.DRAFT,
    )
    transition_product_approval(
        store,
        product_id,
        ApprovalState.APPROVED,
        actor="acceptance-reviewer",
        reason="Golden acceptance research approved.",
        expected_state=ApprovalState.IN_REVIEW,
    )


def _artifact_records(
    root: Path,
    *,
    script: object,
    narration: str,
    metadata: object,
) -> tuple:
    root.mkdir(parents=True, exist_ok=True)
    script_path = root / "script.json"
    narration_path = root / "narration.txt"
    video_path = root / "video.mp4"
    thumbnail_path = root / "thumbnail.png"
    metadata_path = root / "metadata.json"
    _write_json(script_path, script)
    narration_path.write_text(narration, encoding="utf-8")
    video_path.write_bytes(b"affiliate-mate-v1-golden-video")
    thumbnail_path.write_bytes(b"affiliate-mate-v1-golden-thumbnail")
    _write_json(metadata_path, metadata)
    specs = (
        (script_path, "script", ArtifactKind.SCRIPT, "application/json"),
        (narration_path, "narration", ArtifactKind.NARRATION, "text/plain"),
        (video_path, "video", ArtifactKind.VIDEO, "video/mp4"),
        (thumbnail_path, "thumbnail", ArtifactKind.THUMBNAIL, "image/png"),
        (metadata_path, "metadata", ArtifactKind.METADATA, "application/json"),
    )
    return tuple(
        artifact_from_path(
            path,
            logical_name=logical_name,
            kind=kind,
            media_type=media_type,
            root=root,
        )
        for path, logical_name, kind, media_type in specs
    )


def _outcome(
    *,
    forecast,
    kind: OutcomeKind,
    source_event_id: str,
    effective_at: datetime,
    observed_at: datetime,
    count: int = 0,
    amount_minor: int = 0,
) -> OutcomeEvent:
    return OutcomeEvent(
        source="v1-golden-acceptance",
        source_event_id=source_event_id,
        kind=kind,
        product_id=forecast.product_id,
        marketplace=forecast.marketplace,
        content_id=forecast.content_id,
        package_digest=forecast.package_digest,
        effective_at=effective_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        window_start=forecast.predicted_at,
        window_end=effective_at,
        count=count,
        amount_minor=amount_minor,
        currency=forecast.currency
        if kind in {OutcomeKind.COMMISSION, OutcomeKind.REFUND, OutcomeKind.REVERSAL}
        else None,
    )


def run_golden_acceptance(root: str | Path) -> dict[str, object]:
    """Run the complete offline v1 trust chain and return a machine-readable report."""

    base = Path(root).expanduser().resolve()
    workspace = create_demo_workspace(base)
    candidate_inputs = load_candidate_inputs_csv(workspace.data_dir / "products.csv")
    analyses = [
        analyze_candidate(item.candidate, provided_fields=item.provided_fields)
        for item in candidate_inputs
    ]
    accepted = [result for result in analyses if result.decision.accepted]
    if not accepted:
        raise RuntimeError("golden acceptance found no accepted synthetic candidate")
    analysis = accepted[0]
    product_id = analysis.candidate.product_id
    fixed = datetime(2026, 1, 1, tzinfo=UTC)

    research_db = base / ".affiliate-mate" / "acceptance-research.sqlite3"
    with ResearchWorkspaceStore(research_db) as research_store:
        research_store.initialize()
        _build_research(research_store, product_id=product_id, at=fixed)
        guard = evaluate_approval_guard(research_store, product_id)
        if not guard.passed:
            raise RuntimeError(f"golden research approval failed: {guard.failures}")
        authorization = require_production_authorization(research_store, product_id)
        disclosure = disclosure_template(locale="en-US", network="acceptance")
        request = build_script_request(
            research_store,
            authorization,
            working_title=analysis.candidate.title,
            language="en",
            disclosure=disclosure,
        )
        script = generate_and_validate_script(
            research_store,
            authorization,
            request,
            StrictTemplateScriptGenerator(),
        )
        factual_claim_ids = tuple(
            claim_id
            for segment in script.segments
            if segment.kind is ScriptSegmentKind.FACT
            for claim_id in segment.claim_ids
        )
        thumbnail = build_thumbnail_brief(
            product_title=analysis.candidate.title,
            claim_ids=factual_claim_ids,
        )
        metadata = build_video_metadata(
            product_title=analysis.candidate.title,
            affiliate_url="https://example.invalid/affiliate",
            disclosure=disclosure,
            description_body="Credential-free golden acceptance output.",
            tags=("affiliate-mate", "acceptance"),
        )
        artifact_root = workspace.artifacts_dir / "golden"
        artifacts = _artifact_records(
            artifact_root,
            script=script.to_dict(),
            narration=script.narration_text,
            metadata=metadata.to_dict(),
        )
        package = build_production_package(
            research_store,
            authorization,
            script=script,
            metadata=metadata,
            thumbnail=thumbnail,
            adapter_plans=build_dry_run_adapter_plans(script, thumbnail),
            artifacts=artifacts,
            created_at=fixed + timedelta(hours=1),
        )
        signoff = sign_production_package(
            package,
            actor="acceptance-reviewer",
            reason="Golden acceptance production package reviewed.",
            created_at=fixed + timedelta(hours=2),
        )
        publish = build_publish_dry_run(
            research_store,
            authorization,
            package,
            signoff,
            DryRunYouTubePublisher(),
            artifact_root=artifact_root,
        )
        if not publish.ready_for_live_adapter:
            raise RuntimeError(f"golden publish dry-run failed: {publish.failures}")

    policy = EvaluationPolicy()
    policy_version = ScoringPolicyVersion(
        version="v1-golden-baseline",
        policy_payload=policy.to_dict(),
        created_at=fixed,
        notes="Credential-free v1 acceptance policy.",
    )
    predicted_at = fixed + timedelta(days=1)
    learning_db = base / ".affiliate-mate" / "acceptance-learning.sqlite3"
    with LearningStore(learning_db) as learning_store:
        learning_store.register_policy(policy_version)
        forecast = capture_forecast(
            analysis,
            predicted_at=predicted_at,
            horizon_days=2,
            content_id="v1-golden-video",
            category="synthetic-demo",
            policy_version=policy_version,
            evaluation_policy=policy,
            package_digest=package.digest,
        )
        if not learning_store.add_forecast(forecast):
            raise RuntimeError("golden forecast was not inserted")
        # Outcome selection uses a half-open forecast window: [predicted_at, horizon_end).
        # Keep realized events strictly inside that window rather than on its exclusive endpoint.
        effective_at = predicted_at + timedelta(days=1)
        observed_at = effective_at + timedelta(days=1)
        learning_store.add_outcomes(
            (
                _outcome(
                    forecast=forecast,
                    kind=OutcomeKind.VIDEO_VIEW,
                    source_event_id="views",
                    effective_at=effective_at,
                    observed_at=observed_at,
                    count=1000,
                ),
                _outcome(
                    forecast=forecast,
                    kind=OutcomeKind.AFFILIATE_CLICK,
                    source_event_id="clicks",
                    effective_at=effective_at,
                    observed_at=observed_at,
                    count=50,
                ),
                _outcome(
                    forecast=forecast,
                    kind=OutcomeKind.ORDER,
                    source_event_id="orders",
                    effective_at=effective_at,
                    observed_at=observed_at,
                    count=4,
                ),
                _outcome(
                    forecast=forecast,
                    kind=OutcomeKind.COMMISSION,
                    source_event_id="commission",
                    effective_at=effective_at,
                    observed_at=observed_at,
                    amount_minor=800,
                ),
            )
        )
        performance = build_performance_report(
            learning_store,
            forecast,
            evaluated_at=effective_at + timedelta(days=3),
            policy=PerformancePolicy(reporting_lag_days=1),
        )
        if not performance.sample_eligible:
            raise RuntimeError(
                "golden learning report is not eligible: "
                + ", ".join(performance.missing_kinds)
            )

    return {
        "schema_version": "affiliate-mate.golden-acceptance.v1",
        "passed": True,
        "credential_free": True,
        "network_calls": 0,
        "candidate": {
            "product_id": product_id,
            "accepted": analysis.decision.accepted,
            "opportunity_score": analysis.decision.score.opportunity_score,
        },
        "research": {
            "approved": guard.passed,
            "research_digest": authorization.research_digest,
        },
        "production": {
            "package_digest": package.digest,
            "signoff_bound": signoff.package_digest == package.digest,
            "publish_dry_run_ready": publish.ready_for_live_adapter,
            "side_effecting": publish.plan.side_effecting,
        },
        "learning": {
            "forecast_id": forecast.forecast_id,
            "sample_eligible": performance.sample_eligible,
            "realized_value_per_1000_views": performance.totals.realized_value_per_1000_views,
        },
    }
