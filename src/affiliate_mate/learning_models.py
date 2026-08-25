"""Immutable learning-loop domain models and versioned contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any

OUTCOME_SCHEMA_VERSION = "affiliate-mate.outcome-event.v1"
FORECAST_SCHEMA_VERSION = "affiliate-mate.forecast-snapshot.v1"
POLICY_SCHEMA_VERSION = "affiliate-mate.scoring-policy.v1"
PERFORMANCE_SCHEMA_VERSION = "affiliate-mate.performance-report.v1"
CALIBRATION_SCHEMA_VERSION = "affiliate-mate.calibration-report.v1"
BACKTEST_SCHEMA_VERSION = "affiliate-mate.backtest-report.v1"
WALK_FORWARD_SCHEMA_VERSION = "affiliate-mate.walk-forward-report.v1"


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _require_probability(value: float, field_name: str) -> None:
    if not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be finite and between 0 and 1")


def _require_nonnegative(value: float, field_name: str) -> None:
    if not isfinite(float(value)) or value < 0:
        raise ValueError(f"{field_name} must be finite and >= 0")


class OutcomeKind(StrEnum):
    VIDEO_VIEW = "video_view"
    AFFILIATE_CLICK = "affiliate_click"
    ORDER = "order"
    COMMISSION = "commission"
    REFUND = "refund"
    REVERSAL = "reversal"


_COUNT_KINDS = {
    OutcomeKind.VIDEO_VIEW,
    OutcomeKind.AFFILIATE_CLICK,
    OutcomeKind.ORDER,
}
_MONEY_KINDS = {
    OutcomeKind.COMMISSION,
    OutcomeKind.REFUND,
    OutcomeKind.REVERSAL,
}


@dataclass(frozen=True, slots=True)
class OutcomeEvent:
    """One realized metric with explicit event time, report time, and ingestion time."""

    source: str
    source_event_id: str
    kind: OutcomeKind
    product_id: str
    marketplace: str
    content_id: str
    effective_at: datetime
    observed_at: datetime
    ingested_at: datetime
    window_start: datetime
    window_end: datetime
    count: int = 0
    amount_minor: int = 0
    currency: str | None = None
    package_digest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("source", "source_event_id", "product_id", "marketplace", "content_id"):
            _require_text(str(getattr(self, field_name)), field_name)
        for field_name in (
            "effective_at",
            "observed_at",
            "ingested_at",
            "window_start",
            "window_end",
        ):
            _require_aware(getattr(self, field_name), field_name)
        if self.window_start > self.window_end:
            raise ValueError("window_start must not be after window_end")
        if not self.window_start <= self.effective_at <= self.window_end:
            raise ValueError("effective_at must fall inside the reporting window")
        if self.observed_at < self.effective_at:
            raise ValueError("observed_at must not be before effective_at")
        if self.ingested_at < self.observed_at:
            raise ValueError("ingested_at must not be before observed_at")
        if self.count < 0:
            raise ValueError("count must be >= 0")
        if self.amount_minor < 0:
            raise ValueError("amount_minor must be >= 0")
        if self.kind in _COUNT_KINDS:
            if self.amount_minor != 0 or self.currency is not None:
                raise ValueError("count outcomes must not carry money")
        elif self.kind in _MONEY_KINDS:
            if self.count != 0:
                raise ValueError("money outcomes must not carry count")
            if not self.currency or len(self.currency.strip()) != 3:
                raise ValueError("money outcomes require a three-letter currency")
        if self.package_digest is not None:
            digest = self.package_digest
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("package_digest must be a lowercase SHA-256 digest")
        try:
            canonical_json(self.metadata)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be strict JSON-serializable") from exc

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.source, self.source_event_id, self.kind.value)

    @property
    def signed_amount_minor(self) -> int:
        if self.kind in {OutcomeKind.REFUND, OutcomeKind.REVERSAL}:
            return -self.amount_minor
        return self.amount_minor

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": OUTCOME_SCHEMA_VERSION,
            "source": self.source,
            "source_event_id": self.source_event_id,
            "kind": self.kind.value,
            "product_id": self.product_id,
            "marketplace": self.marketplace,
            "content_id": self.content_id,
            "package_digest": self.package_digest,
            "effective_at": _iso(self.effective_at),
            "observed_at": _iso(self.observed_at),
            "ingested_at": _iso(self.ingested_at),
            "window_start": _iso(self.window_start),
            "window_end": _iso(self.window_end),
            "count": self.count,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ForecastSnapshot:
    """Point-in-time forecast frozen before realized outcomes are available."""

    forecast_id: str
    product_id: str
    marketplace: str
    currency: str
    content_id: str
    category: str
    price: float
    predicted_at: datetime
    horizon_days: int
    policy_version: str
    policy_digest: str
    analysis_digest: str
    candidate_digest: str
    accepted: bool
    opportunity_score: float
    predicted_ctr: float
    predicted_conversion_rate: float
    predicted_value_per_1000_views: float
    commission_per_sale: float
    candidate_payload: dict[str, Any]
    available_fields: tuple[str, ...]
    provided_fields_tracked: bool
    package_digest: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "forecast_id",
            "product_id",
            "marketplace",
            "currency",
            "content_id",
            "category",
            "policy_version",
            "policy_digest",
            "analysis_digest",
            "candidate_digest",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_aware(self.predicted_at, "predicted_at")
        if self.horizon_days <= 0:
            raise ValueError("horizon_days must be > 0")
        if self.price <= 0:
            raise ValueError("price must be > 0")
        _require_probability(self.predicted_ctr, "predicted_ctr")
        _require_probability(self.predicted_conversion_rate, "predicted_conversion_rate")
        _require_nonnegative(
            self.predicted_value_per_1000_views,
            "predicted_value_per_1000_views",
        )
        _require_nonnegative(self.commission_per_sale, "commission_per_sale")
        if not 0 <= self.opportunity_score <= 100:
            raise ValueError("opportunity_score must be between 0 and 100")
        for digest_name in ("policy_digest", "analysis_digest", "candidate_digest"):
            digest = str(getattr(self, digest_name))
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError(f"{digest_name} must be a lowercase SHA-256 digest")
        if self.package_digest is not None:
            digest = self.package_digest
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("package_digest must be a lowercase SHA-256 digest")
        if len(set(self.available_fields)) != len(self.available_fields):
            raise ValueError("available_fields must not contain duplicates")
        canonical_json(self.candidate_payload)
        if sha256_json(self.candidate_payload) != self.candidate_digest:
            raise ValueError("candidate_digest does not match candidate_payload")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": FORECAST_SCHEMA_VERSION,
            "forecast_id": self.forecast_id,
            "product_id": self.product_id,
            "marketplace": self.marketplace,
            "currency": self.currency,
            "content_id": self.content_id,
            "category": self.category,
            "price": self.price,
            "predicted_at": _iso(self.predicted_at),
            "horizon_days": self.horizon_days,
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
            "analysis_digest": self.analysis_digest,
            "candidate_digest": self.candidate_digest,
            "accepted": self.accepted,
            "opportunity_score": self.opportunity_score,
            "predicted_ctr": self.predicted_ctr,
            "predicted_conversion_rate": self.predicted_conversion_rate,
            "predicted_value_per_1000_views": self.predicted_value_per_1000_views,
            "commission_per_sale": self.commission_per_sale,
            "candidate_payload": dict(self.candidate_payload),
            "available_fields": list(self.available_fields),
            "provided_fields_tracked": self.provided_fields_tracked,
            "package_digest": self.package_digest,
        }


@dataclass(frozen=True, slots=True)
class ScoringPolicyVersion:
    """Immutable scoring-policy registry entry."""

    version: str
    policy_payload: dict[str, Any]
    created_at: datetime
    parent_version: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _require_text(self.version, "version")
        _require_aware(self.created_at, "created_at")
        if self.parent_version is not None:
            _require_text(self.parent_version, "parent_version")
            if self.parent_version == self.version:
                raise ValueError("parent_version must differ from version")
        canonical_json(self.policy_payload)

    @property
    def digest(self) -> str:
        return sha256_json(self.policy_payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "version": self.version,
            "policy_payload": dict(self.policy_payload),
            "policy_digest": self.digest,
            "created_at": _iso(self.created_at),
            "parent_version": self.parent_version,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class OutcomeTotals:
    views: int = 0
    clicks: int = 0
    orders: int = 0
    gross_commission_minor: int = 0
    refunds_minor: int = 0
    reversals_minor: int = 0
    currency: str | None = None

    @property
    def net_commission_minor(self) -> int:
        return self.gross_commission_minor - self.refunds_minor - self.reversals_minor

    @property
    def ctr(self) -> float | None:
        return None if self.views <= 0 else self.clicks / self.views

    @property
    def conversion_rate(self) -> float | None:
        return None if self.clicks <= 0 else self.orders / self.clicks

    @property
    def realized_value_per_1000_views(self) -> float | None:
        if self.views <= 0 or self.currency is None:
            return None
        return (self.net_commission_minor / 100.0) * 1000.0 / self.views

    def to_dict(self) -> dict[str, object]:
        return asdict(self) | {
            "net_commission_minor": self.net_commission_minor,
            "ctr": self.ctr,
            "conversion_rate": self.conversion_rate,
            "realized_value_per_1000_views": self.realized_value_per_1000_views,
        }
