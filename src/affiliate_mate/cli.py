"""Command-line interface for Affiliate-Mate."""

from __future__ import annotations

import argparse
from pathlib import Path

from .io import load_candidates_csv
from .scoring import rank_candidates


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate",
        description="Rank affiliate product opportunities from transparent inputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="Score candidates from a CSV file.")
    score.add_argument("csv_path", type=Path)
    score.add_argument("--top", type=int, default=20)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "score":
        if args.top <= 0:
            raise SystemExit("--top must be greater than zero")
        return _score_command(args.csv_path, args.top)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
