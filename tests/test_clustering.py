import pytest

from affiliate_mate.clustering import cluster_candidates, title_similarity
from affiliate_mate.models import ProductCandidate


def _candidate(product_id: str, title: str, marketplace: str = "DE") -> ProductCandidate:
    currency = "EUR" if marketplace == "DE" else "USD"
    return ProductCandidate(
        product_id=product_id,
        title=title,
        marketplace=marketplace,
        currency=currency,
        price=100.0,
        commission_rate=0.05,
        monthly_searches=500,
        youtube_competition=50,
        buyer_intent=60,
        content_gap=50,
        evidence_quality=80,
    )


def test_title_similarity_ignores_common_connector_words() -> None:
    score = title_similarity(
        "Example Camera Pro with 4K",
        "Example Camera Pro 4K",
    )
    assert score == 1.0


def test_cluster_candidates_groups_variants_but_not_cross_marketplace() -> None:
    candidates = [
        _candidate("a", "Example Camera Pro 4K"),
        _candidate("b", "Example Camera Pro 4K Black"),
        _candidate("c", "Completely Different GPS Navigator"),
        _candidate("d", "Example Camera Pro 4K", marketplace="US"),
    ]
    clusters = cluster_candidates(candidates, threshold=0.7)
    member_sets = [{member.product_id for member in cluster.members} for cluster in clusters]
    assert {"a", "b"} in member_sets
    assert {"c"} in member_sets
    assert {"d"} in member_sets


def test_cluster_threshold_is_validated() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        cluster_candidates([], threshold=1.1)
