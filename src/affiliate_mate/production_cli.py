"""CLI for fail-closed production planning, package signoff, and publish dry-runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .disclosures import disclosure_template
from .production_adapters import DryRunYouTubePublisher
from .production_manifest import (
    artifact_from_path,
    build_production_package,
    build_publish_dry_run,
    sign_production_package,
)
from .production_models import ArtifactKind, ArtifactRecord
from .production_planner import (
    build_dry_run_adapter_plans,
    build_thumbnail_brief,
    build_video_metadata,
)
from .production_policy import require_production_authorization
from .production_serialization import package_from_dict, script_from_dict, signoff_from_dict
from .research_store import ResearchWorkspaceStore
from .script_compiler import (
    StrictTemplateScriptGenerator,
    build_script_request,
    generate_and_validate_script,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain one JSON object")
    return value


def _write_json(value: object, output: Path | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.write_text(text, encoding="utf-8")


def _authorize(args: argparse.Namespace) -> int:
    with ResearchWorkspaceStore(args.database) as store:
        authorization = require_production_authorization(store, args.product_id)
    _write_json(authorization.to_dict(), args.output)
    return 0


def _script_request(args: argparse.Namespace) -> int:
    disclosure = disclosure_template(locale=args.locale, network=args.network)
    with ResearchWorkspaceStore(args.database) as store:
        authorization = require_production_authorization(store, args.product_id)
        request = build_script_request(
            store,
            authorization,
            working_title=args.title,
            language=args.language,
            disclosure=disclosure,
        )
    _write_json(request.to_dict(), args.output)
    return 0


def _script_template(args: argparse.Namespace) -> int:
    disclosure = disclosure_template(locale=args.locale, network=args.network)
    with ResearchWorkspaceStore(args.database) as store:
        authorization = require_production_authorization(store, args.product_id)
        request = build_script_request(
            store,
            authorization,
            working_title=args.title,
            language=args.language,
            disclosure=disclosure,
        )
        script = generate_and_validate_script(
            store,
            authorization,
            request,
            StrictTemplateScriptGenerator(),
        )
    _write_json(script.to_dict(), args.output)
    return 0


def _artifact_records(
    spec_path: Path | None,
    *,
    root: Path | None,
) -> tuple[ArtifactRecord, ...]:
    if spec_path is None:
        return ()
    raw = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("artifact spec must contain a JSON array")
    records = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise TypeError(f"artifact spec item {index} must be an object")
        records.append(
            artifact_from_path(
                Path(str(item["path"])),
                logical_name=str(item["logical_name"]),
                kind=ArtifactKind(str(item["kind"])),
                media_type=str(item["media_type"]),
                root=root,
            )
        )
    return tuple(records)


def _package(args: argparse.Namespace) -> int:
    disclosure = disclosure_template(locale=args.locale, network=args.network)
    script = script_from_dict(_load_json(args.script))
    artifacts = _artifact_records(args.artifact_spec, root=args.artifact_root)
    with ResearchWorkspaceStore(args.database) as store:
        authorization = require_production_authorization(store, args.product_id)
        metadata = build_video_metadata(
            product_title=args.title,
            affiliate_url=args.affiliate_url,
            disclosure=disclosure,
            description_body=args.description_body,
            tags=tuple(args.tag),
        )
        thumbnail = build_thumbnail_brief(
            product_title=args.title,
            claim_ids=tuple(
                dict.fromkeys(
                    claim_id for segment in script.segments for claim_id in segment.claim_ids
                )
            ),
        )
        package = build_production_package(
            store,
            authorization,
            script=script,
            metadata=metadata,
            thumbnail=thumbnail,
            adapter_plans=build_dry_run_adapter_plans(script, thumbnail),
            artifacts=artifacts,
        )
    _write_json(package.to_dict(), args.output)
    return 0


def _signoff(args: argparse.Namespace) -> int:
    package = package_from_dict(_load_json(args.package))
    signoff = sign_production_package(package, actor=args.actor, reason=args.reason)
    _write_json(signoff.to_dict(), args.output)
    return 0


def _publish_dry_run(args: argparse.Namespace) -> int:
    package = package_from_dict(_load_json(args.package))
    signoff = None if args.signoff is None else signoff_from_dict(_load_json(args.signoff))
    with ResearchWorkspaceStore(args.database) as store:
        authorization = require_production_authorization(store, args.product_id)
        report = build_publish_dry_run(
            store,
            authorization,
            package,
            signoff,
            DryRunYouTubePublisher(),
            artifact_root=args.artifact_root,
            require_rendered_artifacts=not args.allow_missing_artifacts,
        )
    _write_json(report.to_dict(), args.output)
    return 0 if report.ready_for_live_adapter else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate-production",
        description=(
            "Build production plans only from current approved research; no live publishing "
            "adapter is included in v0.6."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    authorize = subparsers.add_parser("authorize")
    authorize.add_argument("database", type=Path)
    authorize.add_argument("product_id")
    authorize.add_argument("--output", type=Path)
    authorize.set_defaults(handler=_authorize)

    request = subparsers.add_parser("script-request")
    request.add_argument("database", type=Path)
    request.add_argument("product_id")
    request.add_argument("--title", required=True)
    request.add_argument("--language", default="de")
    request.add_argument("--locale", default="de-DE")
    request.add_argument("--network", default="affiliate")
    request.add_argument("--output", type=Path)
    request.set_defaults(handler=_script_request)

    template = subparsers.add_parser("script-template")
    template.add_argument("database", type=Path)
    template.add_argument("product_id")
    template.add_argument("--title", required=True)
    template.add_argument("--language", default="de")
    template.add_argument("--locale", default="de-DE")
    template.add_argument("--network", default="affiliate")
    template.add_argument("--output", type=Path)
    template.set_defaults(handler=_script_template)

    package = subparsers.add_parser("package")
    package.add_argument("database", type=Path)
    package.add_argument("product_id")
    package.add_argument("script", type=Path)
    package.add_argument("--title", required=True)
    package.add_argument("--affiliate-url", required=True)
    package.add_argument("--description-body", default="")
    package.add_argument("--tag", action="append", default=[])
    package.add_argument("--locale", default="de-DE")
    package.add_argument("--network", default="affiliate")
    package.add_argument("--artifact-spec", type=Path)
    package.add_argument("--artifact-root", type=Path)
    package.add_argument("--output", type=Path)
    package.set_defaults(handler=_package)

    signoff = subparsers.add_parser("signoff")
    signoff.add_argument("package", type=Path)
    signoff.add_argument("--actor", required=True)
    signoff.add_argument("--reason", required=True)
    signoff.add_argument("--output", type=Path)
    signoff.set_defaults(handler=_signoff)

    publish = subparsers.add_parser("publish-dry-run")
    publish.add_argument("database", type=Path)
    publish.add_argument("product_id")
    publish.add_argument("package", type=Path)
    publish.add_argument("--signoff", type=Path)
    publish.add_argument("--artifact-root", type=Path)
    publish.add_argument("--allow-missing-artifacts", action="store_true")
    publish.add_argument("--output", type=Path)
    publish.set_defaults(handler=_publish_dry_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
