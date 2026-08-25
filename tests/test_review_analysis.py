from affiliate_mate.review_analysis import ReviewRecord, analyze_reviews, review_similarity


def review(review_id: str, rating: float, body: str) -> ReviewRecord:
    return ReviewRecord(
        review_id=review_id,
        product_id="p1",
        marketplace="DE",
        rating=rating,
        body=body,
        source="user-export",
    )


def test_exact_duplicates_are_counted_but_not_double_clustered() -> None:
    rows = [
        review("r1", 5, "Battery life is excellent and lasts all day."),
        review("r2", 5, "Battery life is excellent and lasts all day."),
        review("r3", 4, "Excellent battery runtime for a full work day."),
    ]
    result = analyze_reviews(rows, product_id="p1", marketplace="DE", similarity_threshold=0.2)
    assert result.total_reviews == 3
    assert result.unique_reviews == 2
    assert result.exact_duplicate_copies == 1
    assert sum(len(theme.review_ids) for theme in result.themes) == 2


def test_marketplace_and_product_filters_are_strict() -> None:
    rows = [
        review("r1", 5, "Great battery life."),
        ReviewRecord(
            review_id="r2",
            product_id="p2",
            marketplace="DE",
            rating=1,
            body="Different product.",
            source="user-export",
        ),
        ReviewRecord(
            review_id="r3",
            product_id="p1",
            marketplace="US",
            rating=1,
            body="Different market.",
            source="user-export",
        ),
    ]
    result = analyze_reviews(rows, product_id="p1", marketplace="DE")
    assert result.total_reviews == 1
    assert result.themes[0].review_ids == ("r1",)


def test_similarity_is_explainable_token_overlap() -> None:
    left = review("r1", 5, "Battery runtime is excellent and charging is fast.")
    right = review("r2", 4, "Fast charging and excellent battery runtime.")
    unrelated = review("r3", 2, "The plastic hinge feels weak and noisy.")
    assert review_similarity(left, right) > review_similarity(left, unrelated)


def test_theme_sentiment_uses_rating_not_invented_text_sentiment() -> None:
    rows = [
        review("r1", 1, "Hinge movement feels loose."),
        review("r2", 2, "Loose hinge movement after a week."),
    ]
    result = analyze_reviews(rows, product_id="p1", marketplace="DE", similarity_threshold=0.2)
    assert result.themes[0].sentiment == "negative"
    assert result.themes[0].average_rating == 1.5
