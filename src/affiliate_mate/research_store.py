"""Transactional SQLite persistence for research claims, sources, notes, and approvals."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from .research_models import (
    ApprovalEvent,
    ApprovalState,
    ClaimEvidenceLink,
    ClaimRisk,
    ClaimState,
    ClaimStateEvent,
    EvidenceStance,
    ResearchClaim,
    ResearchNote,
    ResearchSource,
    SourceKind,
    utc_now,
)

RESEARCH_SCHEMA_VERSION = "1"

_CLAIM_TRANSITIONS: dict[ClaimState, frozenset[ClaimState]] = {
    ClaimState.DRAFT: frozenset({ClaimState.SUPPORTED, ClaimState.DISPUTED, ClaimState.REJECTED}),
    ClaimState.SUPPORTED: frozenset({ClaimState.DRAFT, ClaimState.DISPUTED, ClaimState.REJECTED}),
    ClaimState.DISPUTED: frozenset({ClaimState.DRAFT, ClaimState.SUPPORTED, ClaimState.REJECTED}),
    ClaimState.REJECTED: frozenset({ClaimState.DRAFT}),
}
_APPROVAL_TRANSITIONS: dict[ApprovalState, frozenset[ApprovalState]] = {
    ApprovalState.DRAFT: frozenset({ApprovalState.IN_REVIEW}),
    ApprovalState.IN_REVIEW: frozenset(
        {ApprovalState.DRAFT, ApprovalState.APPROVED, ApprovalState.REJECTED}
    ),
    ApprovalState.APPROVED: frozenset({ApprovalState.IN_REVIEW}),
    ApprovalState.REJECTED: frozenset({ApprovalState.DRAFT, ApprovalState.IN_REVIEW}),
}


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("stored research timestamp is not timezone-aware")
    return parsed.astimezone(UTC)


def _json(value: dict[str, object] | None) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ResearchConflictError(RuntimeError):
    """Raised when an optimistic state transition observes an unexpected state."""


class InvalidResearchTransitionError(ValueError):
    """Raised when the requested workflow transition is not permitted."""


class ResearchWorkspaceStore:
    """Append-oriented research workspace with immutable audit events."""

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

    def initialize(self) -> None:
        connection = self._connect()
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_sources (
                    source_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    published_at TEXT,
                    checksum TEXT,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_research_sources_product
                    ON research_sources(product_id, retrieved_at DESC);

                CREATE TABLE IF NOT EXISTS research_claims (
                    claim_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    claim_text TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_research_claims_product
                    ON research_claims(product_id, created_at, claim_id);

                CREATE TABLE IF NOT EXISTS claim_state_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id TEXT NOT NULL REFERENCES research_claims(claim_id) ON DELETE RESTRICT,
                    state TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_claim_state_latest
                    ON claim_state_events(claim_id, event_id DESC);

                CREATE TABLE IF NOT EXISTS claim_evidence_links (
                    claim_id TEXT NOT NULL REFERENCES research_claims(claim_id) ON DELETE RESTRICT,
                    source_id TEXT NOT NULL REFERENCES research_sources(source_id) ON DELETE RESTRICT,
                    stance TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    quote TEXT,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    PRIMARY KEY(claim_id, source_id, stance, locator)
                );
                CREATE INDEX IF NOT EXISTS idx_claim_links_source
                    ON claim_evidence_links(source_id, claim_id);

                CREATE TABLE IF NOT EXISTS research_notes (
                    note_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_research_notes_product
                    ON research_notes(product_id, created_at, note_id);

                CREATE TABLE IF NOT EXISTS note_claim_links (
                    note_id TEXT NOT NULL REFERENCES research_notes(note_id) ON DELETE RESTRICT,
                    claim_id TEXT NOT NULL REFERENCES research_claims(claim_id) ON DELETE RESTRICT,
                    PRIMARY KEY(note_id, claim_id)
                );

                CREATE TABLE IF NOT EXISTS approval_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_approval_latest
                    ON approval_events(product_id, event_id DESC);
                """
            )
            current = connection.execute(
                "SELECT value FROM research_schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO research_schema_meta(key, value) VALUES('schema_version', ?)",
                    (RESEARCH_SCHEMA_VERSION,),
                )
            elif current["value"] != RESEARCH_SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported research database schema version: "
                    f"{current['value']} (expected {RESEARCH_SCHEMA_VERSION})"
                )

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def add_source(self, source: ResearchSource) -> bool:
        self.initialize()
        connection = self._connect()
        with connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO research_sources(
                    source_id, product_id, kind, title, locator, publisher,
                    retrieved_at, published_at, checksum, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.source_id,
                    source.product_id,
                    source.kind.value,
                    source.title,
                    source.locator,
                    source.publisher,
                    _iso(source.retrieved_at),
                    None if source.published_at is None else _iso(source.published_at),
                    source.checksum,
                    _json(source.metadata),
                ),
            )
            return cursor.rowcount == 1

    def add_claim(self, claim: ResearchClaim) -> bool:
        """Add a claim and atomically create its initial draft-state audit event."""

        self.initialize()
        connection = self._connect()
        with connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO research_claims(
                    claim_id, product_id, claim_text, risk, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    claim.product_id,
                    claim.text,
                    claim.risk.value,
                    _iso(claim.created_at),
                    claim.created_by,
                ),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute(
                """
                INSERT INTO claim_state_events(claim_id, state, actor, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    ClaimState.DRAFT.value,
                    claim.created_by,
                    "Claim created.",
                    _iso(claim.created_at),
                ),
            )
            return True

    def add_evidence_link(self, link: ClaimEvidenceLink) -> bool:
        """Link evidence only when claim and source belong to the same product."""

        self.initialize()
        connection = self._connect()
        with connection:
            claim = connection.execute(
                "SELECT product_id FROM research_claims WHERE claim_id = ?",
                (link.claim_id,),
            ).fetchone()
            source = connection.execute(
                "SELECT product_id FROM research_sources WHERE source_id = ?",
                (link.source_id,),
            ).fetchone()
            if claim is None:
                raise KeyError(f"unknown claim_id: {link.claim_id}")
            if source is None:
                raise KeyError(f"unknown source_id: {link.source_id}")
            if claim["product_id"] != source["product_id"]:
                raise ValueError("claim and source belong to different products")
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO claim_evidence_links(
                    claim_id, source_id, stance, locator, quote, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link.claim_id,
                    link.source_id,
                    link.stance.value,
                    link.locator,
                    link.quote,
                    _iso(link.created_at),
                    link.created_by,
                ),
            )
            return cursor.rowcount == 1

    def add_note(self, note: ResearchNote, *, claim_ids: Iterable[str] = ()) -> bool:
        self.initialize()
        unique_claim_ids = tuple(dict.fromkeys(claim_ids))
        connection = self._connect()
        with connection:
            for claim_id in unique_claim_ids:
                row = connection.execute(
                    "SELECT product_id FROM research_claims WHERE claim_id = ?",
                    (claim_id,),
                ).fetchone()
                if row is None:
                    raise KeyError(f"unknown claim_id: {claim_id}")
                if row["product_id"] != note.product_id:
                    raise ValueError("note cannot reference a claim from another product")
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO research_notes(
                    note_id, product_id, title, body, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    note.note_id,
                    note.product_id,
                    note.title,
                    note.body,
                    _iso(note.created_at),
                    note.created_by,
                ),
            )
            if cursor.rowcount != 1:
                return False
            connection.executemany(
                "INSERT INTO note_claim_links(note_id, claim_id) VALUES (?, ?)",
                ((note.note_id, claim_id) for claim_id in unique_claim_ids),
            )
            return True

    def get_source(self, source_id: str) -> ResearchSource | None:
        self.initialize()
        row = self._connect().execute(
            "SELECT * FROM research_sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        return None if row is None else self._source_from_row(row)

    def get_claim(self, claim_id: str) -> ResearchClaim | None:
        self.initialize()
        row = self._connect().execute(
            "SELECT * FROM research_claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        return None if row is None else self._claim_from_row(row)

    def list_sources(self, product_id: str) -> list[ResearchSource]:
        self.initialize()
        rows = self._connect().execute(
            """
            SELECT * FROM research_sources
            WHERE product_id = ?
            ORDER BY retrieved_at, source_id
            """,
            (product_id,),
        ).fetchall()
        return [self._source_from_row(row) for row in rows]

    def list_claims(self, product_id: str) -> list[ResearchClaim]:
        self.initialize()
        rows = self._connect().execute(
            """
            SELECT * FROM research_claims
            WHERE product_id = ?
            ORDER BY created_at, claim_id
            """,
            (product_id,),
        ).fetchall()
        return [self._claim_from_row(row) for row in rows]

    def list_claim_links(self, claim_id: str) -> list[ClaimEvidenceLink]:
        self.initialize()
        rows = self._connect().execute(
            """
            SELECT * FROM claim_evidence_links
            WHERE claim_id = ?
            ORDER BY source_id, stance, locator
            """,
            (claim_id,),
        ).fetchall()
        return [self._link_from_row(row) for row in rows]

    def list_notes(self, product_id: str) -> list[ResearchNote]:
        self.initialize()
        rows = self._connect().execute(
            """
            SELECT * FROM research_notes
            WHERE product_id = ?
            ORDER BY created_at, note_id
            """,
            (product_id,),
        ).fetchall()
        return [self._note_from_row(row) for row in rows]

    def note_claim_ids(self, note_id: str) -> tuple[str, ...]:
        self.initialize()
        rows = self._connect().execute(
            """
            SELECT claim_id FROM note_claim_links
            WHERE note_id = ?
            ORDER BY claim_id
            """,
            (note_id,),
        ).fetchall()
        return tuple(row["claim_id"] for row in rows)

    def current_claim_state(self, claim_id: str) -> ClaimState:
        self.initialize()
        row = self._connect().execute(
            """
            SELECT state FROM claim_state_events
            WHERE claim_id = ?
            ORDER BY event_id DESC LIMIT 1
            """,
            (claim_id,),
        ).fetchone()
        if row is None:
            if self.get_claim(claim_id) is None:
                raise KeyError(f"unknown claim_id: {claim_id}")
            raise RuntimeError(f"claim has no state history: {claim_id}")
        return ClaimState(row["state"])

    def list_claim_state_events(self, claim_id: str) -> list[ClaimStateEvent]:
        self.initialize()
        rows = self._connect().execute(
            """
            SELECT * FROM claim_state_events
            WHERE claim_id = ?
            ORDER BY event_id
            """,
            (claim_id,),
        ).fetchall()
        return [
            ClaimStateEvent(
                event_id=row["event_id"],
                claim_id=row["claim_id"],
                state=ClaimState(row["state"]),
                actor=row["actor"],
                reason=row["reason"],
                created_at=_parse_time(row["created_at"]),
            )
            for row in rows
        ]

    def transition_claim(
        self,
        claim_id: str,
        state: ClaimState,
        *,
        actor: str,
        reason: str,
        expected_state: ClaimState | None = None,
        created_at: datetime | None = None,
    ) -> ClaimStateEvent:
        self.initialize()
        moment = utc_now() if created_at is None else created_at
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                """
                SELECT state FROM claim_state_events
                WHERE claim_id = ? ORDER BY event_id DESC LIMIT 1
                """,
                (claim_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown claim_id: {claim_id}")
            current = ClaimState(row["state"])
            if expected_state is not None and current is not expected_state:
                raise ResearchConflictError(
                    f"claim state changed: expected {expected_state.value}, found {current.value}"
                )
            if state is current:
                raise InvalidResearchTransitionError("claim is already in the requested state")
            if state not in _CLAIM_TRANSITIONS[current]:
                raise InvalidResearchTransitionError(
                    f"claim transition {current.value} -> {state.value} is not allowed"
                )
            cursor = connection.execute(
                """
                INSERT INTO claim_state_events(claim_id, state, actor, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (claim_id, state.value, actor.strip(), reason.strip(), _iso(moment)),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return ClaimStateEvent(
            event_id=cursor.lastrowid,
            claim_id=claim_id,
            state=state,
            actor=actor.strip(),
            reason=reason.strip(),
            created_at=moment,
        )

    def current_approval_state(self, product_id: str) -> ApprovalState:
        self.initialize()
        row = self._connect().execute(
            """
            SELECT state FROM approval_events
            WHERE product_id = ? ORDER BY event_id DESC LIMIT 1
            """,
            (product_id,),
        ).fetchone()
        return ApprovalState.DRAFT if row is None else ApprovalState(row["state"])

    def list_approval_events(self, product_id: str) -> list[ApprovalEvent]:
        self.initialize()
        rows = self._connect().execute(
            """
            SELECT * FROM approval_events
            WHERE product_id = ? ORDER BY event_id
            """,
            (product_id,),
        ).fetchall()
        return [
            ApprovalEvent(
                event_id=row["event_id"],
                product_id=row["product_id"],
                state=ApprovalState(row["state"]),
                actor=row["actor"],
                reason=row["reason"],
                created_at=_parse_time(row["created_at"]),
            )
            for row in rows
        ]

    def transition_approval(
        self,
        product_id: str,
        state: ApprovalState,
        *,
        actor: str,
        reason: str,
        expected_state: ApprovalState | None = None,
        created_at: datetime | None = None,
    ) -> ApprovalEvent:
        """Append an approval event using optimistic-state validation."""

        self.initialize()
        moment = utc_now() if created_at is None else created_at
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                """
                SELECT state FROM approval_events
                WHERE product_id = ? ORDER BY event_id DESC LIMIT 1
                """,
                (product_id,),
            ).fetchone()
            current = ApprovalState.DRAFT if row is None else ApprovalState(row["state"])
            if expected_state is not None and current is not expected_state:
                raise ResearchConflictError(
                    f"approval state changed: expected {expected_state.value}, found {current.value}"
                )
            if state is current:
                raise InvalidResearchTransitionError("product is already in the requested state")
            if state not in _APPROVAL_TRANSITIONS[current]:
                raise InvalidResearchTransitionError(
                    f"approval transition {current.value} -> {state.value} is not allowed"
                )
            cursor = connection.execute(
                """
                INSERT INTO approval_events(product_id, state, actor, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (product_id, state.value, actor.strip(), reason.strip(), _iso(moment)),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return ApprovalEvent(
            event_id=cursor.lastrowid,
            product_id=product_id,
            state=state,
            actor=actor.strip(),
            reason=reason.strip(),
            created_at=moment,
        )

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> ResearchSource:
        return ResearchSource(
            source_id=row["source_id"],
            product_id=row["product_id"],
            kind=SourceKind(row["kind"]),
            title=row["title"],
            locator=row["locator"],
            publisher=row["publisher"],
            retrieved_at=_parse_time(row["retrieved_at"]),
            published_at=(None if row["published_at"] is None else _parse_time(row["published_at"])),
            checksum=row["checksum"],
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _claim_from_row(row: sqlite3.Row) -> ResearchClaim:
        return ResearchClaim(
            claim_id=row["claim_id"],
            product_id=row["product_id"],
            text=row["claim_text"],
            risk=ClaimRisk(row["risk"]),
            created_at=_parse_time(row["created_at"]),
            created_by=row["created_by"],
        )

    @staticmethod
    def _link_from_row(row: sqlite3.Row) -> ClaimEvidenceLink:
        return ClaimEvidenceLink(
            claim_id=row["claim_id"],
            source_id=row["source_id"],
            stance=EvidenceStance(row["stance"]),
            locator=row["locator"],
            quote=row["quote"],
            created_at=_parse_time(row["created_at"]),
            created_by=row["created_by"],
        )

    @staticmethod
    def _note_from_row(row: sqlite3.Row) -> ResearchNote:
        return ResearchNote(
            note_id=row["note_id"],
            product_id=row["product_id"],
            title=row["title"],
            body=row["body"],
            created_at=_parse_time(row["created_at"]),
            created_by=row["created_by"],
        )
