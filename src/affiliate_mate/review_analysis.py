"""Deterministic clustering for user-supplied review corpora."""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)
_STOPWORDS = {
    "and",
    "are",
    "but",
    "das",
    "der",
    "die",
    "ein",
    "eine",
    "for",
    "für",
    "hat",
    "have",
    "ich",
    "ist",
    "mit",
    "nicht",
    "the",
    "this",
    "und",
    "von",
    "was",
    "with",
}


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    review_id: str
    product_id: str
    marketplace: str
    rating: float
    body: str
    source: str
    title: str = ""

    def __post_init__(self) -> None:
        for field_name in ("review_id", "product_id", "marketplace", "body", "source"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} must not be empty")
        if not 1 <= self.rating <= 5:
            raise ValueError("rating must be between 1 and 5")

    def to_dict(self) -> dict[str, object]:
        return {
            "review_id": self.review_id,
            "product_id": self.product_id,
            "marketplace": self.marketplace,
            "rating": self.rating,
            "title": self.title,
            "body": self.body,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class ReviewTheme:
    theme_id: str
    sentiment: str
    average_rating: float
    common_terms: tuple[str, ...]
    review_ids: tuple[str, ...]
    representative_review_id: str
    exact_duplicate_copies: int

    def to_dict(self) -> dict[str, object]:
        return {
            "theme_id": self.theme_id,
            "sentiment": self.sentiment,
            "average_rating": self.average_rating,
            "common_terms": list(self.common_terms),
            "review_ids": list(self.review_ids),
            "representative_review_id": self.representative_review_id,
            "exact_duplicate_copies": self.exact_duplicate_copies,
        }


@dataclass(frozen=True, slots=True)
class ReviewAnalysis:
    product_id: str
    marketplace: str
    total_reviews: int
    unique_reviews: int
    exact_duplicate_copies: int
    themes: tuple[ReviewTheme, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "marketplace": self.marketplace,
            "total_reviews": self.total_reviews,
            "unique_reviews": self.unique_reviews,
            "exact_duplicate_copies": self.exact_duplicate_copies,
            "themes": [theme.to_dict() for theme in self.themes],
        }


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if len(token) >= 3 and token.casefold() not in _STOPWORDS
    )


def review_fingerprint(review: ReviewRecord) -> str:
    normalized = " ".join(_TOKEN_RE.findall(review.body.casefold()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def review_similarity(left: ReviewRecord, right: ReviewRecord) -> float:
    """Use token overlap coefficient so short reviews are not unfairly diluted."""

    left_tokens = _tokens(f"{left.title} {left.body}")
    right_tokens = _tokens(f"{right.title} {right.body}")
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))


def load_reviews_csv(path: str | Path) -> list[ReviewRecord]:
    records: list[ReviewRecord] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"review_id", "product_id", "marketplace", "rating", "body", "source"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError("review CSV missing required columns: " + ", ".join(sorted(missing)))
        for row_number, row in enumerate(reader, start=2):
            try:
                records.append(
                    ReviewRecord(
                        review_id=row["review_id"].strip(),
                        product_id=row["product_id"].strip(),
                        marketplace=row["marketplace"].strip().upper(),
                        rating=float(row["rating"]),
                        title=(row.get("title") or "").strip(),
                        body=row["body"].strip(),
                        source=row["source"].strip(),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid review CSV row {row_number}: {exc}") from exc
    return records


def _sentiment(average_rating: float) -> str:
    if average_rating >= 3.7:
        return "positive"
    if average_rating <= 2.3:
        return "negative"
    return "mixed"


def analyze_reviews(
    reviews: list[ReviewRecord],
    *,
    product_id: str,
    marketplace: str,
    similarity_threshold: float = 0.32,
) -> ReviewAnalysis:
    """Cluster one product's supplied reviews without pretending this is semantic truth."""

    if not 0 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be between 0 and 1")
    market = marketplace.upper()
    selected = [
        review
        for review in reviews
        if review.product_id == product_id and review.marketplace.upper() == market
    ]
    if not selected:
        return ReviewAnalysis(
            product_id=product_id,
            marketplace=market,
            total_reviews=0,
            unique_reviews=0,
            exact_duplicate_copies=0,
            themes=(),
        )

    fingerprint_groups: dict[str, list[ReviewRecord]] = {}
    for review in selected:
        fingerprint_groups.setdefault(review_fingerprint(review), []).append(review)
    unique = [
        min(group, key=lambda review: review.review_id)
        for group in fingerprint_groups.values()
    ]
    unique.sort(key=lambda review: review.review_id)
    duplicate_copies = len(selected) - len(unique)

    parents = list(range(len(unique)))

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

    for left_index, left in enumerate(unique):
        for right_index in range(left_index + 1, len(unique)):
            if review_similarity(left, unique[right_index]) >= similarity_threshold:
                union(left_index, right_index)

    grouped: dict[int, list[ReviewRecord]] = {}
    for index, review in enumerate(unique):
        grouped.setdefault(find(index), []).append(review)

    themes: list[ReviewTheme] = []
    ordered_groups = sorted(
        grouped.values(),
        key=lambda group: min(review.review_id for review in group),
    )
    for theme_number, group in enumerate(ordered_groups, start=1):
        ordered = sorted(group, key=lambda review: review.review_id)
        term_document_frequency: Counter[str] = Counter()
        for review in ordered:
            term_document_frequency.update(_tokens(f"{review.title} {review.body}"))
        common_terms = tuple(
            term
            for term, _ in sorted(
                term_document_frequency.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        )
        average_rating = sum(review.rating for review in ordered) / len(ordered)
        group_duplicate_copies = sum(
            len(fingerprint_groups[review_fingerprint(review)]) - 1 for review in ordered
        )
        themes.append(
            ReviewTheme(
                theme_id=f"theme-{theme_number:03d}",
                sentiment=_sentiment(average_rating),
                average_rating=round(average_rating, 2),
                common_terms=common_terms,
                review_ids=tuple(review.review_id for review in ordered),
                representative_review_id=ordered[0].review_id,
                exact_duplicate_copies=group_duplicate_copies,
            )
        )

    return ReviewAnalysis(
        product_id=product_id,
        marketplace=market,
        total_reviews=len(selected),
        unique_reviews=len(unique),
        exact_duplicate_copies=duplicate_copies,
        themes=tuple(themes),
    )
