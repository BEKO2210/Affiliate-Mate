"""Persistent evidence observations with provenance and expiry semantics."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


@dataclass(frozen=True, slots=True)
class EvidenceObservation:
    """One numeric observation, preserved with source, time, confidence, and expiry."""

    product_id: str
    signal: str
    value: float
    source: str
    marketplace: str = "DE"
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    confidence: float = 1.0
    expires_at: datetime | None = None
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.product_id.strip():
            raise ValueError("product_id must not be empty")
        if not self.signal.strip():
            raise ValueError("signal must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not self.marketplace.strip():
            raise ValueError("marketplace must not be empty")
        if not isfinite(float(self.value)):
            raise ValueError("value must be finite")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        _require_aware(self.observed_at, "observed_at")
        if self.expires_at is not None:
            _require_aware(self.expires_at, "expires_at")
            if self.expires_at <= self.observed_at:
                raise ValueError("expires_at must be after observed_at")
        try:
            json.dumps(
                self.metadata,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be strict JSON-serializable") from exc

    def is_expired(self, at: datetime | None = None) -> bool:
        """Return whether the observation has expired at the supplied instant."""

        if self.expires_at is None:
            return False
        moment = datetime.now(UTC) if at is None else at
        _require_aware(moment, "at")
        return self.expires_at <= moment

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "signal": self.signal,
            "value": self.value,
            "source": self.source,
            "marketplace": self.marketplace,
            "observed_at": _iso(self.observed_at),
            "confidence": self.confidence,
            "expires_at": _iso(self.expires_at),
            "unit": self.unit,
            "metadata": self.metadata,
        }


class SQLiteEvidenceStore:
    """Small local-first SQLite store for append-only evidence observations."""

    def __init__(self, path: str | Path) -> None:
        raw_path = str(path)
        self.path = raw_path if raw_path == ":memory:" else str(Path(raw_path).expanduser())
        self._connection: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if self.path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
        self._connection = connection
        return connection

    def initialize(self) -> None:
        """Create the schema idempotently and verify the schema version."""

        connection = self._connect()
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    numeric_value REAL NOT NULL,
                    source TEXT NOT NULL,
                    marketplace TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    expires_at TEXT,
                    unit TEXT,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(product_id, signal, source, marketplace, observed_at)
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_lookup
                ON evidence_observations(product_id, signal, marketplace, observed_at DESC);

                CREATE INDEX IF NOT EXISTS idx_evidence_expiry
                ON evidence_observations(expires_at);
                """
            )
            current = connection.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?)",
                    (SCHEMA_VERSION,),
                )
            elif current["value"] != SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported evidence database schema version: "
                    f"{current['value']} (expected {SCHEMA_VERSION})"
                )

    @staticmethod
    def _insert(
        connection: sqlite3.Connection,
        observation: EvidenceObservation,
    ) -> bool:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO evidence_observations(
                product_id, signal, numeric_value, source, marketplace,
                observed_at, confidence, expires_at, unit, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.product_id,
                observation.signal,
                float(observation.value),
                observation.source,
                observation.marketplace.upper(),
                _iso(observation.observed_at),
                observation.confidence,
                _iso(observation.expires_at),
                observation.unit,
                json.dumps(
                    observation.metadata,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            ),
        )
        return cursor.rowcount == 1

    def add(self, observation: EvidenceObservation) -> bool:
        """Insert an observation. Returns False for an exact source/time duplicate."""

        self.initialize()
        connection = self._connect()
        with connection:
            return self._insert(connection, observation)

    def add_many(self, observations: list[EvidenceObservation]) -> int:
        """Atomically insert observations and return the number newly stored."""

        self.initialize()
        connection = self._connect()
        with connection:
            return sum(self._insert(connection, observation) for observation in observations)

    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> EvidenceObservation:
        return EvidenceObservation(
            product_id=row["product_id"],
            signal=row["signal"],
            value=row["numeric_value"],
            source=row["source"],
            marketplace=row["marketplace"],
            observed_at=_parse_iso(row["observed_at"]),
            confidence=row["confidence"],
            expires_at=_parse_iso(row["expires_at"]),
            unit=row["unit"],
            metadata=json.loads(row["metadata_json"]),
        )

    def latest(
        self,
        product_id: str,
        signal: str,
        *,
        marketplace: str = "DE",
        as_of: datetime | None = None,
        include_expired: bool = False,
    ) -> EvidenceObservation | None:
        """Return the latest observation available at `as_of`, excluding expired data by default."""

        self.initialize()
        moment = datetime.now(UTC) if as_of is None else as_of
        _require_aware(moment, "as_of")
        moment_iso = _iso(moment)
        clauses = [
            "product_id = ?",
            "signal = ?",
            "marketplace = ?",
            "observed_at <= ?",
        ]
        params: list[Any] = [product_id, signal, marketplace.upper(), moment_iso]
        if not include_expired:
            clauses.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(moment_iso)
        query = (
            "SELECT * FROM evidence_observations WHERE "
            + " AND ".join(clauses)
            + " ORDER BY observed_at DESC, id DESC LIMIT 1"
        )
        row = self._connect().execute(query, params).fetchone()
        return None if row is None else self._row_to_observation(row)

    def history(
        self,
        product_id: str,
        signal: str,
        *,
        marketplace: str = "DE",
    ) -> list[EvidenceObservation]:
        """Return all observations newest first, including expired history."""

        self.initialize()
        rows = self._connect().execute(
            """
            SELECT * FROM evidence_observations
            WHERE product_id = ? AND signal = ? AND marketplace = ?
            ORDER BY observed_at DESC, id DESC
            """,
            (product_id, signal, marketplace.upper()),
        ).fetchall()
        return [self._row_to_observation(row) for row in rows]

    def count(self) -> int:
        self.initialize()
        row = self._connect().execute(
            "SELECT COUNT(*) AS total FROM evidence_observations"
        ).fetchone()
        return int(row["total"])

    def delete_expired(self, as_of: datetime | None = None) -> int:
        """Delete expired rows. This is optional housekeeping; history is kept by default."""

        self.initialize()
        moment = datetime.now(UTC) if as_of is None else as_of
        _require_aware(moment, "as_of")
        with self._connect():
            cursor = self._connect().execute(
                "DELETE FROM evidence_observations "
                "WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (_iso(moment),),
            )
        return cursor.rowcount

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> SQLiteEvidenceStore:
        self.initialize()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
