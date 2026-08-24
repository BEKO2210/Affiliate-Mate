"""Domain models used by Affiliate-Mate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


def _as_float(data: Mapping[str, str], key: str, default: float) -> float:
    raw = data.get(key, "")
    return default if raw in (None, "") else float(raw)


def _as_int(data: Mapping[str, str], key: str, default: int) -> int:
    raw = data.get(key, "")
    return default if raw in (None, "") else int(raw)


@dataclass(frozen=True, slots=True)
class ProductCandidate:
    """A normalized product candidate independent of any affiliate network."""

    product_id: str
    title: str
    marketplace: str
    currency: str
    price: float
    commission_rate: float
    monthly_searches: int
    youtube_competition: int
    buyer_intent: int
    content_gap: int
    evidence_quality: int = 50
    estimated_ctr: float = 0.04
    estimated_conversion_rate: float = 0.03

    def __post_init__(self) -> None:
        if not self.product_id.strip():
            raise ValueError("product_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.price <= 0:
            raise ValueError("price must be > 0")
        if not 0 <= self.commission_rate <= 1:
            raise ValueError("commission_rate must be between 0 and 1")
        if self.monthly_searches < 0:
            raise ValueError("monthly_searches must be >= 0")
        for field_name in (
            "youtube_competition",
            "buyer_intent",
            "content_gap",
            "evidence_quality",
        ):
            value = getattr(self, field_name)
            if not 0 <= value <= 100:
                raise ValueError(f"{field_name} must be between 0 and 100")
        if not 0 <= self.estimated_ctr <= 1:
            raise ValueError("estimated_ctr must be between 0 and 1")
        if not 0 <= self.estimated_conversion_rate <= 1:
            raise ValueError("estimated_conversion_rate must be between 0 and 1")

    @property
    def commission_per_sale(self) -> float:
        return self.price * self.commission_rate

    @property
    def estimated_value_per_1000_views(self) -> float:
        return (
            1000
            * self.estimated_ctr
            * self.estimated_conversion_rate
            * self.commission_per_sale
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, str]) -> ProductCandidate:
        """Build a candidate from a CSV-like mapping."""

        return cls(
            product_id=str(data["product_id"]).strip(),
            title=str(data["title"]).strip(),
            marketplace=str(data.get("marketplace", "DE") or "DE").strip().upper(),
            currency=str(data.get("currency", "EUR") or "EUR").strip().upper(),
            price=_as_float(data, "price", 0.0),
            commission_rate=_as_float(data, "commission_rate", 0.0),
            monthly_searches=_as_int(data, "monthly_searches", 0),
            youtube_competition=_as_int(data, "youtube_competition", 50),
            buyer_intent=_as_int(data, "buyer_intent", 50),
            content_gap=_as_int(data, "content_gap", 50),
            evidence_quality=_as_int(data, "evidence_quality", 50),
            estimated_ctr=_as_float(data, "estimated_ctr", 0.04),
            estimated_conversion_rate=_as_float(
                data, "estimated_conversion_rate", 0.03
            ),
        )
