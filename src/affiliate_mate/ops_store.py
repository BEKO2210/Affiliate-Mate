"""Crash-safe operational job checkpoints and external idempotency claims."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from .learning_models import canonical_json, sha256_json

OPS_DB_SCHEMA_VERSION = "1"


class OpsConflictError(RuntimeError):
    """Raised when immutable job/idempotency identity is reused inconsistently."""


class JobState(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IdempotencyState(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _iso(value: datetime) -> str:
    _require_aware(value, "timestamp")
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("stored operational timestamp is not timezone-aware")
    return parsed.astimezone(UTC)


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_key: str
    kind: str
    payload_digest: str
    state: JobState
    checkpoint: dict[str, Any]
    result: dict[str, Any] | None
    version: int
    created_at: datetime
    updated_at: datetime
    last_error: str | None

    @property
    def resumable(self) -> bool:
        return self.state is JobState.RUNNING

    def to_dict(self) -> dict[str, object]:
        return {
            "job_key": self.job_key,
            "kind": self.kind,
            "payload_digest": self.payload_digest,
            "state": self.state.value,
            "checkpoint": dict(self.checkpoint),
            "result": None if self.result is None else dict(self.result),
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_error": self.last_error,
            "resumable": self.resumable,
        }


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    operation: str
    key: str
    request_digest: str
    state: IdempotencyState
    response_digest: str | None
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "key": self.key,
            "request_digest": self.request_digest,
            "state": self.state.value,
            "response_digest": self.response_digest,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class OpsStore:
    """SQLite operational state isolated from business/evidence truth."""

    def __init__(self, path: str | Path) -> None:
        raw = str(path)
        self.path = raw if raw == ":memory:" else str(Path(raw).expanduser())
        self._connection: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        if self.path != ":memory:":
            Path(self.path).resolve().parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if self.path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
        self._connection = connection
        return connection

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def initialize(self) -> None:
        connection = self._connect()
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ops_schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_jobs (
                    job_key TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('running', 'succeeded', 'failed')),
                    checkpoint_json TEXT NOT NULL,
                    result_json TEXT,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_ops_jobs_state_updated
                    ON ops_jobs(state, updated_at);

                CREATE TABLE IF NOT EXISTS ops_idempotency (
                    operation TEXT NOT NULL,
                    key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('started', 'completed')),
                    response_digest TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(operation, key)
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM ops_schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO ops_schema_meta(key, value) VALUES ('schema_version', ?)",
                    (OPS_DB_SCHEMA_VERSION,),
                )
            elif row["value"] != OPS_DB_SCHEMA_VERSION:
                raise RuntimeError(
                    "unsupported ops schema version: "
                    f"{row['value']} != {OPS_DB_SCHEMA_VERSION}"
                )

    def begin_job(
        self,
        *,
        job_key: str,
        kind: str,
        payload: dict[str, Any],
        at: datetime,
    ) -> tuple[JobRecord, bool]:
        """Start once; identical replay returns the existing job without mutation."""

        self.initialize()
        normalized_key = _require_text(job_key, "job_key")
        normalized_kind = _require_text(kind, "kind")
        _require_aware(at, "at")
        payload_digest = sha256_json(payload)
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT * FROM ops_jobs WHERE job_key = ?",
                (normalized_key,),
            ).fetchone()
            if existing is not None:
                record = self._job_from_row(existing)
                if record.kind != normalized_kind or record.payload_digest != payload_digest:
                    raise OpsConflictError(
                        f"job_key {normalized_key!r} already exists for different input"
                    )
                connection.commit()
                return record, False
            connection.execute(
                """
                INSERT INTO ops_jobs(
                    job_key, kind, payload_digest, state, checkpoint_json, result_json,
                    version, created_at, updated_at, last_error
                ) VALUES (?, ?, ?, 'running', '{}', NULL, 1, ?, ?, NULL)
                """,
                (
                    normalized_key,
                    normalized_kind,
                    payload_digest,
                    _iso(at),
                    _iso(at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM ops_jobs WHERE job_key = ?",
                (normalized_key,),
            ).fetchone()
            assert row is not None
            connection.commit()
            return self._job_from_row(row), True
        except Exception:
            connection.rollback()
            raise

    def get_job(self, job_key: str) -> JobRecord | None:
        self.initialize()
        row = self._connect().execute(
            "SELECT * FROM ops_jobs WHERE job_key = ?",
            (job_key,),
        ).fetchone()
        return None if row is None else self._job_from_row(row)

    def list_resumable_jobs(self) -> list[JobRecord]:
        self.initialize()
        rows = self._connect().execute(
            "SELECT * FROM ops_jobs WHERE state = 'running' ORDER BY updated_at, job_key"
        ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def checkpoint_job(
        self,
        job_key: str,
        checkpoint: dict[str, Any],
        *,
        expected_version: int,
        at: datetime,
    ) -> JobRecord:
        canonical_json(checkpoint)
        _require_aware(at, "at")
        self.initialize()
        connection = self._connect()
        with connection:
            cursor = connection.execute(
                """
                UPDATE ops_jobs
                SET checkpoint_json = ?, version = version + 1, updated_at = ?, last_error = NULL
                WHERE job_key = ? AND version = ? AND state = 'running'
                """,
                (canonical_json(checkpoint), _iso(at), job_key, expected_version),
            )
            if cursor.rowcount != 1:
                self._raise_job_update_conflict(job_key, expected_version)
        record = self.get_job(job_key)
        assert record is not None
        return record

    def complete_job(
        self,
        job_key: str,
        result: dict[str, Any],
        *,
        expected_version: int,
        at: datetime,
    ) -> JobRecord:
        canonical_json(result)
        _require_aware(at, "at")
        self.initialize()
        connection = self._connect()
        with connection:
            cursor = connection.execute(
                """
                UPDATE ops_jobs
                SET state = 'succeeded', result_json = ?, version = version + 1,
                    updated_at = ?, last_error = NULL
                WHERE job_key = ? AND version = ? AND state = 'running'
                """,
                (canonical_json(result), _iso(at), job_key, expected_version),
            )
            if cursor.rowcount != 1:
                self._raise_job_update_conflict(job_key, expected_version)
        record = self.get_job(job_key)
        assert record is not None
        return record

    def fail_job(
        self,
        job_key: str,
        error: str,
        *,
        expected_version: int,
        at: datetime,
    ) -> JobRecord:
        normalized_error = _require_text(error, "error")
        _require_aware(at, "at")
        self.initialize()
        connection = self._connect()
        with connection:
            cursor = connection.execute(
                """
                UPDATE ops_jobs
                SET state = 'failed', version = version + 1, updated_at = ?, last_error = ?
                WHERE job_key = ? AND version = ? AND state = 'running'
                """,
                (_iso(at), normalized_error, job_key, expected_version),
            )
            if cursor.rowcount != 1:
                self._raise_job_update_conflict(job_key, expected_version)
        record = self.get_job(job_key)
        assert record is not None
        return record

    def claim_idempotency(
        self,
        *,
        operation: str,
        key: str,
        request: dict[str, Any],
        at: datetime,
    ) -> tuple[IdempotencyRecord, bool]:
        """Claim one external side effect before execution.

        Reusing the same operation/key with a different request is a hard conflict. Identical
        replay returns the existing claim, allowing callers to resume instead of duplicating the
        external action.
        """

        self.initialize()
        normalized_operation = _require_text(operation, "operation")
        normalized_key = _require_text(key, "key")
        _require_aware(at, "at")
        request_digest = sha256_json(request)
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT * FROM ops_idempotency WHERE operation = ? AND key = ?",
                (normalized_operation, normalized_key),
            ).fetchone()
            if existing is not None:
                record = self._idempotency_from_row(existing)
                if record.request_digest != request_digest:
                    raise OpsConflictError(
                        "idempotency key already belongs to a different request: "
                        f"{normalized_operation}/{normalized_key}"
                    )
                connection.commit()
                return record, False
            connection.execute(
                """
                INSERT INTO ops_idempotency(
                    operation, key, request_digest, state, response_digest, created_at, updated_at
                ) VALUES (?, ?, ?, 'started', NULL, ?, ?)
                """,
                (
                    normalized_operation,
                    normalized_key,
                    request_digest,
                    _iso(at),
                    _iso(at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM ops_idempotency WHERE operation = ? AND key = ?",
                (normalized_operation, normalized_key),
            ).fetchone()
            assert row is not None
            connection.commit()
            return self._idempotency_from_row(row), True
        except Exception:
            connection.rollback()
            raise

    def complete_idempotency(
        self,
        *,
        operation: str,
        key: str,
        response: dict[str, Any],
        at: datetime,
    ) -> IdempotencyRecord:
        _require_aware(at, "at")
        response_digest = sha256_json(response)
        self.initialize()
        connection = self._connect()
        with connection:
            existing = connection.execute(
                "SELECT * FROM ops_idempotency WHERE operation = ? AND key = ?",
                (operation, key),
            ).fetchone()
            if existing is None:
                raise KeyError(f"unknown idempotency claim: {operation}/{key}")
            record = self._idempotency_from_row(existing)
            if record.state is IdempotencyState.COMPLETED:
                if record.response_digest != response_digest:
                    raise OpsConflictError(
                        "completed idempotency claim cannot be rebound to another response"
                    )
                return record
            connection.execute(
                """
                UPDATE ops_idempotency
                SET state = 'completed', response_digest = ?, updated_at = ?
                WHERE operation = ? AND key = ? AND state = 'started'
                """,
                (response_digest, _iso(at), operation, key),
            )
        row = self._connect().execute(
            "SELECT * FROM ops_idempotency WHERE operation = ? AND key = ?",
            (operation, key),
        ).fetchone()
        assert row is not None
        return self._idempotency_from_row(row)

    def _raise_job_update_conflict(self, job_key: str, expected_version: int) -> None:
        record = self.get_job(job_key)
        if record is None:
            raise KeyError(f"unknown job_key: {job_key}")
        raise OpsConflictError(
            f"job update conflict for {job_key!r}: expected version {expected_version}, "
            f"found version {record.version} in state {record.state.value}"
        )

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> JobRecord:
        checkpoint = json.loads(row["checkpoint_json"])
        result = None if row["result_json"] is None else json.loads(row["result_json"])
        if not isinstance(checkpoint, dict) or (result is not None and not isinstance(result, dict)):
            raise RuntimeError("stored ops job JSON is not an object")
        return JobRecord(
            job_key=row["job_key"],
            kind=row["kind"],
            payload_digest=row["payload_digest"],
            state=JobState(row["state"]),
            checkpoint=checkpoint,
            result=result,
            version=int(row["version"]),
            created_at=_parse_time(row["created_at"]),
            updated_at=_parse_time(row["updated_at"]),
            last_error=row["last_error"],
        )

    @staticmethod
    def _idempotency_from_row(row: sqlite3.Row) -> IdempotencyRecord:
        return IdempotencyRecord(
            operation=row["operation"],
            key=row["key"],
            request_digest=row["request_digest"],
            state=IdempotencyState(row["state"]),
            response_digest=row["response_digest"],
            created_at=_parse_time(row["created_at"]),
            updated_at=_parse_time(row["updated_at"]),
        )
