"""Signal-specific expiry policies for time-dependent market evidence."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import timedelta

from .evidence import EvidenceObservation


_DEFAULT_TTLS = {
    "price": timedelta(days=1),
    "commission_rate": timedelta(days=7),
    "monthly_searches": timedelta(days=30),
    "youtube_competition": timedelta(days=7),
    "buyer_intent": timedelta(days=14),
    "content_gap": timedelta(days=7),
    "trend_strength": timedelta(days=14),
    "seasonality": timedelta(days=30),
    "evidence_quality": timedelta(days=30),
}


@dataclass(frozen=True, slots=True)
class SignalFreshnessPolicy:
    """Attach explicit TTLs to evidence without changing observation semantics."""

    ttl_by_signal: Mapping[str, timedelta] = field(
        default_factory=lambda: dict(_DEFAULT_TTLS)
    )

    def __post_init__(self) -> None:
        for signal, ttl in self.ttl_by_signal.items():
            if not signal.strip():
                raise ValueError("freshness signal names must not be empty")
            if ttl <= timedelta(0):
                raise ValueError(f"freshness TTL for {signal!r} must be positive")

    def ttl_for(self, signal: str) -> timedelta | None:
        return self.ttl_by_signal.get(signal)

    def apply(self, observation: EvidenceObservation) -> EvidenceObservation:
        """Add an expiry only when the producer did not already specify one."""

        if observation.expires_at is not None:
            return observation
        ttl = self.ttl_for(observation.signal)
        if ttl is None:
            return observation
        return replace(
            observation,
            expires_at=observation.observed_at + ttl,
        )

    def to_dict(self) -> dict[str, float]:
        """Return TTL values as seconds for stable JSON/reporting output."""

        return {
            signal: ttl.total_seconds()
            for signal, ttl in sorted(self.ttl_by_signal.items())
        }
