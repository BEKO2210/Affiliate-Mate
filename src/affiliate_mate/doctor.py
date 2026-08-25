"""Deterministic environment and SQLite diagnostics for operational readiness."""

from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .ops_backup import inspect_sqlite, sqlite_readonly_uri
from .ops_config import AppConfig

DOCTOR_SCHEMA_VERSION = "affiliate-mate.doctor-report.v1"


class CheckStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    code: str
    status: CheckStatus
    message: str
    remediation: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "status": self.status.value,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass(frozen=True, slots=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]

    @property
    def healthy(self) -> bool:
        return all(check.status is not CheckStatus.FAIL for check in self.checks)

    @property
    def warning_count(self) -> int:
        return sum(check.status is CheckStatus.WARN for check in self.checks)

    @property
    def failure_count(self) -> int:
        return sum(check.status is CheckStatus.FAIL for check in self.checks)

    @property
    def exit_code(self) -> int:
        return 0 if self.healthy else 2

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": DOCTOR_SCHEMA_VERSION,
            "healthy": self.healthy,
            "warning_count": self.warning_count,
            "failure_count": self.failure_count,
            "checks": [check.to_dict() for check in self.checks],
        }


def _database_schema_checks(path: Path) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    health = inspect_sqlite(path)
    if health.integrity_ok:
        checks.append(
            DoctorCheck(
                "sqlite.integrity",
                CheckStatus.PASS,
                "SQLite integrity_check passed.",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                "sqlite.integrity",
                CheckStatus.FAIL,
                f"SQLite integrity_check failed: {health.integrity_message}",
                "Restore a validated backup before continuing writes.",
            )
        )
    if health.foreign_key_violations == 0:
        checks.append(
            DoctorCheck(
                "sqlite.foreign_keys",
                CheckStatus.PASS,
                "No foreign-key violations found.",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                "sqlite.foreign_keys",
                CheckStatus.FAIL,
                f"SQLite foreign_key_check found {health.foreign_key_violations} violation(s).",
                "Inspect the violating rows before relying on lineage or approval state.",
            )
        )

    connection = sqlite3.connect(sqlite_readonly_uri(path), uri=True)
    try:
        meta_tables = {
            "schema_meta": "evidence",
            "research_schema_meta": "research",
            "learning_schema_meta": "learning",
            "ops_schema_meta": "ops",
        }
        table_names = set(health.tables)
        discovered = 0
        for table, namespace in meta_tables.items():
            if table not in table_names:
                continue
            discovered += 1
            row = connection.execute(
                f"SELECT value FROM {table} WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                checks.append(
                    DoctorCheck(
                        f"schema.{namespace}",
                        CheckStatus.FAIL,
                        f"{namespace} schema metadata exists without a schema_version row.",
                    )
                )
            else:
                checks.append(
                    DoctorCheck(
                        f"schema.{namespace}",
                        CheckStatus.PASS,
                        f"{namespace} schema version is {row[0]}.",
                    )
                )
        if discovered == 0:
            checks.append(
                DoctorCheck(
                    "schema.namespaces",
                    CheckStatus.WARN,
                    "Database is valid SQLite but no Affiliate-Mate schema namespace was found.",
                    "Initialize the required Affiliate-Mate stores before production use.",
                )
            )
    finally:
        connection.close()
    return checks


def run_doctor(
    config: AppConfig,
    *,
    env: Mapping[str, str] | None = None,
) -> DoctorReport:
    """Run side-effect-free checks. Secret values are never included in the report."""

    values = os.environ if env is None else env
    checks: list[DoctorCheck] = [
        DoctorCheck(
            "python.version",
            CheckStatus.PASS,
            f"Python {sys.version_info.major}.{sys.version_info.minor} is supported.",
        )
    ]

    checks.append(
        DoctorCheck(
            "config.schema",
            CheckStatus.PASS,
            f"Configuration schema is {config.schema_version}; digest={config.digest[:12]}…",
        )
    )

    db_path = Path(config.database.path).expanduser()
    if db_path.exists():
        if not db_path.is_file():
            checks.append(
                DoctorCheck(
                    "database.path",
                    CheckStatus.FAIL,
                    f"Configured database path is not a regular file: {db_path}",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    "database.path",
                    CheckStatus.PASS,
                    f"Database exists: {db_path}",
                )
            )
            try:
                checks.extend(_database_schema_checks(db_path))
            except (sqlite3.Error, RuntimeError) as exc:
                checks.append(
                    DoctorCheck(
                        "database.open",
                        CheckStatus.FAIL,
                        f"Database diagnostics failed: {type(exc).__name__}: {exc}",
                        (
                            "Verify the path and restore from a validated backup if corruption "
                            "is suspected."
                        ),
                    )
                )
    else:
        parent = db_path.parent if str(db_path.parent) else Path(".")
        writable = parent.exists() and os.access(parent, os.W_OK)
        checks.append(
            DoctorCheck(
                "database.path",
                CheckStatus.WARN if writable else CheckStatus.FAIL,
                f"Database does not exist yet: {db_path}",
                (
                    "Initialize the stores before use."
                    if writable
                    else "Create the parent directory or fix write permissions."
                ),
            )
        )

    if config.features.live_publishing:
        checks.append(
            DoctorCheck(
                "feature.live_publishing",
                CheckStatus.WARN,
                "Live publishing feature flag is enabled.",
                (
                    "Keep it disabled unless a reviewed side-effecting publisher is "
                    "intentionally in use."
                ),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                "feature.live_publishing",
                CheckStatus.PASS,
                "Live publishing is disabled by default.",
            )
        )

    secret_names = (
        "AMAZON_CREATORS_CREDENTIAL_ID",
        "AMAZON_CREATORS_CREDENTIAL_SECRET",
        "AMAZON_ASSOCIATE_TAG",
        "YOUTUBE_API_KEY",
    )
    present = sum(bool(values.get(name, "").strip()) for name in secret_names)
    checks.append(
        DoctorCheck(
            "secrets.optional_providers",
            CheckStatus.PASS,
            (
                f"{present}/{len(secret_names)} optional provider secret variables are present; "
                "values hidden."
            ),
        )
    )

    if config.observability.jsonl_path is None:
        checks.append(
            DoctorCheck(
                "observability.jsonl",
                CheckStatus.WARN,
                "Structured JSONL telemetry is not configured.",
                "Configure observability.jsonl_path for durable local operational events.",
            )
        )
    else:
        telemetry_path = Path(config.observability.jsonl_path).expanduser()
        parent = telemetry_path.parent
        writable = parent.exists() and os.access(parent, os.W_OK)
        checks.append(
            DoctorCheck(
                "observability.jsonl",
                CheckStatus.PASS if writable else CheckStatus.WARN,
                f"Telemetry target: {telemetry_path}",
                None if writable else "Create the telemetry parent directory or fix permissions.",
            )
        )

    return DoctorReport(checks=tuple(checks))
