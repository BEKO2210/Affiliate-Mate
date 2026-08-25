"""Shared fixtures for v0.6 production tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from affiliate_mate.production_models import ProductionAuthorization
from affiliate_mate.production_policy import require_production_authorization
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
from affiliate_mate.research_policy import transition_product_approval
from affiliate_mate.research_store import ResearchWorkspaceStore

NOW = datetime(2026, 8, 25, 1, 0, tzinfo=UTC)
PRODUCT_ID = "prod-1"


def build_approved_store(
    path: Path,
) -> tuple[ResearchWorkspaceStore, ProductionAuthorization]:
    store = ResearchWorkspaceStore(path)
    store.initialize()
    store.add_source(
        ResearchSource(
            source_id="source-1",
            product_id=PRODUCT_ID,
            kind=SourceKind.MANUFACTURER,
            title="Manufacturer specification",
            locator="https://example.invalid/spec",
            publisher="Manufacturer",
            retrieved_at=NOW,
        )
    )
    store.add_source(
        ResearchSource(
            source_id="source-2",
            product_id=PRODUCT_ID,
            kind=SourceKind.EDITORIAL,
            title="Independent reference",
            locator="https://example.invalid/reference",
            publisher="Independent Publisher",
            retrieved_at=NOW,
        )
    )
    store.add_claim(
        ResearchClaim(
            claim_id="claim-1",
            product_id=PRODUCT_ID,
            text="The cable is detachable.",
            risk=ClaimRisk.MEDIUM,
            created_at=NOW,
            created_by="editor",
        )
    )
    store.add_evidence_link(
        ClaimEvidenceLink(
            claim_id="claim-1",
            source_id="source-1",
            stance=EvidenceStance.SUPPORTS,
            locator="Specifications > Cable",
            quote=None,
            created_at=NOW,
            created_by="editor",
        )
    )
    store.transition_claim(
        "claim-1",
        ClaimState.SUPPORTED,
        actor="reviewer",
        reason="Checked cited specification.",
        expected_state=ClaimState.DRAFT,
        created_at=NOW,
    )
    store.add_note(
        ResearchNote(
            note_id="note-1",
            product_id=PRODUCT_ID,
            title="Cable evidence",
            body="The detachable cable statement is supported by the cited specification.",
            created_at=NOW,
            created_by="editor",
        ),
        claim_ids=("claim-1",),
    )
    transition_product_approval(
        store,
        PRODUCT_ID,
        ApprovalState.IN_REVIEW,
        actor="reviewer",
        reason="Ready for review.",
        expected_state=ApprovalState.DRAFT,
    )
    transition_product_approval(
        store,
        PRODUCT_ID,
        ApprovalState.APPROVED,
        actor="reviewer",
        reason="Research approved.",
        expected_state=ApprovalState.IN_REVIEW,
    )
    authorization = require_production_authorization(store, PRODUCT_ID)
    return store, authorization
