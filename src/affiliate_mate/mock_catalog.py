"""Credential-free catalog provider for demos, tests, and contributor workflows."""

from __future__ import annotations

from .catalog import CatalogItem


_FIXTURES = (
    CatalogItem(
        provider="mock",
        product_id="MOCK-DE-CAM-001",
        title="4K Road Camera Pro",
        marketplace="DE",
        price=189.0,
        currency="EUR",
        detail_url="https://example.invalid/products/MOCK-DE-CAM-001",
        category="Electronics",
        brand="ExampleCam",
    ),
    CatalogItem(
        provider="mock",
        product_id="MOCK-DE-GPS-001",
        title="Adventure GPS Navigator",
        marketplace="DE",
        price=349.0,
        currency="EUR",
        detail_url="https://example.invalid/products/MOCK-DE-GPS-001",
        category="Electronics",
        brand="ExampleNav",
    ),
    CatalogItem(
        provider="mock",
        product_id="MOCK-US-MIC-001",
        title="USB Studio Microphone",
        marketplace="US",
        price=129.0,
        currency="USD",
        detail_url="https://example.invalid/products/MOCK-US-MIC-001",
        category="Electronics",
        brand="ExampleAudio",
    ),
    CatalogItem(
        provider="mock",
        product_id="MOCK-DE-PAN-001",
        title="Stainless Steel Frying Pan",
        marketplace="DE",
        price=79.0,
        currency="EUR",
        detail_url="https://example.invalid/products/MOCK-DE-PAN-001",
        category="Kitchen",
        brand="ExampleHome",
    ),
)


class MockCatalogProvider:
    @property
    def name(self) -> str:
        return "mock"

    def search(
        self,
        keywords: str,
        *,
        marketplace: str,
        limit: int = 10,
    ) -> list[CatalogItem]:
        if not keywords.strip():
            raise ValueError("keywords must not be empty")
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        needle = keywords.casefold()
        market = marketplace.strip().upper()
        return [
            item
            for item in _FIXTURES
            if item.marketplace == market
            and (needle in item.title.casefold() or needle in (item.brand or "").casefold())
        ][:limit]
