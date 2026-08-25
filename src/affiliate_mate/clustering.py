"""Deterministic title-similarity clustering for duplicate product variants."""

import re
from dataclasses import dataclass

from affiliate_mate.models import ProductCandidate

_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)
_STOPWORDS = {
    "and",
    "for",
    "the",
    "with",
    "und",
    "für",
    "mit",
    "der",
    "die",
    "das",
    "von",
    "ein",
    "eine",
}


def title_tokens(title: str) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in _TOKEN_RE.findall(title)
        if len(token) >= 2 and token.casefold() not in _STOPWORDS
    )


def title_similarity(left: str, right: str) -> float:
    """Return Jaccard token similarity in the inclusive range 0..1."""

    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


@dataclass(frozen=True, slots=True)
class CandidateCluster:
    canonical_product_id: str
    marketplace: str
    members: tuple[ProductCandidate, ...]


def cluster_candidates(
    candidates: list[ProductCandidate],
    *,
    threshold: float = 0.72,
) -> list[CandidateCluster]:
    """Cluster likely variants with transitive union-find grouping."""

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    parents = list(range(len(candidates)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            if left.marketplace.upper() != right.marketplace.upper():
                continue
            if title_similarity(left.title, right.title) >= threshold:
                union(left_index, right_index)

    grouped: dict[int, list[ProductCandidate]] = {}
    for index, candidate in enumerate(candidates):
        grouped.setdefault(find(index), []).append(candidate)

    clusters: list[CandidateCluster] = []
    for members in grouped.values():
        ordered = tuple(sorted(members, key=lambda item: item.product_id))
        clusters.append(
            CandidateCluster(
                canonical_product_id=ordered[0].product_id,
                marketplace=ordered[0].marketplace.upper(),
                members=ordered,
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.canonical_product_id)
