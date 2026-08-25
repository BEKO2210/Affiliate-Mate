from datetime import UTC, datetime

from affiliate_mate.research_models import (
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
from affiliate_mate.research_policy import evaluate_approval_guard, transition_product_approval
from affiliate_mate.research_snapshot import research_snapshot_digest
from affiliate_mate.research_store import ResearchWorkspaceStore

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=UTC)


def prepare_complete_package(store: ResearchWorkspaceStore) -> None:
    for source_id, publisher in (("s1", "Publisher A"), ("s2", "Publisher B")):
        store.add_source(
            ResearchSource(
                source_id=source_id,
                product_id="p1",
                kind=SourceKind.OFFICIAL,
                title=source_id,
                locator=f"https://example.test/{source_id}",
                publisher=publisher,
                retrieved_at=NOW,
            )
        )
    store.add_claim(
        ResearchClaim(
            claim_id="c1",
            product_id="p1",
            text="The cited feature is documented.",
            risk=ClaimRisk.MEDIUM,
            created_at=NOW,
            created_by="author",
        )
    )
    store.add_evidence_link(
        ClaimEvidenceLink(
            claim_id="c1",
            source_id="s1",
            stance=EvidenceStance.SUPPORTS,
            locator="section 1",
            quote=None,
            created_at=NOW,
            created_by="author",
        )
    )
    store.transition_claim(
        "c1",
        ClaimState.SUPPORTED,
        actor="reviewer",
        reason="Evidence verified.",
        created_at=NOW,
    )
    store.add_note(
        ResearchNote(
            note_id="n1",
            product_id="p1",
            title="Evidence note",
            body="The supported claim is retained with its locator.",
            created_at=NOW,
            created_by="author",
        ),
        claim_ids=["c1"],
    )


def approve(store: ResearchWorkspaceStore) -> None:
    transition_product_approval(
        store,
        "p1",
        ApprovalState.IN_REVIEW,
        actor="reviewer",
        reason="Review started.",
        expected_state=ApprovalState.DRAFT,
    )
    transition_product_approval(
        store,
        "p1",
        ApprovalState.APPROVED,
        actor="reviewer",
        reason="Research package verified.",
        expected_state=ApprovalState.IN_REVIEW,
    )


def test_approved_package_is_bound_to_current_research_digest(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        prepare_complete_package(store)
        digest_before = research_snapshot_digest(store, "p1")
        approve(store)
        guard = evaluate_approval_guard(store, "p1")
    assert guard.passed is True
    assert guard.snapshot_present is True
    assert guard.snapshot_current is True
    assert guard.approved_research_digest == digest_before


def test_any_research_mutation_makes_previous_approval_stale(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        prepare_complete_package(store)
        approve(store)
        approved = evaluate_approval_guard(store, "p1")
        store.add_source(
            ResearchSource(
                source_id="s3",
                product_id="p1",
                kind=SourceKind.EDITORIAL,
                title="New evidence",
                locator="https://example.test/s3",
                publisher="Publisher C",
                retrieved_at=NOW,
            )
        )
        stale = evaluate_approval_guard(store, "p1")
    assert approved.passed is True
    assert stale.raw_state is ApprovalState.APPROVED
    assert stale.completeness.passed is True
    assert stale.snapshot_current is False
    assert stale.passed is False
    assert any("changed after approval" in failure for failure in stale.failures)


def test_claim_history_change_invalidates_approval_even_if_visible_state_returns(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        prepare_complete_package(store)
        approve(store)
        original_digest = research_snapshot_digest(store, "p1")
        store.transition_claim(
            "c1",
            ClaimState.DRAFT,
            actor="reviewer",
            reason="Reopened for checking.",
            created_at=NOW,
        )
        store.transition_claim(
            "c1",
            ClaimState.SUPPORTED,
            actor="reviewer",
            reason="Supported again.",
            created_at=NOW,
        )
        current_digest = research_snapshot_digest(store, "p1")
        guard = evaluate_approval_guard(store, "p1")
    assert current_digest != original_digest
    assert guard.completeness.passed is True
    assert guard.snapshot_current is False
    assert guard.passed is False


def test_raw_approved_event_without_snapshot_is_not_production_ready(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        prepare_complete_package(store)
        store.transition_approval(
            "p1",
            ApprovalState.IN_REVIEW,
            actor="reviewer",
            reason="Review started.",
            created_at=NOW,
        )
        store.transition_approval(
            "p1",
            ApprovalState.APPROVED,
            actor="reviewer",
            reason="Persistence primitive bypass used intentionally in test.",
            created_at=NOW,
        )
        guard = evaluate_approval_guard(store, "p1")
    assert guard.raw_state is ApprovalState.APPROVED
    assert guard.snapshot_present is False
    assert guard.passed is False
