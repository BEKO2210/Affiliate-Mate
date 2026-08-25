from datetime import UTC, datetime

from affiliate_mate.analysis import analyze_candidate
from affiliate_mate.models import ProductCandidate
from affiliate_mate.research_brief import RESEARCH_BRIEF_SCHEMA_VERSION, build_research_brief
from affiliate_mate.research_models import (
    ClaimEvidenceLink,
    ClaimRisk,
    ClaimState,
    EvidenceStance,
    ResearchClaim,
    ResearchNote,
    ResearchSource,
    SourceKind,
)
from affiliate_mate.research_store import ResearchWorkspaceStore

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=UTC)


def candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="p1",
        title="Reference Headphones",
        marketplace="DE",
        currency="EUR",
        price=299.0,
        commission_rate=0.04,
        monthly_searches=5000,
        youtube_competition=35,
        buyer_intent=80,
        content_gap=75,
        evidence_quality=90,
        estimated_ctr=0.05,
        estimated_conversion_rate=0.04,
    )


def populate(store: ResearchWorkspaceStore) -> None:
    for source_id, publisher in (("s1", "Maker"), ("s2", "Independent Lab")):
        store.add_source(
            ResearchSource(
                source_id=source_id,
                product_id="p1",
                kind=SourceKind.OFFICIAL if source_id == "s1" else SourceKind.EDITORIAL,
                title=f"Evidence {source_id}",
                locator=f"https://example.test/{source_id}",
                publisher=publisher,
                retrieved_at=NOW,
            )
        )
    store.add_claim(
        ResearchClaim(
            claim_id="c1",
            product_id="p1",
            text="The detachable cable is documented in the cited materials.",
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
            locator="Specifications / cable",
            quote=None,
            created_at=NOW,
            created_by="author",
        )
    )
    store.transition_claim(
        "c1",
        ClaimState.SUPPORTED,
        actor="reviewer",
        reason="Source checked.",
        created_at=NOW,
    )
    store.add_note(
        ResearchNote(
            note_id="n1",
            product_id="p1",
            title="Cable note",
            body="Use the supported detachable-cable claim and retain the source locator.",
            created_at=NOW,
            created_by="author",
        ),
        claim_ids=["c1"],
    )


def test_brief_contains_versioned_json_and_markdown_source_refs(tmp_path) -> None:
    analysis = analyze_candidate(candidate())
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        populate(store)
        brief = build_research_brief(analysis, store)
    payload = brief.to_dict()
    assert payload["schema_version"] == RESEARCH_BRIEF_SCHEMA_VERSION
    research = payload["research"]
    assert research["completeness"]["passed"] is True
    assert "[S1]" in brief.markdown
    assert "Specifications / cable" in brief.markdown
    assert "The detachable cable" in brief.markdown


def test_brief_rejects_reviews_for_wrong_product(tmp_path) -> None:
    from affiliate_mate.review_analysis import ReviewAnalysis

    analysis = analyze_candidate(candidate())
    wrong = ReviewAnalysis(
        product_id="p2",
        marketplace="DE",
        total_reviews=0,
        unique_reviews=0,
        exact_duplicate_copies=0,
        themes=(),
    )
    with ResearchWorkspaceStore(tmp_path / "research.sqlite3") as store:
        populate(store)
        try:
            build_research_brief(analysis, store, review_analysis=wrong)
        except ValueError as exc:
            assert "different product" in str(exc)
        else:
            raise AssertionError("expected wrong-product review analysis to be rejected")
