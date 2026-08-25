"""SQLite persistence for forecasts, realized outcomes, and policy audit history."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from .learning_models import (
    ForecastSnapshot,
    OutcomeEvent,
    OutcomeKind,
    ScoringPolicyVersion,
    canonical_json,
)

LEARNING_DB_SCHEMA_VERSION = "1"


class LearningConflictError(RuntimeError):
    """Raised when an immutable learning-loop record would be rewritten."""


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _iso(value: datetime) -> str:
    _require_aware(value, "timestamp")
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("stored learning-loop timestamp is not timezone-aware")
    return parsed.astimezone(UTC)


class LearningStore:
    """Append-oriented local store with explicit point-in-time query semantics."""

    def __init__(self, path: str | Path) -> None:
        raw = str(path)
        self.path = raw if raw == ":memory:" else str(Path(raw).expanduser())
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
                CREATE TABLE IF NOT EXISTS learning_schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learning_policy_versions (
                    version TEXT PRIMARY KEY,
                    policy_json TEXT NOT NULL,
                    policy_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_version TEXT,
                    notes TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learning_forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    marketplace TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price REAL NOT NULL,
                    predicted_at TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    policy_version TEXT NOT NULL,
                    policy_digest TEXT NOT NULL,
                    analysis_digest TEXT NOT NULL,
                    candidate_digest TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    opportunity_score REAL NOT NULL,
                    predicted_ctr REAL NOT NULL,
                    predicted_conversion_rate REAL NOT NULL,
                    predicted_value_per_1000_views REAL NOT NULL,
                    commission_per_sale REAL NOT NULL,
                    candidate_json TEXT NOT NULL,
                    available_fields_json TEXT NOT NULL,
                    provided_fields_tracked INTEGER NOT NULL,
                    package_digest TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_learning_forecasts_product_time
                    ON learning_forecasts(product_id, predicted_at);
                CREATE INDEX IF NOT EXISTS idx_learning_forecasts_content_time
                    ON learning_forecasts(content_id, predicted_at);
                CREATE INDEX IF NOT EXISTS idx_learning_forecasts_policy_time
                    ON learning_forecasts(policy_version, predicted_at);

                CREATE TABLE IF NOT EXISTS learning_outcomes (
                    source TEXT NOT NULL,
                    source_event_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    marketplace TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    package_digest TEXT,
                    effective_at TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    amount_minor INTEGER NOT NULL,
                    currency TEXT,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY(source, source_event_id, kind)
                );

                CREATE INDEX IF NOT EXISTS idx_learning_outcomes_product_effective
                    ON learning_outcomes(product_id, effective_at);
                CREATE INDEX IF NOT EXISTS idx_learning_outcomes_content_effective
                    ON learning_outcomes(content_id, effective_at);
                CREATE INDEX IF NOT EXISTS idx_learning_outcomes_ingested
                    ON learning_outcomes(ingested_at);

                CREATE TABLE IF NOT EXISTS learning_policy_decisions (
                    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    baseline_version TEXT NOT NULL,
                    candidate_version TEXT NOT NULL,
                    evaluation_digest TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK(decision IN ('approve', 'reject')),
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM learning_schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO learning_schema_meta(key, value) VALUES ('schema_version', ?)",
                    (LEARNING_DB_SCHEMA_VERSION,),
                )
            elif row["value"] != LEARNING_DB_SCHEMA_VERSION:
                raise RuntimeError(
                    "unsupported learning schema version: "
                    f"{row['value']} != {LEARNING_DB_SCHEMA_VERSION}"
                )

    def register_policy(self, policy: ScoringPolicyVersion) -> bool:
        """Insert an immutable policy version; identical replay is idempotent."""

        self.initialize()
        connection = self._connect()
        existing = connection.execute(
            "SELECT * FROM learning_policy_versions WHERE version = ?",
            (policy.version,),
        ).fetchone()
        if existing is not None:
            stored = self._policy_from_row(existing)
            if stored == policy:
                return False
            raise LearningConflictError(
                f"policy version {policy.version!r} already exists with different content"
            )
        if policy.parent_version is not None:
            parent = self.get_policy(policy.parent_version)
            if parent is None:
                raise KeyError(f"unknown parent policy: {policy.parent_version}")
            if parent.created_at > policy.created_at:
                raise ValueError("parent policy cannot be created after child policy")
        with connection:
            connection.execute(
                """
                INSERT INTO learning_policy_versions(
                    version, policy_json, policy_digest, created_at, parent_version, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.version,
                    canonical_json(policy.policy_payload),
                    policy.digest,
                    _iso(policy.created_at),
                    policy.parent_version,
                    policy.notes,
                ),
            )
        return True

    def get_policy(self, version: str) -> ScoringPolicyVersion | None:
        self.initialize()
        row = self._connect().execute(
            "SELECT * FROM learning_policy_versions WHERE version = ?",
            (version,),
        ).fetchone()
        return None if row is None else self._policy_from_row(row)

    def list_policies(self) -> list[ScoringPolicyVersion]:
        self.initialize()
        rows = self._connect().execute(
            "SELECT * FROM learning_policy_versions ORDER BY created_at, version"
        ).fetchall()
        return [self._policy_from_row(row) for row in rows]

    def add_forecast(self, forecast: ForecastSnapshot) -> bool:
        """Insert once; a forecast ID can never be rebound to another snapshot."""

        self.initialize()
        connection = self._connect()
        existing = connection.execute(
            "SELECT * FROM learning_forecasts WHERE forecast_id = ?",
            (forecast.forecast_id,),
        ).fetchone()
        if existing is not None:
            stored = self._forecast_from_row(existing)
            if stored == forecast:
                return False
            raise LearningConflictError(
                f"forecast_id {forecast.forecast_id!r} already exists with different content"
            )
        policy = self.get_policy(forecast.policy_version)
        if policy is None:
            raise KeyError(f"unknown policy_version: {forecast.policy_version}")
        if policy.digest != forecast.policy_digest:
            raise LearningConflictError(
                "forecast policy_digest does not match the registered policy version"
            )
        if policy.created_at > forecast.predicted_at:
            raise ValueError("forecast cannot use a policy created after predicted_at")
        with connection:
            connection.execute(
                """
                INSERT INTO learning_forecasts(
                    forecast_id, product_id, marketplace, currency, content_id, category,
                    price, predicted_at, horizon_days, policy_version, policy_digest,
                    analysis_digest, candidate_digest, accepted, opportunity_score,
                    predicted_ctr, predicted_conversion_rate,
                    predicted_value_per_1000_views, commission_per_sale,
                    candidate_json, available_fields_json, provided_fields_tracked, package_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    forecast.forecast_id,
                    forecast.product_id,
                    forecast.marketplace,
                    forecast.currency,
                    forecast.content_id,
                    forecast.category,
                    forecast.price,
                    _iso(forecast.predicted_at),
                    forecast.horizon_days,
                    forecast.policy_version,
                    forecast.policy_digest,
                    forecast.analysis_digest,
                    forecast.candidate_digest,
                    int(forecast.accepted),
                    forecast.opportunity_score,
                    forecast.predicted_ctr,
                    forecast.predicted_conversion_rate,
                    forecast.predicted_value_per_1000_views,
                    forecast.commission_per_sale,
                    canonical_json(forecast.candidate_payload),
                    canonical_json(list(forecast.available_fields)),
                    int(forecast.provided_fields_tracked),
                    forecast.package_digest,
                ),
            )
        return True

    def get_forecast(self, forecast_id: str) -> ForecastSnapshot | None:
        self.initialize()
        row = self._connect().execute(
            "SELECT * FROM learning_forecasts WHERE forecast_id = ?",
            (forecast_id,),
        ).fetchone()
        return None if row is None else self._forecast_from_row(row)

    def list_forecasts(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        marketplace: str | None = None,
        policy_version: str | None = None,
    ) -> list[ForecastSnapshot]:
        self.initialize()
        if start is not None:
            _require_aware(start, "start")
        if end is not None:
            _require_aware(end, "end")
        if start is not None and end is not None and start >= end:
            raise ValueError("start must be before end")
        clauses: list[str] = []
        values: list[object] = []
        if start is not None:
            clauses.append("predicted_at >= ?")
            values.append(_iso(start))
        if end is not None:
            clauses.append("predicted_at < ?")
            values.append(_iso(end))
        if marketplace is not None:
            clauses.append("marketplace = ?")
            values.append(marketplace.strip().upper())
        if policy_version is not None:
            clauses.append("policy_version = ?")
            values.append(policy_version)
        where = "" if not clauses else " WHERE " + " AND ".join(clauses)
        rows = self._connect().execute(
            "SELECT * FROM learning_forecasts"
            + where
            + " ORDER BY predicted_at, forecast_id",
            values,
        ).fetchall()
        return [self._forecast_from_row(row) for row in rows]

    def add_outcome(self, event: OutcomeEvent) -> bool:
        """Insert one immutable outcome; source replay is idempotent."""

        self.initialize()
        connection = self._connect()
        existing = connection.execute(
            """
            SELECT * FROM learning_outcomes
            WHERE source = ? AND source_event_id = ? AND kind = ?
            """,
            event.identity,
        ).fetchone()
        if existing is not None:
            stored = self._outcome_from_row(existing)
            if stored == event:
                return False
            raise LearningConflictError(
                "outcome identity already exists with different content: "
                f"{event.identity!r}"
            )
        with connection:
            connection.execute(
                """
                INSERT INTO learning_outcomes(
                    source, source_event_id, kind, product_id, marketplace, content_id,
                    package_digest, effective_at, observed_at, ingested_at,
                    window_start, window_end, count, amount_minor, currency, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.source,
                    event.source_event_id,
                    event.kind.value,
                    event.product_id,
                    event.marketplace,
                    event.content_id,
                    event.package_digest,
                    _iso(event.effective_at),
                    _iso(event.observed_at),
                    _iso(event.ingested_at),
                    _iso(event.window_start),
                    _iso(event.window_end),
                    event.count,
                    event.amount_minor,
                    event.currency,
                    canonical_json(event.metadata),
                ),
            )
        return True

    def add_outcomes(self, events: list[OutcomeEvent]) -> tuple[int, int]:
        """Atomically import a batch; any conflicting replay rolls the whole batch back."""

        self.initialize()
        connection = self._connect()
        inserted = 0
        replayed = 0
        connection.execute("BEGIN IMMEDIATE")
        try:
            for event in events:
                existing = connection.execute(
                    """
                    SELECT * FROM learning_outcomes
                    WHERE source = ? AND source_event_id = ? AND kind = ?
                    """,
                    event.identity,
                ).fetchone()
                if existing is not None:
                    stored = self._outcome_from_row(existing)
                    if stored != event:
                        raise LearningConflictError(
                            "outcome identity already exists with different content: "
                            f"{event.identity!r}"
                        )
                    replayed += 1
                    continue
                connection.execute(
                    """
                    INSERT INTO learning_outcomes(
                        source, source_event_id, kind, product_id, marketplace, content_id,
                        package_digest, effective_at, observed_at, ingested_at,
                        window_start, window_end, count, amount_minor, currency, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.source,
                        event.source_event_id,
                        event.kind.value,
                        event.product_id,
                        event.marketplace,
                        event.content_id,
                        event.package_digest,
                        _iso(event.effective_at),
                        _iso(event.observed_at),
                        _iso(event.ingested_at),
                        _iso(event.window_start),
                        _iso(event.window_end),
                        event.count,
                        event.amount_minor,
                        event.currency,
                        canonical_json(event.metadata),
                    ),
                )
                inserted += 1
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return inserted, replayed

    def list_outcomes(
        self,
        *,
        product_id: str | None = None,
        content_id: str | None = None,
        effective_start: datetime | None = None,
        effective_end: datetime | None = None,
        as_of: datetime | None = None,
    ) -> list[OutcomeEvent]:
        """Query what was both observed and ingested by `as_of`.

        This double cutoff is intentional. Backtests must not use a late affiliate report
        merely because the conversion was attributed to an earlier date.
        """

        self.initialize()
        for field_name, value in (
            ("effective_start", effective_start),
            ("effective_end", effective_end),
            ("as_of", as_of),
        ):
            if value is not None:
                _require_aware(value, field_name)
        if (
            effective_start is not None
            and effective_end is not None
            and effective_start >= effective_end
        ):
            raise ValueError("effective_start must be before effective_end")
        clauses: list[str] = []
        values: list[object] = []
        if product_id is not None:
            clauses.append("product_id = ?")
            values.append(product_id)
        if content_id is not None:
            clauses.append("content_id = ?")
            values.append(content_id)
        if effective_start is not None:
            clauses.append("effective_at >= ?")
            values.append(_iso(effective_start))
        if effective_end is not None:
            clauses.append("effective_at < ?")
            values.append(_iso(effective_end))
        if as_of is not None:
            cutoff = _iso(as_of)
            clauses.extend(("observed_at <= ?", "ingested_at <= ?"))
            values.extend((cutoff, cutoff))
        where = "" if not clauses else " WHERE " + " AND ".join(clauses)
        rows = self._connect().execute(
            "SELECT * FROM learning_outcomes"
            + where
            + " ORDER BY effective_at, observed_at, source, source_event_id, kind",
            values,
        ).fetchall()
        return [self._outcome_from_row(row) for row in rows]

    def record_policy_decision(
        self,
        *,
        baseline_version: str,
        candidate_version: str,
        evaluation_digest: str,
        decision: str,
        actor: str,
        reason: str,
        created_at: datetime,
    ) -> int:
        """Append a human promotion/rejection decision.

        This is deliberately audit-only. It never mutates an "active policy" pointer.
        """

        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be 'approve' or 'reject'")
        if baseline_version == candidate_version:
            raise ValueError("baseline_version and candidate_version must differ")
        _require_aware(created_at, "created_at")
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason must not be empty")
        if len(evaluation_digest) != 64 or any(
            character not in "0123456789abcdef" for character in evaluation_digest
        ):
            raise ValueError("evaluation_digest must be a lowercase SHA-256 digest")
        if self.get_policy(baseline_version) is None:
            raise KeyError(f"unknown baseline policy: {baseline_version}")
        if self.get_policy(candidate_version) is None:
            raise KeyError(f"unknown candidate policy: {candidate_version}")
        connection = self._connect()
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO learning_policy_decisions(
                    baseline_version, candidate_version, evaluation_digest,
                    decision, actor, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baseline_version,
                    candidate_version,
                    evaluation_digest,
                    decision,
                    actor.strip(),
                    reason.strip(),
                    _iso(created_at),
                ),
            )
        return int(cursor.lastrowid)

    @staticmethod
    def _policy_from_row(row: sqlite3.Row) -> ScoringPolicyVersion:
        policy = ScoringPolicyVersion(
            version=row["version"],
            policy_payload=json.loads(row["policy_json"]),
            created_at=_parse_time(row["created_at"]),
            parent_version=row["parent_version"],
            notes=row["notes"],
        )
        if policy.digest != row["policy_digest"]:
            raise RuntimeError(f"policy digest corruption detected for {policy.version}")
        return policy

    @staticmethod
    def _forecast_from_row(row: sqlite3.Row) -> ForecastSnapshot:
        return ForecastSnapshot(
            forecast_id=row["forecast_id"],
            product_id=row["product_id"],
            marketplace=row["marketplace"],
            currency=row["currency"],
            content_id=row["content_id"],
            category=row["category"],
            price=float(row["price"]),
            predicted_at=_parse_time(row["predicted_at"]),
            horizon_days=int(row["horizon_days"]),
            policy_version=row["policy_version"],
            policy_digest=row["policy_digest"],
            analysis_digest=row["analysis_digest"],
            candidate_digest=row["candidate_digest"],
            accepted=bool(row["accepted"]),
            opportunity_score=float(row["opportunity_score"]),
            predicted_ctr=float(row["predicted_ctr"]),
            predicted_conversion_rate=float(row["predicted_conversion_rate"]),
            predicted_value_per_1000_views=float(
                row["predicted_value_per_1000_views"]
            ),
            commission_per_sale=float(row["commission_per_sale"]),
            candidate_payload=json.loads(row["candidate_json"]),
            available_fields=tuple(json.loads(row["available_fields_json"])),
            provided_fields_tracked=bool(row["provided_fields_tracked"]),
            package_digest=row["package_digest"],
        )

    @staticmethod
    def _outcome_from_row(row: sqlite3.Row) -> OutcomeEvent:
        metadata: dict[str, Any] = json.loads(row["metadata_json"])
        return OutcomeEvent(
            source=row["source"],
            source_event_id=row["source_event_id"],
            kind=OutcomeKind(row["kind"]),
            product_id=row["product_id"],
            marketplace=row["marketplace"],
            content_id=row["content_id"],
            package_digest=row["package_digest"],
            effective_at=_parse_time(row["effective_at"]),
            observed_at=_parse_time(row["observed_at"]),
            ingested_at=_parse_time(row["ingested_at"]),
            window_start=_parse_time(row["window_start"]),
            window_end=_parse_time(row["window_end"]),
            count=int(row["count"]),
            amount_minor=int(row["amount_minor"]),
            currency=row["currency"],
            metadata=metadata,
        )
