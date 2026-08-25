"""Deterministic research-package snapshots bound to approval audit events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from .research_store import ResearchConflictError, ResearchWorkspaceStore

SNAPSHOT_SCHEMA_VERSION = "affiliate-mate.research-snapshot.v1"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def build_research_snapshot(store: ResearchWorkspaceStore, product_id: str) -> dict[str, object]:
    """Return the complete editorial research state that an approval attests to.

    Approval events themselves are deliberately excluded so recording an approval does not
    mutate the package it approves. Full claim-state history is included so a claim that was
    disputed and later returned to the same visible state still produces a new revision.
    """

    sources = store.list_sources(product_id)
    claims = store.list_claims(product_id)
    notes = store.list_notes(product_id)
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "product_id": product_id,
        "sources": [source.to_dict() for source in sources],
        "claims": [
            {
                **claim.to_dict(state=store.current_claim_state(claim.claim_id)),
                "state_history": [
                    event.to_dict() for event in store.list_claim_state_events(claim.claim_id)
                ],
                "evidence": [link.to_dict() for link in store.list_claim_links(claim.claim_id)],
            }
            for claim in claims
        ],
        "notes": [
            note.to_dict(claim_ids=store.note_claim_ids(note.note_id))
            for note in notes
        ],
    }


def research_snapshot_digest(store: ResearchWorkspaceStore, product_id: str) -> str:
    """Return a stable SHA-256 digest for the current research package."""

    canonical = _canonical_json(build_research_snapshot(store, product_id))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ApprovalSnapshot:
    approval_event_id: int
    product_id: str
    research_digest: str
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "approval_event_id": self.approval_event_id,
            "product_id": self.product_id,
            "research_digest": self.research_digest,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }


class ApprovalSnapshotRegistry:
    """Package-internal registry tying an APPROVED event to one exact research revision.

    The registry intentionally uses the workspace's existing SQLite connection. This keeps
    `:memory:` stores testable and guarantees the snapshot table lives beside the audit data.
    An approval without a matching snapshot is treated as unusable by the approval guard.
    """

    def __init__(self, store: ResearchWorkspaceStore) -> None:
        self._store = store
        self._initialize()

    def _connection(self):
        # Package-internal use of the store connection is intentional: one workspace, one DB.
        return self._store._connect()

    def _initialize(self) -> None:
        self._store.initialize()
        connection = self._connection()
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS approval_snapshots (
                    approval_event_id INTEGER PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    research_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_approval_snapshots_product
                    ON approval_snapshots(product_id, approval_event_id DESC);
                """
            )

    def record(
        self,
        *,
        approval_event_id: int,
        product_id: str,
        research_digest: str,
        created_at: datetime,
    ) -> ApprovalSnapshot:
        """Record once; an event ID can never be rebound to another research digest."""

        if approval_event_id <= 0:
            raise ValueError("approval_event_id must be positive")
        if not product_id.strip():
            raise ValueError("product_id must not be empty")
        if len(research_digest) != 64 or any(
            character not in "0123456789abcdef" for character in research_digest
        ):
            raise ValueError("research_digest must be a lowercase SHA-256 hex digest")
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        snapshot = ApprovalSnapshot(
            approval_event_id=approval_event_id,
            product_id=product_id,
            research_digest=research_digest,
            created_at=created_at.astimezone(UTC),
        )
        connection = self._connection()
        with connection:
            existing = connection.execute(
                """
                SELECT approval_event_id, product_id, research_digest, created_at
                FROM approval_snapshots WHERE approval_event_id = ?
                """,
                (approval_event_id,),
            ).fetchone()
            if existing is not None:
                current = self._from_row(existing)
                if current == snapshot:
                    return current
                raise ResearchConflictError(
                    f"approval event {approval_event_id} is already bound to another snapshot"
                )
            connection.execute(
                """
                INSERT INTO approval_snapshots(
                    approval_event_id, product_id, research_digest, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    approval_event_id,
                    product_id,
                    research_digest,
                    created_at.astimezone(UTC).isoformat(),
                ),
            )
        return snapshot

    def for_event(self, approval_event_id: int) -> ApprovalSnapshot | None:
        row = self._connection().execute(
            """
            SELECT approval_event_id, product_id, research_digest, created_at
            FROM approval_snapshots WHERE approval_event_id = ?
            """,
            (approval_event_id,),
        ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row) -> ApprovalSnapshot:
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise RuntimeError("stored approval snapshot timestamp is not timezone-aware")
        return ApprovalSnapshot(
            approval_event_id=int(row["approval_event_id"]),
            product_id=str(row["product_id"]),
            research_digest=str(row["research_digest"]),
            created_at=created_at.astimezone(UTC),
        )
