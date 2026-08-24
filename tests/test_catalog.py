from pathlib import Path

import pytest

from affiliate_mate.catalog import (
    CatalogItem,
    CommissionRule,
    CommissionSchedule,
    ResearchSignals,
    candidate_from_catalog,
)


def item(**overrides):
    values = {
        "provider": "test",
        "product_id": "A1",
        "title": "Camera",
        "marketplace": "DE",
        "price": 200.0,
        "currency": "EUR",
        "category": "Electronics",
    }
    values.update(overrides)
    return CatalogItem(**values)


def signals():
    return ResearchSignals(1000, 40, 80, 70, 90, 0.05, 0.03)


def test_commission_schedule_prefers_exact_rule():
    schedule = CommissionSchedule(
        [
            CommissionRule("DE", "*", 0.01),
            CommissionRule("DE", "Electronics", 0.03),
            CommissionRule("*", "*", 0.02),
        ]
    )
    assert schedule.rate_for("de", "electronics") == 0.03
    assert schedule.rate_for("DE", "Kitchen") == 0.01
    assert schedule.rate_for("US", "Kitchen") == 0.02


def test_duplicate_rule_is_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        CommissionSchedule(
            [
                CommissionRule("DE", "Electronics", 0.03),
                CommissionRule("de", "electronics", 0.04),
            ]
        )


def test_schedule_loads_csv(tmp_path: Path):
    path = tmp_path / "rates.csv"
    path.write_text(
        "marketplace,category,commission_rate\nDE,Electronics,0.03\n",
        encoding="utf-8",
    )
    assert CommissionSchedule.from_csv(path).rate_for("DE", "Electronics") == 0.03


def test_catalog_promotion_requires_explicit_economics():
    schedule = CommissionSchedule([CommissionRule("DE", "Electronics", 0.03)])
    candidate = candidate_from_catalog(item(), schedule, signals())
    assert candidate.commission_rate == 0.03
    assert candidate.monthly_searches == 1000


def test_catalog_promotion_rejects_missing_price_or_category():
    schedule = CommissionSchedule([CommissionRule("DE", "*", 0.03)])
    with pytest.raises(ValueError, match="no current price"):
        candidate_from_catalog(item(price=None), schedule, signals())
    with pytest.raises(ValueError, match="no commission category"):
        candidate_from_catalog(item(category=None), schedule, signals())
