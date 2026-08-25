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
from affiliate_mate.research_store import (
    InvalidResearchTransitionError,
    ResearchConflictError,
    ResearchWorkspaceStore,
)

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=UTC)


def source(source_id: str, product_id: str = "p1", publisher: str = "Maker") -> ResearchSource:
    return ResearchSource(
        source_id=source_id,
        product_id=product_id,
        kind=SourceKind.MANUFACTURER,
        title=f"Source {source_id}",
        locator=f"https://example.test/{source_id}",
        publisher=publisher,
        retrieved_at=NOW,
    )


def claim(claim_id: str, product_id: str = "p1") -> ResearchClaim:
    return ResearchClaim(
        claim_id=claim_id,
        product_id=product_id,
        text="Battery runtime is up to 10 hours under the documented test profile.",
        risk=ClaimRisk.MEDIUM,
        created_at=NOW,
        created_by="tester",
    )


def test_claim_creation_is_audited_and_idempotent(tmp_path) -> None:
    database = tmp_path / "research.sqlite3"
    with ResearchWorkspaceStore(database) as store:
        assert store.add_claim(claim("c1")) is True
        assert store.add_claim(claim("c1")) is False
        assert store.current_claim_state("c1") is ClaimState.DRAFT
        events = store.list_claim_state_events("c1")
    assert len(events) == 1
    assert events[0].state is ClaimState.DRAFT


def test_evidence_link_cannot_cross_product_boundary(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        store.add_claim(claim("c1", "p1"))
        store.add_source(source("s1", "p2"))
        with pytest.raises(ValueError, match="different products"):
            store.add_evidence_link(
                ClaimEvidenceLink(
                    claim_id="c1",
                    source_id="s1",
                    stance=EvidenceStance.SUPPORTS,
                    locator="section 2",
                    quote=None,
                    created_at=NOW,
                    created_by="tester",
                )
            )


def test_claim_transition_uses_optimistic_state_check(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        store.add_claim(claim("c1"))
        event = store.transition_claim(
            "c1",
            ClaimState.SUPPORTED,
            actor="reviewer",
            reason="Source verified.",
            expected_state=ClaimState.DRAFT,
            created_at=NOW,
        )
        assert event.state is ClaimState.SUPPORTED
        with pytest.raises(ResearchConflictError):
            store.transition_claim(
                "c1",
                ClaimState.DISPUTED,
                actor="reviewer",
                reason="Stale client expected draft.",
                expected_state=ClaimState.DRAFT,
                created_at=NOW,
            )


def test_rejected_claim_cannot_jump_directly_to_supported(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        store.add_claim(claim("c1"))
        store.transition_claim(
            "c1",
            ClaimState.REJECTED,
            actor="reviewer",
            reason="Claim is not publishable.",
            created_at=NOW,
        )
        with pytest.raises(InvalidResearchTransitionError):
            store.transition_claim(
                "c1",
                ClaimState.SUPPORTED,
                actor="reviewer",
                reason="Invalid shortcut.",
                created_at=NOW,
            )


def test_note_references_must_share_product(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        store.add_claim(claim("c-other", "p2"))
        note = ResearchNote(
            note_id="n1",
            product_id="p1",
            title="Draft",
            body="Research note.",
            created_at=NOW,
            created_by="tester",
        )
        with pytest.raises(ValueError, match="another product"):
            store.add_note(note, claim_ids=["c-other"])


def test_approval_history_is_append_only_and_reopenable(tmp_path) -> None:
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        assert store.current_approval_state("p1") is ApprovalState.DRAFT
        store.transition_approval(
            "p1",
            ApprovalState.IN_REVIEW,
            actor="alice",
            reason="Ready for review.",
            expected_state=ApprovalState.DRAFT,
            created_at=NOW,
        )
        store.transition_approval(
            "p1",
            ApprovalState.APPROVED,
            actor="bob",
            reason="Research accepted.",
            expected_state=ApprovalState.IN_REVIEW,
            created_at=NOW,
        )
        store.transition_approval(
            "p1",
            ApprovalState.IN_REVIEW,
            actor="bob",
            reason="New evidence requires review.",
            expected_state=ApprovalState.APPROVED,
            created_at=NOW,
        )
        events = store.list_approval_events("p1")
    assert [event.state for event in events] == [
        ApprovalState.IN_REVIEW,
        ApprovalState.APPROVED,
        ApprovalState.IN_REVIEW,
    ]
