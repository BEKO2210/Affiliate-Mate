"""Credential-free replay provider for deterministic market-intelligence fixtures."""

import json
from datetime import UTC, datetime
from pathlib import Path

from .evidence import EvidenceObservation
from .models import ProductCandidate


def _parse_time(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


class ReplayEvidenceProvider:
    """Replay previously captured numeric evidence without any network access."""

    def __init__(self, observations: list[EvidenceObservation], *, name: str = "replay") -> None:
        if not name.strip():
            raise ValueError("replay provider name must not be empty")
        self._observations = tuple(observations)
        self._name = name

    @classmethod
    def from_json(cls, path: str | Path, *, name: str = "replay") -> "ReplayEvidenceProvider":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("observations"), list):
            raise ValueError("replay fixture must contain an observations array")
        observations: list[EvidenceObservation] = []
        for index, item in enumerate(raw["observations"]):
            if not isinstance(item, dict):
                raise ValueError(f"replay observation {index} must be an object")
            try:
                observed_at = _parse_time(item.get("observed_at"), "observed_at")
                if observed_at is None:
                    raise ValueError("observed_at is required")
                observations.append(
                    EvidenceObservation(
                        product_id=str(item["product_id"]),
                        signal=str(item["signal"]),
                        value=float(item["value"]),
                        source=str(item.get("source") or name),
                        marketplace=str(item.get("marketplace") or "DE"),
                        observed_at=observed_at,
                        confidence=float(item.get("confidence", 1.0)),
                        expires_at=_parse_time(item.get("expires_at"), "expires_at"),
                        unit=(str(item["unit"]) if item.get("unit") is not None else None),
                        metadata=dict(item.get("metadata") or {}),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid replay observation {index}: {exc}") from exc
        return cls(observations, name=name)

    @property
    def name(self) -> str:
        return self._name

    def collect(self, candidate: ProductCandidate) -> list[EvidenceObservation]:
        return [
            observation
            for observation in self._observations
            if observation.product_id == candidate.product_id
            and observation.marketplace.upper() == candidate.marketplace.upper()
        ]
