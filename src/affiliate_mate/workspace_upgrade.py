"""Fail-closed workspace/config/database upgrade planning and application."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evidence import SQLiteEvidenceStore
from .ops_backup import backup_database, inspect_sqlite
from .ops_config import AppConfig, ConfigError
from .ops_store import OpsStore
from .workspace import Workspace, WorkspaceError

UPGRADE_PLAN_SCHEMA_VERSION = "affiliate-mate.upgrade-plan.v1"
UPGRADE_RESULT_SCHEMA_VERSION = "affiliate-mate.upgrade-result.v1"


class UpgradeError(RuntimeError):
    """Raised when an upgrade cannot be performed safely."""


@dataclass(frozen=True, slots=True)
class UpgradePlan:
    workspace: str
    config_needs_migration: bool
    database_exists: bool
    initialize_evidence_schema: bool
    initialize_ops_schema: bool
    blocked: bool
    blocked_reason: str | None
    actions: tuple[str, ...]

    @property
    def changes_required(self) -> bool:
        return bool(self.actions)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": UPGRADE_PLAN_SCHEMA_VERSION,
            "workspace": self.workspace,
            "config_needs_migration": self.config_needs_migration,
            "database_exists": self.database_exists,
            "initialize_evidence_schema": self.initialize_evidence_schema,
            "initialize_ops_schema": self.initialize_ops_schema,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "changes_required": self.changes_required,
            "actions": list(self.actions),
        }


@dataclass(frozen=True, slots=True)
class UpgradeResult:
    plan: UpgradePlan
    applied: bool
    backup_path: str | None
    backup_sha256: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": UPGRADE_RESULT_SCHEMA_VERSION,
            "applied": self.applied,
            "backup_path": self.backup_path,
            "backup_sha256": self.backup_sha256,
            "plan": self.plan.to_dict(),
        }


def _load_raw_config(path: Path) -> dict[str, object]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UpgradeError(f"workspace config does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UpgradeError(f"workspace config is not valid JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise UpgradeError("workspace config root must be a JSON object")
    return raw


def _resolve_workspace_path(workspace: Workspace, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    return (workspace.root / path).resolve(strict=False)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        tmp.unlink(missing_ok=True)
        raise


def plan_workspace_upgrade(workspace: Workspace) -> UpgradePlan:
    raw = _load_raw_config(workspace.config_path)
    try:
        migrated = AppConfig.from_dict(raw)
    except ConfigError as exc:
        return UpgradePlan(
            workspace=str(workspace.root),
            config_needs_migration=False,
            database_exists=workspace.database_path.is_file(),
            initialize_evidence_schema=False,
            initialize_ops_schema=False,
            blocked=True,
            blocked_reason=f"configuration cannot be migrated safely: {exc}",
            actions=(),
        )

    configured_database = _resolve_workspace_path(workspace, migrated.database.path)
    if configured_database != workspace.database_path.resolve(strict=False):
        return UpgradePlan(
            workspace=str(workspace.root),
            config_needs_migration=raw != migrated.to_dict(),
            database_exists=workspace.database_path.is_file(),
            initialize_evidence_schema=False,
            initialize_ops_schema=False,
            blocked=True,
            blocked_reason=(
                "workspace manifest and operational configuration resolve to different databases"
            ),
            actions=(),
        )

    database_exists = workspace.database_path.is_file()
    tables: set[str] = set()
    if database_exists:
        health = inspect_sqlite(workspace.database_path)
        if not health.integrity_ok or health.foreign_key_violations:
            return UpgradePlan(
                workspace=str(workspace.root),
                config_needs_migration=raw != migrated.to_dict(),
                database_exists=True,
                initialize_evidence_schema=False,
                initialize_ops_schema=False,
                blocked=True,
                blocked_reason=(
                    "database integrity/foreign-key checks must pass before an upgrade"
                ),
                actions=(),
            )
        tables = set(health.tables)

    config_needs_migration = raw != migrated.to_dict()
    initialize_evidence = "schema_meta" not in tables
    initialize_ops = "ops_schema_meta" not in tables
    actions: list[str] = []
    if config_needs_migration:
        actions.append("migrate configuration to current schema")
    if initialize_evidence:
        actions.append("initialize evidence schema namespace")
    if initialize_ops:
        actions.append("initialize operational schema namespace")
    return UpgradePlan(
        workspace=str(workspace.root),
        config_needs_migration=config_needs_migration,
        database_exists=database_exists,
        initialize_evidence_schema=initialize_evidence,
        initialize_ops_schema=initialize_ops,
        blocked=False,
        blocked_reason=None,
        actions=tuple(actions),
    )


def apply_workspace_upgrade(
    workspace: Workspace,
    *,
    confirmed: bool,
    at: datetime | None = None,
) -> UpgradeResult:
    """Apply a planned upgrade only after explicit confirmation and pre-mutation backup."""

    if not confirmed:
        raise UpgradeError("upgrade apply requires explicit confirmation")
    plan = plan_workspace_upgrade(workspace)
    if plan.blocked:
        raise UpgradeError(plan.blocked_reason or "upgrade plan is blocked")
    if not plan.changes_required:
        return UpgradeResult(plan=plan, applied=False, backup_path=None, backup_sha256=None)

    moment = datetime.now(UTC) if at is None else at
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise UpgradeError("upgrade timestamp must be timezone-aware")

    backup_path: Path | None = None
    backup_sha256: str | None = None
    if workspace.database_path.is_file():
        stamp = moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = workspace.artifacts_dir / "backups" / f"pre-upgrade-{stamp}.sqlite3"
        manifest = backup_database(
            workspace.database_path,
            backup_path,
            created_at=moment,
            overwrite=False,
        )
        backup_sha256 = manifest.sha256

    raw = _load_raw_config(workspace.config_path)
    migrated = AppConfig.from_dict(raw)
    if plan.config_needs_migration:
        _atomic_write_json(workspace.config_path, migrated.to_dict())

    if plan.initialize_evidence_schema:
        with SQLiteEvidenceStore(workspace.database_path):
            pass
    if plan.initialize_ops_schema:
        with OpsStore(workspace.database_path):
            pass

    final_plan = plan_workspace_upgrade(workspace)
    if final_plan.blocked or final_plan.changes_required:
        raise UpgradeError("post-upgrade verification did not converge to a clean plan")
    return UpgradeResult(
        plan=final_plan,
        applied=True,
        backup_path=None if backup_path is None else str(backup_path),
        backup_sha256=backup_sha256,
    )
