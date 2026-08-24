"""Provider-neutral catalog models and commission schedule handling."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .models import ProductCandidate


@dataclass(frozen=True, slots=True)
class CatalogItem:
    """A normalized product discovered from a catalog provider."""

    provider: str
    product_id: str
    title: str
    marketplace: str
    price: float | None = None
    currency: str | None = None
    detail_url: str | None = None
    category: str | None = None
    brand: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if not self.product_id.strip():
            raise ValueError("product_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.marketplace.strip():
            raise ValueError("marketplace must not be empty")
        if self.price is not None and self.price <= 0:
            raise ValueError("price must be > 0 when present")
        if self.currency is not None and len(self.currency.strip()) != 3:
            raise ValueError("currency must be a 3-letter ISO 4217 code when present")

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "product_id": self.product_id,
            "title": self.title,
            "marketplace": self.marketplace,
            "price": self.price,
            "currency": self.currency,
            "detail_url": self.detail_url,
            "category": self.category,
            "brand": self.brand,
        }


@dataclass(frozen=True, slots=True)
class ResearchSignals:
    """Non-catalog evidence required by the opportunity engine."""

    monthly_searches: int
    youtube_competition: int
    buyer_intent: int
    content_gap: int
    evidence_quality: int
    estimated_ctr: float = 0.04
    estimated_conversion_rate: float = 0.03


@dataclass(frozen=True, slots=True)
class CommissionRule:
    marketplace: str
    category: str
    commission_rate: float

    def __post_init__(self) -> None:
        if not self.marketplace.strip():
            raise ValueError("commission marketplace must not be empty")
        if not self.category.strip():
            raise ValueError("commission category must not be empty")
        if not 0 <= self.commission_rate <= 1:
            raise ValueError("commission_rate must be between 0 and 1")


class CommissionSchedule:
    """Explicit, user-supplied commission rules; no network rates are hard-coded."""

    def __init__(self, rules: Iterable[CommissionRule]) -> None:
        indexed: dict[tuple[str, str], float] = {}
        for rule in rules:
            key = (rule.marketplace.strip().upper(), rule.category.strip().casefold())
            if key in indexed:
                raise ValueError(
                    f"duplicate commission rule for marketplace={rule.marketplace!r}, "
                    f"category={rule.category!r}"
                )
            indexed[key] = rule.commission_rate
        if not indexed:
            raise ValueError("commission schedule must contain at least one rule")
        self._rates = indexed

    @classmethod
    def from_csv(cls, path: str | Path) -> CommissionSchedule:
        source = Path(path)
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"marketplace", "category", "commission_rate"}
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"commission CSV missing columns: {sorted(missing)}")
            rules = [
                CommissionRule(
                    marketplace=str(row["marketplace"]).strip(),
                    category=str(row["category"]).strip(),
                    commission_rate=float(row["commission_rate"]),
                )
                for row in reader
            ]
        return cls(rules)

    def rate_for(self, marketplace: str, category: str) -> float:
        market = marketplace.strip().upper()
        normalized_category = category.strip().casefold()
        for key in (
            (market, normalized_category),
            (market, "*"),
            ("*", normalized_category),
            ("*", "*"),
        ):
            if key in self._rates:
                return self._rates[key]
        raise KeyError(
            f"no commission rule for marketplace={marketplace!r}, category={category!r}"
        )


@runtime_checkable
class CatalogSearchProvider(Protocol):
    @property
    def name(self) -> str: ...

    def search(
        self,
        keywords: str,
        *,
        marketplace: str,
        limit: int = 10,
    ) -> Iterable[CatalogItem]: ...


def candidate_from_catalog(
    item: CatalogItem,
    schedule: CommissionSchedule,
    signals: ResearchSignals,
) -> ProductCandidate:
    """Promote a catalog item only when economics and research inputs are explicit."""

    if item.price is None:
        raise ValueError(f"catalog item {item.product_id!r} has no current price")
    if item.currency is None:
        raise ValueError(f"catalog item {item.product_id!r} has no currency")
    if item.category is None:
        raise ValueError(
            f"catalog item {item.product_id!r} has no commission category; "
            "assign one before scoring"
        )
    rate = schedule.rate_for(item.marketplace, item.category)
    return ProductCandidate(
        product_id=item.product_id,
        title=item.title,
        marketplace=item.marketplace,
        currency=item.currency,
        price=item.price,
        commission_rate=rate,
        monthly_searches=signals.monthly_searches,
        youtube_competition=signals.youtube_competition,
        buyer_intent=signals.buyer_intent,
        content_gap=signals.content_gap,
        evidence_quality=signals.evidence_quality,
        estimated_ctr=signals.estimated_ctr,
        estimated_conversion_rate=signals.estimated_conversion_rate,
    )


def schedule_from_mapping(rows: Iterable[Mapping[str, object]]) -> CommissionSchedule:
    """Build a schedule from structured data for adapters and tests."""

    return CommissionSchedule(
        CommissionRule(
            marketplace=str(row["marketplace"]),
            category=str(row["category"]),
            commission_rate=float(row["commission_rate"]),
        )
        for row in rows
    )
