import json

import pytest

from affiliate_mate.ops_config import (
    AppConfig,
    ConfigError,
    load_config,
    require_live_publishing_enabled,
)


def test_default_config_is_fail_closed() -> None:
    config = AppConfig()
    assert config.schema_version == "affiliate-mate.config.v1"
    assert config.database.path == "affiliate-mate.sqlite3"
    assert not config.features.live_publishing
    assert len(config.digest) == 64


def test_config_rejects_unknown_keys() -> None:
    with pytest.raises(ConfigError, match="unknown top-level config keys"):
        AppConfig.from_dict(
            {
                "schema_version": "affiliate-mate.config.v1",
                "database": {},
                "features": {},
                "observability": {},
                "surprise": True,
            }
        )


def test_config_rejects_string_that_looks_like_boolean() -> None:
    with pytest.raises(ConfigError, match="JSON boolean"):
        AppConfig.from_dict(
            {
                "schema_version": "affiliate-mate.config.v1",
                "database": {},
                "features": {"live_publishing": "false"},
                "observability": {},
            }
        )


def test_config_rejects_non_string_database_path() -> None:
    with pytest.raises(ConfigError, match="database.path must be a string"):
        AppConfig.from_dict(
            {
                "schema_version": "affiliate-mate.config.v1",
                "database": {"path": 123},
                "features": {},
                "observability": {},
            }
        )


def test_legacy_config_migrates_explicitly(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "affiliate-mate.config.v0",
                "database_path": "legacy.sqlite3",
                "live_publishing": False,
                "telemetry_jsonl": "events.jsonl",
            }
        ),
        encoding="utf-8",
    )
    config = load_config(path, env={})
    assert config.schema_version == "affiliate-mate.config.v1"
    assert config.database.path == "legacy.sqlite3"
    assert config.observability.jsonl_path == "events.jsonl"


def test_environment_overrides_are_explicit(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "affiliate-mate.config.v1",
                "database": {"path": "file.sqlite3"},
                "features": {"live_publishing": False},
                "observability": {"jsonl_path": None},
            }
        ),
        encoding="utf-8",
    )
    config = load_config(
        path,
        env={
            "AFFILIATE_MATE_DB": "env.sqlite3",
            "AFFILIATE_MATE_LIVE_PUBLISHING": "true",
            "AFFILIATE_MATE_TELEMETRY_JSONL": "ops.jsonl",
        },
    )
    assert config.database.path == "env.sqlite3"
    assert config.features.live_publishing
    assert config.observability.jsonl_path == "ops.jsonl"


def test_invalid_environment_boolean_is_rejected() -> None:
    with pytest.raises(ConfigError, match="AFFILIATE_MATE_LIVE_PUBLISHING"):
        load_config(env={"AFFILIATE_MATE_LIVE_PUBLISHING": "sometimes"})


def test_live_publishing_requires_explicit_flag() -> None:
    with pytest.raises(PermissionError, match="live publishing is disabled"):
        require_live_publishing_enabled(AppConfig())
