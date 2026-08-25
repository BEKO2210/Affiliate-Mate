import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from affiliate_mate.ops_store import OpsStore
from affiliate_mate.workspace import create_workspace
from affiliate_mate.workspace_upgrade import (
    UpgradeError,
    apply_workspace_upgrade,
    plan_workspace_upgrade,
)

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)


def test_fresh_workspace_upgrade_initializes_known_schema_namespaces(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path)
    plan = plan_workspace_upgrade(workspace)

    assert plan.blocked is False
    assert plan.database_exists is False
    assert plan.initialize_evidence_schema is True
    assert plan.initialize_ops_schema is True

    result = apply_workspace_upgrade(workspace, confirmed=True, at=NOW)
    assert result.applied is True
    assert result.backup_path is None
    assert workspace.database_path.is_file()

    final_plan = plan_workspace_upgrade(workspace)
    assert final_plan.blocked is False
    assert final_plan.changes_required is False


def test_upgrade_requires_explicit_confirmation(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path)

    with pytest.raises(UpgradeError, match="explicit confirmation"):
        apply_workspace_upgrade(workspace, confirmed=False, at=NOW)


def test_existing_database_is_backed_up_before_mutation(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path)
    with OpsStore(workspace.database_path):
        pass

    result = apply_workspace_upgrade(workspace, confirmed=True, at=NOW)

    assert result.applied is True
    assert result.backup_path is not None
    backup = Path(result.backup_path)
    assert backup.is_file()
    assert backup.name == "pre-upgrade-20260825T100000Z.sqlite3"
    assert result.backup_sha256 is not None


def test_legacy_config_is_migrated_only_when_database_identity_matches(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path)
    workspace.config_path.write_text(
        json.dumps(
            {
                "schema_version": "affiliate-mate.config.v0",
                "database_path": ".affiliate-mate/state.sqlite3",
                "live_publishing": False,
                "telemetry_jsonl": ".affiliate-mate/events.jsonl",
            }
        ),
        encoding="utf-8",
    )

    plan = plan_workspace_upgrade(workspace)
    assert plan.config_needs_migration is True
    result = apply_workspace_upgrade(workspace, confirmed=True, at=NOW)
    assert result.applied is True

    config = json.loads(workspace.config_path.read_text(encoding="utf-8"))
    assert config["schema_version"] == "affiliate-mate.config.v1"


def test_upgrade_blocks_manifest_config_database_mismatch(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path)
    config = json.loads(workspace.config_path.read_text(encoding="utf-8"))
    config["database"]["path"] = "different.sqlite3"
    workspace.config_path.write_text(json.dumps(config), encoding="utf-8")

    plan = plan_workspace_upgrade(workspace)
    assert plan.blocked is True
    assert "different databases" in (plan.blocked_reason or "")

    with pytest.raises(UpgradeError, match="different databases"):
        apply_workspace_upgrade(workspace, confirmed=True, at=NOW)
