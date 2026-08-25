"""CLI for catalog discovery and commission schedule checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .amazon_creators import AmazonCatalogProvider, AmazonCreatorsClient, AmazonCreatorsCredentials
from .catalog import CatalogItem, CommissionSchedule
from .mock_catalog import MockCatalogProvider


def _print_items(items: list[CatalogItem], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps([item.to_dict() for item in items], indent=2, sort_keys=True))
        return
    header = f"{'PROVIDER':<21} {'MARKET':<6} {'PRICE':>11}  {'PRODUCT':<48}"
    print(header)
    print("-" * len(header))
    for item in items:
        price = "n/a"
        if item.price is not None and item.currency is not None:
            price = f"{item.price:.2f} {item.currency}"
        title = item.title if len(item.title) <= 48 else item.title[:45] + "..."
        print(f"{item.provider:<21} {item.marketplace:<6} {price:>11}  {title:<48}")


def _mock_search(args: argparse.Namespace) -> int:
    items = MockCatalogProvider().search(
        args.keywords,
        marketplace=args.marketplace,
        limit=args.limit,
    )
    _print_items(items, args.format)
    return 0


def _amazon_search(args: argparse.Namespace) -> int:
    try:
        credentials = AmazonCreatorsCredentials.from_env()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    provider = AmazonCatalogProvider(
        AmazonCreatorsClient(credentials),
        search_index=args.search_index,
    )
    items = list(
        provider.search(
            args.keywords,
            marketplace=args.marketplace,
            limit=args.limit,
        )
    )
    _print_items(items, args.format)
    return 0


def _commission_lookup(args: argparse.Namespace) -> int:
    schedule = CommissionSchedule.from_csv(args.csv_path)
    try:
        rate = schedule.rate_for(args.marketplace, args.category)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    if args.format == "json":
        print(
            json.dumps(
                {
                    "marketplace": args.marketplace.upper(),
                    "category": args.category,
                    "commission_rate": rate,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"{args.marketplace.upper()} {args.category}: {rate:.4f} ({rate * 100:.2f}%)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate-catalog",
        description="Discover catalog products without mixing acquisition into scoring.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    mock = subparsers.add_parser("mock-search", help="Search the credential-free demo catalog.")
    mock.add_argument("keywords")
    mock.add_argument("--marketplace", default="DE")
    mock.add_argument("--limit", type=int, default=10)
    mock.add_argument("--format", choices=("table", "json"), default="table")

    amazon = subparsers.add_parser("amazon-search", help="Search Amazon through Creators API.")
    amazon.add_argument("keywords")
    amazon.add_argument("--marketplace", default="DE")
    amazon.add_argument("--limit", type=int, default=10)
    amazon.add_argument("--search-index", default="All")
    amazon.add_argument("--format", choices=("table", "json"), default="table")

    commission = subparsers.add_parser(
        "commission-lookup",
        help="Resolve one explicit commission rule from a CSV schedule.",
    )
    commission.add_argument("csv_path", type=Path)
    commission.add_argument("marketplace")
    commission.add_argument("category")
    commission.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"mock-search", "amazon-search"} and not 1 <= args.limit <= 10:
        raise SystemExit("--limit must be between 1 and 10")
    if args.command == "mock-search":
        return _mock_search(args)
    if args.command == "amazon-search":
        return _amazon_search(args)
    if args.command == "commission-lookup":
        return _commission_lookup(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
