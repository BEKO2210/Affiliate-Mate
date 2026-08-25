"""CLI for audited claims, citations, reviews, briefs, and human approval."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .analysis import analyze_candidate
from .evidence import SQLiteEvidenceStore
from .io import load_candidate_inputs_csv
from .research_brief import build_research_brief
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
    utc_now,
)
from .research_policy import (
    ResearchApprovalBlocked,
    evaluate_approval_guard,
    evaluate_research_completeness,
    transition_product_approval,
)
from .research_store import ResearchWorkspaceStore
from .review_analysis import analyze_reviews, load_reviews_csv


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _parse_time(value: str | None) -> datetime:
    if value is None:
        return utc_now()
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _select_candidate(path: Path, product_id: str):
    matches = [item for item in load_candidate_inputs_csv(path) if item.candidate.product_id == product_id]
    if not matches:
        raise SystemExit(f"product_id not found in candidate CSV: {product_id}")
    if len(matches) != 1:
        raise SystemExit(f"product_id appears more than once in candidate CSV: {product_id}")
    return matches[0]


def _init(args: argparse.Namespace) -> int:
    with ResearchWorkspaceStore(args.database):
        pass
    print(f"initialized research workspace: {args.database}")
    return 0


def _source_add(args: argparse.Namespace) -> int:
    source = ResearchSource(
        source_id=args.source_id or _id("src"),
        product_id=args.product_id,
        kind=SourceKind(args.kind),
        title=args.title,
        locator=args.locator,
        publisher=args.publisher,
        retrieved_at=_parse_time(args.retrieved_at),
        published_at=None if args.published_at is None else _parse_time(args.published_at),
        checksum=args.checksum,
    )
    with ResearchWorkspaceStore(args.database) as store:
        if not store.add_source(source):
            raise SystemExit(f"source_id already exists: {source.source_id}")
    print(json.dumps(source.to_dict(), indent=2, sort_keys=True))
    return 0


def _claim_add(args: argparse.Namespace) -> int:
    claim = ResearchClaim(
        claim_id=args.claim_id or _id("claim"),
        product_id=args.product_id,
        text=args.text,
        risk=ClaimRisk(args.risk),
        created_at=utc_now(),
        created_by=args.actor,
    )
    with ResearchWorkspaceStore(args.database) as store:
        if not store.add_claim(claim):
            raise SystemExit(f"claim_id already exists: {claim.claim_id}")
    print(json.dumps(claim.to_dict(state=ClaimState.DRAFT), indent=2, sort_keys=True))
    return 0


def _claim_link(args: argparse.Namespace) -> int:
    link = ClaimEvidenceLink(
        claim_id=args.claim_id,
        source_id=args.source_id,
        stance=EvidenceStance(args.stance),
        locator=args.locator,
        quote=args.quote,
        created_at=utc_now(),
        created_by=args.actor,
    )
    with ResearchWorkspaceStore(args.database) as store:
        if not store.add_evidence_link(link):
            raise SystemExit("identical claim/source/stance/locator link already exists")
    print(json.dumps(link.to_dict(), indent=2, sort_keys=True))
    return 0


def _claim_state(args: argparse.Namespace) -> int:
    expected = None if args.expected_state is None else ClaimState(args.expected_state)
    with ResearchWorkspaceStore(args.database) as store:
        event = store.transition_claim(
            args.claim_id,
            ClaimState(args.state),
            actor=args.actor,
            reason=args.reason,
            expected_state=expected,
        )
    print(json.dumps(event.to_dict(), indent=2, sort_keys=True))
    return 0


def _note_add(args: argparse.Namespace) -> int:
    note = ResearchNote(
        note_id=args.note_id or _id("note"),
        product_id=args.product_id,
        title=args.title,
        body=args.body,
        created_at=utc_now(),
        created_by=args.actor,
    )
    with ResearchWorkspaceStore(args.database) as store:
        if not store.add_note(note, claim_ids=args.claim_id):
            raise SystemExit(f"note_id already exists: {note.note_id}")
    print(json.dumps(note.to_dict(claim_ids=tuple(args.claim_id)), indent=2, sort_keys=True))
    return 0


def _status(args: argparse.Namespace) -> int:
    with ResearchWorkspaceStore(args.database) as store:
        report = evaluate_research_completeness(store, args.product_id)
        guard = evaluate_approval_guard(store, args.product_id)
        payload = {
            "approval_state": guard.raw_state.value,
            "production_ready": guard.passed,
            "approval_guard": guard.to_dict(),
            "completeness": report.to_dict(),
            "sources": [source.to_dict() for source in store.list_sources(args.product_id)],
            "claims": [
                claim.to_dict(state=store.current_claim_state(claim.claim_id))
                for claim in store.list_claims(args.product_id)
            ],
            "notes": [
                note.to_dict(claim_ids=store.note_claim_ids(note.note_id))
                for note in store.list_notes(args.product_id)
            ],
            "approval_history": [
                event.to_dict() for event in store.list_approval_events(args.product_id)
            ],
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _approval(args: argparse.Namespace) -> int:
    expected = None if args.expected_state is None else ApprovalState(args.expected_state)
    try:
        with ResearchWorkspaceStore(args.database) as store:
            event = transition_product_approval(
                store,
                args.product_id,
                ApprovalState(args.state),
                actor=args.actor,
                reason=args.reason,
                expected_state=expected,
            )
            guard = evaluate_approval_guard(store, args.product_id)
    except ResearchApprovalBlocked as exc:
        print(json.dumps(exc.report.to_dict(), indent=2, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "event": event.to_dict(),
                "production_ready": guard.passed,
                "approval_guard": guard.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _reviews(args: argparse.Namespace) -> int:
    analysis = analyze_reviews(
        load_reviews_csv(args.reviews_csv),
        product_id=args.product_id,
        marketplace=args.marketplace,
        similarity_threshold=args.threshold,
    )
    print(json.dumps(analysis.to_dict(), indent=2, sort_keys=True))
    return 0


def _brief(args: argparse.Namespace) -> int:
    candidate_input = _select_candidate(args.candidate_csv, args.product_id)
    evidence_store = None
    try:
        if args.evidence_db is not None:
            evidence_store = SQLiteEvidenceStore(args.evidence_db)
            evidence_store.initialize()
        analysis = analyze_candidate(
            candidate_input.candidate,
            provided_fields=candidate_input.provided_fields,
            evidence_store=evidence_store,
            min_evidence_confidence=args.min_evidence_confidence,
        )
        review_result = None
        if args.reviews_csv is not None:
            review_result = analyze_reviews(
                load_reviews_csv(args.reviews_csv),
                product_id=args.product_id,
                marketplace=analysis.candidate.marketplace,
                similarity_threshold=args.review_threshold,
            )
        with ResearchWorkspaceStore(args.research_db) as store:
            brief = build_research_brief(analysis, store, review_analysis=review_result)
    finally:
        if evidence_store is not None:
            evidence_store.close()

    output = (
        json.dumps(brief.to_dict(), indent=2, sort_keys=True)
        if args.format == "json"
        else brief.markdown
    )
    if args.output is not None:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate-research",
        description="Build an auditable human-approved research workspace before content generation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Initialize a research workspace database.")
    init.add_argument("database", type=Path)
    init.set_defaults(handler=_init)

    source = subparsers.add_parser("source-add", help="Add a provenance-bearing research source.")
    source.add_argument("database", type=Path)
    source.add_argument("product_id")
    source.add_argument("--source-id")
    source.add_argument("--kind", choices=tuple(kind.value for kind in SourceKind), required=True)
    source.add_argument("--title", required=True)
    source.add_argument("--locator", required=True)
    source.add_argument("--publisher", required=True)
    source.add_argument("--retrieved-at")
    source.add_argument("--published-at")
    source.add_argument("--checksum")
    source.set_defaults(handler=_source_add)

    claim = subparsers.add_parser("claim-add", help="Add a claim in draft state.")
    claim.add_argument("database", type=Path)
    claim.add_argument("product_id")
    claim.add_argument("text")
    claim.add_argument("--claim-id")
    claim.add_argument("--risk", choices=tuple(risk.value for risk in ClaimRisk), default="medium")
    claim.add_argument("--actor", required=True)
    claim.set_defaults(handler=_claim_add)

    link = subparsers.add_parser("claim-link", help="Link one claim to one source.")
    link.add_argument("database", type=Path)
    link.add_argument("claim_id")
    link.add_argument("source_id")
    link.add_argument("--stance", choices=tuple(item.value for item in EvidenceStance), required=True)
    link.add_argument("--locator", required=True, help="Page, section, timestamp, or record locator.")
    link.add_argument("--quote")
    link.add_argument("--actor", required=True)
    link.set_defaults(handler=_claim_link)

    claim_state = subparsers.add_parser("claim-state", help="Append an audited claim state transition.")
    claim_state.add_argument("database", type=Path)
    claim_state.add_argument("claim_id")
    claim_state.add_argument("state", choices=tuple(state.value for state in ClaimState))
    claim_state.add_argument("--actor", required=True)
    claim_state.add_argument("--reason", required=True)
    claim_state.add_argument("--expected-state", choices=tuple(state.value for state in ClaimState))
    claim_state.set_defaults(handler=_claim_state)

    note = subparsers.add_parser("note-add", help="Add a citation-ready note linked to claims.")
    note.add_argument("database", type=Path)
    note.add_argument("product_id")
    note.add_argument("title")
    note.add_argument("body")
    note.add_argument("--note-id")
    note.add_argument("--claim-id", action="append", default=[])
    note.add_argument("--actor", required=True)
    note.set_defaults(handler=_note_add)

    status = subparsers.add_parser("status", help="Show completeness and production readiness as JSON.")
    status.add_argument("database", type=Path)
    status.add_argument("product_id")
    status.set_defaults(handler=_status)

    approval = subparsers.add_parser("approval", help="Append a guarded product approval transition.")
    approval.add_argument("database", type=Path)
    approval.add_argument("product_id")
    approval.add_argument("state", choices=tuple(state.value for state in ApprovalState))
    approval.add_argument("--actor", required=True)
    approval.add_argument("--reason", required=True)
    approval.add_argument("--expected-state", choices=tuple(state.value for state in ApprovalState))
    approval.set_defaults(handler=_approval)

    reviews = subparsers.add_parser("reviews", help="Analyze a user-supplied review CSV deterministically.")
    reviews.add_argument("reviews_csv", type=Path)
    reviews.add_argument("product_id")
    reviews.add_argument("marketplace")
    reviews.add_argument("--threshold", type=float, default=0.32)
    reviews.set_defaults(handler=_reviews)

    brief = subparsers.add_parser("brief", help="Build Markdown or JSON research brief.")
    brief.add_argument("candidate_csv", type=Path)
    brief.add_argument("product_id")
    brief.add_argument("research_db", type=Path)
    brief.add_argument("--evidence-db", type=Path)
    brief.add_argument("--min-evidence-confidence", type=float, default=0.0)
    brief.add_argument("--reviews-csv", type=Path)
    brief.add_argument("--review-threshold", type=float, default=0.32)
    brief.add_argument("--format", choices=("markdown", "json"), default="markdown")
    brief.add_argument("--output", type=Path)
    brief.set_defaults(handler=_brief)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    confidence = getattr(args, "min_evidence_confidence", 0.0)
    if not 0 <= confidence <= 1:
        raise SystemExit("--min-evidence-confidence must be between 0 and 1")
    if hasattr(args, "threshold") and not 0 <= args.threshold <= 1:
        raise SystemExit("--threshold must be between 0 and 1")
    if hasattr(args, "review_threshold") and not 0 <= args.review_threshold <= 1:
        raise SystemExit("--review-threshold must be between 0 and 1")
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
