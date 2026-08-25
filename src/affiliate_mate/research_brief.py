"""Citation-ready product brief generation from analysis and audited research records."""

from __future__ import annotations

from dataclasses import dataclass

from .analysis import AnalysisResult
from .research_models import EvidenceStance
from .research_policy import (
    ResearchCompletenessReport,
    ResearchPolicy,
    evaluate_research_completeness,
)
from .research_store import ResearchWorkspaceStore
from .review_analysis import ReviewAnalysis

RESEARCH_BRIEF_SCHEMA_VERSION = "affiliate-mate.research-brief.v1"


@dataclass(frozen=True, slots=True)
class ProductResearchBrief:
    payload: dict[str, object]
    markdown: str

    def to_dict(self) -> dict[str, object]:
        return dict(self.payload)


def _money(value: float, currency: str) -> str:
    return f"{value:.2f} {currency}"


def _source_ref_map(source_ids: list[str]) -> dict[str, str]:
    return {source_id: f"S{index}" for index, source_id in enumerate(source_ids, start=1)}


def build_research_brief(
    analysis: AnalysisResult,
    store: ResearchWorkspaceStore,
    *,
    review_analysis: ReviewAnalysis | None = None,
    policy: ResearchPolicy | None = None,
) -> ProductResearchBrief:
    """Build an inspectable brief; no claim text is invented by this function."""

    product_id = analysis.candidate.product_id
    if review_analysis is not None and review_analysis.product_id != product_id:
        raise ValueError("review analysis belongs to a different product")
    if review_analysis is not None and review_analysis.marketplace != analysis.candidate.marketplace.upper():
        raise ValueError("review analysis belongs to a different marketplace")

    completeness = evaluate_research_completeness(store, product_id, policy=policy)
    sources = store.list_sources(product_id)
    source_refs = _source_ref_map([source.source_id for source in sources])
    claims = store.list_claims(product_id)
    notes = store.list_notes(product_id)
    approval_state = store.current_approval_state(product_id)

    claim_payload: list[dict[str, object]] = []
    for claim in claims:
        state = store.current_claim_state(claim.claim_id)
        links = store.list_claim_links(claim.claim_id)
        evidence = [
            {
                **link.to_dict(),
                "source_ref": source_refs.get(link.source_id),
            }
            for link in links
        ]
        claim_payload.append({**claim.to_dict(state=state), "evidence": evidence})

    note_payload = [
        note.to_dict(claim_ids=store.note_claim_ids(note.note_id))
        for note in notes
    ]
    source_payload = [
        {**source.to_dict(), "ref": source_refs[source.source_id]}
        for source in sources
    ]

    payload: dict[str, object] = {
        "schema_version": RESEARCH_BRIEF_SCHEMA_VERSION,
        "product": analysis.to_dict()["product"],
        "opportunity": {
            "decision": analysis.decision.to_dict(),
            "sensitivity": analysis.sensitivity.to_dict(),
            "evidence_resolution": (
                None
                if analysis.evidence_resolution is None
                else analysis.evidence_resolution.to_dict()
            ),
        },
        "research": {
            "approval_state": approval_state.value,
            "completeness": completeness.to_dict(),
            "sources": source_payload,
            "claims": claim_payload,
            "notes": note_payload,
            "review_analysis": None if review_analysis is None else review_analysis.to_dict(),
        },
    }
    return ProductResearchBrief(
        payload=payload,
        markdown=_render_markdown(
            analysis,
            completeness,
            source_payload,
            claim_payload,
            note_payload,
            approval_state.value,
            review_analysis,
        ),
    )


def _render_markdown(
    analysis: AnalysisResult,
    completeness: ResearchCompletenessReport,
    sources: list[dict[str, object]],
    claims: list[dict[str, object]],
    notes: list[dict[str, object]],
    approval_state: str,
    reviews: ReviewAnalysis | None,
) -> str:
    candidate = analysis.candidate
    score = analysis.decision.score
    lines = [
        f"# Research brief — {candidate.title}",
        "",
        f"- Product ID: `{candidate.product_id}`",
        f"- Marketplace: {candidate.marketplace}",
        f"- Price: {_money(candidate.price, candidate.currency)}",
        f"- Commission / sale: {_money(candidate.commission_per_sale, candidate.currency)}",
        f"- Opportunity score: {score.opportunity_score:.2f}/100",
        f"- Decision: {'SHORTLIST' if analysis.decision.accepted else 'REJECT'}",
        f"- Research approval: {approval_state.upper()}",
        f"- Research completeness: {'PASS' if completeness.passed else 'FAIL'}",
        "",
        "## Opportunity evidence",
        "",
        f"- Monthly searches: {candidate.monthly_searches}",
        f"- YouTube competition: {candidate.youtube_competition}/100",
        f"- Buyer intent: {candidate.buyer_intent}/100",
        f"- Content gap: {candidate.content_gap}/100",
        f"- Evidence quality: {candidate.evidence_quality}/100",
        f"- Estimated value / 1,000 views: {_money(candidate.estimated_value_per_1000_views, candidate.currency)}",
        "",
        "## Research gates",
        "",
    ]
    for check in completeness.checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(f"- **{marker}** `{check.code}` — {check.message}")

    lines.extend(["", "## Claims", ""])
    if not claims:
        lines.append("No claims recorded.")
    for claim in claims:
        lines.append(
            f"### {claim['claim_id']} — {str(claim['state']).upper()} / {str(claim['risk']).upper()}"
        )
        lines.append("")
        lines.append(str(claim["text"]))
        lines.append("")
        evidence = claim["evidence"]
        if isinstance(evidence, list) and evidence:
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                stance = str(item["stance"])
                ref = item.get("source_ref") or item["source_id"]
                locator = item["locator"]
                lines.append(f"- {stance}: [{ref}] {locator}")
        else:
            lines.append("- No linked evidence.")
        lines.append("")

    lines.extend(["## Research notes", ""])
    if not notes:
        lines.append("No notes recorded.")
    for note in notes:
        claim_ids = note.get("claim_ids")
        refs = ", ".join(claim_ids) if isinstance(claim_ids, list) else ""
        lines.append(f"### {note['title']}")
        lines.append("")
        if refs:
            lines.append(f"Claims: {refs}")
            lines.append("")
        lines.append(str(note["body"]))
        lines.append("")

    if reviews is not None:
        lines.extend(["## User-supplied review themes", ""])
        lines.append(
            f"Corpus: {reviews.total_reviews} reviews, {reviews.unique_reviews} unique, "
            f"{reviews.exact_duplicate_copies} exact duplicate copies."
        )
        lines.append("")
        for theme in reviews.themes:
            terms = ", ".join(theme.common_terms) or "no stable common terms"
            lines.append(
                f"- **{theme.theme_id} / {theme.sentiment}** — "
                f"avg {theme.average_rating:.2f}/5; reviews {len(theme.review_ids)}; terms: {terms}"
            )
        lines.append("")

    lines.extend(["## Sources", ""])
    if not sources:
        lines.append("No sources recorded.")
    for source in sources:
        lines.append(
            f"- **[{source['ref']}]** {source['title']} — {source['publisher']} — "
            f"{source['locator']}"
        )

    contradictory = sum(
        1
        for claim in claims
        for item in claim.get("evidence", [])
        if isinstance(item, dict) and item.get("stance") == EvidenceStance.CONTRADICTS.value
    )
    if contradictory:
        lines.extend(
            [
                "",
                "> Warning: contradictory evidence is present. Resolve it before treating this brief as approved.",
            ]
        )
    lines.append("")
    return "\n".join(lines)
