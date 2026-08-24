"""Command-line interface for Affiliate-Mate."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .analysis import analyze_inputs, build_automation_payload
from .decision import EvaluationPolicy
from .evidence import EvidenceObservation, SQLiteEvidenceStore
from .io import load_candidate_inputs_csv, load_candidates_csv
from .scoring import rank_candidates


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "timestamps must include a timezone, e.g. 2026-08-25T12:00:00Z"
        )
    return parsed.astimezone(UTC)


def _score_command(csv_path: Path, top: int) -> int:
    candidates = load_candidates_csv(csv_path)
    ranked = rank_candidates(candidates)[:top]

    header = (
        f"{'SCORE':>7}  {'EV/1K':>9}  {'COMM':>8}  "
        f"{'MARKET':>6}  {'PRODUCT':<48}"
    )
    print(header)
    print("-" * len(header))
    for candidate, score in ranked:
        title = candidate.title if len(candidate.title) <= 48 else candidate.title[:45] + "..."
        print(
            f"{score.opportunity_score:7.2f}  "
            f"{score.estimated_value_per_1000_views:9.2f}  "
            f"{score.commission_per_sale:8.2f}  "
            f"{candidate.marketplace:>6}  "
            f"{title:<48}"
        )
    return 0


def _policy_from_args(args: argparse.Namespace) -> EvaluationPolicy:
    return EvaluationPolicy(
        min_commission_per_sale=args.min_commission,
        min_monthly_searches=args.min_searches,
        max_youtube_competition=args.max_competition,
        min_buyer_intent=args.min_buyer_intent,
        min_evidence_quality=args.min_evidence_quality,
        min_estimated_value_per_1000_views=args.min_ev_per_1k,
        min_opportunity_score=args.min_score,
    )


def _analyze_command(args: argparse.Namespace) -> int:
    policy = _policy_from_args(args)
    inputs = load_candidate_inputs_csv(args.csv_path)
    if args.evidence_db is not None:
        if not args.evidence_db.exists():
            raise SystemExit(f"Evidence database does not exist: {args.evidence_db}")
        with SQLiteEvidenceStore(args.evidence_db) as store:
            results = analyze_inputs(
                inputs,
                policy=policy,
                evidence_store=store,
                as_of=args.as_of,
                min_evidence_confidence=args.min_evidence_confidence,
            )
    else:
        results = analyze_inputs(inputs, policy=policy)
    if not args.include_rejected:
        results = [result for result in results if result.decision.accepted]
    results = results[: args.top]

    if args.format == "json":
        payload = build_automation_payload(results, policy=policy)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    header = f"{'STATUS':<9} {'SCORE':>7} {'EV/1K':>9} {'FLOOR':>9}  {'PRODUCT':<44}  REASON"
    print(header)
    print("-" * len(header))
    for result in results:
        decision = result.decision
        title = result.candidate.title
        if len(title) > 44:
            title = title[:41] + "..."
        reason = "ready for shortlist"
        if decision.rejection_reasons:
            reason = decision.rejection_reasons[0]
        print(
            f"{('SHORTLIST' if decision.accepted else 'REJECT'):<9} "
            f"{decision.score.opportunity_score:7.2f} "
            f"{decision.score.estimated_value_per_1000_views:9.2f} "
            f"{result.sensitivity.floor_ev_per_1000_views:9.2f}  "
            f"{title:<44}  {reason}"
        )
    return 0


def _evidence_init_command(path: Path) -> int:
    with SQLiteEvidenceStore(path) as store:
        print(f"Initialized evidence store at {path} (schema v1, {store.count()} observations).")
    return 0


def _evidence_add_command(args: argparse.Namespace) -> int:
    observed_at = args.observed_at or datetime.now(UTC)
    observation = EvidenceObservation(
        product_id=args.product_id,
        signal=args.signal,
        value=args.value,
        source=args.source,
        marketplace=args.marketplace,
        observed_at=observed_at,
        confidence=args.confidence,
        expires_at=args.expires_at,
        unit=args.unit,
    )
    with SQLiteEvidenceStore(args.db_path) as store:
        inserted = store.add(observation)
    print("stored" if inserted else "duplicate ignored")
    return 0


def _evidence_latest_command(args: argparse.Namespace) -> int:
    with SQLiteEvidenceStore(args.db_path) as store:
        observation = store.latest(
            args.product_id,
            args.signal,
            marketplace=args.marketplace,
            as_of=args.as_of,
            include_expired=args.include_expired,
        )
    if observation is None:
        print("null" if args.format == "json" else "No matching observation.")
        return 1
    if args.format == "json":
        print(json.dumps(observation.to_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"{observation.product_id} {observation.signal}={observation.value} "
            f"source={observation.source} observed_at={observation.observed_at.isoformat()}"
        )
    return 0


def _add_policy_arguments(parser: argparse.ArgumentParser) -> None:
    defaults = EvaluationPolicy()
    parser.add_argument("--min-commission", type=float, default=defaults.min_commission_per_sale)
    parser.add_argument("--min-searches", type=int, default=defaults.min_monthly_searches)
    parser.add_argument("--max-competition", type=int, default=defaults.max_youtube_competition)
    parser.add_argument("--min-buyer-intent", type=int, default=defaults.min_buyer_intent)
    parser.add_argument("--min-evidence-quality", type=int, default=defaults.min_evidence_quality)
    parser.add_argument(
        "--min-ev-per-1k",
        type=float,
        default=defaults.min_estimated_value_per_1000_views,
    )
    parser.add_argument("--min-score", type=float, default=defaults.min_opportunity_score)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate",
        description="Evidence-first affiliate product opportunity research.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="Score candidates from a CSV file.")
    score.add_argument("csv_path", type=Path)
    score.add_argument("--top", type=int, default=20)

    analyze = subparsers.add_parser(
        "analyze",
        help="Run evidence gates, scoring, and sensitivity analysis.",
    )
    analyze.add_argument("csv_path", type=Path)
    analyze.add_argument("--top", type=int, default=20)
    analyze.add_argument("--format", choices=("table", "json"), default="table")
    analyze.add_argument(
        "--include-rejected",
        action="store_true",
        help="Include rejected candidates instead of returning shortlist entries only.",
    )
    analyze.add_argument(
        "--evidence-db",
        type=Path,
        help="Apply the latest valid observations from this SQLite evidence database.",
    )
    analyze.add_argument(
        "--as-of",
        type=_parse_datetime,
        help="Resolve evidence as of an ISO-8601 timestamp instead of now.",
    )
    analyze.add_argument(
        "--min-evidence-confidence",
        type=float,
        default=0.0,
        help="Ignore persisted observations below this 0-1 confidence threshold.",
    )
    _add_policy_arguments(analyze)

    evidence = subparsers.add_parser("evidence", help="Manage the local SQLite evidence store.")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)

    evidence_init = evidence_commands.add_parser("init", help="Initialize an evidence database.")
    evidence_init.add_argument("db_path", type=Path)

    evidence_add = evidence_commands.add_parser("add", help="Append one numeric observation.")
    evidence_add.add_argument("db_path", type=Path)
    evidence_add.add_argument("product_id")
    evidence_add.add_argument("signal")
    evidence_add.add_argument("value", type=float)
    evidence_add.add_argument("--source", required=True)
    evidence_add.add_argument("--marketplace", default="DE")
    evidence_add.add_argument("--confidence", type=float, default=1.0)
    evidence_add.add_argument("--unit")
    evidence_add.add_argument("--observed-at", type=_parse_datetime)
    evidence_add.add_argument("--expires-at", type=_parse_datetime)

    evidence_latest = evidence_commands.add_parser(
        "latest",
        help="Read the latest valid observation for a signal.",
    )
    evidence_latest.add_argument("db_path", type=Path)
    evidence_latest.add_argument("product_id")
    evidence_latest.add_argument("signal")
    evidence_latest.add_argument("--marketplace", default="DE")
    evidence_latest.add_argument("--as-of", type=_parse_datetime)
    evidence_latest.add_argument("--include-expired", action="store_true")
    evidence_latest.add_argument("--format", choices=("text", "json"), default="text")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "score":
        if args.top <= 0:
            raise SystemExit("--top must be greater than zero")
        return _score_command(args.csv_path, args.top)
    if args.command == "analyze":
        if args.top <= 0:
            raise SystemExit("--top must be greater than zero")
        if not 0 <= args.min_evidence_confidence <= 1:
            raise SystemExit("--min-evidence-confidence must be between 0 and 1")
        return _analyze_command(args)
    if args.command == "evidence":
        if args.evidence_command == "init":
            return _evidence_init_command(args.db_path)
        if args.evidence_command == "add":
            return _evidence_add_command(args)
        if args.evidence_command == "latest":
            return _evidence_latest_command(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
