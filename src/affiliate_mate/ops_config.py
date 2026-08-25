"""Strict, versioned operational configuration with explicit migrations."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Self

from .learning_models import sha256_json

CONFIG_SCHEMA_V0 = "affiliate-mate.config.v0"
CONFIG_SCHEMA_V1 = "affiliate-mate.config.v1"
CONFIG_SCHEMA_VERSION = CONFIG_SCHEMA_V1


class ConfigError(ValueError):
    """Raised when configuration is ambiguous, unsupported, or invalid."""


def _strict_keys(payload: Mapping[str, object], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError(f"unknown {context} keys: {', '.join(unknown)}")


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be one of true/false/1/0/yes/no/on/off")


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    path: str = "affiliate-mate.sqlite3"

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ConfigError("database.path must not be empty")


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    live_publishing: bool = False


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    jsonl_path: str | None = None

    def __post_init__(self) -> None:
        if self.jsonl_path is not None and not self.jsonl_path.strip():
            raise ConfigError("observability.jsonl_path must not be blank")


@dataclass(frozen=True, slots=True)
class AppConfig:
    schema_version: str = CONFIG_SCHEMA_VERSION
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    def __post_init__(self) -> None:
        if self.schema_version != CONFIG_SCHEMA_VERSION:
            raise ConfigError(f"unsupported config schema: {self.schema_version}")

    @property
    def digest(self) -> str:
        return sha256_json(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "database": asdict(self.database),
            "features": asdict(self.features),
            "observability": asdict(self.observability),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> Self:
        migrated = migrate_config(raw)
        _strict_keys(
            migrated,
            {"schema_version", "database", "features", "observability"},
            "top-level config",
        )
        database_raw = migrated.get("database", {})
        features_raw = migrated.get("features", {})
        observability_raw = migrated.get("observability", {})
        if not isinstance(database_raw, dict):
            raise ConfigError("database must be an object")
        if not isinstance(features_raw, dict):
            raise ConfigError("features must be an object")
        if not isinstance(observability_raw, dict):
            raise ConfigError("observability must be an object")
        _strict_keys(database_raw, {"path"}, "database")
        _strict_keys(features_raw, {"live_publishing"}, "features")
        _strict_keys(observability_raw, {"jsonl_path"}, "observability")
        return cls(
            schema_version=str(migrated["schema_version"]),
            database=DatabaseConfig(path=str(database_raw.get("path", "affiliate-mate.sqlite3"))),
            features=FeatureFlags(
                live_publishing=bool(features_raw.get("live_publishing", False))
            ),
            observability=ObservabilityConfig(
                jsonl_path=(
                    None
                    if observability_raw.get("jsonl_path") is None
                    else str(observability_raw["jsonl_path"])
                )
            ),
        )


def migrate_config(raw: Mapping[str, object]) -> dict[str, object]:
    """Migrate supported historical config shapes to the current schema."""

    payload = dict(raw)
    schema = payload.get("schema_version")
    if schema is None or schema == CONFIG_SCHEMA_V0:
        _strict_keys(
            payload,
            {"schema_version", "database_path", "live_publishing", "telemetry_jsonl"},
            "legacy config",
        )
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "database": {"path": str(payload.get("database_path", "affiliate-mate.sqlite3"))},
            "features": {"live_publishing": bool(payload.get("live_publishing", False))},
            "observability": {"jsonl_path": payload.get("telemetry_jsonl")},
        }
    if schema != CONFIG_SCHEMA_VERSION:
        raise ConfigError(f"unsupported config schema: {schema}")
    return payload


def load_config(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load JSON config and apply a small, explicit environment override surface."""

    values = os.environ if env is None else env
    if path is None:
        config = AppConfig()
    else:
        config_path = Path(path).expanduser()
        try:
            raw: Any = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"config file does not exist: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"config file is not valid JSON: {config_path}") from exc
        if not isinstance(raw, dict):
            raise ConfigError("config root must be a JSON object")
        config = AppConfig.from_dict(raw)

    database = config.database
    features = config.features
    observability = config.observability
    if values.get("AFFILIATE_MATE_DB", "").strip():
        database = DatabaseConfig(path=values["AFFILIATE_MATE_DB"].strip())
    if "AFFILIATE_MATE_LIVE_PUBLISHING" in values:
        features = FeatureFlags(
            live_publishing=_parse_bool(
                values["AFFILIATE_MATE_LIVE_PUBLISHING"],
                "AFFILIATE_MATE_LIVE_PUBLISHING",
            )
        )
    if "AFFILIATE_MATE_TELEMETRY_JSONL" in values:
        raw_path = values["AFFILIATE_MATE_TELEMETRY_JSONL"].strip()
        observability = ObservabilityConfig(jsonl_path=raw_path or None)
    return AppConfig(database=database, features=features, observability=observability)


def require_live_publishing_enabled(config: AppConfig) -> None:
    """Central fail-closed feature gate for any future side-effecting publisher."""

    if not config.features.live_publishing:
        raise PermissionError(
            "live publishing is disabled; set the explicit operational feature flag first"
        )
