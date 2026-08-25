import pytest

from affiliate_mate.mock_catalog import MockCatalogProvider


def test_mock_search_is_deterministic_and_marketplace_scoped():
    provider = MockCatalogProvider()
    results = provider.search("camera", marketplace="DE")
    assert [item.product_id for item in results] == ["MOCK-DE-CAM-001"]
    assert all(item.marketplace == "DE" for item in results)


def test_mock_search_validates_limit():
    with pytest.raises(ValueError, match="between 1 and 10"):
        MockCatalogProvider().search("camera", marketplace="DE", limit=0)
