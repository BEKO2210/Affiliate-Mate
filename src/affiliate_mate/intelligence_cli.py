"""CLI for market-intelligence collection, replay, and clustering."""

import argparse
import json
from pathlib import Path

from .budgets import SourceCallBudget
from .clustering import cluster_candidates
from .collection import collect_evidence
from .evidence import SQLiteEvidenceStore
from .io import load_candidates_csv
from .keyword_intelligence import CSVKeywordEvidenceProvider
from .providers import EvidenceProvider
from .replay import ReplayEvidenceProvider
from .trend_intelligence import CSVTrendEvidenceProvider
from .youtube_intelligence import YouTubeCompetitionProvider, YouTubeDataAPIClient


def _build_providers(args: argparse.Namespace) -> list[EvidenceProvider]:
    providers: list[EvidenceProvider] = []
    if args.keyword_csv is not None:
        providers.append(CSVKeywordEvidenceProvider.from_csv(args.keyword_csv))
    if args.trend_csv is not None:
        providers.append(CSVTrendEvidenceProvider.from_csv(args.trend_csv))
    if args.replay is not None:
        providers.append(ReplayEvidenceProvider.from_json(args.replay))
    if args.youtube:
        budget = SourceCallBudget(
            {
                "youtube.search.list": args.youtube_max_collections,
                "youtube.videos.list": args.youtube_max_collections,
            }
        )
        providers.append(
            YouTubeCompetitionProvider(
                YouTubeDataAPIClient.from_env(budget=budget),
                max_results=args.youtube_max_results,
                relevance_language=args.youtube_language,
            )
        )
    if not providers:
        raise SystemExit("configure at least one intelligence provider")
    return providers


def _collect_command(args: argparse.Namespace) -> int:
    candidates = load_candidates_csv(args.csv_path)
    providers = _build_providers(args)
    reports: list[dict[str, object]] = []
    with SQLiteEvidenceStore(args.evidence_db) as store:
        for candidate in candidates:
            report = collect_evidence(
                candidate,
                providers,
                store=store,
                fail_fast=args.fail_fast,
            )
            reports.append(report.to_dict())
    if args.format == "json":
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
        return 0

    print(f"{'PRODUCT':<28} {'COLLECTED':>9} {'STORED':>7}  FAILED")
    print("-" * 72)
    for report in reports:
        failed_providers = report["failed_providers"]
        failed = ",".join(failed_providers) if isinstance(failed_providers, list) else "-"
        print(
            f"{str(report['product_id'])[:28]:<28} "
            f"{report['observations_collected']!s:>9} "
            f"{report['observations_stored']!s:>7}  {failed or '-'}"
        )
    return 0


def _cluster_command(args: argparse.Namespace) -> int:
    candidates = load_candidates_csv(args.csv_path)
    clusters = cluster_candidates(candidates, threshold=args.threshold)
    payload = [
        {
            "canonical_product_id": cluster.canonical_product_id,
            "marketplace": cluster.marketplace,
            "members": [member.product_id for member in cluster.members],
        }
        for cluster in clusters
    ]
    if args.format == "json":
        print(json.dumps({"clusters": payload}, indent=2, sort_keys=True))
        return 0
    for cluster in payload:
        members = ", ".join(cluster["members"])
        print(f"{cluster['canonical_product_id']}: {members}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate-intel",
        description="Collect auditable market intelligence into the evidence store.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect evidence for CSV candidates.")
    collect.add_argument("csv_path", type=Path)
    collect.add_argument("evidence_db", type=Path)
    collect.add_argument("--keyword-csv", type=Path)
    collect.add_argument("--trend-csv", type=Path)
    collect.add_argument("--replay", type=Path)
    collect.add_argument("--youtube", action="store_true")
    collect.add_argument("--youtube-max-results", type=int, default=25)
    collect.add_argument(
        "--youtube-max-collections",
        type=int,
        default=20,
        help="Maximum YouTube product landscapes collected in this process.",
    )
    collect.add_argument("--youtube-language")
    collect.add_argument("--fail-fast", action="store_true")
    collect.add_argument("--format", choices=("table", "json"), default="table")

    cluster = subparsers.add_parser(
        "cluster",
        help="Cluster likely near-duplicate product variants.",
    )
    cluster.add_argument("csv_path", type=Path)
    cluster.add_argument("--threshold", type=float, default=0.72)
    cluster.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "collect":
        if not 1 <= args.youtube_max_results <= 50:
            raise SystemExit("--youtube-max-results must be between 1 and 50")
        if args.youtube_max_collections < 0:
            raise SystemExit("--youtube-max-collections must be >= 0")
        return _collect_command(args)
    if args.command == "cluster":
        if not 0 <= args.threshold <= 1:
            raise SystemExit("--threshold must be between 0 and 1")
        return _cluster_command(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
