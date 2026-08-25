"""Keyword-demand evidence from user-owned or licensed CSV exports."""

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .evidence import EvidenceObservation
from .freshness import SignalFreshnessPolicy
from .models import ProductCandidate


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip())
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("keyword observed_at must include a timezone")
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class KeywordDemandSnapshot:
    product_id: str
    marketplace: str
    monthly_searches: int
    buyer_intent: int
    observed_at: datetime
    source: str = "keyword-csv"
    confidence: float = 0.8

    def __post_init__(self) -> None:
        if not self.product_id.strip():
            raise ValueError("product_id must not be empty")
        if not self.marketplace.strip():
            raise ValueError("marketplace must not be empty")
        if self.monthly_searches < 0:
            raise ValueError("monthly_searches must be >= 0")
        if not 0 <= self.buyer_intent <= 100:
            raise ValueError("buyer_intent must be between 0 and 100")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


def load_keyword_demand_csv(path: str | Path) -> list[KeywordDemandSnapshot]:
    """Load explicit demand and buyer-intent evidence without guessing missing values."""

    snapshots: list[KeywordDemandSnapshot] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "product_id",
            "marketplace",
            "monthly_searches",
            "buyer_intent",
            "observed_at",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                "keyword CSV missing required columns: " + ", ".join(sorted(missing))
            )
        for row_number, row in enumerate(reader, start=2):
            try:
                snapshots.append(
                    KeywordDemandSnapshot(
                        product_id=row["product_id"].strip(),
                        marketplace=row["marketplace"].strip().upper(),
                        monthly_searches=int(row["monthly_searches"]),
                        buyer_intent=int(row["buyer_intent"]),
                        observed_at=_parse_timestamp(row["observed_at"]),
                        source=(row.get("source") or "keyword-csv").strip(),
                        confidence=float(row.get("confidence") or 0.8),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid keyword CSV row {row_number}: {exc}") from exc
    return snapshots


class CSVKeywordEvidenceProvider:
    """Resolve the latest supplied demand snapshot for each candidate."""

    def __init__(
        self,
        snapshots: list[KeywordDemandSnapshot],
        *,
        freshness: SignalFreshnessPolicy | None = None,
    ) -> None:
        self._freshness = freshness or SignalFreshnessPolicy()
        self._index: dict[tuple[str, str], KeywordDemandSnapshot] = {}
        for snapshot in snapshots:
            key = (snapshot.product_id, snapshot.marketplace.upper())
            current = self._index.get(key)
            if current is None or snapshot.observed_at > current.observed_at:
                self._index[key] = snapshot

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        freshness: SignalFreshnessPolicy | None = None,
    ) -> "CSVKeywordEvidenceProvider":
        return cls(load_keyword_demand_csv(path), freshness=freshness)

    @property
    def name(self) -> str:
        return "keyword-csv"

    def collect(self, candidate: ProductCandidate) -> list[EvidenceObservation]:
        snapshot = self._index.get((candidate.product_id, candidate.marketplace.upper()))
        if snapshot is None:
            return []
        common = {
            "product_id": candidate.product_id,
            "source": snapshot.source,
            "marketplace": candidate.marketplace,
            "observed_at": snapshot.observed_at,
            "confidence": snapshot.confidence,
            "metadata": {"kind": "user-owned-keyword-export"},
        }
        observations = [
            EvidenceObservation(
                signal="monthly_searches",
                value=float(snapshot.monthly_searches),
                unit="searches/month",
                **common,
            ),
            EvidenceObservation(
                signal="buyer_intent",
                value=float(snapshot.buyer_intent),
                unit="score_0_100",
                **common,
            ),
        ]
        return [self._freshness.apply(observation) for observation in observations]
