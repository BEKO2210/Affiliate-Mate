from datetime import UTC, datetime

import pytest

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
from affiliate_mate.research_policy import (
    ResearchApprovalBlocked,
    evaluate_research_completeness,
    transition_product_approval,
)
from affiliate_mate.research_store import ResearchWorkspaceStore

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=UTC)


def add_source(store: ResearchWorkspaceStore, source_id: str, publisher: str) -> None:
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


def add_claim(
    store: ResearchWorkspaceStore,
    claim_id: str = "c1",
    risk: ClaimRisk = ClaimRisk.MEDIUM,
) -> None:
    store.add_claim(
        ResearchClaim(
            claim_id=claim_id,
            product_id="p1",
            text="The documented feature exists under the cited conditions.",
            risk=risk,
            created_at=NOW,
            created_by="author",
        )
    )


def support(store: ResearchWorkspaceStore, claim_id: str, source_id: str) -> None:
    store.add_evidence_link(
        ClaimEvidenceLink(
            claim_id=claim_id,
            source_id=source_id,
            stance=EvidenceStance.SUPPORTS,
            locator="section 1",
            quote=None,
            created_at=NOW,
            created_by="author",
        )
    )


def add_note(store: ResearchWorkspaceStore, claim_id: str = "c1") -> None:
    store.add_note(
        ResearchNote(
            note_id=f"note-{claim_id}",
            product_id="p1",
            title="Evidence note",
            body="The claim is supported by the linked primary material.",
            created_at=NOW,
            created_by="author",
        ),
        claim_ids=[claim_id],
    )


def prepare_complete_medium_claim(store: ResearchWorkspaceStore) -> None:
    add_source(store, "s1", "Publisher A")
    add_source(store, "s2", "Publisher B")
    add_claim(store)
    support(store, "c1", "s1")
    add_note(store)
    store.transition_claim(
        "c1",
        ClaimState.SUPPORTED,
        actor="reviewer",
        reason="Evidence checked.",
        created_at=NOW,
    )


def test_empty_workspace_fails_closed(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        report = evaluate_research_completeness(store, "p1")
    assert report.passed is False
    assert {check.code for check in report.checks if not check.passed} >= {
        "sources",
        "distinct_publishers",
        "active_claims",
        "notes",
    }


def test_complete_medium_claim_passes(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        prepare_complete_medium_claim(store)
        report = evaluate_research_completeness(store, "p1")
    assert report.passed is True


def test_high_risk_claim_requires_independent_support(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        add_source(store, "s1", "Publisher A")
        add_source(store, "s2", "Publisher B")
        add_claim(store, risk=ClaimRisk.HIGH)
        support(store, "c1", "s1")
        add_note(store)
        store.transition_claim(
            "c1",
            ClaimState.SUPPORTED,
            actor="reviewer",
            reason="One source checked.",
            created_at=NOW,
        )
        first = evaluate_research_completeness(store, "p1")
        support(store, "c1", "s2")
        second = evaluate_research_completeness(store, "p1")
    assert first.passed is False
    assert second.passed is True


def test_contradictory_evidence_blocks_supported_claim(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        prepare_complete_medium_claim(store)
        store.add_evidence_link(
            ClaimEvidenceLink(
                claim_id="c1",
                source_id="s2",
                stance=EvidenceStance.CONTRADICTS,
                locator="section 9",
                quote=None,
                created_at=NOW,
                created_by="reviewer",
            )
        )
        report = evaluate_research_completeness(store, "p1")
    assert report.passed is False
    assert any(check.code == "claim_contradictions:c1" and not check.passed for check in report.checks)


def test_approval_is_blocked_until_completeness_passes(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        store.transition_approval(
            "p1",
            ApprovalState.IN_REVIEW,
            actor="reviewer",
            reason="Review started.",
            created_at=NOW,
        )
        with pytest.raises(ResearchApprovalBlocked):
            transition_product_approval(
                store,
                "p1",
                ApprovalState.APPROVED,
                actor="reviewer",
                reason="Premature approval.",
                expected_state=ApprovalState.IN_REVIEW,
            )
        prepare_complete_medium_claim(store)
        event = transition_product_approval(
            store,
            "p1",
            ApprovalState.APPROVED,
            actor="reviewer",
            reason="All research gates pass.",
            expected_state=ApprovalState.IN_REVIEW,
        )
    assert event.state is ApprovalState.APPROVED


def test_rejected_claim_is_excluded_from_active_completeness(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        prepare_complete_medium_claim(store)
        add_claim(store, claim_id="c2")
        store.transition_claim(
            "c2",
            ClaimState.REJECTED,
            actor="reviewer",
            reason="Not suitable for publication.",
            created_at=NOW,
        )
        report = evaluate_research_completeness(store, "p1")
    assert report.passed is True
    assert report.rejected_claim_ids == ("c2",)
