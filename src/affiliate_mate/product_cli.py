"""Unified product-facing command tree while preserving all legacy CLI shims."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .config_reference import config_reference_markdown, config_reference_payload
from .doctor import DoctorReport, run_doctor
from .exit_codes import ExitCode, exit_code_contract
from .onboarding import build_onboarding_plan, execute_onboarding
from .ops_config import AppConfig, ConfigError, DatabaseConfig, ObservabilityConfig, load_config
from .plugin_registry import plugin_health_payload, plugin_registry_payload
from .release_channel import ReleaseChannelError, resolve_release_channel
from .workspace import (
    Workspace,
    WorkspaceError,
    create_demo_workspace,
    create_workspace,
    find_workspace,
    load_workspace,
)
from .workspace_upgrade import UpgradeError, apply_workspace_upgrade, plan_workspace_upgrade

CommandMain = Callable[[list[str] | None], int]

_DELEGATED_COMMANDS = {
    "catalog": ("affiliate_mate.catalog_cli", "Catalog acquisition and normalization"),
    "intel": ("affiliate_mate.intelligence_cli", "Market-intelligence acquisition and replay"),
    "research": ("affiliate_mate.research_cli", "Evidence-backed research workspace"),
    "production": ("affiliate_mate.production_cli", "Human-approved production packages"),
    "learning": ("affiliate_mate.learning_cli", "Outcome evaluation and policy learning"),
    "ops": ("affiliate_mate.ops_cli", "Diagnostics, recovery, signing, and SBOMs"),
}
_CORE_COMMANDS = {"score", "analyze", "evidence"}
_TOP_LEVEL_COMMANDS = (
    "analyze",
    "catalog",
    "completion",
    "config",
    "contract",
    "demo",
    "doctor",
    "evidence",
    "init",
    "intel",
    "learning",
    "ops",
    "plugins",
    "production",
    "release",
    "research",
    "score",
    "status",
    "upgrade",
    "workspace",
)


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _write_text(text: str, output: Path | None = None) -> None:
    if output is None:
        print(text, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def _delegate(module_name: str, argv: list[str]) -> int:
    module = __import__(module_name, fromlist=["main"])
    main: CommandMain = module.main
    return int(main(argv))


def _top_help() -> str:
    delegated = "\n".join(
        f"  {name:<12} {description}" for name, (_, description) in _DELEGATED_COMMANDS.items()
    )
    return (
        "Affiliate-Mate — evidence-first affiliate research and production\n\n"
        "Usage:\n"
        "  affiliate-mate <command> [options]\n\n"
        "Product commands:\n"
        "  init         Guided local onboarding with safe defaults\n"
        "  workspace    Create, inspect, and resolve a portable workspace/profile\n"
        "  demo         Create a credential-free end-to-end demo workspace\n"
        "  status       Show current workspace state without mutating it\n"
        "  doctor       Run operational diagnostics for a workspace/config\n"
        "  plugins      Inspect and diagnose adapter capabilities\n"
        "  upgrade      Plan/apply backed-up workspace schema upgrades\n"
        "  config       Generate the current configuration reference\n"
        "  release      Inspect explicit stable/beta/dev channel policy\n"
        "  completion   Generate shell completion for bash, zsh, or fish\n"
        "  contract     Print stable machine-readable CLI contracts\n\n"
        "Domain commands:\n"
        f"{delegated}\n\n"
        "Compatibility commands:\n"
        "  score        Score candidates from CSV\n"
        "  analyze      Run gates, scoring, and sensitivity analysis\n"
        "  evidence     Manage the SQLite evidence store\n\n"
        "Global:\n"
        "  --version    Print the installed Affiliate-Mate version\n"
        "  --help       Show this help\n\n"
        "Every domain command keeps its previous standalone CLI as a compatibility shim.\n"
    )


def _init_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate init")
    parser.add_argument("path", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--profile", default="default")
    parser.add_argument("--marketplace", default="DE")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--channel", choices=("stable", "beta", "dev"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--plan", action="store_true", help="Show the onboarding plan only.")
    args = parser.parse_args(argv)
    try:
        plan = build_onboarding_plan(
            args.path,
            profile=args.profile,
            marketplace=args.marketplace,
            demo=args.demo,
            channel=args.channel,
        )
        if args.plan:
            _json(plan.to_dict())
            return ExitCode.OK
        workspace = execute_onboarding(plan, force=args.force)
    except (WorkspaceError, ReleaseChannelError) as exc:
        print(f"onboarding error: {exc}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR
    _json({"plan": plan.to_dict(), "workspace": workspace.to_dict()})
    return ExitCode.OK


def _workspace_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="affiliate-mate workspace")
    sub = parser.add_subparsers(dest="workspace_command", required=True)

    init = sub.add_parser("init", help="Initialize a portable workspace.")
    init.add_argument("path", type=Path, nargs="?", default=Path("."))
    init.add_argument("--profile", default="default")
    init.add_argument("--marketplace", default="DE")
    init.add_argument("--force", action="store_true")

    show = sub.add_parser("show", help="Show the resolved workspace manifest.")
    show.add_argument("path", type=Path, nargs="?", default=Path("."))
    show.add_argument("--profile")
    show.add_argument("--format", choices=("json", "text"), default="json")

    where = sub.add_parser("where", help="Find the nearest workspace root.")
    where.add_argument("path", type=Path, nargs="?")
    where.add_argument("--profile")
    return parser


def _workspace_command(argv: list[str]) -> int:
    args = _workspace_parser().parse_args(argv)
    try:
        if args.workspace_command == "init":
            workspace = create_workspace(
                args.path,
                profile_name=args.profile,
                marketplace=args.marketplace,
                force=args.force,
            )
            _json(workspace.to_dict())
            return ExitCode.OK
        if args.workspace_command == "show":
            workspace = load_workspace(args.path, profile=args.profile)
            if args.format == "json":
                _json(workspace.to_dict())
            else:
                print(workspace.root)
                print(f"profile={workspace.profile.name} marketplace={workspace.profile.marketplace}")
                print(f"config={workspace.config_path}")
                print(f"database={workspace.database_path}")
            return ExitCode.OK
        if args.workspace_command == "where":
            workspace = find_workspace(args.path, profile=args.profile)
            print(workspace.root)
            return ExitCode.OK
    except WorkspaceError as exc:
        print(f"workspace error: {exc}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR
    return ExitCode.INTERNAL_ERROR


def _demo_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate demo")
    sub = parser.add_subparsers(dest="demo_command", required=True)
    init = sub.add_parser("init", help="Create a deterministic credential-free demo workspace.")
    init.add_argument("path", type=Path)
    init.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        workspace = create_demo_workspace(args.path, force=args.force)
    except WorkspaceError as exc:
        print(f"workspace error: {exc}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR
    _json(
        {
            "workspace": workspace.to_dict(),
            "candidate_csv": str(workspace.data_dir / "products.csv"),
            "next": "affiliate-mate analyze data/products.csv --include-rejected",
        }
    )
    return ExitCode.OK


def _plugins_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate plugins")
    sub = parser.add_subparsers(dest="plugins_command", required=True)
    listed = sub.add_parser("list", help="List adapter/plugin capabilities without loading them.")
    listed.add_argument("--builtin-only", action="store_true")
    listed.add_argument("--format", choices=("json", "text"), default="text")
    doctor = sub.add_parser("doctor", help="Check adapter prerequisites without exposing secrets.")
    doctor.add_argument("--builtin-only", action="store_true")
    doctor.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)

    if args.plugins_command == "list":
        payload = plugin_registry_payload(include_external=not args.builtin_only)
        if args.format == "json":
            _json(payload)
        else:
            for plugin in payload["plugins"]:
                capabilities = ",".join(plugin["capabilities"])
                trust = "builtin" if plugin["trusted_builtin"] else plugin["source"]
                print(f"{plugin['name']:<24} {capabilities:<28} {trust}")
        return ExitCode.OK

    payload = plugin_health_payload(include_external=not args.builtin_only)
    if args.format == "json":
        _json(payload)
    else:
        for plugin in payload["plugins"]:
            print(f"[{plugin['status']:<13}] {plugin['name']}: {plugin['message']}")
            missing = plugin["missing_requirements"]
            if missing:
                print(f"                  missing: {', '.join(missing)}")
    return ExitCode.OK if payload["healthy"] else ExitCode.CHECK_FAILED


def _status_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate status")
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--profile")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    try:
        workspace = find_workspace(args.path, profile=args.profile)
    except WorkspaceError as exc:
        print(f"workspace error: {exc}", file=sys.stderr)
        return ExitCode.NOT_FOUND
    state = {
        "schema_version": "affiliate-mate.status.v1",
        "version": __version__,
        "workspace": str(workspace.root),
        "profile": workspace.profile.name,
        "marketplace": workspace.profile.marketplace,
        "paths": {
            "manifest": {
                "path": str(workspace.root / ".affiliate-mate" / "workspace.json"),
                "exists": True,
            },
            "config": {"path": str(workspace.config_path), "exists": workspace.config_path.is_file()},
            "database": {
                "path": str(workspace.database_path),
                "exists": workspace.database_path.is_file(),
            },
            "data": {"path": str(workspace.data_dir), "exists": workspace.data_dir.is_dir()},
            "artifacts": {
                "path": str(workspace.artifacts_dir),
                "exists": workspace.artifacts_dir.is_dir(),
            },
        },
    }
    if args.format == "json":
        _json(state)
    else:
        print(f"Affiliate-Mate {__version__}")
        print(f"workspace: {state['workspace']}")
        print(f"profile:   {state['profile']} ({state['marketplace']})")
        for name, item in state["paths"].items():
            marker = "ok" if item["exists"] else "missing"
            print(f"{name:<9} [{marker:<7}] {item['path']}")
    return ExitCode.OK


def _doctor_text(report: DoctorReport) -> str:
    lines: list[str] = []
    for check in report.checks:
        lines.append(f"[{check.status.value.upper():4}] {check.code}: {check.message}")
        if check.remediation:
            lines.append(f"       remediation: {check.remediation}")
    lines.append(
        f"summary: healthy={str(report.healthy).lower()} "
        f"warnings={report.warning_count} failures={report.failure_count}"
    )
    return "\n".join(lines) + "\n"


def _resolved_observability(workspace: Workspace, raw: str | None) -> str | None:
    if raw is None:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return str(path)
    return str(workspace.resolve(raw))


def _doctor_command(argv: list[str]) -> int:
    if "--config" in argv:
        return _delegate("affiliate_mate.ops_cli", ["doctor", *argv])
    parser = argparse.ArgumentParser(prog="affiliate-mate doctor")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        workspace = find_workspace(args.workspace, profile=args.profile)
    except WorkspaceError as exc:
        if args.workspace is None and args.profile is None:
            return _delegate("affiliate_mate.ops_cli", ["doctor", *argv])
        print(f"workspace error: {exc}", file=sys.stderr)
        return ExitCode.NOT_FOUND
    try:
        loaded = load_config(workspace.config_path, env={})
        config = AppConfig(
            database=DatabaseConfig(path=str(workspace.database_path)),
            features=loaded.features,
            observability=ObservabilityConfig(
                jsonl_path=_resolved_observability(workspace, loaded.observability.jsonl_path)
            ),
        )
    except (ConfigError, WorkspaceError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR

    report = run_doctor(config)
    if args.format == "json":
        text = json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    else:
        text = _doctor_text(report)
    _write_text(text, args.output)
    return report.exit_code


def _upgrade_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate upgrade")
    sub = parser.add_subparsers(dest="upgrade_command", required=True)
    plan_parser = sub.add_parser("plan", help="Inspect required workspace migrations.")
    plan_parser.add_argument("path", type=Path, nargs="?")
    plan_parser.add_argument("--profile")
    apply_parser = sub.add_parser("apply", help="Backup, migrate, and verify a workspace.")
    apply_parser.add_argument("path", type=Path, nargs="?")
    apply_parser.add_argument("--profile")
    apply_parser.add_argument("--yes", action="store_true", help="Confirm all planned mutations.")
    args = parser.parse_args(argv)
    try:
        workspace = find_workspace(args.path, profile=args.profile)
        if args.upgrade_command == "plan":
            plan = plan_workspace_upgrade(workspace)
            _json(plan.to_dict())
            return ExitCode.CHECK_FAILED if plan.blocked else ExitCode.OK
        result = apply_workspace_upgrade(workspace, confirmed=args.yes)
        _json(result.to_dict())
        return ExitCode.OK
    except WorkspaceError as exc:
        print(f"workspace error: {exc}", file=sys.stderr)
        return ExitCode.NOT_FOUND
    except UpgradeError as exc:
        print(f"upgrade error: {exc}", file=sys.stderr)
        return ExitCode.CHECK_FAILED


def _config_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate config")
    sub = parser.add_subparsers(dest="config_command", required=True)
    reference = sub.add_parser("reference", help="Generate the current config contract.")
    reference.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    if args.format == "json":
        _json(config_reference_payload())
    else:
        print(config_reference_markdown(), end="")
    return ExitCode.OK


def _release_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate release")
    sub = parser.add_subparsers(dest="release_command", required=True)
    channel = sub.add_parser("channel", help="Resolve explicit stable/beta/dev channel policy.")
    channel.add_argument("--channel", choices=("stable", "beta", "dev"))
    channel.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    try:
        state = resolve_release_channel(args.channel)
    except ReleaseChannelError as exc:
        print(f"release channel error: {exc}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR
    if args.format == "json":
        _json(state.to_dict())
    else:
        print(f"{state.channel.value} ({state.version}, source={state.source})")
    return ExitCode.OK


def _completion_script(shell: str) -> str:
    words = " ".join(_TOP_LEVEL_COMMANDS)
    if shell == "bash":
        return (
            "_affiliate_mate() {\n"
            "  local cur=${COMP_WORDS[COMP_CWORD]}\n"
            f"  COMPREPLY=( $(compgen -W \"{words}\" -- \"$cur\") )\n"
            "}\n"
            "complete -F _affiliate_mate affiliate-mate\n"
        )
    if shell == "zsh":
        return (
            "#compdef affiliate-mate\n"
            "_affiliate_mate() {\n"
            f"  local -a commands; commands=({words})\n"
            "  _describe 'command' commands\n"
            "}\n"
            "compdef _affiliate_mate affiliate-mate\n"
        )
    return "complete -c affiliate-mate -f -a '" + words + "'\n"


def _completion_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate completion")
    parser.add_argument("shell", choices=("bash", "zsh", "fish"))
    args = parser.parse_args(argv)
    print(_completion_script(args.shell), end="")
    return ExitCode.OK


def _contract_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="affiliate-mate contract")
    parser.add_argument("name", choices=("exit-codes",))
    parser.parse_args(argv)
    _json(exit_code_contract())
    return ExitCode.OK


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw[0] in {"-h", "--help"}:
        print(_top_help(), end="")
        return ExitCode.OK
    if raw[0] in {"-V", "--version"}:
        print(__version__)
        return ExitCode.OK

    command, rest = raw[0], raw[1:]
    if command in _CORE_COMMANDS:
        return _delegate("affiliate_mate.cli", raw)
    if command in _DELEGATED_COMMANDS:
        return _delegate(_DELEGATED_COMMANDS[command][0], rest)
    if command == "init":
        return int(_init_command(rest))
    if command == "workspace":
        return int(_workspace_command(rest))
    if command == "demo":
        return int(_demo_command(rest))
    if command == "plugins":
        return int(_plugins_command(rest))
    if command == "status":
        return int(_status_command(rest))
    if command == "doctor":
        return int(_doctor_command(rest))
    if command == "upgrade":
        return int(_upgrade_command(rest))
    if command == "config":
        return int(_config_command(rest))
    if command == "release":
        return int(_release_command(rest))
    if command == "completion":
        return int(_completion_command(rest))
    if command == "contract":
        return int(_contract_command(rest))

    print(f"unknown command: {command}\n", file=sys.stderr)
    print(_top_help(), file=sys.stderr, end="")
    return ExitCode.CONFIG_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
