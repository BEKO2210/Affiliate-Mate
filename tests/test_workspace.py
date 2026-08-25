import json
from pathlib import Path

import pytest

from affiliate_mate.workspace import (
    WORKSPACE_SCHEMA_VERSION,
    WorkspaceError,
    WorkspaceProfile,
    create_demo_workspace,
    create_workspace,
    find_workspace,
    load_workspace,
)


def test_workspace_round_trip_and_resolved_paths(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path, profile_name="creator", marketplace="de")

    loaded = load_workspace(tmp_path)
    assert loaded.manifest.schema_version == WORKSPACE_SCHEMA_VERSION
    assert loaded.profile.name == "creator"
    assert loaded.profile.marketplace == "DE"
    assert loaded.config_path == tmp_path / ".affiliate-mate" / "config.json"
    assert loaded.database_path == tmp_path / ".affiliate-mate" / "state.sqlite3"
    assert workspace.to_dict() == loaded.to_dict()

    config = json.loads(loaded.config_path.read_text(encoding="utf-8"))
    assert config["features"]["live_publishing"] is False


def test_workspace_manifest_is_strict_and_rejects_unknown_keys(tmp_path: Path) -> None:
    create_workspace(tmp_path)
    manifest_path = tmp_path / ".affiliate-mate" / "workspace.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["secret"] = "must-not-be-accepted"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(WorkspaceError, match="unknown workspace keys"):
        load_workspace(tmp_path)


def test_workspace_profile_rejects_path_escape() -> None:
    with pytest.raises(WorkspaceError, match="must not contain"):
        WorkspaceProfile(database_path="../outside.sqlite3")


def test_workspace_init_is_fail_closed_without_force(tmp_path: Path) -> None:
    create_workspace(tmp_path)
    with pytest.raises(WorkspaceError, match="already exists"):
        create_workspace(tmp_path)


def test_find_workspace_walks_upward(tmp_path: Path) -> None:
    create_workspace(tmp_path, profile_name="default")
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)

    found = find_workspace(nested)
    assert found.root == tmp_path.resolve()


def test_profile_selection_is_explicit(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path, profile_name="primary")
    raw = workspace.manifest.to_dict()
    raw["profiles"].append(
        WorkspaceProfile(
            name="secondary",
            marketplace="US",
            config_path="profiles/secondary/config.json",
            database_path="profiles/secondary/state.sqlite3",
            data_dir="profiles/secondary/data",
            artifacts_dir="profiles/secondary/artifacts",
        ).to_dict()
    )
    manifest_path = tmp_path / ".affiliate-mate" / "workspace.json"
    manifest_path.write_text(json.dumps(raw), encoding="utf-8")

    selected = load_workspace(tmp_path, profile="secondary")
    assert selected.profile.name == "secondary"
    assert selected.profile.marketplace == "US"


def test_demo_workspace_is_credential_free_and_deterministic(tmp_path: Path) -> None:
    workspace = create_demo_workspace(tmp_path)
    csv_path = workspace.data_dir / "products.csv"
    first = csv_path.read_text(encoding="utf-8")

    assert "DEMO-001" in first
    assert "API_KEY" not in first
    assert "SECRET" not in first
    assert workspace.profile.name == "demo"
    assert (tmp_path / "DEMO.md").is_file()

    create_demo_workspace(tmp_path, force=True)
    assert csv_path.read_text(encoding="utf-8") == first
