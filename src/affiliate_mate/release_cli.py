"""Stable-release verification and manifest CLI."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .exit_codes import ExitCode
from .release_channel import ReleaseChannel, ReleaseChannelError, resolve_release_channel
from .release_manifest import build_release_manifest, verify_release_manifest
from .stable_contract import compatibility_contract, performance_budget_contract


def _time(raw: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be ISO-8601") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return value.astimezone(UTC)


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain one JSON object")
    return value


def _write(value: object, output: Path | None = None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output is None:
        print(text, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def _verify(_args: argparse.Namespace) -> int:
    checks: list[dict[str, object]] = []
    try:
        channel = resolve_release_channel(env={})
        checks.append(
            {
                "code": "stable_channel",
                "passed": channel.channel is ReleaseChannel.STABLE,
                "actual": channel.channel.value,
                "expected": "stable",
            }
        )
    except ReleaseChannelError as exc:
        checks.append(
            {
                "code": "stable_channel",
                "passed": False,
                "actual": str(exc),
                "expected": "stable",
            }
        )
    major = int(__version__.split(".", 1)[0]) if __version__.split(".", 1)[0].isdigit() else -1
    contract = compatibility_contract()
    checks.extend(
        [
            {
                "code": "stable_major",
                "passed": major == 1,
                "actual": major,
                "expected": 1,
            },
            {
                "code": "python_runtime",
                "passed": sys.version_info >= (3, 11),
                "actual": f"{sys.version_info.major}.{sys.version_info.minor}",
                "expected": ">=3.11",
            },
            {
                "code": "compatibility_contract",
                "passed": contract["stable_major"] == 1,
                "actual": contract["schema_version"],
                "expected": "affiliate-mate.compatibility.v1",
            },
        ]
    )
    passed = all(bool(item["passed"]) for item in checks)
    _write(
        {
            "schema_version": "affiliate-mate.stable-release-verification.v1",
            "version": __version__,
            "passed": passed,
            "checks": checks,
        }
    )
    return ExitCode.OK if passed else ExitCode.CHECK_FAILED


def _manifest(args: argparse.Namespace) -> int:
    manifest = build_release_manifest(
        args.files,
        root=args.root,
        version=__version__,
        commit_sha=args.commit_sha,
        created_at=args.created_at,
    )
    _write(manifest, args.output)
    return ExitCode.OK


def _manifest_verify(args: argparse.Namespace) -> int:
    report = verify_release_manifest(_load_object(args.manifest), root=args.root)
    _write(report, args.output)
    return ExitCode.OK if report["passed"] else ExitCode.CHECK_FAILED


def _contract(_args: argparse.Namespace) -> int:
    _write(compatibility_contract())
    return ExitCode.OK


def _performance_budget(_args: argparse.Namespace) -> int:
    _write(performance_budget_contract())
    return ExitCode.OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate-release",
        description="Inspect v1 compatibility commitments and verify release artifacts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    contract = sub.add_parser("contract", help="Print the stable v1 compatibility contract.")
    contract.set_defaults(handler=_contract)

    budget = sub.add_parser("performance-budget", help="Print stable acceptance budgets.")
    budget.set_defaults(handler=_performance_budget)

    verify = sub.add_parser("verify", help="Verify that the installed package satisfies v1 stable policy.")
    verify.set_defaults(handler=_verify)

    manifest = sub.add_parser("manifest", help="Create a SHA-256 release manifest.")
    manifest.add_argument("files", nargs="+", type=Path)
    manifest.add_argument("--root", type=Path, default=Path("."))
    manifest.add_argument("--commit-sha", required=True)
    manifest.add_argument("--created-at", type=_time, required=True)
    manifest.add_argument("--output", type=Path)
    manifest.set_defaults(handler=_manifest)

    verify_manifest = sub.add_parser("manifest-verify", help="Verify exact release bytes against a manifest.")
    verify_manifest.add_argument("manifest", type=Path)
    verify_manifest.add_argument("--root", type=Path, default=Path("."))
    verify_manifest.add_argument("--output", type=Path)
    verify_manifest.set_defaults(handler=_manifest_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"release error: {exc}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
